"""
Compliance Task Matcher (Ultimate Edition)
------------------------------------------
Single-file Streamlit app for:
- Reading PDFs (Native Text + Enhanced OCR), Word Docs, and Images
- Pre-processing images to fix bad Tesseract output
- Building a ChromaDB vector index over 19 compliance tasks (CPU safe)
- Doing semantic search + word overlap reranking
- Using OpenAI to intelligently summarize documents before searching
"""

from __future__ import annotations

import io
import os
import re
from typing import Dict, List

import chromadb
from chromadb.utils import embedding_functions
import fitz  # PyMuPDF
import pytesseract
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps
import docx
from openai import OpenAI

# Optional: set this on Windows if Tesseract is not in PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

APP_TITLE = "Document to Compliance Task Matcher"

# --- 1. FULL TASK DATA (19 Tasks) ---
TASK_ROWS: List[Dict[str, str]] = [
    {
        "task_name": "Payment on employing less than 1000 employees",
        "description": "Pay minimum rate of wages in cash on or before 7th day of every month",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Pay minimum rate of wages in cash on or before 7th day of every month",
    },
    {
        "task_name": "Payment of stipend to apprentices",
        "description": "Pay apprentices a monthly stipend at the minimum rate specified in additional information as per the qualifications stipulated in the curriculum",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Pay apprentices a monthly stipend at the minimum rate specified in additional information as per the qualifications stipulated in the curriculum",
    },
    {
        "task_name": "Monthly maintenance",
        "description": "Ensure monthly maintenance of fire extinguishers as specified in help text",
        "due_date": "2025/08/31",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Ensure monthly maintenance of fire extinguishers as specified in help text",
    },
    {
        "task_name": "Storage of waste",
        "description": "Segregate and store the waste generated in 3 separate streams namely 1) bio-degradable or wet waste 2) non biodegradable or dry waste 3) domestic hazardous wastes, in suitable bins and handover segregated wastes to waste collectors as per the direction by the local authorities from time to time",
        "due_date": "2025/08/01",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Segregate and store the waste generated in 3 separate streams namely 1) bio-degradable or wet waste 2) non biodegradable or dry waste 3) domestic hazardous wastes, in suitable bins and handover segregated wastes to waste collectors as per the direction by the local authorities from time to time",
    },
    {
        "task_name": "Testing and maintenance of lift or escalator or passenger conveyor",
        "description": "Test and maintain the lift or escalator or passenger conveyor by any registered person once in every 3 months",
        "due_date": "2025/08/01",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Test and maintain the lift or escalator or passenger conveyor by any registered person once in every 3 months",
    },
    {
        "task_name": "Notification or display of the name of authorized person",
        "description": "Notify or display the name of the authorized person to whom a complaint may be made in case of any violation with respect to the Anti-Smoking Law, who observes any person violating the provision of these Rules",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Notify or display the name of the authorized person to whom a complaint may be made in case of any violation with respect to the Anti-Smoking Law, who observes any person violating the provision of these Rules",
    },
    {
        "task_name": "Spread Over",
        "description": "Ensure that working hours in any day inclusive of interval for rest shall not exceed: i) 12 hours - in case of employment in Public Motor Transport and Plantations ii) 10 and half hours - in case of any other scheduled employment",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Ensure that working hours in any day inclusive of interval for rest shall not exceed: i) 12 hours - in case of employment in Public Motor Transport and Plantations ii) 10 and half hours - in case of any other scheduled employment",
    },
    {
        "task_name": "Amount of compensation",
        "description": "Ensure the amount of compensation to be as given in additional text. Subject to the provisions of this Act, the amount of compensation shall be as follows: (a) where death results from the injury an amount equal to 50% of the monthly wages of the deceased employee multiplied by the relevant factor; or an amount of Rs. 1,20,000, whichever is more; (b) where permanent total disablement results from the injury an amount equal to 60% of the monthly wages of the injured employee multiplied by the relevant factor; or an amount of Rs. 1,40,000 whichever is more",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Ensure the amount of compensation to be as given in additional text. Subject to the provisions of this Act, the amount of compensation shall be as follows: (a) where death results from the injury an amount equal to 50% of the monthly wages of the deceased employee multiplied by the relevant factor; or an amount of Rs. 1,20,000, whichever is more; (b) where permanent total disablement results from the injury an amount equal to 60% of the monthly wages of the injured employee multiplied by the relevant factor; or an amount of Rs. 1,40,000 whichever is more",
    },
    {
        "task_name": "Organizing workshops",
        "description": "Organize workshops and awareness programmes at regular intervals for sensitizing the employees with the provisions of the Act",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Organize workshops and awareness programmes at regular intervals for sensitizing the employees with the provisions of the Act",
    },
    {
        "task_name": "Publishing equal opportunity policy",
        "description": "Publish an equal opportunity policy for transgender persons",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Publish an equal opportunity policy for transgender persons",
    },
    {
        "task_name": "Notice to be displayed in a proper and legible condition",
        "description": "Ensure display of notice is readily seen and exhibited in a proper and legible condition",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Ensure display of notice is readily seen and exhibited in a proper and legible condition",
    },
    {
        "task_name": "Deductions for recovery of advances",
        "description": "Make sure to deduct recovery of advances or for adjustment of over payments of wages",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Make sure to deduct recovery of advances or for adjustment of over payments of wages",
    },
    {
        "task_name": "Deductions for house accomodation or Services or amenities",
        "description": "Ensure to deduct for house accommodation or amenities and services supplied by the employer",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Ensure to deduct for house accommodation or amenities and services supplied by the employer",
    },
    {
        "task_name": "Duties of employer",
        "description": "Organise workshops and awareness programmes at regular intervals for sensitising the employees with the provisions of the Act and orientation programmes for the members of the Internal Committee in the manner as may be prescribed",
        "due_date": "2025/08/30",
        "company_name": "Fujitsu Research India Private Limited",
        "unit_name": "FRIPL-Bangalore",
        "state": "Bangalore",
        "help_text": "Organise workshops and awareness programmes at regular intervals for sensitising the employees with the provisions of the Act and orientation programmes for the members of the Internal Committee in the manner as may be prescribed",
    },
    {
        "task_name": "Quarterly Return to Local Employment Exchange",
        "description": "Furnish quarterly returns in Form ER-I within 30 days of the due date, namely: 31 March, 30 June, 30 September, and 31 December.",
        "due_date": "2026/01/29",
        "company_name": "ZYDUS LIFESCIENCES LIMITED",
        "unit_name": "N/A",
        "state": "N/A",
        "help_text": "Employment Exchange (Compulsory Notification of Vacancies) Act, 1959 and Employment Exchange (Compulsory Notification of Vacancies) Rules, 1960",
    },
    {
        "task_name": "Submission of Quarterly Statement in respect of TDS on Salary electronically",
        "description": "Submit electronically a quarterly statement to the Director General of Income-tax (or authorized person) in Form 24Q for TDS on salary.",
        "due_date": "2026/07/31",
        "company_name": "ZYDUS LIFESCIENCES LIMITED",
        "unit_name": "N/A",
        "state": "N/A",
        "help_text": "Income Tax Act, 1961 and Income Tax Rules, 1962",
    },
    {
        "task_name": "Furnishing of Form III",
        "description": "Furnish the information as stated in Form III of Schedule-II of the Order on a quarterly basis.",
        "due_date": "2026/06/05",
        "company_name": "ZYDUS LIFESCIENCES LIMITED",
        "unit_name": "N/A",
        "state": "N/A",
        "help_text": "The Essential Commodities Act, 1955 and The Drug (Prices Control) Order, 2013",
    },
    {
        "task_name": "Submission of Quarterly Compliance Report",
        "description": "Submit a quarterly compliance report on corporate governance through Integrated Filing (Governance). - Within 30 days from the end of each quarter",
        "due_date": "2026/01/20",
        "company_name": "ZYDUS LIFESCIENCES LIMITED",
        "unit_name": "N/A",
        "state": "N/A",
        "help_text": "Securities and Exchange Board of India Act, 1992 and Securities and Exchange Board of India (Listing Obligations and Disclosure Requirements) Regulations, 2015",
    },
    {
        "task_name": "Filing of Shareholding Pattern in XBRL mode",
        "description": "Ensure filing of a statement showing holding of securities to the Stock Exchange in the format specified by the Board from time to time.",
        "due_date": "2026/01/10",
        "company_name": "ZYDUS LIFESCIENCES LIMITED",
        "unit_name": "N/A",
        "state": "N/A",
        "help_text": "Securities and Exchange Board of India Act, 1992 and Securities and Exchange Board of India (Listing Obligations and Disclosure Requirements) Regulations, 2015",
    }
]


