# KissBot – Architecture V2 (Core + Modules)

> **TL;DR**  
> KissBot v2 = un **core ultra simple & robuste** + une **couche modulaire** (LLM, TTS, OBS, etc.)  
> Tout ce qui est "magique" ou spécifique à un use-case va dans des **modules**, pas dans le core.

---

## 1. Objectifs d'architecture

- **KISS** – Le core fait le minimum vital **parfaitement** :
  - Connexion Twitch (IRC + EventSub)
  - Parsing des messages
  - Routing de commandes
  - Sécurité de base (rate limit, permissions)
  
- **Modulaire** – Tout le reste se branche :
  - LLM (local ou cloud)
  - Système de persona
  - Commandes custom
  - Intégrations (Streamer.bot, TTS, webhooks, etc.)
  
- **Par chaîne** – Chaque chaîne Twitch a :
  - Sa config
  - Ses commandes custom
  - Sa "personnalité"
  
- **Auditable** – Le core doit rester lisible, diffable, auditable en sécurité.

- **Extensible** – Un module = un dossier + un README + un petit registre → facile à PR.

### Inspirations
- **Unix** : "Do one thing well, then compose"
- **VSCode** : Core léger + extensions puissantes
- **Home Assistant** : Automations modulaires
- **Streamer.bot** : Actions scriptables

---

## 2. Vue d'ensemble

Flux logique global :

```
       ┌──────────────────┐
       │  Twitch (IRC +   │
       │  EventSub/Helix) │
       └────────┬─────────┘
                │ events / messages
                ▼
        ┌───────────────┐
        │   Core Input  │  (= clients + normalisation)
        │   (irc/event) │
        └──────┬────────┘
               │ ChatMessage / TwitchEvent unifié
               ▼
        ┌───────────────┐
        │ CommandRouter │  (détecte !commande, args, contexte)
        └──────┬────────┘
    core cmd   │     custom cmd
───────────────┼────────────────────────────
               │
         ┌─────▼───────────┐
         │ CustomCommand   │
         │   Engine        │
         └─────┬───────────┘
               │
               │   (optionnel)
               ▼
       ┌───────────────────┐
       │   LLM Engine      │  (ON/OFF par commande + persona)
       └────────┬──────────┘
                │ texte final
                ▼
        ┌──────────────────┐
        │  Output Router   │
        └─────┬─────┬──────┘
              │     │
              │     │
        chat / TTS / OBS / webhook / etc. (modules)
```

---

## 3. Structure des dossiers

```
kissbot/
  core/
    __init__.py
    config.py
    irc_client.py           # IRC Twitch (keepalive, reconnect)
    eventsub_hub.py         # WebSocket centralisé
    twitch_models.py        # ChatMessage, TwitchEvent, User, ChannelContext
    message_parser.py       # Parsing + validation
    command_router.py       # Dispatch vers modules
    rate_limiter.py         # Anti-spam + cooldowns
    permissions.py          # Vérifications mod/VIP/broadcaster
    storage.py              # Accès BDD générique (tokens, settings)

  modules/
    custom_commands/
      __init__.py
      engine.py             # !kbadd / !kbdel / résolution
      models.py             # Représentation commande utilisateur
      README.md

    personality/
      __init__.py
      db.py                 # PersonalityDB par channel
      style_engine.py       # Profil style (soft/cru, ton, etc.)
      README.md

    llm/
      __init__.py
      engine.py             # Abstraction LLM: local, OpenAI, autre
      providers/
        openai_client.py
        local_client.py
      README.md

    outputs/
      chat/
        __init__.py
        handler.py
      tts/
        __init__.py
        streamerbot_adapter.py
      obs/
        __init__.py
        streamerbot_adapter.py
      webhook/
        __init__.py
        client.py

    examples/
      game_info/            # Ancien !gc / !gi, exemple de module
        __init__.py
        commands.py
        README.md

  database/
    ...

  docs/
    ARCHITECTURE_V2.md      # (ce fichier)
    MODULE_HOWTO.md         # Comment faire un module & PR
    MIGRATION_PLAN.md       # Plan migration V1 → V2
```

