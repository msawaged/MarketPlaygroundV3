# backend/routes/auth_router.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/auth_test")
def test_auth():
    return {"message": "✅ Auth router is live."}
