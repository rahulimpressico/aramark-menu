from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {"message": "Menu Analysis API", "status": "ok"}


@router.get("/health")
async def health():
    return {"status": "healthy"}
