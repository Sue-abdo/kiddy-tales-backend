import smtplib
import random
import string
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")


def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def send_verification_email(to_email: str, code: str, child_name: str):
    """Send verification code to parent email"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "English Buddy — Email Verification Code"
    msg["From"] = MAIL_FROM
    msg["To"] = to_email

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #4A90D9;">🎓 English Buddy</h2>
        <p>Hello!</p>
        <p>Thank you for registering <strong>{child_name}</strong> on English Buddy.</p>
        <p>Your verification code is:</p>
        <h1 style="color: #4A90D9; font-size: 40px; letter-spacing: 10px;">
            {code}
        </h1>
        <p>This code expires in <strong>10 minutes</strong>.</p>
        <p>If you didn't create this account, please ignore this email.</p>
        <br>
        <p>Best regards,<br>English Buddy Team 🌟</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False