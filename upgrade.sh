#!/bin/bash
#===============================================================================
# KissBot Upgrade Script
# Usage: scp upgrade.sh user@vps:/path/to/kissbot/ && ssh user@vps "cd /path/to/kissbot && bash upgrade.sh"
#===============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
BRANCH="refactor/v2-modular"
BACKUP_DIR="backups"
DATE_TAG=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           🤖 KissBot Upgrade Script v2.0                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

#-------------------------------------------------------------------------------
# Step 1: Pre-flight checks
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[1/8]${NC} Vérifications préliminaires..."

# Check if we're in a git repo
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ Erreur: Ce script doit être lancé depuis le répertoire KissBot${NC}"
    exit 1
fi

# Check if kissbot.sh exists
if [ ! -f "kissbot.sh" ]; then
    echo -e "${RED}❌ Erreur: kissbot.sh non trouvé - mauvais répertoire ?${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Dans le bon répertoire${NC}"

#-------------------------------------------------------------------------------
# Step 2: Stop running services
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[2/8]${NC} Arrêt des services en cours..."

# Stop bot if running
if [ -f "pids/main.pid" ] && kill -0 $(cat pids/main.pid 2>/dev/null) 2>/dev/null; then
    echo "  → Arrêt du bot principal..."
    bash ./kissbot.sh stop 2>/dev/null || true
    sleep 2
fi

# Stop web if running
if pgrep -f "uvicorn.*main:app" > /dev/null 2>&1; then
    echo "  → Arrêt du serveur web..."
    pkill -f "uvicorn.*main:app" 2>/dev/null || true
    sleep 1
fi

# Stop supervisor if running
if [ -f "pids/supervisor.pid" ] && kill -0 $(cat pids/supervisor.pid 2>/dev/null) 2>/dev/null; then
    echo "  → Arrêt du supervisor..."
    kill $(cat pids/supervisor.pid) 2>/dev/null || true
    sleep 1
fi

echo -e "${GREEN}✓ Services arrêtés${NC}"

#-------------------------------------------------------------------------------
# Step 3: Create backups
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[3/8]${NC} Création des sauvegardes..."

mkdir -p "$BACKUP_DIR"

# Backup database
if [ -f "kissbot.db" ]; then
    cp kissbot.db "$BACKUP_DIR/kissbot.db.backup_$DATE_TAG"
    echo "  → kissbot.db sauvegardé"
fi

# Backup config
if [ -f "config/config.yaml" ]; then
    cp config/config.yaml "$BACKUP_DIR/config.yaml.backup_$DATE_TAG"
    echo "  → config.yaml sauvegardé"
fi

# Backup .env web
if [ -f "web/backend/.env" ]; then
    cp web/backend/.env "$BACKUP_DIR/web_env.backup_$DATE_TAG"
    echo "  → web/.env sauvegardé"
fi

# Backup encryption key
if [ -f ".kissbot.key" ]; then
    cp .kissbot.key "$BACKUP_DIR/.kissbot.key.backup_$DATE_TAG"
    echo "  → .kissbot.key sauvegardé"
fi

echo -e "${GREEN}✓ Sauvegardes créées dans $BACKUP_DIR/${NC}"

#-------------------------------------------------------------------------------
# Step 4: Git pull
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[4/8]${NC} Mise à jour du code depuis git..."

# Stash any local changes
git stash 2>/dev/null || true

# Fetch and pull
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo -e "${GREEN}✓ Code mis à jour (branche: $BRANCH)${NC}"

#-------------------------------------------------------------------------------
# Step 5: Install Python dependencies
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[5/8]${NC} Installation des dépendances Python..."

# Check for virtual environment
if [ -d "kissbot-venv" ]; then
    source kissbot-venv/bin/activate
    echo "  → Environnement virtuel activé"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "  → Environnement virtuel activé"
fi

# Install main requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    echo "  → requirements.txt installé"
fi

