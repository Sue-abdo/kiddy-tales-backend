from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# ════════════════════════════════
#     User Table
# ════════════════════════════════
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)           # اسم الـ parent
    child_name = Column(String, nullable=True)      # اسم الطفل
    child_age = Column(Integer, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)  # email الـ parent
    child_email = Column(String, nullable=True)     # email الطفل
    hashed_password = Column(String, nullable=False)
    
#═══════════════════════════════
#     NEW: Words Table
# ════════════════════════════════
class Word(Base):
    __tablename__ = "words"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    sound = Column(String, nullable=True)


# ════════════════════════════════
#     NEW: Story Table
# ════════════════════════════════
class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    original_words = Column(String, nullable=False)   # اللي كتبه الطفل
    corrected_words = Column(String, nullable=False)  # بعد التصحيح
    was_corrected = Column(Boolean, default=False)
    story_text = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    parent_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    story_audio_url = Column(String, nullable=True)  # ← URL صوت القصة
    # relationship
    questions = relationship("StoryQuestion", back_populates="story")


# ════════════════════════════════
#     NEW: Questions Table
# ════════════════════════════════
class StoryQuestion(Base):
    __tablename__ = "story_questions"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    question = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)

    # relationship
    story = relationship("Story", back_populates="questions")
    child_answer = relationship("ChildAnswer", back_populates="question", uselist=False)


# ════════════════════════════════
#     NEW: Child Answers Table
# ════════════════════════════════
class ChildAnswer(Base):
    __tablename__ = "child_answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("story_questions.id"), nullable=False)
    child_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)
    score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relationship
    question = relationship("StoryQuestion", back_populates="child_answer")


# ════════════════════════════════
#     NEW: Story Result Table
# ════════════════════════════════
class StoryResult(Base):
    __tablename__ = "story_results"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    child_feedback = Column(Text, nullable=True)
    parent_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
