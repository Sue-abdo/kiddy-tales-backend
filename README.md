---
title: English Buddy Backend
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# English Buddy Backend API

AI-powered English learning app for kids aged 6-11.

## Endpoints
- `GET /docs` - Swagger documentation
- `GET /words?level=1` - Get words by level
- `GET /words/{id}/audio` - Get word audio
- `POST /evaluate` - Evaluate child pronunciation
- `POST /practice/{id}` - Full listening + speaking flow
