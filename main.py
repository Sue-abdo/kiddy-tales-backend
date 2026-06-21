from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
import bcrypt
import uvicorn
import models, schemas, database
from reading_service import evaluate_reading

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
from story_service import correct_words
from image_service import generate_image
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
    # 1. تأكدي إن الـ child_email مش موجود
    existing_child = db.query(models.User).filter(
        models.User.child_email == user.child_email
    ).first()
    if existing_child:
        raise HTTPException(
            status_code=400,
            detail="This child email is already registered"
        )

    # 3. حفظي الـ user مع الكود
    new_user = models.User(
        child_name=user.child_name,
        email=user.email,
        child_email=user.child_email,
        hashed_password=hash_password(user.password),
        child_age=user.child_age,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Account created successfully",
        "child_email": new_user.child_email,
        "child_name": new_user.child_name
    }

@app.post("/login", tags=["Auth"])
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    # ابحثي بـ child_email بدل email
    user = db.query(models.User).filter(
        models.User.child_email == user_credentials.email
    ).first()

    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid Credentials")

    access_token = create_access_token(
        data={"sub": user.child_email, "user_name": user.child_name}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "child_name": user.child_name
    }



@app.get("/profile", response_model=schemas.UserProfileResponse, tags=["Auth"])
def get_my_profile(token: str, db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        child_email: str = payload.get("sub")
        user = db.query(models.User).filter(models.User.child_email == child_email).first()
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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        child_email: str = payload.get("sub")
        db_user = db.query(models.User).filter(models.User.child_email == child_email).first()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if user_data.child_age is not None:
            db_user.child_age = user_data.child_age
        if user_data.parent_email:
            db_user.email = user_data.parent_email
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
async def generate_story_endpoint(
    words: str = Form(...),
    token: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = get_current_user(token, db)

    try:
        correction = correct_words(words)
        corrected = correction["corrected"]
        was_corrected = correction["was_corrected"]
        corrections = correction.get("corrections", [])

        result = generate_story(corrected)

        safe_name = corrected.replace(" ", "_")[:20]
        image_filename = f"story_{safe_name}_{uuid.uuid4().hex[:8]}.png"
        image_path = f"static/{image_filename}"

        try:
            generate_image(result["image_prompt"], image_path)
            image_url = f"{BASE_URL}/static/{image_filename}"
        except Exception:
            image_url = f"{BASE_URL}/static/default.png"

        story_audio_filename = f"story_audio_{uuid.uuid4().hex[:8]}.mp3"
        story_audio_path = f"static/{story_audio_filename}"
        text_to_speech(result["story"], story_audio_path)
        story_audio_url = f"{BASE_URL}/static/{story_audio_filename}"

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
            "parent_feedback": parent_feedback,
            "created_at": new_story.created_at
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/story/evaluate/{story_id}", response_model=schemas.StoryReadingEvaluateResponse, tags=["AI"])
async def evaluate_story_reading(
    story_id: int,
    audio: UploadFile = File(...),
    token: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = get_current_user(token, db)

    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    temp_path = f"temp_story_{user.id}_{story_id}.wav"
    with open(temp_path, "wb") as f:
        f.write(await audio.read())

    whisper_result = whisper_model.transcribe(temp_path)  # ⚠️ غيّر "whisper_model" لاسم المتغير الفعلي عندك
    transcript = whisper_result["text"]
    os.remove(temp_path)

    evaluation = evaluate_reading(story.story_text, transcript)

    story_result = models.StoryResult(
        story_id=story_id,
        user_id=user.id,
        whisper_transcript=transcript,
        score=evaluation["score"],
        total_words=evaluation["total_words"],
        correct_words=evaluation["correct_words"],
        missed_words=", ".join(evaluation["missed_words"]),
        feedback=evaluation["feedback"],
        is_passed=evaluation["is_passed"]
    )
    db.add(story_result)
    db.commit()

    return {
        "story_id": story_id,
        "score": evaluation["score"],
        "total_words": evaluation["total_words"],
        "correct_words": evaluation["correct_words"],
        "missed_words": evaluation["missed_words"],
        "feedback": evaluation["feedback"],
        "is_passed": evaluation["is_passed"],
        "whisper_transcript": transcript
    }
# ════════════════════════════════
#        READING ENDPOINTS
# ════════════════════════════════

@app.post("/passages", response_model=schemas.PassageResponse, tags=["Reading"])
def add_passage(
    passage: schemas.PassageCreate,
    db: Session = Depends(database.get_db)
):
    """
    Add a new reading passage.
    Automatically generates TTS audio so the child can listen first.
    """
    # 1. Generate audio for the passage (reusing existing tts_service)
    safe_title = passage.title.replace(" ", "_")[:20]
    audio_filename = f"passage_{safe_title}_{uuid.uuid4().hex[:8]}.mp3"
    audio_path = f"static/{audio_filename}"
    text_to_speech(passage.content, audio_path)
    audio_url = f"{BASE_URL}/static/{audio_filename}"

    # 2. Save passage to DB
    new_passage = models.ReadingPassage(
        title=passage.title,
        content=passage.content,
        level=passage.level,
        audio_url=audio_url
    )
    db.add(new_passage)
    db.commit()
    db.refresh(new_passage)
    return new_passage


@app.get("/passages", response_model=schemas.PassagesListResponse, tags=["Reading"])
def get_passages_by_level(
    level: int,
    db: Session = Depends(database.get_db)
):
    """
    Get all reading passages for a specific level (1, 2, or 3).
    Flutter displays the passage text and audio to the child.
    """
    passages = db.query(models.ReadingPassage).filter(
        models.ReadingPassage.level == level
    ).all()

    if not passages:
        raise HTTPException(
            status_code=404,
            detail="No passages found for this level"
        )
    return {"passages": passages}


@app.get("/passages/{passage_id}", response_model=schemas.PassageResponse, tags=["Reading"])
def get_passage(
    passage_id: int,
    db: Session = Depends(database.get_db)
):
    """
    Get a single reading passage by ID.
    """
    passage = db.query(models.ReadingPassage).filter(
        models.ReadingPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")
    return passage


@app.post("/reading/evaluate", response_model=schemas.ReadingEvaluateResponse, tags=["Reading"])
async def evaluate_reading_attempt(
    passage_id: int = Form(...),
    audio: UploadFile = File(...),
    token: str = Form(...),
    db: Session = Depends(database.get_db)
):
    """
    Child records themselves reading the passage.
    Whisper transcribes the audio → word-by-word evaluation →
    score + missed words + feedback saved and returned.
    """
    # 1. Get user from token
    user = get_current_user(token, db)

    # 2. Get passage from DB
    passage = db.query(models.ReadingPassage).filter(
        models.ReadingPassage.id == passage_id
    ).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    # 3. Save audio to temp file and transcribe with Whisper
    suffix = os.path.splitext(audio.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = whisper_model.transcribe(tmp_path)
        whisper_transcript = result["text"]

        # 4. Evaluate using our reading_service
        evaluation = evaluate_reading(passage.content, whisper_transcript)

        # 5. Save result to DB
        reading_result = models.ReadingResult(
            user_id=user.id,
            passage_id=passage_id,
            whisper_transcript=whisper_transcript.strip(),
            score=evaluation["score"],
            missed_words=", ".join(evaluation["missed_words"]),
            feedback=evaluation["feedback"]
        )
        db.add(reading_result)
        db.commit()

        return {
            "passage_id": passage_id,
            "whisper_transcript": whisper_transcript.strip(),
            **evaluation
        }

    finally:
        os.unlink(tmp_path)


@app.get("/reading/progress", response_model=schemas.ReadingProgressResponse, tags=["Reading"])
def get_reading_progress(
    token: str,
    db: Session = Depends(database.get_db)
):
    """
    Get the child's full reading history:
    total attempts, average score, and all results.
    """
    user = get_current_user(token, db)

    results = db.query(models.ReadingResult).filter(
        models.ReadingResult.user_id == user.id
    ).all()

    total = len(results)
    avg_score = round(
        sum(r.score for r in results) / total, 1
    ) if total > 0 else 0.0

    return {
        "child_name": user.child_name,
        "total_attempts": total,
        "average_score": avg_score,
        "results": results
    }

# ════════════════════════════════
#        READING QUESTIONS ENDPOINTS
# ════════════════════════════════

@app.get("/passages/{passage_id}/questions",
         response_model=schemas.ReadingQuestionsListResponse,
         tags=["Reading"])
def get_passage_questions(
    passage_id: int,
    db: Session = Depends(database.get_db)
):
    """
    Get the 3 multiple choice questions for a specific passage.
    Flutter shows these questions after the child finishes reading.
    Correct answer is NOT included in response — only shown after submission.
    """
    passage = db.query(models.ReadingPassage).filter(
        models.ReadingPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    questions = db.query(models.ReadingQuestion).filter(
        models.ReadingQuestion.passage_id == passage_id
    ).all()

    if not questions:
        raise HTTPException(
            status_code=404,
            detail="No questions found for this passage"
        )

    return {
        "passage_id": passage_id,
        "questions": questions
    }


@app.post("/reading/submit-answers",
          response_model=schemas.SubmitReadingAnswersResponse,
          tags=["Reading"])
def submit_reading_answers(
    request: schemas.SubmitReadingAnswersRequest,
    db: Session = Depends(database.get_db)
):
    """
    Child submits their multiple choice answers.
    System checks each answer, calculates score,
    generates feedback for child and parent,
    saves result to database.
    """
    # 1. Get user from token
    user = get_current_user(request.token, db)

    # 2. Verify passage exists
    passage = db.query(models.ReadingPassage).filter(
        models.ReadingPassage.id == request.passage_id
    ).first()
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    # 3. Evaluate each answer
    results = []
    correct_count = 0
    total = len(request.answers)

    for item in request.answers:
        question = db.query(models.ReadingQuestion).filter(
            models.ReadingQuestion.id == item.question_id
        ).first()
        if not question:
            continue

        is_correct = item.selected_option == question.correct_answer

        if is_correct:
            correct_count += 1
            feedback = "Correct! Well done! 🌟"
        else:
            # Get the correct option text to show in feedback
            correct_text = getattr(
                question,
                question.correct_answer.lower()
            )
            feedback = f"The correct answer is: '{correct_text}' 💪"

        results.append({
            "question_id": item.question_id,
            "question_text": question.question_text,
            "selected_option": item.selected_option,
            "correct_answer": question.correct_answer,
            "is_correct": is_correct,
            "feedback": feedback
        })

    # 4. Calculate final score
    score = round((correct_count / total) * 100) if total > 0 else 0
    child_name = user.child_name or "Your child"

    # 5. Generate feedback messages
    if score == 100:
        child_feedback = "Amazing! You answered all questions correctly! 🏆⭐"
        parent_feedback = (
            f"Excellent! {child_name} answered all {total} questions "
            f"correctly. Score: {score}/100!"
        )
    elif score >= 60:
        child_feedback = (
            f"Good job! You got {correct_count} out of {total} correct! 👍"
        )
        parent_feedback = (
            f"Good progress! {child_name} answered {correct_count}/{total} "
            f"correctly. Score: {score}/100. "
            f"Review the incorrect answers together."
        )
    else:
        child_feedback = (
            f"Keep practicing! You got {correct_count} out of {total}. "
            f"Try reading the story again! 💪"
        )
        parent_feedback = (
            f"{child_name} needs more practice. Score: {score}/100. "
            f"We recommend re-reading the story and trying again."
        )

    # 6. Save result to DB
    reading_result = models.ReadingResult(
        user_id=user.id,
        passage_id=request.passage_id,
        whisper_transcript="N/A",
        score=score,
        missed_words="",
        feedback=child_feedback
    )
    db.add(reading_result)
    db.commit()

    return {
        "passage_id": request.passage_id,
        "total_questions": total,
        "correct_answers": correct_count,
        "score": score,
        "child_feedback": child_feedback,
        "parent_feedback": parent_feedback,
        "results": results
    }

# ════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════

@app.get("/passages/{passage_id}/full",
         response_model=schemas.FullPassageResponse,
         tags=["Reading"])
def get_full_passage(
    passage_id: int,
    db: Session = Depends(database.get_db)
):
    """
    ONE combined endpoint for Flutter's reading screen.
    Returns everything needed in a single call:
      - story title + text
      - all images for this story (in order)
      - all 3 multiple choice questions (correct_answer hidden)

    No audio_url, no TTS — this feature is text + images + questions only.
    """
    passage = db.query(models.ReadingPassage).filter(
        models.ReadingPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    images = db.query(models.StoryImage).filter(
        models.StoryImage.passage_id == passage_id
    ).order_by(models.StoryImage.image_order).all()

    questions = db.query(models.ReadingQuestion).filter(
        models.ReadingQuestion.passage_id == passage_id
    ).all()

    return {
        "id": passage.id,
        "title": passage.title,
        "content": passage.content,
        "level": passage.level,
        "images": images,
        "questions": questions
    }
# ════════════════════════════════
#        RUN SERVER
# ════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

