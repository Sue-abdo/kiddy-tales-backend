from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
from email_service import generate_verification_code, send_verification_email
import bcrypt
import uvicorn
import models, schemas, database

# ════════════════════════════════
#        WORD & AUDIO SERVICES
# ════════════════════════════════
import whisper
import tempfile
import os
import uuid
from dotenv import load_dotenv
from tts_service import text_to_speech
import Levenshtein
load_dotenv()

# ════════════════════════════════
#        Story & Image Services
# ════════════════════════════════
from story_service import generate_story_and_questions, correct_words
from image_service import generate_image
from fastapi.responses import FileResponse
from typing import List, Optional

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
    title="Kiddy Tales API",
    description="AI-powered English learning app for kids aged 6-11",
    version="1.0.0"
)
@app.get("/", tags=["Root"])
def root():
    return {
        "app": "Kiddy Tales",
        "status": "running",
        "docs": "/docs",
        "version": "1.0.0"
    }
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
    # 1. تأكدي إن الـ child_email مش موجود
    existing_child = db.query(models.User).filter(
        models.User.child_email == user.child_email
    ).first()
    if existing_child:
        raise HTTPException(
            status_code=400,
            detail="This child email is already registered"
        )

    # 2. عملي verification code
    code = generate_verification_code()

    # 3. حفظي الـ user مع الكود
    new_user = models.User(
        name=user.name,
        child_name=user.child_name,
        email=user.email,
        child_email=user.child_email,
        hashed_password=hash_password(user.password),
        child_age=user.child_age,
        is_verified=False,
        verification_code=code
    )
    db.add(new_user)
    db.commit()

    # 4. ابعتي الكود على الـ email
    sent = send_verification_email(user.email, code, user.child_name)

    if sent:
        return {
            "message": f"Verification code sent to {user.email}. Please verify your email.",
            "email": user.email
        }
    else:
        return {
            "message": "Account created but email could not be sent. Contact support.",
            "email": user.email
        }

@app.post("/verify-email", tags=["Auth"])
def verify_email(email: str, code: str, db: Session = Depends(database.get_db)):
    """Parent enters the 6-digit code they received"""
    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.verification_code == code
    ).first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid email or verification code"
        )

    if user.is_verified:
        return {"message": "Email already verified!"}

    # تأكيد الـ email
    user.is_verified = True
    user.verification_code = None
    db.commit()

    return {"message": "Email verified successfully! You can now login. ✅"}

@app.post("/login", tags=["Auth"])
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    # ابحثي بـ child_email بدل email
    user = db.query(models.User).filter(
        models.User.child_email == user_credentials.email
    ).first()

    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid Credentials")

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email first. Check your inbox."
        )

    access_token = create_access_token(
        data={"sub": user.child_email, "user_name": user.child_name}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "child_name": user.child_name
    }


@app.post("/resend-code", tags=["Auth"])
def resend_code(email: str, db: Session = Depends(database.get_db)):
    """Resend verification code"""
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    if user.is_verified:
        return {"message": "Email already verified!"}

    # عملي كود جديد
    new_code = generate_verification_code()
    user.verification_code = new_code
    db.commit()

    send_verification_email(email, new_code, user.child_name)
    return {"message": f"New verification code sent to {email}"}


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

