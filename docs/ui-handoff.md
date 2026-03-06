# Ralph Pipeline UI - Implementation Handoff

**Date:** March 6, 2026  
**Status:** ✅ Design Complete - Ready for Implementation  
**Next Phase:** AI Agent Autonomous Implementation

---

## Quick Start for New AI Session

This document provides everything needed to implement the Ralph Pipeline Web UI from scratch.

### 📁 Essential Documentation

1. **[ui-implementation-guide.md](ui-implementation-guide.md)** (1,826 lines)
   - Complete backend implementation (Flask + SocketIO)
   - Database models (8 tables with SQLAlchemy)
   - API endpoints (29 REST endpoints)
   - WebSocket event system
   - Pipeline runner & file watcher services
   - Frontend configuration (Vite, TypeScript, Tailwind)
   - TypeScript types and API client

2. **[ui-implementation-guide-part2.md](ui-implementation-guide-part2.md)** (1,368 lines)
   - React component implementations
   - Layout system (Sidebar, TopBar)
   - Dashboard with FSM visualization
   - Live logs with real-time updates
   - Control panel for pipeline execution
   - Testing implementation (pytest + Vitest)
   - Docker deployment configuration
   - Troubleshooting guide

**Total Documentation:** 3,193 lines of comprehensive specifications

---

## Project Summary

### Primary Goal
Transform the CLI-based Ralph Pipeline into a web application with:
- ✅ Real-time monitoring dashboard
- ✅ Infrastructure validation with auto-fix loops
- ✅ Project management UI
- ✅ Live log streaming
- ✅ Cost tracking and visualization
- ✅ FSM state visualization

### Scope
- **MVP Focus:** Single-user, local development environment
- **Deployment:** Docker Compose, local-only
- **User:** Single developer on same machine as target project
- **Explicitly Excluded:** Multi-user, authentication, notifications, PM integrations

---

## Technical Stack

### Backend
- **Framework:** Flask 3.0 + Flask-SocketIO 5.3
- **Database:** SQLite with SQLAlchemy 2.0 ORM
- **Real-time:** WebSocket via eventlet
- **File Monitoring:** Watchdog 3.0
- **Pipeline Integration:** Subprocess calls to `ralph-pipeline` CLI

### Frontend
- **Framework:** React 18 + TypeScript 5.3
- **Build Tool:** Vite 5.0
- **State Management:** Zustand 4.4 (UI state) + TanStack Query 5.0 (server state)
- **UI Components:** Tailwind CSS 3.4 + shadcn/ui
- **Code Editor:** Monaco Editor 0.45
- **Visualization:** React Flow 11.10 (FSM), Recharts 2.10 (charts)
- **Animations:** Framer Motion 10.16

### Deployment
- **Container:** Docker Compose
- **Dev Mode:** Vite dev server (port 3000) + Flask backend (port 5000)
- **Production:** Flask serves React static bundle (single port 5000)

---

## Architecture Highlights

### Database Schema (8 Tables)
1. **projects** - Core project metadata
2. **state_snapshots** - Reinstantiation points
3. **execution_logs** - Historical log records
4. **token_usage** - Cost tracking per phase
5. **model_configs** - Per-phase model configuration
6. **requirement_checks** - Dependency validation
7. **project_setup** - Infrastructure setup tracking
8. **infrastructure_backups** - File backup history

### API Design (29 Endpoints)

**Projects API:**
- `GET /api/projects` - List all projects
- `POST /api/projects` - Link new project
- `DELETE /api/projects/<id>` - Unlink project
- `POST /api/projects/pre-check` - Validate docs structure
- `POST /api/projects/<id>/setup` - Initialize infrastructure
- `GET /api/projects/<id>/config` - Get pipeline config
- `GET /api/projects/<id>/state` - Get current state
- `GET /api/projects/<id>/snapshots` - List reinstantiation points
- `POST /api/projects/<id>/reinstantiate` - Restore to snapshot
- `GET /api/projects/<id>/models` - Get model configs
- `POST /api/projects/<id>/models` - Update model config

