#!/bin/bash
# Script pour lancer les tests CI localement
# Basé sur prototype SerdaBot - adapté pour KissBot

set -e  # Exit on error

echo "🧪 KissBot - Tests CI Locaux"
echo "=================================="
echo ""

# Vérifier que le venv est activé
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Venv non activé. Activation..."
    source kissbot-venv/bin/activate
fi

echo "✅ Venv: $VIRTUAL_ENV"
echo "✅ Python: $(python --version)"
echo ""

# Installer dépendances CI si nécessaire
echo "📦 Installation dépendances CI..."
pip install -q -r tests-ci/requirements-ci.txt
echo ""

# Lancer les tests
echo "🧪 Exécution des tests CI..."
echo ""

# Tests unitaires rapides (unit)
echo "📋 [1/4] Tests unitaires..."
pytest tests-ci/ -m "unit" -v || echo "⚠️  Quelques tests unitaires échoués"

# Tests d'intégration (integration)
echo ""
echo "📋 [2/4] Tests d'intégration..."
pytest tests-ci/ -m "integration" -v || echo "⚠️  Quelques tests intégration échoués"

# Tests intelligence (intelligence)
echo ""
echo "📋 [3/4] Tests système Neural V2..."
pytest tests-ci/ -m "intelligence" -v || echo "⚠️  Quelques tests intelligence échoués"

# Tests complets (all)
echo ""
echo "📋 [4/4] Tests complets (all markers)..."
pytest tests-ci/ -v --tb=short

echo ""
echo "=================================="
echo "✅ Tests CI locaux terminés !"
echo ""
echo "💡 Tip: Utilise des markers pour filtrer:"
echo "   pytest tests-ci/ -m 'unit'         # Seulement tests rapides"
echo "   pytest tests-ci/ -m 'intelligence' # Seulement Neural V2"
echo "   pytest tests-ci/ -m 'not slow'     # Exclure tests lents"