# --- 2. VECTOR DATABASE ---

def row_to_document(row: Dict[str, str]) -> str:
    return (
        f"Task Name: {row['task_name']}\n"
        f"Description: {row['description']}\n"
        f"Help Text: {row['help_text']}\n"
        f"Company Name: {row['company_name']}\n"
        f"Unit Name: {row['unit_name']}\n"
        f"State: {row['state']}\n"
        f"Due Date: {row['due_date']}"
    )

def build_collection():
    client = chromadb.PersistentClient(path="./chroma_db")
    # Device="cpu" prevents the PyTorch Meta Tensor crash
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2",
        device="cpu"
    )
    return client.get_or_create_collection(
        name="semantic_search",
        embedding_function=embedding_fn,
    )

def index_tasks(collection) -> None:
    ids, docs, metas = [], [], []

    for i, row in enumerate(TASK_ROWS, start=1):
        ids.append(str(i))
        docs.append(row_to_document(row))
        metas.append(
            {
                "task_name": row["task_name"],
                "due_date": row["due_date"],
                "company_name": row["company_name"],
                "unit_name": row["unit_name"],
                "state": row["state"],
            }
        )

    try:
        collection.add(ids=ids, documents=docs, metadatas=metas)
    except Exception:
        # Avoid duplicate additions
        existing = collection.get(ids=ids)
        existing_ids = set(existing.get("ids", []))
        new_ids, new_docs, new_metas = [], [], []
        for _id, doc, meta in zip(ids, docs, metas):
            if _id not in existing_ids:
                new_ids.append(_id)
                new_docs.append(doc)
                new_metas.append(meta)
        if new_ids:
            collection.add(ids=new_ids, documents=new_docs, metadatas=new_metas)


