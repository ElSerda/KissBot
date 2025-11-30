# 🏗️ KissBot V2 — Architecture Modulaire

> **Vision** : Bot Twitch modulaire avec core KISS + plugins  
> **Philosophie** : Une chose simple qui fait une chose bien, puis composer  
> **Features** : Commandes dynamiques + LLM optionnel + output routing

---

## 🎯 Principe fondamental

```
┌─────────────────────────────────────────────────────────────┐
│  KissBot = Core KISS + Modules Composables                  │
│                                                               │
│  Twitch Event → Core → [Modules] → Output Router            │
│                   ↓                         ↓                │
│              Sécurité                chat|tts|obs|webhook    │
└─────────────────────────────────────────────────────────────┘
```

### Inspirations
- **Unix** : "Do one thing well, then compose"
- **VSCode** : Core léger + extensions puissantes
- **Home Assistant** : Automations modulaires
- **Streamer.bot** : Actions scriptables

---

## 🧱 Architecture en couches

### Layer 1️⃣ : Core (KISS absolu)
**Responsabilité** : Connexion stable, parsing sécurisé, routing simple

```
core/
├── irc_client.py           # IRC Twitch (keepalive, reconnect)
├── eventsub_hub.py         # WebSocket centralisé
├── message_handler.py      # Parsing + validation
├── rate_limiter.py         # Anti-spam + cooldowns
├── command_router.py       # Dispatch vers modules
└── security.py             # Filtres, tokens chiffrés
```

**Règles du Core** :
- ✅ Zéro dépendance externe (sauf Twitch API)
- ✅ 100% testable unitairement
- ✅ Logs structurés (pas de print())
- ✅ Pas de "magie" (pas de métaprog complexe)
- ✅ Documentation inline (docstrings)

---

### Layer 2️⃣ : Modules (Features branchables)

#### 📦 Module Structure
```python
# modules/example_module.py

class ExampleModule:
    """
    Description brève du module
    """
    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
    
    async def handle(self, event: BotEvent) -> Optional[BotResponse]:
        """
        Traite un événement, retourne None si pas géré
        """
        if not self.enabled:
            return None
        # ... logique métier
        return BotResponse(...)
    
    async def shutdown(self):
        """Nettoyage propre"""
        pass
```

#### 🧩 Modules disponibles

##### 1. `personality/` — Personnalité par channel
```yaml
# config/modules/personality.yaml
enabled: true
default_profile:
  tone: soft
  energy: medium
  emoji_level: some
  politeness: high
  nsfw_level: none

presets:
  soir_cru:
    tone: cru
    energy: high
    emoji_level: many
    politeness: low
    nsfw_level: light
  
  chill:
    tone: soft
    energy: low
    emoji_level: some
    politeness: high
    nsfw_level: none
```

**Commandes** :
- `!persona` → affiche profil actuel
- `!persona tone cru` → modifie un paramètre
- `!persona preset soir_cru` → applique preset
- `!persona reset` → retour défaut

---

##### 2. `llm/` — LLM on-demand
```yaml
# config/modules/llm.yaml
enabled: true
provider: openai
model: gpt-4
max_tokens_default: 90

# LLM utilisé UNIQUEMENT si :
# - Commande contient LLM:ON
# - Message classé gen_short/gen_long
# - Pas de pattern reflex match
```

**Injection de style** :
```python
# modules/llm/cloud_synapse.py

async def generate(self, prompt: str, persona: PersonalityProfile):
    style_prompt = build_style_instructions(persona)
    
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": style_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=self.config.max_tokens_default
    )
    return response.choices[0].message.content
```

---

##### 3. `custom_commands/` — Commandes dynamiques
**Le Game Changer** 🔥

```python
# Syntaxe : !addcmd <nom> "<texte>" [OPTIONS]

!addcmd greet "Coucou {user} ! 👋" LLM:OFF OUTPUT:chat

!addcmd analyse "{user} demande: {msg}" LLM:ON PERSONA:serious OUTPUT:obs+chat

!addcmd hype "LETS GOOOO 🔥" LLM:ON PERSONA:sassy OUTPUT:tts POINTS:50

!addcmd webhook "New sub!" OUTPUT:webhook:https://myapi.com/notify
```

**Variables disponibles** :
- `{user}` → username
- `{msg}` → message complet
- `{args}` → arguments commande
- `{channel}` → nom du channel
- `{points}` → points utilisateur

**Options** :
- `LLM:ON|OFF` → passe par GPT-4 ou non
- `PERSONA:cru|soft|serious|sassy` → style override
- `OUTPUT:chat|tts|obs|webhook:URL` → routing
- `POINTS:X` → coût en points

---

