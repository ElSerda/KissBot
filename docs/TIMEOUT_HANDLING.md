# Gestion des Timeouts - Phase 2.6

## 🎯 Objectif

Protéger le bot contre les blocages causés par:
- Requêtes Helix API lentes
- Envoi IRC bloqué
- **LLM inférence longue (Phase 3)**
- Problèmes réseau

Sans gestion timeout, un seul appel bloqué peut freezer tout le bot. 🧊

---

## ⏱️ Configuration

**Fichier**: `config/config.yaml`

```yaml
# ⏱️ Timeouts pour les transports (Phase 2.6)
timeouts:
  irc_send: 5.0       # Timeout envoi message IRC
  helix_request: 8.0  # Timeout requête Helix API
  llm_inference: 30.0 # Timeout inférence LLM (peut être long)
```

### Valeurs recommandées

| Transport | Timeout | Justification |
|-----------|---------|---------------|
| **IRC Send** | 5s | Message chat = rapide. Si >5s → problème réseau |
| **Helix API** | 8s | API publique Twitch, devrait répondre <5s normalement |
| **LLM Inference** | 30s | OpenAI peut être lent (GPT-4), local LLM encore plus |

---

## 🔧 Implémentation

### IRC Client

**Fichier**: `twitchapi/transports/irc_client.py`

```python
async def _handle_outbound_message(self, msg: OutboundMessage) -> None:
    """Phase 2.6: Envoie un message via IRC avec timeout"""
    try:
        # Phase 2.6: Envoyer avec timeout
        await asyncio.wait_for(
            self.chat.send_message(msg.channel, msg.text),
            timeout=self.irc_send_timeout
        )
        LOGGER.info(f"✅ Sent to #{msg.channel}")
        
    except asyncio.TimeoutError:
        LOGGER.error(f"⏱️ Timeout envoi IRC à #{msg.channel} après {self.irc_send_timeout}s")
    except Exception as e:
        LOGGER.error(f"❌ Erreur envoi IRC: {e}")
```

**Comportement**:
- Si timeout → Log erreur + **message suivant continue** (pas de blocage)
- User ne voit pas le message (timeout), mais bot reste opérationnel
- Alternative: Retry logic (à implémenter en Phase 3 si besoin)

### Helix Client

**Fichier**: `twitchapi/transports/helix_readonly.py`

```python
async def get_stream(self, user_login: str) -> Optional[dict]:
    """Récupère stream info avec timeout"""
    try:
        # Phase 2.6: Wrap avec timeout
        async def _fetch():
            streams = []
            async for stream in self.twitch.get_streams(user_login=[user_login]):
                streams.append(stream)
            return streams
        
        streams = await asyncio.wait_for(_fetch(), timeout=self.helix_timeout)
        # ... process streams ...
        
    except asyncio.TimeoutError:
        LOGGER.error(f"⏱️ Timeout get_stream({user_login}) après {self.helix_timeout}s")
        return None
    except Exception as e:
        LOGGER.error(f"Erreur get_stream: {e}")
        return None
```

**Comportement**:
- Si timeout → Return `None` (comme si stream offline)
- Command handler reçoit `None` et peut répondre "Erreur API, réessaie plus tard"

### Main.py

**Fichier**: `main.py`

```python
# Phase 2.6: Charger les timeouts depuis config
timeouts = config.get("timeouts", {})
irc_send_timeout = timeouts.get("irc_send", 5.0)
helix_timeout = timeouts.get("helix_request", 8.0)

# Phase 2.6: Helix Read-Only (avec timeout)
helix = HelixReadOnlyClient(twitch_app, bus, helix_timeout=helix_timeout)

# Phase 2.6: IRC Client (avec timeout)
irc_client = IRCClient(
    twitch=twitch_bot,
    bus=bus,
    bot_user_id=bot_user_id,
    bot_login=bot_token.user_login,
    channels=irc_channels,
    irc_send_timeout=irc_send_timeout
)
```

---

## 🧪 Scénarios de Test

### Test 1: IRC Timeout (simulation)

```python
# Dans IRC Client, temporairement:
async def _handle_outbound_message(self, msg: OutboundMessage):
    await asyncio.sleep(10)  # Simuler blocage
    await self.chat.send_message(msg.channel, msg.text)
```

**Résultat attendu**:
```
📤 Tentative envoi IRC à #el_serda: pong
⏱️ Timeout envoi IRC à #el_serda après 5.0s: pong
```