# --- 3. ENHANCED EXTRACTION & PREPROCESSING LOGIC ---

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()

def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    # 1. Convert to grayscale to remove color noise
    img = img.convert('L')
    
    # 2. Mildly boost contrast (1.5 instead of 2.0) to make text stand out 
    img = ImageEnhance.Contrast(img).enhance(1.5)
    return img

def extract_text_from_image(uploaded_file) -> str:
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((3000, 4000), Image.Resampling.LANCZOS) 
    img = preprocess_image_for_ocr(img)
    
    tesseract_cfg = r'--oem 3 --psm 3'
    return pytesseract.image_to_string(img, config=tesseract_cfg)
    
def extract_text_from_pdf(uploaded_file) -> str:
    pdf_bytes = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts: List[str] = []
    tesseract_cfg = r'--oem 3 --psm 6'

    for page in doc:
        text = (page.get_text("text") or "").strip()
        if text:
            parts.append(text)

        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = preprocess_image_for_ocr(img)
        
        ocr_text = (pytesseract.image_to_string(img, config=tesseract_cfg) or "").strip()
        if ocr_text:
            parts.append(ocr_text)

    doc.close()
    return "\n\n".join(parts)

def extract_text_from_docx(uploaded_file) -> str:
    doc = docx.Document(uploaded_file)
    return "\n".join([para.text for para in doc.paragraphs])

