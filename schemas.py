from pydantic import BaseModel, EmailStr
from typing import Optional, List


# ════════════════════════════════
#        USER SCHEMAS
# ════════════════════════════════

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    child_age: int
    parent_email: Optional[EmailStr] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileResponse(BaseModel):
    name: str
    email: str
    child_age: int
    parent_email: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    child_age: Optional[int] = None
    parent_email: Optional[str] = None
    password: Optional[str] = None


# ════════════════════════════════
#        WORD SCHEMAS
# ════════════════════════════════

class WordCreate(BaseModel):
    word: str
    level: int


class WordResponse(BaseModel):
    id: int
    word: str
    level: int
    sound: Optional[str] = None  # URL بتاع الـ audio

    class Config:
        from_attributes = True


class WordsListResponse(BaseModel):
    words: List[WordResponse]


# ════════════════════════════════
#        AI SCHEMAS
# ════════════════════════════════

class AudioResponse(BaseModel):
    word: str
    sound_url: str


class EvaluateResponse(BaseModel):
    word_id: int
    correct_word: str
    whisper_heard: str
    score: int
    feedback: str
    is_correct: bool