### Test 2: Helix Timeout (réseau lent)

Si Twitch API lente:
```
[HELIX] get_stream(el_serda)
⏱️ Timeout get_stream(el_serda) après 8.0s
```

User reçoit: "❌ Erreur API, réessaie plus tard"

### Test 3: LLM Timeout (Phase 3)

Quand LLM intégré:
```python
# Dans LLM handler:
response = await asyncio.wait_for(
    openai.chat.completions.create(...),
    timeout=llm_timeout
)
```

Si OpenAI prend >30s:
```
⏱️ Timeout LLM inference après 30.0s
```

User reçoit: "🧠 Mon cerveau lag, réessaie !"

---

## 🚨 Cas Critiques

### Cas 1: Timeout trop court

**Problème**:
```yaml
timeouts:
  helix_request: 0.5  # Trop court !
```

**Symptôme**:
- Timeout à chaque requête Helix
- Bot répond toujours "Erreur API"

**Solution**: Augmenter timeout à 8s minimum

### Cas 2: Timeout trop long

**Problème**:
```yaml
timeouts:
  irc_send: 60.0  # Trop long !
```

**Symptôme**:
- Si problème réseau IRC → Bot bloqué 60s
- Messages en queue s'accumulent

**Solution**: IRC devrait être <10s max

### Cas 3: Pas de timeout

**Problème**: Code sans `asyncio.wait_for()`

**Symptôme**:
- Bot freeze complètement
- Plus de réponse à aucune commande
- Nécessite redémarrage

**Impact**: **CRITIQUE** pour LLM Phase 3

---

## 📊 Métriques à Surveiller

En production, tracker:

1. **Taux de timeout IRC**:
   - Si >5% → Problème réseau ou Twitch instable
   
2. **Taux de timeout Helix**:
   - Si >1% → Twitch API lente ou problème réseau
   
3. **Latence moyenne**:
   - IRC: <500ms normalement
   - Helix: <3s normalement
   - LLM: 5-15s (OpenAI), 1-5s (local)

4. **Timeout LLM** (Phase 3):
   - Si >10% → Modèle trop lent ou prompt trop complexe

---

## 🔮 Phase 3: LLM Integration

Quand LLM sera branché, timeout handling devient **CRITIQUE**:

### Scénario sans timeout

```python
# ❌ DANGER: Pas de timeout
response = await openai.chat.completions.create(...)
# Si OpenAI freeze → Bot freeze
```

User tape `!ask quoi de neuf?` → Bot **ne répond jamais** → User spam → Queue explose

### Scénario avec timeout

```python
# ✅ SAFE: Avec timeout
try:
    response = await asyncio.wait_for(
        openai.chat.completions.create(...),
        timeout=llm_timeout
    )
except asyncio.TimeoutError:
    await bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        text="🧠 Mon cerveau lag, réessaie !"
    ))
```

User reçoit feedback + bot continue de fonctionner

---

## 🎓 Best Practices

1. **Toujours wrap les appels externes**:
   - API Twitch (Helix)
   - OpenAI / LLM
   - Bases de données
   - HTTP requests

2. **Timeouts adaptatifs**:
   - Court pour IRC (5s)
   - Moyen pour API (8s)
   - Long pour LLM (30s)

3. **Log timeout avec contexte**:
   ```python
   LOGGER.error(f"⏱️ Timeout {operation} après {timeout}s: {context}")
   ```

4. **Fallback gracieux**:
   - IRC timeout → Log + skip message
   - Helix timeout → Return None
   - LLM timeout → Message d'erreur friendly

5. **Monitoring production**:
   - Tracker taux de timeout
   - Alerter si >seuil
   - Ajuster timeouts si nécessaire

---

## 🔗 Références

- **asyncio.wait_for()**: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
- **Phase 2 Architecture**: `docs/PHASE2_ARCHITECTURE.md`
- **Config**: `config/config.yaml`

---

## ✅ Checklist Phase 2.6

- [x] Config `timeouts` section ajoutée
- [x] IRC Client timeout handling
- [x] Helix Client timeout handling
- [x] Main.py passe timeouts depuis config
- [x] Tests syntaxe OK
- [x] Documentation créée
- [ ] **Test avec bot lancé** (prochain step)
- [ ] Test simulation timeout (optionnel)

---

**Phase 2.6 Status**: ✅ CODE COMPLETE, prêt pour test live

**Next**: Tester bot avec timeouts + Préparer Phase 3 (LLM + Game Lookup)