# Install web backend requirements
if [ -f "web/backend/requirements.txt" ]; then
    pip install -r web/backend/requirements.txt -q
    echo "  → web/backend/requirements.txt installé"
fi

echo -e "${GREEN}✓ Dépendances installées${NC}"

#-------------------------------------------------------------------------------
# Step 6: Setup web backend .env if needed
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[6/8]${NC} Configuration du backend web..."

if [ ! -f "web/backend/.env" ]; then
    if [ -f "web/backend/.env.example" ]; then
        cp web/backend/.env.example web/backend/.env
        echo -e "${YELLOW}  ⚠ web/backend/.env créé depuis .env.example${NC}"
        echo -e "${YELLOW}  → IMPORTANT: Édite web/backend/.env avec tes credentials Twitch !${NC}"
        WEB_ENV_NEEDS_CONFIG=true
    else
        # Create minimal .env
        cat > web/backend/.env << 'EOF'
# Twitch OAuth Configuration
TWITCH_CLIENT_ID=your_client_id_here
TWITCH_CLIENT_SECRET=your_client_secret_here
TWITCH_REDIRECT_URI=http://localhost:8080/auth/callback

# Security
SECRET_KEY=change_me_to_a_random_32_char_string

# Environment
DEBUG=false
EOF
        echo -e "${YELLOW}  ⚠ web/backend/.env créé avec template par défaut${NC}"
        echo -e "${YELLOW}  → IMPORTANT: Édite web/backend/.env avec tes credentials Twitch !${NC}"
        WEB_ENV_NEEDS_CONFIG=true
    fi
else
    echo "  → web/backend/.env existe déjà"
    # Restore from backup if we had one
    if [ -f "$BACKUP_DIR/web_env.backup_$DATE_TAG" ]; then
        cp "$BACKUP_DIR/web_env.backup_$DATE_TAG" web/backend/.env
        echo "  → .env restauré depuis backup"
    fi
fi

echo -e "${GREEN}✓ Configuration web vérifiée${NC}"

#-------------------------------------------------------------------------------
# Step 7: Rebuild Rust engine if needed
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[7/8]${NC} Vérification du moteur Rust..."

if [ -d "kissbot-game-engine" ] && command -v maturin &> /dev/null; then
    echo "  → Compilation du moteur Rust..."
    cd kissbot-game-engine
    maturin develop --features python --release -q 2>/dev/null || echo "  → Rust engine: compilation ignorée (optionnel)"
    cd ..
else
    echo "  → Moteur Rust: ignoré (maturin non installé ou dossier absent)"
fi

echo -e "${GREEN}✓ Moteur Rust vérifié${NC}"

#-------------------------------------------------------------------------------
# Step 8: Final summary
#-------------------------------------------------------------------------------
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    ✅ UPGRADE TERMINÉ                     ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Sauvegardes:${NC} $BACKUP_DIR/"
echo -e "${GREEN}Branche:${NC} $BRANCH"
echo ""

if [ "$WEB_ENV_NEEDS_CONFIG" = true ]; then
    echo -e "${YELLOW}⚠ ACTION REQUISE:${NC}"
    echo "   Édite web/backend/.env avec tes credentials Twitch Dev Console"
    echo ""
fi

echo -e "${BLUE}Commandes disponibles:${NC}"
echo "  ./kissbot.sh start        → Démarrer le bot seul"
echo "  ./kissbot.sh start-web    → Démarrer le dashboard web (port 8080)"
echo "  ./kissbot.sh start-all    → Démarrer bot + web"
echo "  ./kissbot.sh status       → Voir le statut"
echo "  ./kissbot.sh logs         → Voir les logs bot"
echo "  ./kissbot.sh logs-web     → Voir les logs web"
echo ""
echo -e "${GREEN}🚀 Prêt ! Lance: ./kissbot.sh start-all${NC}"
