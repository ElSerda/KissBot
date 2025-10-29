# 🔧 Debug Scripts

Scripts de debug/test standalone pour développement rapide.

## 📋 Usage

```bash
# Activer le venv
source kissbot-venv/bin/activate

# Lancer un script de debug
python debug/test_gamecategory.py
```

## 📁 Scripts disponibles

### `test_gamecategory.py`
Teste la commande `!gamecategory` (auto-détection du jeu du stream):
- **Mode 1**: Test de la logique avec mocks (rapide)
- **Mode 2**: Test avec vraie API Twitch (nécessite credentials)

**Modifier le script pour tester différents cas:**
```python
# Ligne 30: Change le broadcaster
broadcaster_name = "el_serda"  # Ton channel

# Ligne 35: Test stream offline
mock_stream_active = False

# Ligne 36: Change le jeu
mock_game_name = "Hades"

# Ligne 101: Test avec un vrai channel
broadcaster_name = "elserda"
```

## 🎯 Workflow de debug

1. **Develop**: Modifier le code de la commande
2. **Debug**: Lancer `python debug/test_X.py` pour tester rapidement
3. **Validate**: Une fois que ça marche, écrire les tests unitaires
4. **Commit**: Push avec les tests qui passent

## 📝 Notes

- Ces scripts ne sont **PAS** des tests unitaires
- Ils sont pour le **développement rapide** et le **debugging**
- Ne pas commit de credentials dans ces fichiers
- Utiliser `.gitignore` si tu crées des fichiers de test persos
