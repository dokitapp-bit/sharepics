from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class EventCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    date: str
    location: Optional[str] = ""
    organizer_id: str


class EventResponse(BaseModel):
    id: str
    name: str
    description: str
    date: str
    location: str
    organizer_id: str
    qr_code_url: Optional[str] = None
    lead_count: int = 0
    photo_count: int = 0
    created_at: str


class LeadCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    event_id: str


class LeadResponse(BaseModel):
    id: str
    lead_number: int
    name: str
    phone: str
    email: str
    event_id: str
    qr_code_url: Optional[str] = None
    photo_count: int = 0
    gallery_url: Optional[str] = None
    created_at: str


class PhotoResponse(BaseModel):
    id: str
    filename: str
    original_url: str
    preview_url: str
    thumbnail_url: str
    event_id: str
    lead_id: Optional[str] = None
    lead_number: Optional[int] = None
    uploaded_at: str


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "photographer"


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    name: str
    role: str


class WhatsAppMessage(BaseModel):
    lead_id: str
    gallery_url: str
