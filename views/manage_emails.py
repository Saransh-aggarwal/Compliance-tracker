import streamlit as st
from database import add_email_account, get_all_email_accounts, delete_email_account
from scheduler import run_sync_job, get_sync_status

def main():
    st.markdown("<h1 style='text-align: center; color: #6366f1;'>🔌 IMAP Integrations</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 30px;'>Configure autonomous email ingestion via secure Google App Passwords.</p>", unsafe_allow_html=True)

    # Manual Sync Section
    st.markdown("### 🔄 Sync Operations")
    col1, col2 = st.columns([1, 3])
    
    status = get_sync_status()
    
    with col1:
        if st.button("🚀 Sync Now", type="primary", use_container_width=True, disabled=status['is_syncing']):
            with st.spinner("Syncing emails..."):
                run_sync_job()
                st.rerun()
                
    with col2:
        if status['is_syncing']:
            st.info("⏳ Sync in progress...")
        else:
            st.write("**Last Sync Log:**")
            st.code(status['last_log'])

    st.markdown("---")

    # Add New Account Form
    st.markdown("### ➕ Connect New Service Account")
    with st.expander("Establish Secure IMAP Connection", expanded=False):
        with st.form("add_email_form"):
            email_input = st.text_input("Service Email Address", placeholder="admin@domain.com")
            password_input = st.text_input("16-Character App Password", type="password", help="Use a Google App Password, not your standard account password.")
            submit_btn = st.form_submit_button("Authenticate & Connect", type="primary")

            if submit_btn:
                if not email_input or not password_input:
                    st.error("Please provide both email and app password.")
                else:
                    try:
                        add_email_account(email_input, password_input)
                        st.success(f"Successfully authenticated: {email_input}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Connection Failed: {e}")

    st.markdown("---")

    # List Existing Accounts
    st.markdown("### 📋 Active IMAP Streams")
    accounts = get_all_email_accounts()

    if not accounts:
        st.info("No active streams currently configured.")
    else:
        for account in accounts:
            with st.container(border=True):
                col_info, col_action = st.columns([5, 1])
                with col_info:
                    st.markdown(f"**Stream Endpoint:** `{account['email']}`")
                    status_text = "🟢 Active & Polling" if account['is_active'] else "🔴 Disconnected"
                    last_sync = account['last_sync_time'] or "Pending initial sync..."
                    
                    st.write(f"{status_text} | **Last Heartbeat:** {last_sync}")
                
                with col_action:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Disconnect", key=f"del_{account['id']}", type="secondary", use_container_width=True):
                        delete_email_account(account['id'])
                        st.rerun()

if __name__ == "__main__":
    main()
