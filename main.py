from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
import bcrypt
import uvicorn
import models, schemas, database
import whisper
import tempfile
import os
import uuid
from dotenv import load_dotenv
from tts_service import text_to_speech
import Levenshtein

load_dotenv()

# ════════════════════════════════
#        CONFIG
# ════════════════════════════════
SECRET_KEY = os.getenv("SECRET_KEY", "your_super_secret_key_here")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# ════════════════════════════════
#        APP SETUP
# ════════════════════════════════
app = FastAPI(
    title="KidsApp API",
    description="AI-powered English learning app for kids aged 6-11",
    version="1.0.0"
)

# Static folder for audio files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create all DB tables automatically on startup
models.Base.metadata.create_all(bind=database.engine)

# Load Whisper once when server starts
print("Loading Whisper model...")
whisper_model = whisper.load_model("tiny")  # tiny = fastest, works on free hosting
print("Whisper ready!")


# ════════════════════════════════
#        AUTH HELPERS
# ════════════════════════════════
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def hash_password(password: str):
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


# ════════════════════════════════
#        AUTH ENDPOINTS
# ════════════════════════════════
@app.post("/signup", tags=["Auth"])
def signup(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Parent creates an account"""
    db_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        child_age=user.child_age,
        parent_email=user.parent_email
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully!"}


@app.post("/login", tags=["Auth"])
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    """Parent logs in and gets a token"""
    user = db.query(models.User).filter(
        models.User.email == user_credentials.email
    ).first()

    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid Credentials")

    access_token = create_access_token(
        data={"sub": user.email, "user_name": user.name}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_name": user.name
    }


@app.get("/profile", response_model=schemas.UserProfileResponse, tags=["Auth"])
def get_my_profile(token: str, db: Session = Depends(database.get_db)):
    """Get parent profile using token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token or session expired")


@app.patch("/profile/update", response_model=schemas.UserProfileResponse, tags=["Auth"])
def update_my_profile(
    token: str,
    user_data: schemas.UserUpdate,
    db: Session = Depends(database.get_db)
):
    """Update parent profile"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        db_user = db.query(models.User).filter(models.User.email == email).first()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if user_data.name:
            db_user.name = user_data.name
        if user_data.child_age is not None:
            db_user.child_age = user_data.child_age
        if user_data.parent_email:
            db_user.parent_email = user_data.parent_email
        if user_data.password:
            db_user.hashed_password = hash_password(user_data.password)

        db.commit()
        db.refresh(db_user)
        return db_user
    except:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


@app.post("/logout", tags=["Auth"])
def sign_out():
    """Parent logs out"""
    return {"status": "success", "message": "Successfully logged out"}


# ════════════════════════════════
#        WORDS ENDPOINTS
# ════════════════════════════════
@app.post("/words", response_model=schemas.WordResponse, tags=["Words"])
def add_word(word: schemas.WordCreate, db: Session = Depends(database.get_db)):
    """
    Add new word to DB
    Auto generates audio and saves URL in sound column
    """
    word_text = word.word.lower().strip()

    # 1. Generate audio file
    audio_filename = f"{word_text}.mp3"
    audio_path = f"static/{audio_filename}"
    text_to_speech(word_text, audio_path)

    # 2. Build the URL that will be saved in DB
    sound_url = f"{BASE_URL}/static/{audio_filename}"

    # 3. Save word + sound URL to DB
    new_word = models.Word(
        word=word_text,
        level=word.level,
        sound=sound_url
    )
    db.add(new_word)
    db.commit()
    db.refresh(new_word)
    return new_word


@app.get("/words", response_model=schemas.WordsListResponse, tags=["Words"])
def get_words_by_level(level: int, db: Session = Depends(database.get_db)):
    """
    Get all words for a level
    Each word includes its sound URL → Flutter plays it to the child
    """
    words = db.query(models.Word).filter(models.Word.level == level).all()
    if not words:
        raise HTTPException(status_code=404, detail="No words found for this level")
    return {"words": words}


@app.get("/words/{word_id}/audio", response_model=schemas.AudioResponse, tags=["Words"])
async def get_word_audio(word_id: int, db: Session = Depends(database.get_db)):
    """
    Step 1 of listening flow:
    Get word audio URL → Flutter plays it → child hears the word
    If audio not generated yet → generate it and save URL in DB
    """
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    # If audio URL already in DB → return it directly
    if word.sound:
        return {"word": word.word, "sound_url": word.sound}

    # If not → generate it now and save in DB
    audio_filename = f"{word.word}.mp3"
    audio_path = f"static/{audio_filename}"
    text_to_speech(word.word, audio_path)

    sound_url = f"{BASE_URL}/static/{audio_filename}"
    word.sound = sound_url
    db.commit()

    return {"word": word.word, "sound_url": sound_url}


@app.get("/words/{word_id}", response_model=schemas.WordResponse, tags=["Words"])
def get_word(word_id: int, db: Session = Depends(database.get_db)):
    """Get one word by ID"""
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return word


# ════════════════════════════════
#        AI HELPERS
# ════════════════════════════════


def compare_pronunciation(whisper_text: str, correct_word: str):
    """
    Compare what Whisper heard vs the correct word
    Uses Levenshtein Distance for smart scoring
    """
    whisper_clean = whisper_text.strip().lower()
    correct_clean = correct_word.strip().lower()

    # لو الكلمة جزء من كلام أطول — جيب الكلمة الأقرب
    whisper_words = whisper_clean.split()
    if len(whisper_words) > 1:
        # اختاري أقرب كلمة من اللي Whisper سمعه
        whisper_clean = min(
            whisper_words,
            key=lambda w: Levenshtein.distance(w, correct_clean)
        )

    # احسبي الـ similarity كـ percentage
    max_len = max(len(whisper_clean), len(correct_clean))
    if max_len == 0:
        similarity = 0
    else:
        distance = Levenshtein.distance(whisper_clean, correct_clean)
        similarity = round((1 - distance / max_len) * 100)

    # الـ scoring بناءً على الـ similarity
    if similarity == 100:
        return {
            "score": 100,
            "feedback": "Perfect! Well done! 🌟",
            "is_correct": True
        }
    elif similarity >= 80:
        return {
            "score": similarity,
            "feedback": f"Great job! Almost perfect! 👍",
            "is_correct": True  # 80%+ يعتبر صح
        }
    elif similarity >= 60:
        return {
            "score": similarity,
            "feedback": f"Good try! You said '{whisper_clean}', try again! 😊",
            "is_correct": False
        }
    elif similarity >= 40:
        return {
            "score": similarity,
            "feedback": f"Keep trying! The word is '{correct_clean}' 💪",
            "is_correct": False
        }
    else:
        return {
            "score": similarity,
            "feedback": f"Try again! Listen carefully and say '{correct_clean}' 🎯",
            "is_correct": False
        }

# ════════════════════════════════
#        AI ENDPOINTS
# ════════════════════════════════
@app.post("/evaluate", response_model=schemas.EvaluateResponse, tags=["AI"])
async def evaluate(
    word_id: int = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(database.get_db)
):
    """
    Send child audio + word_id → get score and feedback
    Input:  word_id (int) + audio (file)
    Output: score, feedback, is_correct, whisper_heard
    """
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail=f"Word '{word_id}' not found")

    suffix = os.path.splitext(audio.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = whisper_model.transcribe(tmp_path)
        whisper_text = result["text"]
        evaluation = compare_pronunciation(whisper_text, word.word)
        return {
            "word_id": word_id,
            "correct_word": word.word,
            "whisper_heard": whisper_text.strip(),
            **evaluation
        }
    finally:
        os.unlink(tmp_path)


@app.post("/practice/{word_id}", response_model=schemas.EvaluateResponse, tags=["AI"])
async def practice_word(
    word_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(database.get_db)
):
    """
    Full listening + speaking flow:
    Step 1: Flutter called GET /words/{id}/audio → child heard the word
    Step 2: Child recorded their voice
    Step 3: Send recording here → get score + feedback
    """
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    suffix = os.path.splitext(audio.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = whisper_model.transcribe(tmp_path)
        whisper_text = result["text"]
        evaluation = compare_pronunciation(whisper_text, word.word)
        return {
            "word_id": word_id,
            "correct_word": word.word,
            "whisper_heard": whisper_text.strip(),
            **evaluation
        }
    finally:
        os.unlink(tmp_path)


# ════════════════════════════════
#        RUN SERVER
# ════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(app, host="192.168.138.127", port=8000)
