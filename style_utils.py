import streamlit as st

def inject_minimalist_theme():
    """Injects high-quality CSS for an Absolute Top Toolbar style."""
    
    premium_css = """
    <style>
        /* Global Background & Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Inter', sans-serif;
            background-color: #FFFFFF !important;
        }

        /* 1. NUKE THE TOP WHITE SPACE COMPLETELY */
        header[data-testid="stHeader"], [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Target the Main Block Container to eliminate the huge default Streamlit gap */
        .block-container {
            padding-top: 1rem !important; /* Brings everything much higher */
            padding-bottom: 0rem !important;
            max-width: 98% !important;
            margin-top: -1.5rem !important; /* Pull up slightly more if needed */
        }

        /* 2. PIN THE NAVIGATION BAR */
        /* Target the row containing the header content */
        [data-testid="stVerticalBlock"] > div:has(h2) {
            position: sticky !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            z-index: 1000 !important;
            background-color: white !important;
            border: none !important; /* Remove ALL borders */
            padding: 1rem 40px !important;
            margin-bottom: 2rem !important;
            display: flex !important;
            align-items: center !important;
            box-shadow: none !important; 
            border-radius: 0 !important; /* Un-box the top header */
        }

        /* Prevent rogue bottom borders on native elements */
        h2 {
            border: none !important;
            padding-bottom: 0 !important;
        }

        /* 3. FIX BUTTON SIZES AND ALLIGNMENT */
        /* Make Edit and Upload uniform */
        div.stButton > button {
            height: 42px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            background: #2563EB !important;
            color: white !important;
            border-radius: 8px !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            padding: 0 20px !important;
            line-height: 1 !important;
            border: none !important;
            transition: background-color 0.2s ease !important;
        }

        div.stButton > button:hover {
            background-color: #1D4ED8 !important;
        }

        /* Force icon + text to align properly horizontally and never wrap */
        div.stButton > button p {
            white-space: nowrap !important;
            margin: 0 !important;
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
        }
        
        div.stButton > button div[data-testid="stMarkdownContainer"] {
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            justify-content: center !important;
        }

        /* 4. FIX PROFILE BUTTON TO BE EXACTLY CIRCULAR */
        [data-testid="stPopover"] button {
            width: 42px !important;
            height: 42px !important;
            min-width: 0 !important; /* Remove Streamlit's default min-width for buttons */
            border-radius: 50% !important; /* Perfect circle */
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            overflow: hidden !important;
            font-size: 1.2rem !important; /* Adjust emoji size */
            background: #F3F4F6 !important; /* Light background instead of loud blue */
            color: #1F2937 !important;
            border: 1px solid #E5E7EB !important;
        }

        [data-testid="stPopover"] button:hover {
            background: #E5E7EB !important;
        }
        
        [data-testid="stPopover"] button div[data-testid="stMarkdownContainer"] {
            width: 100% !important;
            height: 100% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* 5. SIDEBAR ALIGNMENT */
        [data-testid="stSidebar"] {
            background-color: #F8FAFC !important;
            border-right: 1px solid #E2E8F0 !important;
        }

        footer {visibility: hidden !important;}
    </style>
    """
    st.markdown(premium_css, unsafe_allow_html=True)

def render_header(title="Dashboard"):
    """Renders a single-row sticky toolbar at absolute zero-gap top."""
    
    # Grid layout for the toolbar, slightly larger action cols to avoid text wrapping
    col_brand, col_spacer, col_edit, col_upload, col_profile = st.columns([3, 3.6, 1.4, 1.4, 0.6], vertical_alignment="center")
    
    with col_brand:
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 10px;">
                <h2 style="margin: 0; font-size: 1.2rem; font-weight: 600; color: #1e293b; white-space: nowrap; border: none !important;">{title}</h2>
            </div>
        """, unsafe_allow_html=True)
        
    with col_profile:
        with st.popover("👤"):
            st.markdown("**Admin User**")
            st.caption("admin@livingliquid.com")
            st.divider()
            if st.button("Logout"):
                st.info("Logging out...")

    return col_edit, col_upload
