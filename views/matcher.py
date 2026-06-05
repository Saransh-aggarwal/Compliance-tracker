import os
import streamlit as st
import datetime
from dotenv import load_dotenv

load_dotenv()

# TASK_ROWS was removed from config
from src.document_processor import extract_text_from_pdf, extract_text_from_docx, extract_text_from_image
from src.retrieval import build_collection, index_tasks, index_single_task
from src.agent_workflow import agentic_matching_workflow
from src.database import init_db, get_all_tasks, add_task


APP_TITLE = "Engine: Agentic Compliance Workflow"

def main():
    
    with st.sidebar:
        st.markdown("### ⚙️ Engine Tuning")
        st.markdown("Adjust the hyper-parameters for the retrieval and inference engine.")
        
        with st.container(border=True):
            st.markdown("#### 🔎 Search Architecture")
            top_k = st.slider("Candidate Retrieval Count", min_value=1, max_value=15, value=5, help="Number of semantic nearest-neighbors to fetch from ChromaDB.")
            use_reranker = st.toggle("Enable Keyword Reranker", value=True, help="Applies a BM25-style lexical overlap reranking over the semantic results.")
        
        with st.container(border=True):
            st.markdown("#### 🛠️ Developer Tracing")
            show_raw_text = st.toggle("Show OCR Extraction Traces", value=True)
            show_workflow = st.toggle("Show LangGraph State Transitions", value=True)
            
        st.markdown("---")
        
        # Displaying stats cleanly
        st.metric(label="📚 Total Indexed Compliance Rules", value=st.session_state.get('task_count', 0))

    st.markdown(f"<h1 style='text-align: center; color: #6366f1;'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    st.markdown("""
        <p style='text-align: center; color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;'>
        Provide a document or paste text below. The AI Agent will autonomously extract the context, find the matching compliance task, analyze the timeframe, and execute a ledger update.
        </p>
    """, unsafe_allow_html=True)

    if "db_initialized" not in st.session_state:
        with st.spinner("Initializing Database..."):
            try:
                init_db()
                tasks = get_all_tasks()
                if not tasks:
                    st.warning("Database is empty. Please add tasks using the 'Add Task' page.")
                tasks = get_all_tasks()
                st.session_state.task_count = len(tasks)
                st.session_state.db_initialized = True
            except Exception as e:
                st.error(f"Database Initialization Failed: {e}")
                return

    if "collection" not in st.session_state:
        with st.spinner("Initializing Vector Database..."):
            collection = build_collection()
            tasks = get_all_tasks()
            index_tasks(collection, tasks)
            st.session_state.collection = collection

    collection = st.session_state.collection

    st.markdown("### 📤 Ingestion Pipeline")
    
    input_method = st.radio("Select Ingestion Mode", ["📁 Document Upload", "📝 Raw Text Input"], horizontal=True)
    
    raw_text = ""
    
    # Use a container to cleanly box the input section
    with st.container(border=True):
        if input_method == "📁 Document Upload":
            st.markdown("#### Upload Unstructured Data")
            uploaded_file = st.file_uploader(
                "Supports PDF, Word Documents, and Images (OCR will be applied).", 
                type=["pdf", "docx", "png", "jpg", "jpeg"]
            )
            
            if uploaded_file is not None:
                file_ext = uploaded_file.name.split(".")[-1].lower()
                with st.spinner(f"Running Document Processing Pipeline on {file_ext.upper()}..."):
                    if file_ext == "pdf":
                        raw_text = extract_text_from_pdf(uploaded_file)
                    elif file_ext == "docx":
                        raw_text = extract_text_from_docx(uploaded_file)
                    elif file_ext in ["png", "jpg", "jpeg"]:
                        raw_text = extract_text_from_image(uploaded_file)
                        
        else:
            pasted_text = st.text_area("Paste unstructured text, email bodies, or JSON snippets here:", height=200, placeholder="E.g., Please find attached the monthly GST filing for August 2026...")
            process_btn = st.button("🚀 Execute Pipeline", type="primary", use_container_width=True)
            if process_btn and pasted_text.strip():
                raw_text = pasted_text
                
    if not raw_text.strip():
        # Stop here until the user provides input
        return

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.warning("⚠️ GOOGLE_API_KEY not found in .env file. Falling back to non-LLM matching.")

    with st.spinner("Agentic Workflow Running (Extraction -> Retrieval -> Selection -> Period Analysis -> Tracking)..."):
        upload_date = datetime.datetime.now().strftime("%Y-%m-%d")
        workflow_result = agentic_matching_workflow(
            api_key=api_key,
            db_collection=collection,
            raw_text=raw_text,
            upload_date=upload_date,
            top_k=top_k,
            use_reranker=use_reranker
        )
        
    if workflow_result["status"] == "error":
        st.error(workflow_result["message"])
        return
        
    final_sel = workflow_result["final_result"]
    history = workflow_result["history"]
    tracking_status = workflow_result.get("tracking_status")

    tab_names = ["🎯 AI Resolution", "📋 Semantic Candidates"]
    if show_workflow: tab_names.append("🧬 State Transitions")
    if show_raw_text: tab_names.append("🔍 Extracted Trace")
    
    tabs = st.tabs(tab_names)

    # TAB 1: Top Decision
    with tabs[0]:
        st.markdown("### Agent Resolution")
        
        if final_sel["selected_task_id"] is None:
            st.warning("⚠️ **Agent Conclusion:** No valid mappings found in the active ruleset.")
            with st.expander("View Agent's Reasoning"):
                st.info(f"{final_sel['reasoning']}")
        else:
            st.success(f"**Matched Rule:** {final_sel['task_name']}")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("LLM Confidence Score", f"{final_sel['confidence']:.2f}")
            with c2:
                st.metric("Iterative Refinements", workflow_result["total_attempts"])
            with c3:
                st.metric("Rule Entity ID", final_sel["selected_task_id"])
            
            with st.expander("🧠 View Agent's Reasoning", expanded=True):
                st.info(final_sel['reasoning'])
            
            # Show Tracking Status
            if tracking_status:
                st.markdown("#### Autonomous Ledger Execution")
                
                with st.container(border=True):
                    if tracking_status.get("status") == "Error":
                        st.error(f"❌ Execution Failure: {tracking_status.get('message')}")
                    else:
                        c_stat, c_per = st.columns(2)
                        with c_stat:
                            if tracking_status.get("status") == "Already Marked":
                                st.warning("⚠️ **Status:** Skipped (Duplicate)")
                            else:
                                st.success("✅ **Status:** Executed & Logged")
                        with c_per:
                            st.info(f"**Period Extracted:** {tracking_status.get('period_label')}")
                            
                        st.write(f"**Context Analysis:** {tracking_status.get('reasoning', 'No reasoning provided.')}")
            
            # Show the selected document metadata from the last attempt's candidates if possible
            last_candidates = history[-1]["candidates"]
            best_doc = next((c for c in last_candidates if c["id"] == final_sel["selected_task_id"]), None)
            if best_doc:
                with st.expander("View Retrieved Data Payload"):
                    st.json(best_doc["metadata"])
                    st.text(best_doc["document"])

    # TAB 2: All Candidates
    with tabs[1]:
        st.subheader(f"Candidates Retrieved on Terminal Attempt")
        
        last_candidates = history[-1]["candidates"]
        for idx, cand in enumerate(last_candidates, start=1):
            with st.expander(f"{idx}. {cand['metadata'].get('task_name', 'Unknown')}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.write("**Stats:**")
                    st.write(f"- **Distance:** `{cand['distance']:.4f}`")
                    if use_reranker:
                        st.write(f"- **Final Rank Score:** `{cand.get('final_score', 0):.4f}`")
                with c2:
                    st.text(cand["document"])

    # TAB 3: Workflow Details (Conditional)
    if show_workflow:
        with tabs[tab_names.index("🧬 Workflow Details")]:
            st.subheader(f"LangGraph-style State Walkthrough (Attempts: {workflow_result['total_attempts']})")
            
            for step in history:
                with st.container():
                    st.write(f"### Attempt {step['attempt']}")
                    st.write("**Executed Query:** ", step["query"])
                    st.json(step["selection"])
                    st.write("---")

    # TAB 4: Extracted Text (Conditional)
    if show_raw_text:
        with tabs[tab_names.index("🔍 Extracted Text")]:
            st.subheader("Raw Text Post-OCR")
            st.text_area("Original Unprocessed Text:", raw_text, height=400)

if __name__ == "__main__":
    main()
