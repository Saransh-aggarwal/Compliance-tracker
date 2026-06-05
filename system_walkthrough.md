 # Complete Application Walkthrough

This document explains the Agentic Compliance Task Matcher application function by function, and important pieces line by line.

The system is designed to take an uploaded unstructured document (PDF, Image, or Word Document), extract the raw text, and use an AI "Agent" (powered by Gemini and LangGraph) to match the document against a database of known **Compliance Tasks**. It searches a local vector database iteratively until it confidently finds the right match.

---

## 1. The Entry Point: `app.py`
This file is the Streamlit frontend. It connects the user interface with backend document processing and the AI workflow.

### `main()` 
This is the only function in `app.py`. It runs top-to-bottom every time the user interacts with the app.

```python
def main():
    # 1. UI Setup
    st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
    
    # 2. Sidebar Configuration
    with st.sidebar:
        ...
        top_k = st.slider("Matches to retrieve initially", 1, 15, 5)
        use_reranker = st.checkbox("Use Word Overlap Reranker", value=True)
```
**Explanation:** Configures the Streamlit page layout and creates a left sidebar where users can tune the algorithm (e.g., how many vectors to retrieve `top_k`, and whether to use the keyword reranker).

```python
    # 3. Vector Database Initialization
    if "collection" not in st.session_state:
        with st.spinner("Initializing Vector Database..."):
            collection = build_collection()
            index_tasks(collection, TASK_ROWS)
            st.session_state.collection = collection
```
**Explanation:** Because Streamlit reruns on every interaction, it checks `st.session_state` to see if the ChromaDB vector database is already loaded. If not, it calls `build_collection()` and `index_tasks()` to load the hardcoded compliance rules (`TASK_ROWS` from `config.py`) into the vector DB, and caches it.

```python
    # 4. File Upload & Processing
    uploaded_file = st.file_uploader(...)
    if uploaded_file is None: return

    file_ext = uploaded_file.name.split(".")[-1].lower()
    if file_ext == "pdf":
        raw_text = extract_text_from_pdf(uploaded_file)
    ...
```
**Explanation:** Provides a drag-and-drop file uploader. When a file is uploaded, it checks the extension and calls the corresponding file extraction function from `src/document_processor.py`.

```python
    # 5. Agent Execution
    with st.spinner("Agentic Workflow Running..."):
        workflow_result = agentic_matching_workflow(
            api_key=api_key,
            db_collection=collection,
            raw_text=raw_text,
            top_k=top_k,
            use_reranker=use_reranker
        )
```
**Explanation:** Passes the extracted text and the database instance to the LangGraph AI workflow (`agentic_matching_workflow`).

```python
    # 6. Display Results
    final_sel = workflow_result["final_result"]
    # ... Streamlit UI code to show metrics and reasoning ...
```
**Explanation:** Parses the JSON output from the agent and renders it securely into UI tabs, separating out the AI's final decision from its underlying process history.

---

## 2. Text Extraction: `src/document_processor.py`
This file contains specific functions to translate complex file formats into plain strings.

### `extract_text_from_image(uploaded_file)`
```python
def extract_text_from_image(uploaded_file) -> str:
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img) # Fixes rotation issues based on EXIF data
    img.thumbnail((3000, 4000), Image.Resampling.LANCZOS) # Downscales massive images to prevent memory errors
    img = preprocess_image_for_ocr(img) # Converts to Grayscale & increases contrast
    
    tesseract_cfg = r'--oem 3 --psm 3' 
    return pytesseract.image_to_string(img, config=tesseract_cfg)
```
**Explanation:** Opens an image, standardizes its rotation, compresses it, passes it through an image enhancement function (making text stand out), and finally uses Tesseract OCR to read the text.

### `extract_text_from_pdf(uploaded_file)`
```python
def extract_text_from_pdf(uploaded_file) -> str:
    # ... opens the PDF with PyMuPDF (fitz) ...
    for page in doc:
        text = (page.get_text("text") or "").strip() # Try to extract standard digital text
        if text: parts.append(text)
        
        # Take a high-res screenshot of the PDF page and run OCR (for scanned PDFs)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = preprocess_image_for_ocr(img)
        ocr_text = (pytesseract.image_to_string(img, config=tesseract_cfg) or "").strip()
        if ocr_text: parts.append(ocr_text)
```
**Explanation:** It does a two-pronged extraction. First, it tries to read embedded digital text. Second, it converts the page into an image and runs OCR. This ensures extraction works for both digital and purely scanned PDFs.

---

## 3. Database & Retrieval: `src/retrieval.py`
This manages the local ChromaDB deployment and query ranking.

### `build_collection()`
```python
def build_collection():
    client = chromadb.PersistentClient(path="./chroma_db")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2", device="cpu"
    )
    return client.get_or_create_collection("semantic_search", embedding_function=embedding_fn)
```
**Explanation:** Creates a local persistence path for ChromaDB. It initializes a lightweight, fast, CPU-bound sentence-transformer embedding model (`all-MiniLM-L6-v2`) which turns words into numerical arrays (vectors), and returns the collection object.