**Pipeline API:**
- `POST /api/pipeline/<id>/start` - Start pipeline execution
- `POST /api/pipeline/<id>/stop` - Stop running pipeline
- `POST /api/pipeline/<id>/resume` - Resume from checkpoint
- `GET /api/pipeline/<id>/logs` - Get execution logs
- `GET /api/pipeline/<id>/tokens` - Get token usage
- `GET /api/pipeline/<id>/milestones` - Get milestone status

**WebSocket Events:**
- `state_change` - Pipeline state updates
- `log` - Real-time log streaming
- `token_update` - Cost updates
- `file_change` - File system changes
- `milestone_update` - Progress updates

### Key Features

#### 1. Infrastructure Validation Flow
```
Link Project → Pre-check → Pipeline Configurator → Validate Test Env
                                ↓ (if failed)
                          Auto-fix (max 3 attempts)
                                ↓ (still failed)
                          Manual Intervention UI
```

#### 2. Real-time Monitoring
- WebSocket subscription per project
- Live log streaming (last 10,000 lines)
- Auto-scroll with manual override
- Token cost tracking
- FSM phase visualization

#### 3. Pipeline Control
- Start/Stop/Resume operations
- Lock file prevention (concurrent execution)
- Reinstantiation from snapshots
- Model configuration override

---

## Design System

### Colors (Dark Mode Primary)
```css
--bg-primary: #0a0e1a     /* Main background */
--bg-secondary: #0f1420    /* Cards, sidebar */
--bg-tertiary: #161b2e     /* Hover states */
--accent-cyan: #06b6d4     /* Primary actions */
--accent-purple: #a855f7    /* Secondary accents */
--status-success: #10b981
--status-error: #ef4444
--status-warning: #f59e0b
```

### Typography
- **Body:** Inter (Google Fonts)
- **Code:** JetBrains Mono

### Animation Guidelines
- Transitions: 0.2-0.3s ease-in-out
- Hover scale: 1.02
- Tap scale: 0.98
- Glow effects for active states

---

## Implementation Checklist

### Phase 1: Backend Setup
- [ ] Create `ui/backend/` directory structure
- [ ] Install Python dependencies (`requirements.txt`)
- [ ] Implement Flask app with SocketIO
- [ ] Create 8 SQLAlchemy models
- [ ] Implement Projects API (11 endpoints)
- [ ] Implement Pipeline API (6 endpoints)
- [ ] Implement WebSocket handlers
- [ ] Create PipelineRunner service
- [ ] Create FileWatcher service
- [ ] Set up Alembic migrations

### Phase 2: Frontend Setup
- [ ] Create `ui/frontend/` directory structure
- [ ] Install Node dependencies (`package.json`)
- [ ] Configure Vite with proxy
- [ ] Configure TypeScript
- [ ] Configure Tailwind CSS
- [ ] Define TypeScript types
- [ ] Implement API client
- [ ] Implement WebSocket hook
- [ ] Create Zustand store

### Phase 3: React Components
- [ ] App.tsx with routing
- [ ] Layout (Sidebar + TopBar)
- [ ] Dashboard page
- [ ] FSM Visualization (React Flow)
- [ ] Live Logs component
- [ ] Control Panel
- [ ] Token Dashboard
- [ ] Infrastructure Tab
- [ ] Setup Flow modal
- [ ] All supporting modals

### Phase 4: Infrastructure Integration
- [ ] ConfiguratorInvoker service
- [ ] CLI `validate-test-env` command
- [ ] Auto-fix loop logic
- [ ] Backup/restore functionality

### Phase 5: Testing
- [ ] Backend API tests (pytest)
- [ ] WebSocket tests
- [ ] Frontend component tests (Vitest)
- [ ] Integration tests
- [ ] E2E workflow tests

