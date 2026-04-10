# Outlook Connector Backend

FastAPI backend for Microsoft Graph OAuth, Outlook mail/calendar operations, pending approvals, and an MCP server surface for external agents.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -e ".[dev]"
```

3. Copy `.env.example` to `.env` and fill the blank values.
4. Generate `TOKEN_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

5. Run migrations:

```bash
alembic upgrade head
```

6. Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

## Required Microsoft Entra Settings

- Supported account types: personal Microsoft accounts and work/school accounts.
- Redirect URI: match `MICROSOFT_REDIRECT_URI`, for example `http://localhost:8000/auth/microsoft/callback`.
- Delegated Microsoft Graph permissions: `User.Read`, `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`, plus `offline_access`.

The env template intentionally leaves secrets blank. Fill them before connecting a real Outlook account.
