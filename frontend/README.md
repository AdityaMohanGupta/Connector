# Outlook Connector Frontend

React dashboard for connecting Outlook, working with mail and calendar data, testing MCP tools, approving write actions, and reviewing audit history.

## Setup

1. Install dependencies:

```bash
npm install
```

2. Copy `.env.example` to `.env` and fill:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

3. Start the app:

```bash
npm run dev
```

The browser app never stores Microsoft secrets. It uses the backend session cookie and API routes.
