# backend/auth_handler.py
from user_models import add_user, verify_user

def handle_signup(username: str, password: str):
    if add_user(username, password):
        return {"message": "✅ Signup successful."}
    else:
        return {"error": "🚫 Username already exists."}

def handle_login(username: str, password: str):
    if verify_user(username, password):
        return {"message": "✅ Login successful."}
    else:
        return {"error": "🚫 Invalid credentials."}
