# backend/routes/auth_routes.py

from fastapi import APIRouter
from backend.schemas import UserAuth
from backend.auth_handler import handle_signup, handle_login

router = APIRouter()

@router.post("/signup")
def signup(user: UserAuth):
    return handle_signup(user.username, user.password)

@router.post("/login")
def login(user: UserAuth):
    return handle_login(user.username, user.password)
