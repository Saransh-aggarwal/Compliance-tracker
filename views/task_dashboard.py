import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_all_tasks, get_task_logs_for_year

st.markdown("<h1 style='text-align: center; color: #6366f1;'>📊 Audit & Analytics Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 30px;'>Live monitor of compliance rule execution across all operational frequencies.</p>", unsafe_allow_html=True)

# Custom CSS for table styling
st.markdown("""
<style>
    .stDataFrame {
        width: 100%;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Year Selector
current_year = datetime.now().year
years = [str(y) for y in range(current_year - 2, current_year + 3)]
selected_year = st.selectbox("Select Year", years, index=2)

# Fetch Data
with st.spinner("Loading tasks and logs..."):
    all_tasks = get_all_tasks()
    all_logs = get_task_logs_for_year(selected_year)

# Filter logs to only include "Completed" or "Already Marked" statuses to consider them as done
completed_logs = [log for log in all_logs if log["status"] in ["Completed", "Already Marked", "Newly Logged"]]

# Helper to build the dataframe
def build_grid(track_type: str, periods: list, period_keys: list):
    tasks_of_type = [t for t in all_tasks if t.get("track_type", "yearly").lower() == track_type]
    
    if not tasks_of_type:
        st.info(f"No compliance rules registered for frequency: {track_type}")
        return
    
    data = []
    total_expected = len(tasks_of_type) * len(period_keys)
    total_completed = 0
    
    for t in tasks_of_type:
        row = {"Entity ID": f"#{t['id']}", "Rule Signature": t["task_name"]}
        
        for i, p_key in enumerate(period_keys):
            expected_label = f"{selected_year}-{p_key}" if p_key else selected_year
            is_completed = any(log["task_id"] == t["id"] and log["period_label"] == expected_label for log in completed_logs)
            if is_completed:
                total_completed += 1
            row[periods[i]] = "✅" if is_completed else "❌"
            
        data.append(row)
        
    df = pd.DataFrame(data)
    
    # Progress Metric
    completion_rate = (total_completed / total_expected) * 100 if total_expected > 0 else 0
    st.progress(completion_rate / 100.0, text=f"Completion Rate: {completion_rate:.1f}%")
    
    # Render with Streamlit
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Entity ID": st.column_config.TextColumn("ID", width="small"),
            "Rule Signature": st.column_config.TextColumn("Rule Name", width="large"),
        }
    )

# Setup Tabs
tab_monthly, tab_quarterly, tab_half, tab_yearly = st.tabs([
    "📅 Monthly", "📊 Quarterly", "⏳ 6 Months", "📆 Yearly"
])

with tab_monthly:
    st.subheader("Monthly Tasks")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    keys = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
    build_grid("monthly", months, keys)

with tab_quarterly:
    st.subheader("Quarterly Tasks")
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    keys = ["Q1", "Q2", "Q3", "Q4"]
    build_grid("quarterly", quarters, keys)

with tab_half:
    st.subheader("Half-Yearly Tasks")
    halves = ["First Half (H1)", "Second Half (H2)"]
    keys = ["H1", "H2"]
    build_grid("6 months", halves, keys)

with tab_yearly:
    st.subheader("Yearly Tasks")
    build_grid("yearly", ["Status"], [""])
