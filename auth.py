"""Authentication wrapper using streamlit-authenticator."""

from pathlib import Path

import bcrypt
import streamlit as st
import yaml
import streamlit_authenticator as stauth


CONFIG_PATH = Path(__file__).parent / "config" / "users.yaml"

# Admin credentials — injected into authenticator config at runtime
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
_ADMIN_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    # Inject admin user into credentials so authenticator handles it natively
    config["credentials"]["usernames"][ADMIN_USERNAME] = {
        "name": "Administratör",
        "password": _ADMIN_HASH,
        "email": "",
        "role": "admin",
    }
    return config


def _get_authenticator() -> stauth.Authenticate:
    """Return a single cached Authenticate instance per session."""
    if "_authenticator" not in st.session_state:
        config = _load_config()
        st.session_state["_authenticator"] = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
        )
    return st.session_state["_authenticator"]


def check_auth() -> bool:
    """Show login form and return True if authenticated.

    Must be called at top of app.py — halts rendering if not logged in.
    Admin credentials are injected into the authenticator at runtime.
    """
    authenticator = _get_authenticator()
    authenticator.login(location="main")

    if st.session_state.get("authentication_status"):
        return True
    elif st.session_state.get("authentication_status") is False:
        st.error("Felaktigt användarnamn eller lösenord.")
        return False
    else:
        st.info("Logga in för att fortsätta.")
        return False


def get_current_user() -> dict | None:
    """Return current user info or None if not authenticated.

    Returns dict with keys: username, name, role, email.
    """
    if not st.session_state.get("authentication_status"):
        return None

    username = st.session_state.get("username")
    if not username:
        return None

    config = _load_config()
    user_data = config["credentials"]["usernames"].get(username, {})

    return {
        "username": username,
        "name": user_data.get("name", username),
        "role": user_data.get("role", "kam"),
        "email": user_data.get("email", ""),
    }


def require_role(role: str) -> bool:
    """Check if current user has the required role."""
    user = get_current_user()
    if not user:
        return False
    return user["role"] == role


def render_sidebar_user():
    """Render user info + logout button in sidebar."""
    user = get_current_user()
    if not user:
        return

    role_labels = {"saljchef": "Säljchef", "kam": "KAM", "admin": "Admin"}
    role_label = role_labels.get(user["role"], user["role"])

    st.sidebar.markdown(
        f'<div style="padding:12px 16px;background:var(--bg-2);border:1px solid var(--border);'
        f'border-radius:var(--r-sm);margin:0 0 12px">'
        f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{user["name"]}</div>'
        f'<div style="font-size:11px;color:var(--text-2);margin-top:2px">{role_label}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    authenticator = _get_authenticator()
    authenticator.logout("Logga ut", location="sidebar")
