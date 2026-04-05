from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.admin import AdminCreate, AdminResponse, Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def register(admin_in: AdminCreate, db: AsyncSession = Depends(get_db)):
    return await AuthService.register_admin(db, admin_in)

@router.post("/login", response_model=Token)
async def login(db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    token = await AuthService.authenticate(db, form_data.username, form_data.password)
    return {"access_token": token, "token_type": "bearer"}