##### 4. `outputs/` — Output Router
```
outputs/
├── chat_output.py         # IRC Twitch
├── tts_output.py          # TTS via streamer.bot
├── obs_output.py          # OBS WebSocket
└── webhook_output.py      # HTTP POST
```

**Interface unifiée** :
```python
class OutputRouter:
    async def send(self, response: BotResponse, targets: list[str]):
        for target in targets:
            if target == "chat":
                await self.chat.send(response.text)
            elif target == "tts":
                await self.tts.speak(response.text)
            elif target == "obs":
                await self.obs.trigger_event(response.data)
            elif target.startswith("webhook:"):
                url = target.split(":", 1)[1]
                await self.webhook.post(url, response.data)
```

---

##### 5. `integrations/` — Rust + APIs externes
```
integrations/
├── game_engine/          # kissbot-game-engine (Rust)
├── steam_api/            # Steam Web API
├── rawg_api/             # RAWG Games DB
└── wikipedia/            # Wikipedia context
```

**Principe** : Chaque intégration = module isolé, désactivable

---

### Layer 3️⃣ : Configuration (YAML + DB)

```yaml
# config/kissbot.yaml

core:
  max_message_length: 500
  rate_limit_messages: 20
  rate_limit_window: 30

modules:
  personality:
    enabled: true
    config_file: config/modules/personality.yaml
  
  llm:
    enabled: true
    config_file: config/modules/llm.yaml
  
  custom_commands:
    enabled: true
    storage: database  # ou yaml
  
  outputs:
    chat: true
    tts: false        # désactivé par défaut
    obs: false
    webhook: false

channels:
  - twitch_id: "12345"
    name: "el_serda"
    modules:
      personality: true
      llm: true
      custom_commands: true
```

**Database** :
```sql
-- Table principale : commandes custom
CREATE TABLE custom_commands (
    id INTEGER PRIMARY KEY,
    channel_id TEXT NOT NULL,
    command_name TEXT NOT NULL,
    template TEXT NOT NULL,
    llm_enabled BOOLEAN DEFAULT 0,
    persona_override TEXT,
    output_targets TEXT,  -- JSON: ["chat", "tts"]
    points_cost INTEGER DEFAULT 0,
    cooldown_seconds INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, command_name)
);

-- Table : personnalité par channel
CREATE TABLE personality (
    id INTEGER PRIMARY KEY,
    channel_id TEXT UNIQUE NOT NULL,
    tone TEXT DEFAULT 'soft',
    energy TEXT DEFAULT 'medium',
    emoji_level TEXT DEFAULT 'some',
    politeness TEXT DEFAULT 'high',
    nsfw_level TEXT DEFAULT 'none',
    temp_profile TEXT,           -- JSON nullable
    temp_expires_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🚀 Pipeline de traitement

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Twitch IRC Message                                               │
│    ↓                                                                 │
│ 2. Core: Parsing + Validation (security.py, message_handler.py)    │
│    ↓                                                                 │
│ 3. Core: Rate Limiting + Cooldowns (rate_limiter.py)               │
│    ↓                                                                 │
│ 4. Core: Command Router (command_router.py)                        │
│    ↓                                                                 │
│ 5. Module: Custom Command Match ? (custom_commands/)               │
│    ├─ YES → Template rendering                                      │
│    │   ↓                                                             │
│    │   LLM:ON ? → llm/ (GPT-4 + persona)                           │
│    │   LLM:OFF → direct output                                      │
│    │                                                                 │
│    └─ NO → Classic Command (user_commands/, mod_commands/)         │
│        ↓                                                             │
│        LLM needed ? → llm/ (classifier + GPT-4)                    │
│                                                                      │
│ 6. Output Router (outputs/)                                         │
│    ├─ chat → IRC send                                               │
│    ├─ tts → Streamer.bot                                            │
│    ├─ obs → OBS WebSocket                                           │
│    └─ webhook → HTTP POST                                           │
│                                                                      │
│ 7. Analytics (metrics.jsonl, logs/)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔥 Exemples concrets

### Exemple 1 : Commande simple
```
Streamer: !addcmd bienvenue "Bienvenue {user} sur la chaîne ! 🎉" LLM:OFF OUTPUT:chat

User: !bienvenue
Bot: Bienvenue ExampleUser sur la chaîne ! 🎉
```

### Exemple 2 : LLM avec persona
```
Streamer: !addcmd conseil "{user} demande conseil: {args}" LLM:ON PERSONA:serious OUTPUT:chat

