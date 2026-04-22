import streamlit as st
import extra_streamlit_components as stx
import requests
import os
import logging
import hashlib
import base64
import time
import datetime
import json

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fallback Cookie Secret since user stated they don't have one right now
COOKIE_SECRET = "fallback_temporary_dev_secret_key"

# AuthService class (backend)
class AuthService:
    def __init__(self):
        # Load from secrets.json as requested, fallback to environment variables
        logger.info("Initializing AuthService...")
        try:
            with open('secrets.json', 'r') as f:
                creds = json.load(f)
            self.base_url = creds.get("FIREAI_BASE_URL", os.getenv("FIREAI_BASE_URL"))
            self.api_key = creds.get("FIREAI_API_KEY", os.getenv("FIREAI_API_KEY"))
            logger.info(f"AuthService initialized with Base URL: {self.base_url}")
        except Exception as e:
            logger.error(f"Failed to load secrets for AuthService: {e}")
            self.base_url = os.getenv("FIREAI_BASE_URL")
            self.api_key = os.getenv("FIREAI_API_KEY")

    def login(self, email, password):
        # Restrict to allowed emails
        allowed_emails = ["gyaneswar@livingliquidz.com", "shyam@fireai.in"]
        
        logger.info(f"Login attempt for email: {email}")
        if email.lower() not in [e.lower() for e in allowed_emails]:
            logger.warning(f"Login attempt rejected: {email} not in allowed list")
            return False, "Access denied: Email not authorized."

        if not self.base_url or not self.api_key:
            logger.error("Authentication service not configured (missing URL or API Key).")
            return False, "Authentication service not configured. Please check secrets.json"

        url = f"{self.base_url}/users/v1/authentication/login"
        payload = {
            "data": {
                "email": email,
                "password": password,
                "provider": "fireai",
                "platform": "app" 
            }
        }
        headers = {
            "Content-Type": "application/json",
            "x-fireai-api-key": self.api_key
        }

        try:
            logger.info(f"Sending login request to: {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == 200 and "data" in data:
                logger.info(f"Login success for: {email}")
                return True, data["data"]
            else:
                error_msg = data.get("message", "Invalid email or password.")
                logger.warning(f"Login failed for {email}: {error_msg} (Status: {response.status_code})")
                return False, error_msg
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error during login: {e}")
            return False, "Could not connect to authentication server."
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}")
            return False, "An unexpected error occurred."

# Initialize auth service
auth_service = AuthService()

def log_to_audit(action_type, message=None):
    """Bridge to the audit logger in db.py"""
    try:
        from db import log_audit_action
        log_audit_action(action_type=action_type, error_message=message)
    except Exception as e:
        logger.error(f"Audit Log Failed: {e}")

# Helper functions
def _generate_session_token(username: str) -> str:
    timestamp = str(int(time.time()))
    data = f"{username}:{timestamp}:{COOKIE_SECRET}"
    return base64.b64encode(hashlib.sha256(data.encode()).digest()).decode()[:32]

def get_cookie_manager():
    if "cookie_manager_instance" not in st.session_state:
        logger.info("Initializing CookieManager component...")
        st.session_state.cookie_manager_instance = stx.CookieManager(key="cookie_manager")
    return st.session_state.cookie_manager_instance