### Phase 6: Deployment
- [ ] Write Dockerfile.backend
- [ ] Write docker-compose.yml
- [ ] Create build scripts
- [ ] Create dev startup script
- [ ] Configure environment variables
- [ ] Test volume mounts
- [ ] Verify Docker socket access

---

## Critical Implementation Notes

### 1. Lock File Mechanism
```python
# Backend must check lock file before starting pipeline
lock_file = Path(project.root_path) / '.ralph' / 'execution.lock'
if lock_file.exists():
    raise ConflictError("Pipeline already running")
```

### 2. WebSocket Room Management
```python
# Use project-specific rooms for targeted broadcasts
@socketio.on('subscribe')
def handle_subscribe(data):
    project_id = data['project_id']
    join_room(f'project_{project_id}')
```

### 3. File Watcher Debouncing
```python
# Debounce file events to avoid spam
last_event_time = {}
DEBOUNCE_SECONDS = 1

if time.time() - last_event_time.get(file_path, 0) < DEBOUNCE_SECONDS:
    return
```

### 4. Frontend Auto-scroll Logic
```typescript
// Disable auto-scroll when user scrolls up
const handleScroll = () => {
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
  setAutoScroll(isAtBottom);
};
```

### 5. Error Recovery
- Database transactions with rollback
- WebSocket reconnection logic (exponential backoff)
- Pipeline subprocess cleanup on stop
- Backup restoration on setup failure

---

## File Locations Reference

### Backend Files
```
ui/backend/
├── app.py                      # Flask + SocketIO initialization
├── database.py                  # SQLAlchemy setup
├── models.py                    # 8 database models
├── config.py                    # Environment configuration
├── requirements.txt             # Python dependencies
├── api/
│   ├── projects.py             # Projects API endpoints
│   ├── pipeline.py             # Pipeline control endpoints
│   └── websocket.py            # WebSocket event handlers
└── services/
    ├── pipeline_runner.py      # Subprocess management
    ├── file_watcher.py         # Watchdog integration
    └── configurator_invoker.py # Infrastructure setup
```

### Frontend Files
```
ui/frontend/
├── src/
│   ├── App.tsx                 # Main application
│   ├── types/index.ts          # TypeScript definitions
│   ├── api/client.ts           # Axios API client
│   ├── hooks/useWebSocket.ts   # WebSocket hook
│   ├── store/appStore.ts       # Zustand store
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Layout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── TopBar.tsx
│   │   └── pipeline/
│   │       ├── FSMVisualization.tsx
│   │       ├── LiveLogs.tsx
│   │       ├── ControlPanel.tsx
│   │       └── TokenDashboard.tsx
│   └── pages/
│       └── DashboardPage.tsx
├── vite.config.ts              # Vite configuration
├── tsconfig.json               # TypeScript config
├── tailwind.config.js          # Tailwind CSS config
└── package.json                # Node dependencies
```

---

## Testing Strategy

### Backend Tests
- **Framework:** pytest
- **Coverage Target:** >80%
- **Test Types:**
  - API endpoint tests (status codes, response schema)
  - WebSocket event tests
  - Database model tests
  - Service integration tests

### Frontend Tests
- **Framework:** Vitest + Testing Library
- **Coverage Target:** >70%
- **Test Types:**
  - Component rendering tests
  - Hook behavior tests
  - API client tests
  - Store state management tests

---

## Deployment Instructions

### Development Mode
```bash
# Terminal 1: Backend
cd ui/backend
source venv/bin/activate
python app.py

# Terminal 2: Frontend
cd ui/frontend
npm run dev
```

**Access:** http://localhost:3000

### Production Mode
```bash
# Build frontend
cd ui/frontend
npm run build

# Start with Docker
cd ui
docker-compose up -d
```

**Access:** http://localhost:5000

---

## Environment Variables

