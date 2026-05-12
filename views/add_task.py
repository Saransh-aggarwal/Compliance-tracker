import streamlit as st
from database import add_task
from retrieval import index_single_task

st.markdown("<h1 style='text-align: center; color: #6366f1;'>✨ Create Compliance Rule</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 30px;'>Define new regulatory requirements. These will be immediately synchronized to the vector engine.</p>", unsafe_allow_html=True)

with st.container(border=True):
    with st.form("add_task_form"):
        st.markdown("### Rule Metadata")
        
        col1, col2 = st.columns(2)
        with col1:
            new_task_name = st.text_input("Rule Signature (Task Name)", placeholder="e.g. Monthly GST Filing")
            new_due = st.text_input("Expected Execution Date (YYYY/MM/DD)", placeholder="2026/12/31")
            new_track_type = st.selectbox("Execution Frequency", ["monthly", "quarterly", "6 months", "yearly"])
        with col2:
            new_company = st.text_input("Corporate Entity")
            new_unit = st.text_input("Business Unit")
            new_state = st.text_input("Jurisdiction (State/Region)")
            
        st.markdown("### Functional Context")
        new_desc = st.text_area("Detailed Description", height=100)
        new_help = st.text_area("Resolution Guide / Help Text", height=100)
    
        submitted = st.form_submit_button("Deploy Rule", type="primary", use_container_width=True)
    
    if submitted:
        if new_task_name and new_desc and new_due:
            new_task_data = {
                "task_name": new_task_name,
                "description": new_desc,
                "due_date": new_due,
                "company_name": new_company,
                "unit_name": new_unit,
                "state": new_state,
                "help_text": new_help,
                "track_type": new_track_type
            }
            try:
                added_task = add_task(new_task_data)
                if "collection" in st.session_state:
                    index_single_task(st.session_state.collection, added_task)
                st.success(f"Task '{new_task_name}' added successfully!")
                
                # Update global count
                if "task_count" in st.session_state:
                    st.session_state.task_count += 1
                    
            except Exception as e:
                st.error(f"Failed to add task: {e}")
        else:
            st.error("Task Name, Description, and Due Date are required.")