---

## 4. Core vs Modules

### 4.1 Ce que le core **doit** faire

- ✅ Gérer la connexion Twitch (IRC + EventSub/Helix)
- ✅ Normaliser tous les événements dans des modèles (`ChatMessage`, `TwitchEvent`)
- ✅ Router les commandes vers :
  - Commandes core (`!ping`, `!uptime`, `!help`, `!kbadd`, `!kbdel`)
  - `CustomCommandEngine` pour le reste
- ✅ Appliquer :
  - Rate limiting global / par user
  - Checks de permission (mod, VIP, broadcaster)
  - Logs de base

**Règles du Core** :
- ✅ Zéro dépendance externe (sauf Twitch API)
- ✅ 100% testable unitairement
- ✅ Logs structurés (pas de `print()`)
- ✅ Pas de "magie" (pas de métaprog complexe)
- ✅ Documentation inline (docstrings)

### 4.2 Ce que le core ne doit **PAS** faire

⚠️ **Important** :
- ❌ Parler LLM directement
- ❌ Faire OBS/TTS lui-même
- ❌ Contenir de la logique métier spécifique à un stream

**Tout ça va dans les modules.**

### 4.3 Ce que les modules **peuvent** faire

✅ Ajouter des commandes :
- Ex: `modules/game_info` expose `!gc` / `!gi`
- Ex: `modules/personality` expose `!persona`

✅ Brancher des outputs :
- Envoyer à Streamer.bot, TTS, OBS, webhook, etc.

✅ Ajouter des pipelines :
- `ChatMessage → LLM → réponse chat`
- `Event new_sub → TTS + animation OBS`

**Interface module** :
```python
# modules/some_module/__init__.py
def register(registry):
    registry.register_command("cmd_name", handler, permissions=...)
    registry.register_event_handler("on_sub", on_sub_handler)
```

Chaque module déclare un petit `README.md` avec :
- Ce que fait le module
- Comment l'activer
- Quelles variables d'environnement / configs il utilise

---

## 5. Custom Commands & Pipeline LLM

### 5.1 Commandes dynamiques (concept)

**Objectif** : Que le broadcaster puisse définir une commande **sans coder** :

```bash
!kbadd !roast llm:on persona:troll prompt:"insulte gentiment {user}" output:chat
!kbadd !trad llm:off lang:en input:{user_message} output:chat
!kbadd !hype llm:on persona:hyper output:chat+tts cost:50points
```

Chaque définition de commande décrit :
- **trigger** : `!roast`, `!trad`, etc.
- **options** :
  - `llm:on/off`
  - `persona:<name>`
  - `prompt:` ce qui est envoyé au LLM
  - `output:` une ou plusieurs destinations (`chat`, `tts`, `obs`, `webhook`, …)
  - `cost:` (optionnel) coût en points de chaîne

Le `CustomCommandEngine` stocke ça en BDD (perso par channel).

### 5.2 Pipeline logique pour une commande custom

Exemple pour `!roast` :

```
ChatMessage("!roast @pseudo") 
  ↓
CommandRouter détecte "roast" 
  ↓
CustomCommandEngine
  → Récupère définition de !roast pour cette chaîne
  → Vérifie:
    - Permissions
    - Coût en points
    - Cooldown
  → Construit contexte LLM:
    - persona: "troll"
    - prompt: "insulte gentiment @pseudo"
    - contraintes de sécurité (no hate, no harcèlement)
  → Si llm:on → LLM Engine → réponse
  → Sinon     → formatage simple
  ↓
Output Router:
  → chat
  → (optionnel) TTS via module outputs/tts
```

---

## 6. Modules essentiels

### 6.1 `personality/` — Personnalité par channel

**Philosophy** : La personnalité ne doit pas être un corpus de phrases copiées/collées,  
mais un **profil de style** :
- Niveau "cru" vs "soft"
- Registre (casual / neutre / soutenu)
- Densité d'emojis
- Énergie (calme vs excité)
- Niveau de sarcasme / troll

Chaque chaîne a sa `PersonalityDB`, stockée chiffrée comme tes autres données.

