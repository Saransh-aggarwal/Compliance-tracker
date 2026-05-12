import streamlit as st
from scheduler import start_scheduler
from database import authenticate_admin, init_db, register_admin, get_security_question, reset_password

st.set_page_config(page_title="Legasis | Compliance Agent", page_icon="🏛️", layout="wide")

# Custom CSS for UI Overhaul
st.markdown("""
    <style>
    /* Center the Auth Forms */
    .auth-container {
        max-width: 450px;
        margin: 0 auto;
        padding-top: 50px;
    }
    .main-title {
        text-align: center;
        font-weight: 800;
        font-size: 3rem;
        background: -webkit-linear-gradient(45deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: -10px;
    }
    .sub-title {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 40px;
    }
    /* Style for buttons to look more premium */
    div.stButton > button:first-child {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize DB to ensure admin user exists
if "db_initialized" not in st.session_state:
    with st.spinner("Initializing Database..."):
        try:
            init_db()
            st.session_state.db_initialized = True
        except Exception as e:
            st.error(f"Database Initialization Failed: {e}")

# Initialize background scheduler for email ingestion
start_scheduler()

# Session state for login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    
    st.markdown("<div class='auth-container'>", unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>Legasis Agent</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-title'>Autonomous Compliance & Monitoring</p>", unsafe_allow_html=True)
    
    # Center block using columns
    _, col_center, _ = st.columns([1, 2, 1])
    
    with col_center:
        tab1, tab2, tab3 = st.tabs(["🔒 Login", "✨ Register", "🔑 Forgot Password"])
        
        with tab1:
            with st.container(border=True):
                with st.form("login_form"):
                    st.markdown("### Welcome Back")
                    username = st.text_input("Username", placeholder="admin")
                    password = st.text_input("Password", type="password", placeholder="••••••••")
                    submit = st.form_submit_button("Authenticate", type="primary", use_container_width=True)
                    
                    if submit:
                        if authenticate_admin(username, password):
                            st.session_state.logged_in = True
                            st.success("Authentication successful. Initializing workspace...")
                            st.rerun()
                        else:
                            st.error("Invalid credentials.")
                        
        with tab2:
            with st.container(border=True):
                with st.form("register_form"):
                    st.markdown("### Create Account")
                    reg_username = st.text_input("New Username")
                    reg_password = st.text_input("New Password", type="password")
                    reg_question = st.text_input("Security Question", placeholder="e.g. What is your pet's name?")
                    reg_answer = st.text_input("Security Answer")
                    reg_submit = st.form_submit_button("Register Account", type="primary", use_container_width=True)
                    
                    if reg_submit:
                        if not reg_username or not reg_password or not reg_question or not reg_answer:
                            st.error("Please fill in all fields.")
                        else:
                            success, msg = register_admin(reg_username, reg_password, reg_question, reg_answer)
                            if success:
                                st.success("Account created! You may now login.")
                            else:
                                st.error(msg)
                            
        with tab3:
            with st.container(border=True):
                st.markdown("### Recover Password")
                fp_username = st.text_input("Enter your Username", key="fp_username")
                
                if fp_username:
                    question = get_security_question(fp_username)
                    if question:
                        with st.form("reset_password_form"):
                            st.info(f"**Security Question:** {question}")
                            fp_answer = st.text_input("Answer")
                            fp_new_password = st.text_input("New Password", type="password")
                            fp_submit = st.form_submit_button("Reset Password", type="primary", use_container_width=True)
                            
                            if fp_submit:
                                if not fp_answer or not fp_new_password:
                                    st.error("Please fill in all fields.")
                                else:
                                    success, msg = reset_password(fp_username, fp_answer, fp_new_password)
                                    if success:
                                        st.success("Password reset successfully.")
                                    else:
                                        st.error(msg)
                    else:
                        st.warning("Username not found or no security question set.")
    st.markdown("</div>", unsafe_allow_html=True)
else:
    # Define pages
    matcher_page = st.Page("views/matcher.py", title="Compliance AI Workflow", icon="🎯", default=True)
    add_task_page = st.Page("views/add_task.py", title="Create Compliance Rule", icon="✨")
    dashboard_page = st.Page("views/task_dashboard.py", title="Audit & Analytics", icon="📊")
    manage_emails_page = st.Page("views/manage_emails.py", title="IMAP Integrations", icon="🔌")
    
    # Sidebar Profile UI
    st.sidebar.markdown("""
        <div style="text-align: center; padding-bottom: 20px;">
            <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Admin&backgroundColor=6366f1" width="80" style="border-radius: 50%; border: 2px solid #6366f1;">
            <h3 style="margin-top: 10px; margin-bottom: 0px;">Admin Workspace</h3>
            <p style="color: #94a3b8; font-size: 0.9rem;">Authenticated Session</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Logout function
    def logout():
        st.session_state.logged_in = False
        st.rerun()
        
    st.sidebar.button("Log Out Securely", on_click=logout, use_container_width=True)

    # Setup Navigation Menu
    pg = st.navigation({
        "Engine": [matcher_page],
        "Management Panel": [dashboard_page, add_task_page, manage_emails_page]
    })
    
    # Run the selected page
    pg.run()
