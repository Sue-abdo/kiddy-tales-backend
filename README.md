---
title: Kiddy Tales Backend
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# Kiddy Tales — AI-Powered English Learning App for Kids

## Overview
Kiddy Tales is an AI-powered mobile application designed to improve English language skills for children aged 6 to 11. This repository contains the complete backend API built with FastAPI.

## Features
- 🎤 **Listening & Speaking** — Children listen to correct pronunciation via TTS, record their voice, and get scored using Whisper AI + Levenshtein Distance
- 📖 **Story Generation** — AI generates personalized stories based on words the child provides, complete with illustrations and audio
- 🖼️ **Image Generation** — Each story gets a colorful AI-generated illustration using Hugging Face FLUX
- ❓ **Comprehension Questions** — Three questions generated per story to test understanding
- 📊 **Progress Tracking** — All results saved and linked to each child's account
- 📧 **Email Verification** — Real email validation via 6-digit code sent to parent
- 👨‍👩‍👧 **Multi-Child Support** — One parent can register multiple children

## Tech Stack
| Component | Technology |
|---|---|
| Framework | FastAPI (Python) |
| Database | PostgreSQL (Supabase) |
| Speech-to-Text | OpenAI Whisper |
| Text-to-Speech | Google gTTS |
| Story Generation | Groq + Llama-3.3-70B |
| Image Generation | Hugging Face FLUX.1 |
| Scoring | Levenshtein Distance |
| Auth | JWT Tokens |
| Deployment | Hugging Face Spaces |

## API Endpoints
### Auth
- `POST /signup` — Register parent + child account
- `POST /verify-email` — Verify email with 6-digit code
- `POST /login` — Login with child email → returns token
- `GET /profile` — Get user profile
- `POST /logout` — Logout

### Words (Listening & Speaking)
- `GET /words?level=1` — Get words by level with audio URLs
- `GET /words/{id}/audio` — Get word audio URL
- `POST /evaluate` — Submit voice recording → get pronunciation score
- `POST /practice/{word_id}` — Same as evaluate (word_id in URL)
- `GET /progress` — Get child's pronunciation progress

### Stories
- `POST /generate-story` — Generate story + image + audio + questions
- `POST /evaluate-answers` — Submit answers → get score + feedback

## Live API
- **Swagger Docs:** https://sue-ii99-kiddy-tales-backend.hf.space/docs

## Supervised by
Dr. Bahaa  — Ahram Canadian University, Egypt 2026