from sqlalchemy import Column, Integer, String
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    child_age = Column(Integer, nullable=False)
    parent_email = Column(String, nullable=True)


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    sound = Column(String, nullable=True)  # URL بتاع الـ audio محفوظ هنا