**Config exemple** :
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
```bash
!persona set tone:casual spice:cru emojis:high
!persona set tone:soft spice:light emojis:low
!persona           # Affiche profil actuel
!persona reset     # Retour défaut
```

Le `LLM Engine` reçoit toujours le profil de style, **pas des phrases brutes**.

---

### 6.2 `llm/` — LLM on-demand
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
# modules/llm/engine.py

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

**Important** : 
- Reçoit uniquement le contexte nécessaire (jamais de secrets)
- Instructions système pour respecter les règles Twitch / anti-harcèlement

---

### 6.3 `custom_commands/` — Commandes dynamiques

**Syntaxe** :
```bash
!kbadd <cmd> [OPTIONS]        # Create
!kbedit <cmd> <key> <value>   # Update
!kbdel <cmd>                  # Delete
!kblist                       # List all
!kbinfo <cmd>                 # Show config
```

**Variables disponibles** :
- `{user}` → username
- `{msg}` → message complet
- `{args}` → arguments commande
- `{channel}` → nom du channel
- `{points}` → points utilisateur

**Options** :
- `llm:on|off` → passe par LLM ou non
- `persona:<name>` → style override
- `prompt:"..."` → template pour LLM
- `output:chat|tts|obs|webhook:URL` → routing
- `cost:X` → coût en points

---

### 6.4 `outputs/` — Output Router
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

### 6.5 `integrations/` — Rust + APIs externes
```
integrations/
├── game_engine/          # kissbot-game-engine (Rust)
├── steam_api/            # Steam Web API
├── rawg_api/             # RAWG Games DB
└── wikipedia/            # Wikipedia context
```

**Principe** : Chaque intégration = module isolé, désactivable

---

## 7. Sécurité & Isolation

### Tokens & secrets
- ✅ Déjà chiffrés (Fernet) en BDD → on garde
- ✅ `.kissbot.key` indispensable pour déchiffrage

### OAuth & Pipeline des Scopes

**Problème résolu (Dec 6, 2025)** : `!kbupdate` nécessitait `moderator:manage:announcements` scope

**Pipeline complet :**

1. **Configuration des Scopes** (`main.py` lignes 520-574)
   ```python
   # Mode YAML (scopes statiques)
   bot_scopes = [AuthScope.CHAT_READ, AuthScope.CHAT_WRITE, ...]
   
   # Mode DB (scopes dynamiques)
   bot_token = db.get_user_token(bot_user_id, "bot")
   scopes = convert_scope_strings_to_enums(bot_token.scopes)  # ["chat_read", ...] → AuthScope enums
   ```

2. **Chargement du Token** (`main.py` lignes 560-568)
   ```python
   await twitch_bot.set_user_authentication(
       token=bot_token.access_token,
       scope=scopes,                    # ← Scopes appliqués ici
       refresh_token=bot_token.refresh_token,
       validate=True                     # ← Valide token ET scopes
   )
   ```

3. **Force Refresh des Scopes** (`main.py` lignes 578-599) ⭐ **CRUCIAL**
   ```python
   # Si les scopes ont été ajoutées APRÈS le dernier refresh,
   # pyTwitchAPI ne les chargera que si on force un refresh du token
   async for user in twitch_bot.get_users():
       LOGGER.info(f"✅ Bot user verified: {user.login} (ID: {user.id})")
       break
   ```
   **Pourquoi ?** `set_user_authentication(validate=True)` ne force refresh que si token expiré.
   Si token est frais, pyTwitchAPI peut garder l'ancienne liste de scopes en mémoire.
   Appel Helix = force pyTwitchAPI à vérifier que le token a tous les scopes requis.

4. **Ajout de Scopes** (via `scripts/update_bot_scopes.py`)
   ```bash
   python scripts/update_bot_scopes.py
   # → Ouvre navigateur OAuth
   # → User authentifie le bot avec NEW scopes
   # → Callback capture la response et met à jour kissbot.db
   # → Au prochain redémarrage avec --use-db : les scopes sont chargés
   ```

