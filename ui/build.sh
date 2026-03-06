#!/usr/bin/env bash
# Build production bundle for Ralph Pipeline UI.
# Builds frontend static files and copies them to backend/static/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Building Ralph Pipeline UI for production${NC}"
echo "==========================================="

# Build frontend
echo -e "${GREEN}Building frontend...${NC}"
cd frontend
npm install
npm run build

cd "$SCRIPT_DIR"

# The vite config already outputs to ../backend/static
echo -e "${GREEN}Frontend built to backend/static/${NC}"

# Install backend deps
echo -e "${GREEN}Installing backend dependencies...${NC}"
cd backend
pip install -q -r requirements.txt
mkdir -p data

echo -e "\n${GREEN}Build complete!${NC}"
echo "Run with: cd backend && python app.py"
echo "Open: http://localhost:5000"
