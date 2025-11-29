#!/bin/bash
# Nettoyage intelligent avant push git
# Usage: bash scripts/cleanup_before_push.sh [--dry-run]

set -e

DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
    echo "🔍 MODE DRY-RUN (aucun fichier ne sera supprimé)"
fi

echo "🧹 KissBot Cleanup Script"
echo "========================="
echo ""

# Compteurs
MOVED=0
DELETED=0
KEPT=0

# Fonction pour déplacer vers archive
move_to_archive() {
    local file=$1
    local reason=$2
    
    if [ ! -f "$file" ]; then
        return
    fi
    
    local dest="archive/legacy/$(basename $file)"
    
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY] Archiver: $file → $dest ($reason)"
    else
        mkdir -p archive/legacy
        mv "$file" "$dest"
        echo "  ✅ Archivé: $file ($reason)"
    fi
    MOVED=$((MOVED + 1))
}

# Fonction pour supprimer
delete_file() {
    local file=$1
    local reason=$2
    
    if [ ! -f "$file" ]; then
        return
    fi
    
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY] Supprimer: $file ($reason)"
    else
        rm -f "$file"
        echo "  🗑️  Supprimé: $file ($reason)"
    fi
    DELETED=$((DELETED + 1))
}

echo "📋 1. Fichiers de test à la racine (obsolètes)"
echo "----------------------------------------------"
move_to_archive "test_rate_limiting.py" "test obsolète"
move_to_archive "test_rust_integration.py" "doublon de tests-ci"
move_to_archive "test_rust_wrapper.py" "doublon de tests-ci"

echo ""
echo "📋 2. Tests-local (développement uniquement)"
echo "----------------------------------------------"
echo "  ℹ️  Ces tests ne sont PAS pushés (dans .gitignore)"
echo "  ℹ️  Aucune action nécessaire"
KEPT=$((KEPT + 85))

echo ""
echo "📋 3. Répertoires legacy déjà archivés"
echo "----------------------------------------------"
echo "  ✅ _scripts_legacy/ (1 fichier) - OK, déjà archivé"
echo "  ✅ archive/ (162 fichiers) - OK, ne sera pas pushé"
echo "  ✅ braindev/ (6 fichiers) - OK, documentation R&D"
KEPT=$((KEPT + 169))

echo ""
echo "📋 4. Fichiers temporaires/backup"
echo "----------------------------------------------"
delete_file "*.backup" "backup temporaire"
delete_file "*.old" "ancien fichier"
delete_file "*.tmp" "fichier temporaire"
delete_file ".tio.tokens.json.backup" "backup tokens"

# Nettoyer les pycache
echo ""
echo "📋 5. Cache Python (__pycache__)"
echo "----------------------------------------------"
if [ "$DRY_RUN" = false ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    echo "  🗑️  Supprimé: tous les __pycache__ et *.pyc"
else
    echo "  [DRY] Supprimer: tous les __pycache__ et *.pyc"
fi

echo ""
echo "========================="
echo "📊 Résumé"
echo "========================="
echo "  📦 Archivés: $MOVED fichiers"
echo "  🗑️  Supprimés: $DELETED fichiers"
echo "  ✅ Conservés: $KEPT fichiers"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "⚠️  Mode dry-run activé. Pour appliquer:"
    echo "   bash scripts/cleanup_before_push.sh"
else
    echo "✅ Nettoyage terminé !"
    echo ""
    echo "📝 Prochaines étapes:"
    echo "   1. Vérifier les fichiers stagés: git status"
    echo "   2. Commiter: git add . && git commit -m 'fix: cleanup + classifier simplification'"
    echo "   3. Push: git push"
fi
