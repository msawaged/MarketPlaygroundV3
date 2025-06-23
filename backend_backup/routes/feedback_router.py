from fastapi import APIRouter

router = APIRouter()

@router.get("/feedback_test")
def test_feedback():
    return {"message": "✅ Feedback router connected."}
