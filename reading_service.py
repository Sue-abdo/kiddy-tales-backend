import re
import Levenshtein

def normalize(text: str) -> str:
    """
    Clean text for comparison:
    - lowercase
    - remove punctuation
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def evaluate_reading(original_text: str, whisper_transcript: str) -> dict:
    """
    Compare what the child read (whisper_transcript)
    vs the original passage (original_text)
    word by word using Levenshtein Distance.

    Returns: score, missed_words, feedback, is_passed
    """

    # 1. Normalize both texts
    original_words = normalize(original_text).split()
    whisper_words = normalize(whisper_transcript).split()

    total_words = len(original_words)
    correct_count = 0
    missed_words = []

    # 2. For each word in the original passage,
    #    find the closest match in what Whisper heard
    for orig_word in original_words:
        if not whisper_words:
            missed_words.append(orig_word)
            continue

        # Find the closest word Whisper heard
        closest = min(
            whisper_words,
            key=lambda w: Levenshtein.distance(w, orig_word)
        )

        max_len = max(len(closest), len(orig_word))
        similarity = (
            1 - Levenshtein.distance(closest, orig_word) / max_len
        ) * 100

        if similarity >= 70:
            correct_count += 1
        else:
            missed_words.append(orig_word)

    # 3. Calculate score
    score = round((correct_count / total_words) * 100) if total_words > 0 else 0
    is_passed = score >= 60

    # 4. Build feedback message
    if score == 100:
        feedback = "Amazing! You read everything perfectly! 🏆⭐"
    elif score >= 80:
        feedback = f"Great reading! You got {score}%! Keep it up! 🌟"
    elif score >= 60:
        feedback = f"Good job! You read {score}% correctly. Practice the missed words! 👍"
    elif score >= 40:
        feedback = f"Keep trying! You got {score}%. Listen to the passage and try again! 💪"
    else:
        feedback = f"Don't give up! Listen carefully and try again. You can do it! 🎯"

    return {
        "score": score,
        "total_words": total_words,
        "correct_words": correct_count,
        "missed_words": missed_words,
        "feedback": feedback,
        "is_passed": is_passed
    }
