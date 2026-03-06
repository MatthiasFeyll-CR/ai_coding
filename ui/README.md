# Ralph Pipeline Web UI

A web-based control panel for the Ralph Pipeline automation system.

## Architecture

```
ui/
├── backend/           # Flask + SocketIO API server
│   ├── api/           # REST API blueprints
│   ├── services/      # Business logic
│   ├── models.py      # SQLAlchemy models
│   ├── database.py    # DB initialization
│   ├── config.py      # Configuration
│   └── app.py         # Entry point
├── frontend/          # React + TypeScript SPA
│   └── src/
│       ├── api/       # HTTP client
│       ├── components/  # UI components
│       ├── hooks/     # Custom hooks
│       ├── pages/     # Route pages
│       ├── store/     # Zustand state
│       ├── styles/    # CSS
│       └── types/     # TypeScript types
├── docker-compose.yml
├── dev.sh             # Development launcher
└── build.sh           # Production build
```

## Quick Start

### Development Mode

```bash
cd ui
chmod +x dev.sh
./dev.sh
```

This starts:
- **Backend** at http://localhost:5000 (Flask + SocketIO)
- **Frontend** at http://localhost:3000 (Vite dev server with HMR)

### Docker Mode

```bash
cd ui
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
docker compose up
```

### Production Build

```bash
cd ui
chmod +x build.sh
./build.sh
# Then:
cd backend && python app.py
# Open http://localhost:5000
```

## Requirements

- Python 3.11+
- Node.js 20+
- npm 9+

## Features

- **Dashboard**: Real-time pipeline state visualization with FSM diagram
- **Live Logs**: WebSocket-powered log streaming with auto-scroll
- **Token Tracking**: Cost monitoring with charts (bar + pie)
- **File Browser**: Monaco editor integration for viewing project files
- **Infrastructure**: System requirements checker and project setup wizard
- **Model Configuration**: Per-phase AI model selection
- **State Management**: Snapshot/restore pipeline state
- **Git Operations**: Automated branch management visibility

## Design

Dark mode UI with NEXUS OS aesthetic:
- Background: `#0a0e1a`
- Accent Cyan: `#06b6d4`
- Accent Purple: `#a855f7`
- Fonts: Inter (UI) + JetBrains Mono (code)