### `index_tasks()` & `search_tasks()`
- **`index_tasks`**: Loops over the hard-coded `TASK_ROWS` dictionary, converts each to a string, and sends them to ChromaDB alongside their metadata. It has safeguard `except` blocks to prevent duplicating vectors if the app restarts.
- **`search_tasks`**: Takes a string query, gets ChromaDB to convert it to a vector, and uses cosine distance to find the closest `top_k` tasks in the database.

### `rerank_with_word_overlap(query_text, candidates)`
```python
def rerank_with_word_overlap(query_text: str, candidates: List[Dict]) -> List[Dict]:
    # Extracts pure alphanumeric words from the search query
    query_words = set(re.findall(r"[a-zA-Z0-9]+", query_text.lower()))
    scored = []

    for c in candidates:
        # Extracts words from the Candidate retrieved from ChromaDB
        doc_words = set(re.findall(r"[a-zA-Z0-9]+", c["document"].lower()))
        overlap = len(query_words.intersection(doc_words)) # How many exact words match
        
        # A hybrid score combining Vector Semantic Distance and Exact Keyword Overlap
        score = (1.0 / (1.0 + c["distance"])) + (overlap * 0.05) 
        scored.append({**c, "overlap_score": overlap, "final_score": score})

    return sorted(scored, key=lambda x: x["final_score"], reverse=True)
```
**Explanation:** Vectors are great at matching meaning, but bad at matching exact IDs or spelling. This function acts as a second pass. After the vector DB gets the top 5 documents, this function counts exactly how many literal words the document shares with the query, boosts its score, and re-sorts them.

---

## 4. AI Brain: `src/agent_workflow.py`
This contains the LangGraph state machine. It is cyclical, allowing the AI to retry tasks if it makes a mistake.

### `AgentState` (TypedDict)
```python
class AgentState(TypedDict):
    # Variables that get passed between nodes
    api_key: str
    db_collection: Any
    current_query: str
    candidates: List[Dict]
    retry_count: int
    ...
```
**Explanation:** This acts as the shared "memory payload" that gets passed continually between every step of the agent.

### `extract_node(state)`
```python
def extract_node(state: AgentState):
    raw_text = clean_text(state.get("raw_text", ""))
    llm = get_llm(...)
    
    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Input Document:\n{truncated_text}")
    ]
    response = llm.invoke(messages)
    return {"current_query": response.content[:2500]}
```
**Explanation:** The first node. It takes the giant, messy blob of text Extracted by PyTesseract, and uses the Gemini LLM to summarize it into a concise, focused "Search Query" representing the core legal/compliance entities.

### `retrieve_node(state)`
```python
def retrieve_node(state: AgentState):
    query = state["current_query"]
    candidates = search_tasks(...)
    candidates = rerank_with_word_overlap(query, candidates)
    return {"candidates": candidates}
```
**Explanation:** The second node. Takes the summarized `current_query` generated by the previous node, passes it to `src/retrieval.py` functions to search ChromaDB, and returns the list of matched `candidates`.

### `selection_node(state)`
```python
def selection_node(state: AgentState):
    # Set up LLM to force outputting a Pydantic Structured JSON schema
    llm = get_llm(api_key, structured_out=True) 
    
    messages = [
        SystemMessage(content=TASK_SELECTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Input Request: {query}\n\nCandidate Tasks:\n{formatted_candidates}")
    ]
    
    # LLM replies with JSON: {selected_task_id, confidence, reasoning, needs_retry}
    parsed_res = llm.invoke(messages) 
    
    # Force retry if confidence is too low
    if parsed_res.confidence < CONFIDENCE_THRESHOLD:
        parsed_res.needs_retry = True
        
    return {"final_result": parsed_res.model_dump(), "history": ...}
```
**Explanation:** The third node. The LLM acts as a judge. It looks at the query *and* the top candidates retrieved by the database. It is forced to respond in a strict JSON format (`TaskSelectionResult`). It decides which candidate is best, explains its logic (`reasoning`), and scores its `confidence`.

### `assess_edge(state)`
```python
def assess_edge(state: AgentState):
    final_res = state.get("final_result", {})
    if final_res.get("confidence", 0) >= CONFIDENCE_THRESHOLD or not final_res.get("needs_retry", False) or retry_count >= MAX_RETRIES:
        return "end"
    return "refine"
```
**Explanation:** A "Conditional Edge". Unlike nodes which perform actions, edges do routing. This simple function checks the LLM's confidence from the `selection_node`. If it's high enough, it routes the graph to `end` (stopping). If confidence is low, it routes to `refine` (trying again).

### `refinement_node(state)`
```python
def refinement_node(state: AgentState):
    messages = [
        SystemMessage(content=QUERY_REFINEMENT_SYSTEM_PROMPT),
        HumanMessage(content=f"Original Query: {original_query}\nReasoning for Failure: {final_res.get('reasoning', '')}\nPreviously Retrieved Tasks: {formatted_candidates}")
    ]
    new_query_res = llm.invoke(messages)
    return {"current_query": new_query_res.content.strip(), "retry_count": retry_count + 1}
```
**Explanation:** The fourth node (only accessed if `assess_edge` says so). Because the first search failed, the LLM is asked to review *why* it failed (using its own prior `reasoning`). It then generates an entirely new `current_query` to look for different keywords, and increments the retry loop count. The graph then points it back to the `retrieve_node` to start the vector search over again using the new query.
