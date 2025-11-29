#!/bin/bash
# Migration KissBot vers VPS
# Usage: bash migrate_to_vps.sh

set -e

echo "🚀 KissBot VPS Migration Script"
echo "================================"

# 1. Vérifier que nous sommes sur le VPS (ou local pour test)
echo ""
echo "📍 Étape 1: Vérification environnement"
if [ ! -f "main.py" ]; then
    echo "❌ Erreur: Lancez ce script depuis la racine du projet KissBot"
    exit 1
fi
echo "✅ Répertoire projet détecté"

# 2. Copier les fichiers sensibles depuis le dev (manuel)
echo ""
echo "📋 Étape 2: Fichiers à copier manuellement depuis votre machine de dev:"
echo "   1. .kissbot.key (clé de chiffrement)"
echo "   2. kissbot.db (base de données avec tokens)"
echo "   3. config/config.yaml (configuration avec clés API)"
echo ""
read -p "Avez-vous copié ces 3 fichiers ? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Migration annulée. Copiez d'abord les fichiers sensibles."
    exit 1
fi

# 3. Vérifier que les fichiers existent
echo ""
echo "🔍 Étape 3: Vérification fichiers critiques"
MISSING=0
if [ ! -f ".kissbot.key" ]; then
    echo "❌ .kissbot.key manquant"
    MISSING=1
fi
if [ ! -f "kissbot.db" ]; then
    echo "❌ kissbot.db manquant"
    MISSING=1
fi
if [ ! -f "config/config.yaml" ]; then
    echo "❌ config/config.yaml manquant"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo "❌ Fichiers manquants. Migration impossible."
    exit 1
fi
echo "✅ Tous les fichiers critiques présents"

# 4. Créer les répertoires nécessaires
echo ""
echo "📁 Étape 4: Création des répertoires"
mkdir -p logs/broadcast/{el_serda,pelerin_,ekylybryum,morthycya,neemmy_os,leschevaliersdubuffet}
mkdir -p pids
mkdir -p cache
echo "✅ Répertoires créés"

# 5. Installer les dépendances Python
echo ""
echo "📦 Étape 5: Installation dépendances Python"
if [ ! -d "kissbot-venv" ]; then
    python3 -m venv kissbot-venv
fi
source kissbot-venv/bin/activate
pip install -r requirements.txt
echo "✅ Dépendances installées"

# 6. Compiler le moteur Rust
echo ""
echo "🦀 Étape 6: Compilation moteur Rust"
cd kissbot-game-engine
maturin develop --features python --release
cd ..
echo "✅ Moteur Rust compilé"

# 7. Vérifier la base de données
echo ""
echo "💾 Étape 7: Vérification base de données"
python3 -c "
from database.manager import DatabaseManager
from database.crypto import CryptoManager
crypto = CryptoManager()
db = DatabaseManager('kissbot.db', crypto)
users = db.get_all_users()
print(f'✅ Base de données OK: {len(users)} utilisateurs trouvés')
"

# 8. Test de démarrage à sec
echo ""
echo "🧪 Étape 8: Test de démarrage (dry-run)"
timeout 10 python main.py --channel el_serda --enable-hub --hub-socket /tmp/kissbot_hub.sock 2>&1 | grep -q "KissBot démarré" && echo "✅ Bot démarre correctement" || echo "⚠️  Vérifiez les logs si le bot ne démarre pas"

# 9. Instructions finales
echo ""
echo "================================"
echo "✅ Migration terminée !"
echo ""
echo "📝 Prochaines étapes:"
echo "   1. Démarrer le bot: ./kissbot.sh start"
echo "   2. Vérifier le statut: ./kissbot.sh status"
echo "   3. Voir les logs: ./kissbot.sh logs el_serda -f"
echo ""
echo "🔒 Sécurité:"
echo "   - Vérifiez que .kissbot.key n'est PAS dans git"
echo "   - Sauvegardez .kissbot.key en lieu sûr"
echo "   - Ne commitez JAMAIS config.yaml avec des tokens"
echo ""
