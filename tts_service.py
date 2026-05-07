from gtts import gTTS
import os


def text_to_speech(word: str, output_path: str) -> str:
    """
    Convert word to audio using Google TTS
    slow=True عشان الأطفال يسمعوا بوضوح
    Returns: path to the generated audio file
    """
    tts = gTTS(text=word, lang='en', slow=True)
    tts.save(output_path)
    return output_path
