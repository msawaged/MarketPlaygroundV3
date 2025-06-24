# backend/user_models.py
from tinydb import TinyDB, Query
import os

# Ensure data directory exists
os.makedirs("backend/data", exist_ok=True)

# Initialize database
db = TinyDB("backend/data/users.json")
User = Query()

def init_db():
    if db is None:
        raise RuntimeError("DB failed to initialize")

def add_user(username: str, password: str):
    if db.search(User.username == username):
        return False  # User already exists
    db.insert({"username": username, "password": password})
    return True

def verify_user(username: str, password: str):
    return db.contains((User.username == username) & (User.password == password))
