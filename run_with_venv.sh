#!/bin/bash
# Wrapper pour activer le venv et lancer le script Python

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/kissbot-venv"

# Vérifier si le venv existe
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found at: $VENV_DIR"
    echo ""
    echo "Please create it with:"
    echo "  python3 -m venv kissbot-venv"
    echo "  source kissbot-venv/bin/activate"
    echo "  pip install httpx"
    exit 1
fi

# Activer le venv
source "$VENV_DIR/bin/activate"

# Vérifier httpx
if ! python3 -c "import httpx" 2>/dev/null; then
    echo "⚠️  httpx not found in venv"
    echo "Installing httpx..."
    pip install httpx
fi

# Lancer le script demandé
if [ $# -eq 0 ]; then
    echo "Usage: $0 <script.py> [args...]"
    echo ""
    echo "Examples:"
    echo "  $0 quick_test_nahl.py"
    echo "  $0 test_quality_gate.py"
    echo "  $0 test_nahl_integration.py"
    exit 1
fi

python3 "$@"
