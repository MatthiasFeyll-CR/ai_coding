#!/usr/bin/env bash
# Development launcher for Ralph Pipeline UI
# Starts both backend and frontend in development mode.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Ralph Pipeline UI - Development Mode${NC}"
echo "======================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "Error: node not found"
    exit 1
fi

# Backend setup
echo -e "\n${GREEN}Setting up backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

# Create data directory
mkdir -p data

# Initialize database
python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database initialized.')
"

echo -e "${GREEN}Starting backend on :5000...${NC}"
python app.py &
BACKEND_PID=$!

cd "$SCRIPT_DIR"

# Frontend setup
echo -e "\n${GREEN}Setting up frontend...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    npm install
fi

echo -e "${GREEN}Starting frontend on :3000...${NC}"
npm run dev &
FRONTEND_PID=$!

cd "$SCRIPT_DIR"

# Trap cleanup
cleanup() {
    echo -e "\n${CYAN}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait
}
trap cleanup EXIT INT TERM

echo -e "\n${GREEN}Ready!${NC}"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:5000"
echo "  Press Ctrl+C to stop"
echo ""

wait
