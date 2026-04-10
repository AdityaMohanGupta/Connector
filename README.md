# Outlook Connector

Two-folder web app for connecting a user's Outlook account, working with mail and calendar data, and exposing approved Outlook actions to MCP-compatible agents.

## Folders

- `frontend`: Vite React TypeScript dashboard.
- `backend`: FastAPI, Microsoft Graph OAuth, Postgres-ready persistence, approvals, and MCP tools.

## Local Run

Backend:

```bash
cd backend
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

## Secrets To Fill Later

Fill the blank backend `.env` values before connecting a real Microsoft account:

- `DATABASE_URL`
- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`
- `MICROSOFT_REDIRECT_URI`
- `SESSION_SECRET`
- `TOKEN_ENCRYPTION_KEY`
- `FRONTEND_ORIGIN`
- `MCP_BEARER_TOKEN`

Fill the frontend `.env` value:

- `VITE_API_BASE_URL`

Generate `TOKEN_ENCRYPTION_KEY` with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For Microsoft Entra, configure delegated Graph permissions: `User.Read`, `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`, and `offline_access`.
