# 🎬 Debug Streaming Mode

## Description

Active l'affichage en temps réel des chunks de streaming LLM dans le terminal.

Utile pour :
- 🔍 **Debug** : Voir les chunks arriver progressivement
- 🎓 **Comprendre** : Visualiser le streaming en action
- ⚡ **Performance** : Identifier latence par chunk
- 🧪 **Test** : Valider GPU layers bridés (+ chunks = visible)
- 🎬 **Production** : Voir chunks en live pendant que le bot tourne

## Activation

### Option 1 : Boolean (recommandé pour tests)
```yaml
# config/config.yaml
llm:
  debug_streaming: true  # Affiche chunks en temps réel
```

### Option 2 : String (recommandé pour production)
```yaml
# config/config.yaml
llm:
  stream_response_debug: "on"  # Voir chunks en live
  # stream_response_debug: "off"  # Production propre (défaut)
```

**Défaut :** `false` / `"off"` (pas de debug)

**Note :** Les deux options sont équivalentes (OR logic). Utiliser `stream_response_debug: "on"` est plus parlant en production.

## Exemple de sortie

```
🌊 [STREAMING START] Pourquoi les développeurs confondent-ils Halloween et Noël ? Parce que Oct 31 == Dec 25 ! [STREAMING END] finish_reason=stop
```

## Tests

```bash
# Test visuel streaming
python tests-local/test_streaming_debug_visual.py

# Test pipeline complet
python -m pytest tests-local/test_streaming_real.py -v
```

## Notes

- **Production** : Laisser `debug_streaming: false` (pas de spam console)
- **Dev/Test** : Activer pour voir chunks LLM en direct
- **GPU bridé** : Plus de chunks visibles (latence + lente = + découpage)
- **Accumulation** : Chunks affichés terminal ≠ chat (pas de spam Twitch)

## Architecture

```
LM Studio → Streaming chunks → LocalSynapse
                               ↓
                    if debug_streaming=True:
                        print(chunk)  ← Terminal
                               ↓
                    Accumulation complète
                               ↓
                    Message final → Twitch chat
```

**Résultat :** Terminal voit chunks progressifs, Twitch voit message complet.