def fallback_summarize_text(raw_text: str, max_chars: int = 2500) -> str:
    """Basic keyword-based fallback if OpenAI fails or key is missing."""
    raw_text = clean_text(raw_text)
    if not raw_text: return ""

    lines = [line.strip() for line in raw_text.split(". ") if line.strip()]
    keywords = [
        "employee", "employees", "wage", "salary", "pay", "stipend", "fire",
        "waste", "lift", "escalator", "smoking", "notice", "compensation",
        "workshop", "policy", "deduction", "house", "accommodation", "manpower",
        "working hours", "maintenance", "complaint", "authorized", "return",
        "exchange", "tds", "governance", "shareholding", "xbrl", "compliance"
    ]

    interesting = [line for line in lines if any(k in line.lower() for k in keywords)]
    if not interesting:
        interesting = lines[:20]

    return " ".join(interesting)[:max_chars]

def summarize_with_openai(raw_text: str, api_key: str, max_chars: int = 2500) -> str:
    """Use OpenAI to generate a highly relevant semantic summary for the vector search."""
    raw_text = clean_text(raw_text)
    if not raw_text: return ""
    
    if not api_key:
        st.warning("⚠️ No OpenAI API key provided. Falling back to basic keyword extraction.")
        return fallback_summarize_text(raw_text, max_chars)

    try:
        client = OpenAI(api_key=api_key)
        
        # Truncate text to avoid massive token costs. First 15,000 chars is usually enough to identify the document type.
        truncated_text = raw_text[:15000]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Cost effective and fast
            messages=[
                {"role": "system", "content": "You are a legal and HR compliance assistant. Extract and summarize the core compliance, HR, taxation, and corporate governance actions required in the provided text. Keep it concise, highlighting actionable duties, forms, and regulations. Do not include introductory fluff."},
                {"role": "user", "content": truncated_text}
            ],
            max_tokens=400,
            temperature=0.2
        )
        summary = response.choices[0].message.content
        return summary[:max_chars]
        
    except Exception as e:
        st.error(f"❌ OpenAI API Error: {e}. Falling back to basic extraction.")
        return fallback_summarize_text(raw_text, max_chars)


# --- 4. SEARCH & RERANKING ---

def search_tasks(collection, query_text: str, top_k: int = 5):
    results = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    
    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "distance": float(results["distances"][0][i]),
            "metadata": results["metadatas"][0][i],
            "document": results["documents"][0][i]
        })
    return hits

def rerank_with_word_overlap(query_text: str, candidates: List[Dict]) -> List[Dict]:
    query_words = set(re.findall(r"[a-zA-Z0-9]+", query_text.lower()))
    scored = []

    for c in candidates:
        doc_words = set(re.findall(r"[a-zA-Z0-9]+", c["document"].lower()))
        overlap = len(query_words.intersection(doc_words))
        score = (1.0 / (1.0 + c["distance"])) + (overlap * 0.05)
        scored.append({**c, "overlap_score": overlap, "final_score": score})

    return sorted(scored, key=lambda x: x["final_score"], reverse=True)

def confidence_from_distance(distance: float) -> str:
    if distance <= 0.35: return "High"
    if distance <= 0.50: return "Medium"
    return "Low"