def show_login_page():
    cookie_manager = get_cookie_manager()
    
    st.markdown("""
        <style>
        .stButton>button { width: 100%; border-radius: 6px; }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("Secure Login")
        st.markdown("Enter your credentials to access the Dashboard.")
        st.divider()

        with st.form("login_form"):
            username_or_email = st.text_input("Company Email", placeholder="Enter your email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login", type="primary")

            if submitted:
                st.info("Authenticating...")
                success, response_data = auth_service.login(username_or_email, password)
                
                if success:
                    log_to_audit("LOGIN")
                    token = _generate_session_token(username_or_email)
                    
                    user_data = response_data.get("user", {})
                    profile = {
                        "profile_image_url": user_data.get("profile_image_url"),
                        "first_name": user_data.get("first_name"),
                        "last_name": user_data.get("last_name"),
                        "id": user_data.get("id"),
                        "access_token": response_data.get("access_token"),
                        "refresh_token": response_data.get("refresh_token")
                    }
                    
                    # Store in session state
                    st.session_state.authenticated = True
                    st.session_state.username = username_or_email
                    st.session_state.user_email = username_or_email
                    st.session_state.session_token = token
                    st.session_state.auth_profile = profile
                    
                    # Set cookies (Session-Only Mode: these expire when the browser is closed)
                    cookie_manager.set("auth_token", token, key="set_at")
                    cookie_manager.set("auth_user", username_or_email, key="set_au")
                    cookie_manager.set("auth_profile", json.dumps(profile), key="set_ap")
                    
                    # Set the Sentinel Switch
                    cookie_manager.set("auth_session_active", "1", key="set_asa")

                    logger.info(f"User {username_or_email} logged in successfully.")
                    # Force a cache clear to ensure the first dashboard load is live and correct
                    st.cache_data.clear()
                    st.rerun()
                else:
                    logger.warning(f"Login failed for {username_or_email}: {response_data}")
                    st.error(f"🔒 {response_data}")

    st.stop()

def require_login():
    cookie_manager = get_cookie_manager()
    
    # 1. Handle Logout Trigger (Immediate server-side lockout)
    if st.session_state.get("logout_triggered"):
        logger.info("Logout triggered: Clearing session flags.")
        st.session_state.authenticated = False
        st.session_state.logout_triggered = False
        show_login_page()
        return False

    # 2. Check current session state (Fast path)
    if st.session_state.get("authenticated", False):
        return True

    # 3. Handle Async Cookie Loading (Surgical One-Shot)
    all_cookies = cookie_manager.get_all()
    
    # On refresh, all_cookies starts as {}. We wait once, silently.
    if not all_cookies:
        if "cookie_wait_count" not in st.session_state:
            st.session_state.cookie_wait_count = 0
            
        if st.session_state.cookie_wait_count < 1: # Reduced from 3 to 1 for speed
            st.session_state.cookie_wait_count += 1
            time.sleep(0.1) # Tiny delay for JS component to wake up
            st.rerun()

    # 4. Check for Sentinel Switch (The Master Switch)
    session_active = all_cookies.get("auth_session_active")
    
    if session_active != "1":
        # No session sentinel found. Show login page.
        show_login_page()
        return False
    
    # Special: On the very first SUCCESSFUL auth frame after a reload/login, 
    # we don't want to block. We proceed.
    is_authenticated = st.session_state.get("authenticated", False)

    if session_active != "1" and not is_authenticated:
        # We only show the login page if we have truly waited and NO session was found.
        show_login_page()
        return False

    # 5. Fallback to Cookies (Only because Sentinel is active)
    if not is_authenticated:
        saved_token = all_cookies.get("auth_token")
        saved_user = all_cookies.get("auth_user")
        
        if saved_token and saved_user:
            logger.info(f"Restoring session from cookies for user: {saved_user}")
            st.session_state.authenticated = True
            st.session_state.username = saved_user
            st.session_state.user_email = saved_user
            st.session_state.session_token = saved_token
            
            saved_profile = all_cookies.get("auth_profile")
            if saved_profile:
                try:
                    st.session_state.auth_profile = json.loads(saved_profile)
                except:
                    pass
            # Reset wait count
            st.session_state.cookie_wait_count = 0
            return True

    # Reset wait count if we are already authenticated
    if is_authenticated:
        st.session_state.cookie_wait_count = 0
        return True

    # 6. Completely unauthenticated
    show_login_page()
    return False

    # 5. Completely unauthenticated
    show_login_page()
    return False

def logout(cookie_manager=None):
    logger.info("Triggering secure logout with Sentinel purge...")
    log_to_audit("LOGOUT")
    
    # 1. Purge Sentinel IMMEDIATELY
    if cookie_manager:
        cookie_manager.delete("auth_session_active", key="purge_sentinel")
    
    # 2. Clear server flags
    st.session_state.authenticated = False
    st.session_state.logout_triggered = True
    
    # 3. Clear session sensitive data
    st.session_state.clear()
    st.session_state.logout_triggered = True # Re-set after clear
    
    # 4. Rerun to hit the top-level require_login guard
    st.rerun()

# Main logic
if __name__ == "__main__":
    require_login()