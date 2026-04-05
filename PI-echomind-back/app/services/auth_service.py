from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.admin import Admin
from app.schemas.admin import AdminCreate
from app.core.security import get_password_hash, verify_password, create_access_token

class AuthService:
    @staticmethod
    async def register_admin(db: AsyncSession, admin_in: AdminCreate):
        hashed_pw = get_password_hash(admin_in.password)
        new_admin = Admin(username=admin_in.username, hashed_password=hashed_pw)
        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)
        return new_admin

    @staticmethod
    async def authenticate(db: AsyncSession, username: str, password: str):
        stmt = select(Admin).where(Admin.username == username)
        result = await db.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if not admin or not verify_password(password, admin.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        return create_access_token(admin.id)
    