#!/usr/bin/env bash
# =============================================================================
# Ralph Pipeline UI — Test Runner
# =============================================================================
# Usage:
#   ./scripts/run-tests.sh          # Run all tests (backend + frontend unit)
#   ./scripts/run-tests.sh backend  # Run only backend tests
#   ./scripts/run-tests.sh frontend # Run only frontend unit tests
#   ./scripts/run-tests.sh e2e      # Run Playwright E2E tests (requires servers)
#   ./scripts/run-tests.sh all      # Run everything including E2E
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$UI_DIR/backend"
FRONTEND_DIR="$UI_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

run_backend_tests() {
    echo -e "${BLUE}━━━ Running Backend Tests ━━━${NC}"
    cd "$BACKEND_DIR"
    python -m pytest tests/ -v --tb=short "$@"
    echo -e "${GREEN}✓ Backend tests passed${NC}\n"
}

run_frontend_tests() {
    echo -e "${BLUE}━━━ Running Frontend Unit Tests ━━━${NC}"
    cd "$FRONTEND_DIR"
    npx vitest run "$@"
    echo -e "${GREEN}✓ Frontend unit tests passed${NC}\n"
}

run_e2e_tests() {
    echo -e "${BLUE}━━━ Running E2E Tests (Playwright) ━━━${NC}"
    cd "$FRONTEND_DIR"
    npx playwright test "$@"
    echo -e "${GREEN}✓ E2E tests passed${NC}\n"
}

MODE="${1:-all-unit}"
shift 2>/dev/null || true

case "$MODE" in
    backend)
        run_backend_tests "$@"
        ;;
    frontend)
        run_frontend_tests "$@"
        ;;
    e2e)
        run_e2e_tests "$@"
        ;;
    all)
        run_backend_tests "$@"
        run_frontend_tests "$@"
        run_e2e_tests "$@"
        ;;
    all-unit|"")
        run_backend_tests "$@"
        run_frontend_tests "$@"
        ;;
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo "Usage: $0 {backend|frontend|e2e|all|all-unit}"
        exit 1
        ;;
esac

echo -e "${GREEN}━━━ All requested tests passed ━━━${NC}"