**File: `ui/backend/.env`**
```env
FLASK_ENV=production
DATABASE_URL=sqlite:///data/pipeline.db
SECRET_KEY=<generate-random-key>
CORS_ORIGINS=http://localhost:5000
RALPH_PIPELINE_PATH=/path/to/ralph-pipeline
HOST_PROJECTS_ROOT=/home/user/projects
```

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| WebSocket disconnects | Check CORS_ORIGINS, ensure eventlet installed |
| Database locked | Use connection pooling, proper transaction management |
| File watcher not working | Verify .ralph/ exists, check permissions |
| Monaco editor not loading | Move to dependencies (not devDependencies) |
| Docker permission errors | Add user to docker group, check socket mount |
| Lock file stuck | Manually delete `.ralph/execution.lock` |
| Port already in use | Change ports in .env and docker-compose.yml |

---

## Next Steps for AI Implementation

1. **Read Both Implementation Guides:**
   - [ui-implementation-guide.md](ui-implementation-guide.md) - Backend & infrastructure
   - [ui-implementation-guide-part2.md](ui-implementation-guide-part2.md) - Frontend & deployment

2. **Start with Backend:**
   - Create directory structure
   - Implement models and database
   - Build API endpoints
   - Add WebSocket support

3. **Build Frontend:**
   - Set up React + TypeScript project
   - Implement core layouts
   - Add dashboard components
   - Connect WebSocket events

4. **Integrate & Test:**
   - Connect backend and frontend
   - Test WebSocket real-time updates
   - Verify pipeline integration
   - Run test suites

5. **Deploy:**
   - Build Docker images
   - Configure docker-compose
   - Test end-to-end workflow
   - Verify all checklist items

---

## Success Criteria

The implementation is complete when:

✅ All 29 API endpoints return correct responses  
✅ WebSocket events stream in real-time  
✅ Projects can be linked and managed  
✅ Pipeline can start/stop/resume successfully  
✅ Live logs display with auto-scroll  
✅ FSM visualization shows current phase  
✅ Token costs are tracked and displayed  
✅ Infrastructure validation runs with auto-fix  
✅ Reinstantiation restores working state  
✅ Tests pass with >75% coverage  
✅ Docker deployment works end-to-end  

---

## Contact & Context

**Original Design Session:** March 6, 2026  
**Design Phases Completed:** 5 (Requirements → Technical → UI/UX → Verification → Documentation)  
**Repository:** /home/feyll/ralph-pipeline  
**Documentation Location:** docs/ui-*.md  

**Key Design Decisions:**
- Dark mode with NEXUS OS aesthetic (cyan/purple accents)
- Flask backend for simplicity and Python ecosystem compatibility
- React for modern, maintainable UI
- WebSocket for real-time updates (not polling)
- SQLite for local-only, single-user deployment
- Docker Compose for deployment simplicity
- Infrastructure validation with auto-fix to catch configurator bugs
- Lock files to prevent concurrent execution
- Snapshot-based reinstantiation

**Implementation Estimate:** 2-3 days for experienced AI agent with full context

---

## Appendix: Component Hierarchy

```
App
├── RequirementsPage (standalone)
└── Layout
    ├── Sidebar
    │   ├── ProjectList
    │   └── StatusIcons
    ├── TopBar
    │   ├── SearchBar
    │   ├── Notifications
    │   └── ThemeToggle
    └── DashboardPage
        ├── ControlPanel
        ├── TabNavigation
        │   ├── StateTab
        │   │   ├── FSMVisualization (React Flow)
        │   │   └── LiveLogs
        │   ├── GitTab (future)
        │   ├── CostsTab
        │   │   └── TokenDashboard (Recharts)
        │   ├── TestsTab (future)
        │   └── InfrastructureTab
        │       ├── ServiceHealth
        │       ├── ValidationReport
        │       └── ManualFixUI
        └── Modals
            ├── LinkProjectModal
            ├── SetupFlowModal
            ├── ReinstantiateModal
            ├── ModelSelectorModal
            └── ErrorModal
```

---

**End of Handoff Document**

All information needed for implementation is contained in this handoff and the two implementation guide files. An AI agent with access to these three documents has complete specifications to build the Ralph Pipeline UI autonomously.