User: !conseil comment améliorer mon setup ?
Bot: ExampleUser, pour ton setup je recommande de prioriser l'audio (micro cardioïde), puis l'éclairage (ring light 18"), et enfin la caméra. L'ordre compte plus que le prix ! 🎧
```

### Exemple 3 : Multi-output
```
Streamer: !addcmd hype "ALLEZ LES COPAINS ON SE MOTIVE ! 🔥" LLM:ON PERSONA:sassy OUTPUT:chat+tts+obs

User: !hype
Bot (chat): ALLEZ LES COPAINS ON SE MOTIVE ! 🔥
Bot (TTS): [Voix synthétique lit le message]
Bot (OBS): [Déclenche animation overlay "HYPE MODE"]
```

### Exemple 4 : Webhook externe
```
Streamer: !addcmd notif_discord "New follower: {user}" OUTPUT:webhook:https://discord.com/api/webhooks/...

EventSub: [New follower event]
Bot: [POST https://discord.com/api/webhooks/... avec payload]
```

---

## 🧪 Tests & Qualité

### Tests Core (obligatoires)
```bash
# Core doit être 100% testé
pytest tests/core/
pytest tests/core/test_rate_limiter.py -v
pytest tests/core/test_security.py -v
```

### Tests Modules (optionnels mais recommandés)
```bash
pytest tests/modules/personality/
pytest tests/modules/custom_commands/
```

### Benchmarks
```bash
# Performance Rust engine
python test_rust_integration.py

# Rate limiting stress test
python test_rate_limiting.py
```

---

## 📚 Documentation requise

### Pour contributeurs
- [ ] `CONTRIBUTING.md` : Guidelines contribution
- [ ] `docs/CORE_ARCHITECTURE.md` : Détails core
- [ ] `docs/MODULE_DEVELOPMENT.md` : Créer un module
- [ ] `docs/API_REFERENCE.md` : Interfaces + types

### Pour utilisateurs
- [ ] `README.md` : Quickstart + features
- [ ] `docs/QUICKSTART.md` : Installation pas-à-pas
- [ ] `docs/CUSTOM_COMMANDS.md` : Guide !addcmd
- [ ] `docs/PERSONALITY.md` : Guide !persona
- [ ] `docs/INTEGRATIONS.md` : TTS, OBS, Streamer.bot

---

## 🎯 Roadmap V2

### Phase 1 : Refactoring Core (1 semaine)
- [x] Isoler `core/` (KISS pur)
- [ ] Extraire modules existants
- [ ] Tests unitaires core (>80% coverage)
- [ ] Documentation inline

### Phase 2 : Modules Essentiels (1 semaine)
- [ ] `personality/` : DB + !persona
- [ ] `custom_commands/` : !addcmd système
- [ ] `outputs/` : chat + TTS + OBS
- [ ] Tests modules

### Phase 3 : Intégrations Externes (1 semaine)
- [ ] Streamer.bot WebSocket
- [ ] OBS WebSocket
- [ ] Webhook router
- [ ] Documentation intégrations

### Phase 4 : Polish & Release (3 jours)
- [ ] README complet
- [ ] Quickstart vidéo
- [ ] Examples repo
- [ ] CI/CD GitHub Actions
- [ ] Release v2.0.0

---

## 🔍 Comparaison outils existants

| Feature | KissBot V2 | NightBot | StreamElements | Streamer.bot |
|---------|------------|----------|----------------|--------------|
| **Core KISS** | ✅ | ✅ | ❌ (bloated) | ✅ |
| **LLM natif** | ✅ GPT-4 | ❌ | ❌ | ❌ |
| **Personnalité custom** | ✅ per-channel | ❌ | ❌ | ❌ |
| **Commandes dynamiques** | ✅ !addcmd | ✅ basic | ✅ basic | ⚠️ (scripting) |
| **Output routing** | ✅ multi-target | ❌ chat only | ❌ chat only | ✅ |
| **Open source** | ✅ MIT | ❌ | ❌ | ❌ |
| **Rust performance** | ✅ 93x speedup | ❌ | ❌ | ❌ |
| **Modulaire** | ✅ plugins | ❌ | ❌ | ⚠️ (actions) |

**KissBot V2 = Le seul à combiner KISS + LLM + Routing + Open Source**

---

## 💎 Philosophie finale

> **"Commence simple, compose infiniment."**

Le core fait **une chose** : router des messages Twitch de manière fiable.

Les modules font **chacun une chose** : personnalité, LLM, outputs, intégrations.

Le broadcaster **compose** : `!addcmd X "..." LLM:ON PERSONA:Y OUTPUT:Z`

**C'est l'esprit Unix appliqué au streaming Twitch.**

---

## 🎯 Objectifs long terme

KissBot V2 :
1. Bot modulaire utile pour streamers tech
2. Architecture propre et maintenable
3. Open source et documenté
4. Extensible par la communauté

Croissance organique, pas de target artificielle.

---

**Date** : 30 novembre 2025  
**Version** : 2.0.0-alpha  
**Auteur** : ElSerda + GitHub Copilot (Claude Sonnet 4.5)  
**Licence** : MIT