# --- 5. STREAMLIT UI ---

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
    
    # Build Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key Input
        openai_api_key = st.text_input("OpenAI API Key (Optional but recommended)", type="password", help="Used to intelligently summarize documents before searching.")
        
        # Primary Settings
        st.subheader("Search Parameters")
        top_k = st.slider("Matches to retrieve", 1, 15, 5)
        use_reranker = st.checkbox("Use Word Overlap Reranker", value=True)
        
        st.write("---")
        
        # Advanced Settings Expandable Section
        with st.expander("🛠️ Advanced Settings", expanded=True):
            show_raw_text = st.checkbox("Show Raw Extracted Text Tab", value=True)
            show_summary = st.checkbox("Show AI Query Summary Tab", value=True)
            max_chars = st.number_input("Max Extraction Chars", min_value=500, max_value=10000, value=2500, step=500)
            
        st.write("---")
        st.success(f"📚 Loaded Tasks: **{len(TASK_ROWS)}**")

    # Main Application Area
    st.title("📄 " + APP_TITLE)
    st.markdown("Upload a document to automatically extract text, summarize it using AI, and find the closest matching compliance task.")

    # Initialize Vector DB
    if "collection" not in st.session_state:
        with st.spinner("Initializing Vector Database..."):
            collection = build_collection()
            index_tasks(collection)
            st.session_state.collection = collection

    collection = st.session_state.collection

    # File Upload Component
    uploaded_file = st.file_uploader(
        "Drop your file here", 
        type=["pdf", "docx", "png", "jpg", "jpeg"],
        help="Supports PDF, Word Documents, and Images. Images will be processed with OCR."
    )

    if uploaded_file is None:
        return

    # Processing Routing
    file_ext = uploaded_file.name.split(".")[-1].lower()
    
    with st.spinner(f"Extracting text from {file_ext.upper()}..."):
        if file_ext == "pdf":
            raw_text = extract_text_from_pdf(uploaded_file)
        elif file_ext == "docx":
            raw_text = extract_text_from_docx(uploaded_file)
        elif file_ext in ["png", "jpg", "jpeg"]:
            raw_text = extract_text_from_image(uploaded_file)
        else:
            raw_text = ""

    # Call the new OpenAI summarizer
    with st.spinner("Generating smart summary..."):
        query_text = summarize_with_openai(raw_text, api_key=openai_api_key, max_chars=int(max_chars))

    if not query_text:
        st.error("No text could be extracted from this document. It might be blank, handwritten, or highly illegible.")
        return

    with st.spinner("Running semantic search and scoring..."):
        candidates = search_tasks(collection, query_text, top_k=top_k)
        if use_reranker:
            candidates = rerank_with_word_overlap(query_text, candidates)

    if not candidates:
        st.warning("No matches found in the database.")
        return

    # --- RESULTS PRESENTATION (Tabbed Layout) ---
    st.markdown("---")
    
    # Dynamically build tabs based on settings
    tab_names = ["🎯 Top Match", "📋 All Candidates"]
    if show_raw_text: tab_names.append("🔍 Extracted Text")
    if show_summary: tab_names.append("🧠 AI Query Summary")
    
    tabs = st.tabs(tab_names)

    # TAB 1: Top Match
    with tabs[0]:
        best = candidates[0]
        st.subheader("Best Compliance Task Match")
        
        # Styled Container for Top Match
        with st.container():
            st.success(f"**Task Name:** {best['metadata'].get('task_name', 'Unknown Task')}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Confidence", confidence_from_distance(best["distance"]))
            c2.metric("Vector Distance", f"{best['distance']:.4f}")
            c3.metric("Due Date", best['metadata'].get('due_date', 'N/A'))
            if use_reranker:
                c4.metric("Keyword Overlap", best.get("overlap_score", 0))
            
            st.info(f"**Task Description / Details:**\n\n{best['document']}")

    # TAB 2: All Candidates
    with tabs[1]:
        st.subheader(f"Top {len(candidates)} Candidate Matches")
        
        for idx, cand in enumerate(candidates, start=1):
            with st.expander(f"{idx}. {cand['metadata'].get('task_name', 'Unknown')} (Confidence: {confidence_from_distance(cand['distance'])})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.write("**Stats:**")
                    st.write(f"- **Distance:** `{cand['distance']:.4f}`")
                    if use_reranker:
                        st.write(f"- **Overlap Score:** `{cand.get('overlap_score', 'N/A')}`")
                        st.write(f"- **Final Rank Score:** `{cand.get('final_score', 0):.4f}`")
                with c2:
                    st.write("**Document Data:**")
                    st.text(cand["document"])

    # TAB 3: Extracted Text (Conditional)
    if show_raw_text:
        with tabs[tab_names.index("🔍 Extracted Text")]:
            st.subheader("Raw Text Post-OCR")
            st.text_area("This is the exact text read from your file:", raw_text, height=400)

    # TAB 4: AI Query Summary (Conditional)
    if show_summary:
        with tabs[tab_names.index("🧠 AI Query Summary")]:
            st.subheader("Filtered Search Query")
            st.markdown("To improve search accuracy, the AI isolated these key points to query the Vector Database:")
            st.write(query_text)

if __name__ == "__main__":
    main()