5. **Utilisation des Scopes** (exemple : `!kbupdate` API call)
   ```python
   # broadcast.py ligne 274
   await twitch_client.send_chat_announcement(
       broadcaster_id=msg.channel_id,      # Qui reçoit l'annonce
       moderator_id="1209350837",          # Qui l'envoie (MUST = token user!)
       message=announce_msg,
       color="purple"
   )
   # ⚠️ CRITICAL: moderator_id DOIT = l'ID du user du token authentifié
   # Sinon Twitch rejette avec "incorrect user authorization"
   ```

**Checklist pour ajouter un nouveau Scope :**
- [ ] Identifier le scope requis (ex: `moderator:manage:announcements`)
- [ ] Ajouter au `scripts/update_bot_scopes.py` dans la liste des 16 scopes
- [ ] Exécuter `python scripts/update_bot_scopes.py` et s'authentifier
- [ ] Vérifier le scope dans `kissbot.db` : `SELECT scopes FROM users WHERE user_id='bot_id'`
- [ ] Redémarrer avec `./kissbot.sh start --use-db`
- [ ] Vérifier les logs : `✅ Bot user verified` + `✅ Token has valid scopes`
- [ ] Tester la commande qui utilise le scope (ex: `!kbupdate test`)

**Debugging :**
```bash
# Voir les scopes en mémoire (logs)
tail -f logs/broadcast/el_serda/instance.log | grep -E "(Force refresh|Bot user verified|Token has valid)"

# Vérifier scopes en DB
sqlite3 kissbot.db "SELECT user_id, token_type, scopes FROM users WHERE user_id='1209350837';"

# Forcer refresh du token au redémarrage
./kissbot.sh stop && ./kissbot.sh start --use-db
```

### Modules
- ✅ N'ont accès qu'au strict minimum (contexte, config de channel)
- ❌ Pas d'`eval`, pas d'`exec`, pas de SQL direct sans passer par le core

### LLM
- ✅ Reçoit uniquement le contexte nécessaire (jamais de secrets)
- ✅ Instructions système pour respecter les règles Twitch / anti-harcèlement

---

## 8. Configuration (YAML + DB)

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

## 9. Pipeline de traitement complet

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

## 10. Exemples concrets

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

## 11. Roadmap V2

### Phase 1 – Isolation du core
- Extraire tout ce qui est "Twitch + routing" dans `core/`
- Marquer ce qui est "module candidate" (`!gc`, `!gi`, LLM, TTS, etc.)

### Phase 2 – Modules essentiels
- `modules/custom_commands` (+ `!kbadd` / `!kbdel`)
- `modules/llm` (abstraction OpenAI/local)
- `modules/personality`
- `modules/outputs/chat` + `outputs/tts` (streamer.bot)

### Phase 3 – Polish & doc
- `ARCHITECTURE_V2.md` (ce fichier)
- `MODULE_HOWTO.md` (comment faire un module & une PR)
- Exemples :
  - `modules/examples/game_info` (ancien `!gc` / `!gi`)
  - `modules/examples/roast`
  - `modules/examples/trad`

### Phase 4 – Ecosystème
- "Module Gallery" dans le README
- Labels GitHub : `module-idea`, `good first issue`

Voir `MIGRATION_PLAN.md` pour le plan détaillé.

---

## 12. Tests & Qualité

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

## 15. Licence & usage

- Le **core** reste sous ta licence actuelle (non-commercial pour usage pro / SaaS)
- Les **modules communautaires** peuvent rester sous la même licence, sauf mention contraire
- **Objectif** : Laissé libre pour streamers & devs, tout en évitant les gros abus commerciaux non déclarés

---

## 16. Philosophie finale

> **"Commence simple, compose infiniment."**

Le core fait **une chose** : router des messages Twitch de manière fiable.

Les modules font **chacun une chose** : personnalité, LLM, outputs, intégrations.

Le broadcaster **compose** : `!kbadd X "..." llm:on persona:Y output:Z`

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
**Auteurs** : ElSerda + GitHub Copilot (Claude Sonnet 4.5)  
**Licence** : Voir LICENSE
