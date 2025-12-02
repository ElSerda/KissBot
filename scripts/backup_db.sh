#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# KissBot Database Backup Script
# ═══════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./backup_db.sh              # Backup manuel
#   ./backup_db.sh --install    # Installer le cron daily
#
# Backups stockés dans: backups/
# Rétention: 7 jours
#
# Installation cron:
#   ./backup_db.sh --install
#   # Ou manuellement: crontab -e
#   # 0 3 * * * /path/to/kissbot/scripts/backup_db.sh >> /path/to/kissbot/logs/backup.log 2>&1
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Chemin du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Fichiers
DB_FILE="$PROJECT_DIR/kissbot.db"
KEY_FILE="$PROJECT_DIR/.kissbot.key"
BACKUP_DIR="$PROJECT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════════════════
# FONCTIONS
# ═══════════════════════════════════════════════════════════════════════════

log_info() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌${NC} $1"
}

do_backup() {
    # Vérifier que la DB existe
    if [ ! -f "$DB_FILE" ]; then
        log_error "Database not found: $DB_FILE"
        exit 1
    fi

    # Créer le dossier backups si nécessaire
    mkdir -p "$BACKUP_DIR"

    # Nom du backup
    BACKUP_FILE="$BACKUP_DIR/kissbot.db.$DATE"

    # Copier la DB (avec sqlite3 .backup pour cohérence)
    if command -v sqlite3 &> /dev/null; then
        # Méthode propre avec sqlite3 (évite corruption si DB en cours d'écriture)
        sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"
        log_info "✅ Backup created (sqlite3): $BACKUP_FILE"
    else
        # Fallback: copie simple
        cp "$DB_FILE" "$BACKUP_FILE"
        log_info "✅ Backup created (cp): $BACKUP_FILE"
    fi

    # Copier aussi la clé de chiffrement (IMPORTANT!)
    if [ -f "$KEY_FILE" ]; then
        KEY_BACKUP="$BACKUP_DIR/.kissbot.key.$DATE"
        cp "$KEY_FILE" "$KEY_BACKUP"
        chmod 600 "$KEY_BACKUP"
        log_info "✅ Encryption key backed up: $KEY_BACKUP"
    else
        log_warn "No encryption key found at $KEY_FILE"
    fi

    # Cleanup: supprimer les backups > 7 jours
    find "$BACKUP_DIR" -name "kissbot.db.*" -mtime +7 -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name ".kissbot.key.*" -mtime +7 -delete 2>/dev/null || true
    log_info "🧹 Old backups cleaned (>7 days)"

    # Stats
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/kissbot.db.* 2>/dev/null | wc -l)
    BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log_info "📊 Total backups: $BACKUP_COUNT | Size: $BACKUP_SIZE"
}

install_cron() {
    CRON_CMD="0 3 * * * $SCRIPT_DIR/backup_db.sh >> $PROJECT_DIR/logs/backup.log 2>&1"
    
    # Vérifier si déjà installé
    if crontab -l 2>/dev/null | grep -q "backup_db.sh"; then
        log_warn "Cron job already installed"
        crontab -l | grep "backup_db.sh"
        exit 0
    fi
    
    # Ajouter au crontab
    (crontab -l 2>/dev/null || true; echo "$CRON_CMD") | crontab -
    log_info "✅ Cron job installed (daily at 3:00 AM)"
    log_info "📝 Added: $CRON_CMD"
    
    # Créer le dossier logs si nécessaire
    mkdir -p "$PROJECT_DIR/logs"
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

case "${1:-}" in
    --install)
        install_cron
        ;;
    --help|-h)
        echo "Usage: $0 [--install|--help]"
        echo ""
        echo "Options:"
        echo "  (none)     Run backup now"
        echo "  --install  Install daily cron job (3:00 AM)"
        echo "  --help     Show this help"
        ;;
    *)
        do_backup
        ;;
esac
