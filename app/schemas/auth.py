"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Schema for user creation."""

    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Schema for registration - creates tenant + owner."""

    email: EmailStr
    password: str
    tenant_name: str


class Token(BaseModel):
    """JWT response schema."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT payload schema."""

    sub: str
    tenant_id: str
    role: str