def get_current_user(token: str, db: Session) -> models.User:
    """Get user from token automatically"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
# ═══════════════════════════════
#     AUTH HELPERS
# ════════════════════════════════

def get_current_user(token: str, db: Session) -> models.User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        child_email: str = payload.get("sub")
        user = db.query(models.User).filter(
            models.User.child_email == child_email
        ).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


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
#         AI EVALUATION ENDPOINTS
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
#        Audio ENDPOINTS
# ════════════════════════════════
@app.post("/evaluate", response_model=schemas.EvaluateResponse, tags=["AI"])
async def evaluate(
    word_id: int = Form(...),
    audio: UploadFile = File(...),
    token: str = Form(...),          # ← أضيفي token
    db: Session = Depends(database.get_db)
):
    # جيبي الـ user من الـ token
    user = get_current_user(token, db)

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

        # حفظ النتيجة مربوطة بالطفل
        pronunciation_result = models.PronunciationResult(
            user_id=user.id,
            word_id=word_id,
            whisper_heard=whisper_text.strip(),
            score=evaluation["score"],
            is_correct=evaluation["is_correct"]
        )
        db.add(pronunciation_result)
        db.commit()

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
    token: str = Form(...),          # ← أضيفي token
    db: Session = Depends(database.get_db)
):
    # جيبي الـ user من الـ token
    user = get_current_user(token, db)

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

        # حفظ النتيجة مربوطة بالطفل
        pronunciation_result = models.PronunciationResult(
            user_id=user.id,
            word_id=word_id,
            whisper_heard=whisper_text.strip(),
            score=evaluation["score"],
            is_correct=evaluation["is_correct"]
        )
        db.add(pronunciation_result)
        db.commit()

        return {
            "word_id": word_id,
            "correct_word": word.word,
            "whisper_heard": whisper_text.strip(),
            **evaluation
        }
    finally:
        os.unlink(tmp_path)
# ════════════════════════════════
#     STORY + IMAGE ENDPOINT
# ════════════════════════════════

@app.post("/generate-story", response_model=schemas.StoryResponse, tags=["AI"])
async def generate_story(
    words: str = Form(...),
    token: str = Form(...),        # ← token بدل user_id
    db: Session = Depends(database.get_db)
):
    # 1. جيبي الـ user من الـ token أوتوماتيك
    user = get_current_user(token, db)

    try:
        # 2. تصحيح الإملاء
        correction = correct_words(words)
        corrected = correction["corrected"]
        was_corrected = correction["was_corrected"]
        corrections = correction.get("corrections", [])

        # 3. توليد القصة
        result = generate_story_and_questions(corrected)

        # 4. توليد الصورة
        safe_name = corrected.replace(" ", "_")[:20]
        image_filename = f"story_{safe_name}_{uuid.uuid4().hex[:8]}.png"
        image_path = f"static/{image_filename}"

        try:
            generate_image(result["image_prompt"], image_path)
            image_url = f"{BASE_URL}/static/{image_filename}"
        except Exception:
            image_url = f"{BASE_URL}/static/default.png"

        # 5. توليد audio للقصة عشان الطفل يسمعها
        story_audio_filename = f"story_audio_{uuid.uuid4().hex[:8]}.mp3"
        story_audio_path = f"static/{story_audio_filename}"
        text_to_speech(result["story"], story_audio_path)
        story_audio_url = f"{BASE_URL}/static/{story_audio_filename}"

        # 6. feedback للـ parent
        child_name = user.child_name or "Your child"
        if was_corrected and corrections:
            mistakes = ", ".join(
                [f"'{c['wrong']}' → '{c['right']}'" for c in corrections]
            )
            parent_feedback = (
                f"{child_name} wrote '{words}' with spelling mistakes. "
                f"The system corrected: {mistakes}. "
                f"Consider practicing these words together."
            )
        else:
            parent_feedback = (
                f"Great! {child_name} wrote '{words}' correctly "
                f"with no spelling mistakes!"
            )

        # 7. حفظ في الـ DB
        new_story = models.Story(
            user_id=user.id,
            original_words=words,
            corrected_words=corrected,
            was_corrected=was_corrected,
            story_text=result["story"],
            image_url=image_url,
            story_audio_url=story_audio_url,
            parent_feedback=parent_feedback
        )
        db.add(new_story)
        db.flush()

        # 8. حفظ الأسئلة
        saved_questions = []
        for q in result["questions"]:
            new_q = models.StoryQuestion(
                story_id=new_story.id,
                question=q["question"],
                correct_answer=q["answer"]
            )
            db.add(new_q)
            db.flush()
            saved_questions.append(new_q)

        db.commit()
        db.refresh(new_story)

        return {
            "id": new_story.id,
            "original_words": words,
            "corrected_words": corrected,
            "was_corrected": was_corrected,
            "corrections": corrections,
            "story": result["story"],
            "story_audio_url": story_audio_url,
            "image_url": image_url,
            "questions": saved_questions,
            "parent_feedback": parent_feedback,
            "created_at": new_story.created_at
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate-answers", response_model=schemas.AnswersEvaluationResponse, tags=["AI"])
async def evaluate_answers(
    request: schemas.AnswersRequest,
    db: Session = Depends(database.get_db)
):
    # جيبي الـ user من الـ token
    user = get_current_user(request.token, db)

    story = db.query(models.Story).filter(
        models.Story.id == request.story_id
    ).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    results = []
    correct_count = 0
    total = len(request.answers)

    for item in request.answers:
        question = db.query(models.StoryQuestion).filter(
            models.StoryQuestion.id == item.question_id
        ).first()
        if not question:
            continue

        child_clean = item.child_answer.strip().lower()
        correct_clean = question.correct_answer.strip().lower()

        max_len = max(len(child_clean), len(correct_clean))
        if max_len == 0:
            similarity = 100
        else:
            distance = Levenshtein.distance(child_clean, correct_clean)
            similarity = round((1 - distance / max_len) * 100)

        is_correct = similarity >= 60

        if is_correct:
            correct_count += 1
            feedback = "Great answer! Well done! 🌟"
        elif similarity >= 40:
            feedback = f"Almost! The answer is '{question.correct_answer}' 😊"
        else:
            feedback = f"The correct answer is '{question.correct_answer}' 💪"

        child_answer = models.ChildAnswer(
            question_id=item.question_id,
            child_answer=item.child_answer,
            is_correct=is_correct,
            score=similarity
        )
        db.add(child_answer)

        results.append({
            "question_id": item.question_id,
            "question": question.question,
            "child_answer": item.child_answer,
            "correct_answer": question.correct_answer,
            "is_correct": is_correct,
            "feedback": feedback
        })

    score = round((correct_count / total) * 100) if total > 0 else 0
    child_name = user.child_name or "Your child"

    if score == 100:
        child_feedback = "Amazing! You answered everything correctly! 🏆⭐"
        parent_feedback = (
            f"Excellent! {child_name} answered all {total} questions correctly. "
            f"Score: {score}/100!"
        )
    elif score >= 60:
        child_feedback = f"Good job! You got {correct_count} out of {total} correct! 👍"
        parent_feedback = (
            f"Good progress! {child_name} answered {correct_count}/{total} correctly. "
            f"Score: {score}/100. Review the incorrect answers together."
        )
    else:
        child_feedback = f"Keep practicing! You got {correct_count} out of {total}. You can do it! 💪"
        parent_feedback = (
            f"{child_name} needs more practice. Score: {score}/100. "
            f"We recommend re-reading the story and trying again."
        )

    story_result = models.StoryResult(
        story_id=request.story_id,
        user_id=user.id,
        total_questions=total,
        correct_answers=correct_count,
        score=score,
        child_feedback=child_feedback,
        parent_feedback=parent_feedback
    )
    db.add(story_result)
    db.commit()

    return {
        "story_id": request.story_id,
        "total_questions": total,
        "correct_answers": correct_count,
        "score": score,
        "child_feedback": child_feedback,
        "parent_feedback": parent_feedback,
        "results": results
    }

@app.get("/progress", response_model=schemas.ProgressResponse, tags=["AI"])
def get_progress(token: str, db: Session = Depends(database.get_db)):
    """Get child's pronunciation progress"""
    user = get_current_user(token, db)

    results = db.query(models.PronunciationResult).filter(
        models.PronunciationResult.user_id == user.id
    ).all()

    total = len(results)
    correct = sum(1 for r in results if r.is_correct)
    rate = round((correct / total) * 100, 1) if total > 0 else 0

    return {
        "child_name": user.child_name,
        "total_attempts": total,
        "correct_attempts": correct,
        "success_rate": rate,
        "results": results
    }
    
    

# ════════════════════════════════
#        RUN SERVER
# ════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(app, host="192.168.138.127", port=8000)

