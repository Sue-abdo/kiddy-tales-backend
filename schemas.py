from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime


# ════════════════════════════════
#        USER SCHEMAS
# ════════════════════════════════
class UserCreate(BaseModel):
    name: str
    child_name: str
    email: EmailStr                    # ← validation أوتوماتيك
    child_email: EmailStr              # ← validation أوتوماتيك
    password: str
    child_age: int

    @field_validator('child_age')
    @classmethod
    def validate_age(cls, v):
        if v < 6 or v > 11:
            raise ValueError('Child age must be between 6 and 11')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileResponse(BaseModel):
    id: int
    name: str
    child_name: Optional[str] = None
    email: str
    child_email: Optional[str] = None
    child_age: int   

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
    sound: Optional[str] = None

    class Config:
        from_attributes = True


class WordsListResponse(BaseModel):
    words: List[WordResponse]


# ════════════════════════════════
#        AI — Evaluate SCHEMAS
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

class PronunciationResultResponse(BaseModel):
    id: int
    word_id: int
    whisper_heard: str
    score: int
    is_correct: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ProgressResponse(BaseModel):
    child_name: str
    total_attempts: int
    correct_attempts: int
    success_rate: float
    results: List[PronunciationResultResponse]


# ════════════════════════════════
#   STORY SCHEMAS — الترتيب مهم!
# ════════════════════════════════

# 1 — لازم يكون الأول
class CorrectionItem(BaseModel):
    wrong: str
    right: str


# 2
class StoryQuestionResponse(BaseModel):
    id: int
    question: str
    correct_answer: str

    class Config:
        from_attributes = True


# 3 — بعد CorrectionItem و StoryQuestionResponse
class StoryResponse(BaseModel):
    id: int
    original_words: str
    corrected_words: str
    was_corrected: bool
    corrections: List[CorrectionItem]
    story: str
    story_audio_url: str    # ← الطفل يضغط يسمع القصة
    image_url: str
    questions: List[StoryQuestionResponse]
    parent_feedback: str
    created_at: datetime

    class Config:
        from_attributes = True


# ════════════════════════════════
#   ANSWERS SCHEMAS
# ════════════════════════════════
class QuestionAnswer(BaseModel):
    question_id: int
    child_answer: str


class AnswersRequest(BaseModel):
    story_id: int
    token: str          # ← بدل user_id
    answers: List[QuestionAnswer]

class AnswerResult(BaseModel):
    question_id: int
    question: str
    child_answer: str
    correct_answer: str
    is_correct: bool
    feedback: str


class AnswersEvaluationResponse(BaseModel):
    story_id: int
    total_questions: int
    correct_answers: int
    score: int
    child_feedback: str
    parent_feedback: str
    results: List[AnswerResult]
    
