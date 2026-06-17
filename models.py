from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# == Models for the application ==
#== User model to store parent and child information ===
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    child_name = Column(String, nullable=False)
    child_age = Column(Integer, nullable=False)
    email = Column(String, nullable=False)         # ← مش unique عشان parent ممكن يسجل أكتر من طفل
    child_email = Column(String, unique=True, nullable=False)  # ← unique
    hashed_password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)   # ← اتأكد من الـ email ولا لسه
    verification_code = Column(String, nullable=True)  # ← الكود المؤقت


#== Word model to store words for different levels ==
class Word(Base):
    __tablename__ = "words"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    sound = Column(String, nullable=True)

class PronunciationResult(Base):
    __tablename__ = "pronunciation_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    whisper_heard = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    is_correct = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
#== Story model to store stories created by parents and answered by children ==
class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    original_words = Column(String, nullable=False)
    corrected_words = Column(String, nullable=False)
    was_corrected = Column(Boolean, default=False)
    story_text = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    story_audio_url = Column(String, nullable=True)
    parent_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    questions = relationship("StoryQuestion", back_populates="story")

#== StoryQuestion model to store questions related to each story ==
class StoryQuestion(Base):
    __tablename__ = "story_questions"
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    question = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)
    story = relationship("Story", back_populates="questions")
    child_answer = relationship("ChildAnswer", back_populates="question", uselist=False)

#== ChildAnswer model to store answers provided by children for each question ==
class ChildAnswer(Base):
    __tablename__ = "child_answers"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("story_questions.id"), nullable=False)
    child_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)
    score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    question = relationship("StoryQuestion", back_populates="child_answer")

#== StoryResult model to store the results of each story attempt by children ==
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

# == Reading Passage model to store reading texts for children ==
class ReadingPassage(Base):
    __tablename__ = "reading_passages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    level = Column(Integer, nullable=False)
    audio_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("ReadingResult", back_populates="passage")


# == ReadingResult model to store each child's reading attempt ==
class ReadingResult(Base):
    __tablename__ = "reading_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    passage_id = Column(Integer, ForeignKey("reading_passages.id"), nullable=False)
    whisper_transcript = Column(Text, nullable=False)
    score = Column(Integer, nullable=False)
    missed_words = Column(String, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    passage = relationship("ReadingPassage", back_populates="results")

# == ReadingQuestion model for multiple choice questions ==
class ReadingQuestion(Base):
    __tablename__ = "reading_questions"

    id = Column(Integer, primary_key=True, index=True)
    passage_id = Column(Integer, ForeignKey("reading_passages.id"), nullable=False)
    question_text = Column(String, nullable=False)
    option_1 = Column(String, nullable=False)
    option_2 = Column(String, nullable=False)
    option_3 = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)  # "Option_1", "Option_2", or "Option_3"
    created_at = Column(DateTime, default=datetime.utcnow)

    passage = relationship("ReadingPassage", back_populates="questions")
