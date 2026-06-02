# VolShape

VolShape is a fitness assistant app with two parts:

- `frontend/`: an Expo + React Native client with chat, training, and exploration screens
- `backend/`: a FastAPI service that powers auth, chat, diet, workout, and payment flows

## Project Layout

```text
VolShape/
├─ backend/      # FastAPI app, database models, workflows, and service integrations
├─ frontend/     # Expo Router app for mobile and web
├─ VolShape方案.md
└─ README.md
```

## Frontend

The frontend is an Expo Router app.

```bash
cd frontend
npm install
npm run dev
```

Useful scripts:

- `npm run android`
- `npm run ios`
- `npm run web`
- `npm run lint`

The app currently points to a local backend in `frontend/src/services/api.ts`.

## Backend

The backend is a FastAPI app.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the values you need. The backend can use:

- `DATABASE_URL`
- `REDIS_URL`
- `SUPABASE_JWT_SECRET`
- `AUTH_JWT_SECRET`
- `TOKEN_ENCRYPTION_SECRET`
- `DEEPSEEK_API_KEY`
- `NEWAPI_BASE_URL`
- `NEWAPI_ACCESS_TOKEN`
- `NEWAPI_USER_ID`
- `TAVILY_API_KEY`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

## Notes

- The backend enables CORS for local development.
- The repo is meant to be run as a local full-stack workspace.
- Large generated artifacts, logs, databases, and dependency folders are ignored by `.gitignore`.

