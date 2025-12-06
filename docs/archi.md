# 🏗️ KissBot Stack Architecture - Documentation Complète

> **Date**: 5 décembre 2025  
> **Version**: 4.1 - Découverte EventSub Chat  
> **Auteur**: ElSerda + Copilot Audit

---

## 📚 Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Séquence de démarrage](#2-séquence-de-démarrage-première-connexion)
3. [Authentification OAuth](#3-authentification-oauth)
4. [IRC Client](#4-irc-client)
5. [EventSub](#5-eventsub)
6. [Database Manager](#6-database-manager)
7. [Supervisor](#7-supervisor)
8. [Flux de données](#8-flux-de-données)
9. [Gestion des erreurs](#9-gestion-des-erreurs)
10. [**EventSub Chat vs IRC** ⭐](#10-eventsub-chat-vs-irc---découverte-majeure) *(Nouveau!)*
11. [Tests de robustesse](#11-tests-de-robustesse-ab)

---

## 1. Vue d'ensemble

### Architecture globale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COUCHE SUPERVISION                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     supervisor_v1.py (optionnel)                     │   │
│  │   • Spawne N process (1 par channel)                                │   │
│  │   • Health check 30s                                                 │   │
│  │   • Auto-restart avec backoff                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COUCHE APPLICATION                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           main.py                                    │   │
│  │   • Parse args (--channel, --use-db, --eventsub)                    │   │
│  │   • Load tokens (DB ou YAML)                                         │   │
│  │   • Configure refresh callback                                       │   │
│  │   • Initialise composants                                            │   │
│  │   • Run event loop                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│    IRC Client     │    │  EventSub Client  │    │   Helix Client    │
│  irc_client.py    │    │ hub_eventsub.py   │    │ helix_readonly.py │
│                   │    │ eventsub_hub.py   │    │                   │
│  • Chat recv/send │    │ • Stream online   │    │  • API REST       │
│  • Commands       │    │ • Stream offline  │    │  • get_users()    │
│  • Permissions    │    │ • IPC routing     │    │  • get_streams()  │
└───────────────────┘    └───────────────────┘    └───────────────────┘
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COUCHE TRANSPORT                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          pyTwitchAPI                                 │   │
│  │   • Chat() - IRC WebSocket                                          │   │
│  │   • Twitch() - Helix API + OAuth                                    │   │
│  │   • EventSubWebsocket() - EventSub WebSocket                        │   │
│  │                                                                      │   │
│  │   ✅ Reconnexion auto         ✅ Token refresh auto                 │   │
│  │   ✅ Keepalive PING/PONG      ✅ Rate limiting                      │   │
│  │   ✅ Backoff exponentiel      ⚠️ Callback save: à nous             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COUCHE PERSISTANCE                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      database/manager.py                             │   │
│  │   • SQLite + WAL mode                                               │   │
│  │   • Tokens chiffrés (Fernet)                                        │   │
│  │   • Tracking refresh failures                                        │   │
│  │   • Auto needs_reauth après 3 échecs                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Fichiers clés

| Fichier | Rôle | Lignes |
|---------|------|--------|
| `main.py` | Entry point, orchestration | ~1000 |
| `supervisor_v1.py` | Multi-process manager | ~900 |
| `twitchapi/transports/irc_client.py` | IRC Chat | ~870 |
| `eventsub_hub.py` | Hub EventSub centralisé | ~1100 |
| `twitchapi/transports/hub_eventsub_client.py` | Client IPC vers Hub | ~250 |
| `database/manager.py` | Tokens + persistence | ~1200 |
| `core/ipc_protocol.py` | Protocol Hub ↔ Bots | ~540 |

---

## 2. Séquence de démarrage (Première connexion)

### 2.1 Démarrage via Supervisor (mode multi-process)

```bash
./kissbot.sh start --use-db
```

```
┌─────────────────────────────────────────────────────────────────────┐
│ kissbot.sh                                                          │
│  1. Source le venv                                                  │
│  2. Lance supervisor_v1.py                                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ supervisor_v1.py::main()                                            │
│  1. Parse config.yaml → liste des channels                         │
│  2. Pour chaque channel:                                            │
│     └── BotProcess(channel).start()                                 │
│         └── subprocess.Popen(["python", "main.py", "--channel", ch])│
│  3. Démarre health_check_loop() (async, 30s interval)              │
└─────────────────────────────────────────────────────────────────────┘
```

**Code source** (`supervisor_v1.py` L50-85):
```python
def start(self) -> bool:
    venv_python = Path("kissbot-venv/bin/python")
    python_cmd = str(venv_python) if venv_python.exists() else "python3"
    
    cmd = [
        python_cmd,
        "main.py",
        "--channel", self.channel,
        "--config", self.config_path,
        "--eventsub", self.eventsub_mode
    ]
    
    if self.use_db:
        cmd.extend(["--use-db", "--db", self.db_path])
    
    self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.start_time = time.time()
    LOGGER.info(f"✅ {self.channel}: Started (PID {self.process.pid})")
    return True
```

### 2.2 Démarrage direct (mode mono-process)

```bash
python main.py --channel el_serda --use-db
```

### 2.3 Séquence main.py détaillée

```
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 1: Initialisation                                             │
├─────────────────────────────────────────────────────────────────────┤
│ 1.1  parse_args()                                                   │
│      → --channel el_serda                                           │
│      → --use-db                                                     │
│      → --eventsub direct                                            │
│                                                                     │
│ 1.2  setup_logging(channel="el_serda")                             │
│      → logs/broadcast/el_serda/instance.log                        │
│      → logs/broadcast/el_serda/chat.log                            │
│                                                                     │
│ 1.3  write_pid_file()                                              │
│      → pids/el_serda.pid                                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 2: Configuration                                              │
├─────────────────────────────────────────────────────────────────────┤
│ 2.1  load_config("config/config.yaml")                             │
│      → client_id, client_secret                                     │
│      → channels list                                                │
│      → timeouts, features, etc.                                     │
│                                                                     │
│ 2.2  DatabaseManager(db_path="kissbot.db")                         │
│      → Charge clé Fernet (.kissbot.key)                            │
│      → Configure SQLite (WAL, foreign_keys, etc.)                  │
│                                                                     │
│ 2.3  init_feature_manager(config)                                  │
│      → Parse features activées/désactivées                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 3: Authentification (CRITIQUE)                                │
├─────────────────────────────────────────────────────────────────────┤
│ 3.1  Twitch(app_id, app_secret)                                    │
│      → Instance "App Token" pour Helix API                         │
│                                                                     │
│ 3.2  load_token_from_db(db, "serda_bot", "bot")                    │
│      → Déchiffre access_token, refresh_token                       │
│      → Vérifie needs_reauth == 0                                   │
│      → Vérifie status != "revoked"                                  │
│      → Parse scopes JSON → AuthScope enums                         │
│                                                                     │
│ 3.3  Twitch(app_id, app_secret)  # Deuxième instance              │
│      → Instance "User Token" pour IRC                               │
│                                                                     │
│ 3.4  ⚠️ CRITIQUE: Définir callback AVANT set_user_authentication   │
│      twitch_bot.user_auth_refresh_callback = save_refreshed_token  │
│                                                                     │
│ 3.5  await twitch_bot.set_user_authentication(                     │
│          token=access_token,                                        │
│          scope=scopes,                                              │
│          refresh_token=refresh_token,                               │
│          validate=True  # Auto-refresh si expiré                   │
│      )                                                              │
│                                                                     │
│ 3.6  Si token refreshé pendant validation:                         │
│      → save_refreshed_token() appelé automatiquement               │
│      → Nouveau token sauvé en DB                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 4: Initialisation des composants                              │
├─────────────────────────────────────────────────────────────────────┤
│ 4.1  MessageBus()        → Pub/sub interne                         │
│ 4.2  Registry()          → Registre des commandes                  │
│ 4.3  RateLimiter()       → Limite messages sortants                │
│ 4.4  AnalyticsHandler()  → Métriques (optionnel)                   │
│ 4.5  ChatLogger()        → Log des messages chat                   │
│ 4.6  MessageHandler()    → Routage des messages                    │
│ 4.7  HelixReadOnlyClient() → API REST avec App Token               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 5: Démarrage IRC                                              │
├─────────────────────────────────────────────────────────────────────┤
│ 5.1  IRCClient(twitch_bot, bus, channels=["el_serda"])             │
│                                                                     │
│ 5.2  await irc_client.start()                                      │
│      │                                                              │
│      ├── Chat(twitch, initial_channel=self.channels)  # CRITIQUE   │
│      │   └── pyTwitchAPI crée WebSocket IRC                        │
│      │                                                              │
│      ├── _apply_monkey_patches()                                   │
│      │   ├── Patch PING → track _last_twitch_ping_time            │
│      │   ├── Patch USERSTATE → VIP detection                      │
│      │   └── Patch reconnect → verify channel joins               │
│      │                                                              │
│      ├── chat.register_event(ChatEvent.READY, ...)                 │
│      ├── chat.register_event(ChatEvent.MESSAGE, ...)               │
│      ├── chat.register_event(ChatEvent.JOIN, ...)                  │
│      │                                                              │
│      ├── chat.start()  # Lance le WebSocket                       │
│      │                                                              │
│      └── _keepalive_task = asyncio.create_task(_keepalive_loop()) │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 6: Démarrage EventSub (optionnel)                            │
├─────────────────────────────────────────────────────────────────────┤
│ Mode "direct":                                                      │
│   EventSubClient(twitch, bus, channels, broadcaster_ids)           │
│   → WebSocket EventSub direct vers Twitch                          │
│                                                                     │
│ Mode "hub":                                                         │
│   HubEventSubClient(bus, channels, broadcaster_ids)                │
│   → IPC vers eventsub_hub.py via Unix socket                       │
│                                                                     │
│ Mode "disabled":                                                    │
│   → Pas d'EventSub, polling uniquement                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAPE 7: Event Loop principal                                       │
├─────────────────────────────────────────────────────────────────────┤
│ while True:                                                         │
│     await asyncio.sleep(1)                                         │
│     # Tous les composants tournent en background:                  │
│     # - IRC: _keepalive_loop() vérifie santé toutes les 2 min     │
│     # - IRC: _on_message() publie sur bus                          │
│     # - MessageHandler: écoute bus, traite commandes              │
│     # - EventSub: reçoit events stream online/offline             │
└─────────────────────────────────────────────────────────────────────┘
```

**Code source** (`main.py` L500-530):
```python
# CRITICAL: Définir le callback AVANT set_user_authentication !
twitch_bot.user_auth_refresh_callback = save_refreshed_token
LOGGER.info("🔄 Callback de refresh token activé")

await twitch_bot.set_user_authentication(
    token=bot_token.access_token,
    scope=bot_token.scopes,
    refresh_token=bot_token.refresh_token,
    validate=True  # Active validation + auto-refresh si expiré
)

# Sauvegarder le token si pyTwitchAPI l'a refreshé pendant validation
current_token = twitch_bot.get_user_auth_token()
if current_token and current_token != bot_token.access_token:
    LOGGER.info("🔄 Token refreshé pendant validation - sauvegarde en DB...")
    await save_refreshed_token(current_token, twitch_bot._user_auth_refresh_token)
```

---

## 3. Authentification OAuth

### 3.1 Flux OAuth initial (première utilisation)

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Humain    │         │ oauth_flow  │         │   Twitch    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  python oauth_flow.py │                       │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  Authorization URL    │
       │<──────────────────────│                       │
       │                       │                       │
       │  Ouvre navigateur     │                       │
       │──────────────────────────────────────────────>│
       │                       │                       │
       │                       │  code=xxx (callback)  │
       │                       │<──────────────────────│
       │                       │                       │
       │                       │  POST /oauth2/token   │
       │                       │──────────────────────>│
       │                       │                       │
       │                       │  access_token,        │
       │                       │  refresh_token        │
       │                       │<──────────────────────│
       │                       │                       │
       │                       │  store_tokens(db)     │
       │                       │  → Chiffre Fernet     │
       │                       │  → SQLite             │
       │                       │                       │
       │  ✅ Token saved       │                       │
       │<──────────────────────│                       │
```

### 3.2 Flux de refresh automatique

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│    Bot      │         │ pyTwitchAPI │         │   Twitch    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  API call (token expiré)                      │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  401 Unauthorized     │
       │                       │<──────────────────────│
       │                       │                       │
       │                       │  POST /oauth2/token   │
       │                       │  grant_type=refresh   │
       │                       │──────────────────────>│
       │                       │                       │
       │                       │  new access_token     │
       │                       │  new refresh_token    │
       │                       │<──────────────────────│
       │                       │                       │
       │  user_auth_refresh_callback(new_token, new_refresh)
       │<──────────────────────│                       │
       │                       │                       │
       │  save_refreshed_token()                       │
       │  → db.store_tokens()  │                       │
       │  → Chiffre Fernet     │                       │
       │  → SQLite             │                       │
       │                       │                       │
       │  Retry API call       │                       │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  200 OK               │
       │                       │<──────────────────────│
```

### 3.3 Structure des tokens en DB

```sql
CREATE TABLE oauth_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,           -- FK vers users.id
    token_type TEXT NOT NULL,           -- 'bot' ou 'broadcaster'
    access_token_encrypted TEXT,        -- Chiffré Fernet
    refresh_token_encrypted TEXT,       -- Chiffré Fernet
    expires_at DATETIME,                -- Date expiration
    scopes TEXT,                        -- JSON array ["chat:read", ...]
    last_refresh INTEGER,               -- Unix timestamp
    status TEXT DEFAULT 'valid',        -- valid, expired, revoked
    needs_reauth INTEGER DEFAULT 0,     -- 1 si refresh échoué 3x
    refresh_failures INTEGER DEFAULT 0, -- Compteur échecs
    key_version INTEGER DEFAULT 1       -- Version clé Fernet
);
```

### 3.4 Callback save_refreshed_token

**Code source** (`main.py` L470-500):
```python
async def save_refreshed_token(token: str, refresh_token: str):
    """Callback appelé automatiquement par pyTwitchAPI quand le token est refreshé"""
    try:
        if args.use_db:
            user = db_manager.get_user_by_login(bot_name)
            if user:
                # Convert AuthScope enums to strings for JSON serialization
                scopes_for_db = [
                    s.value if hasattr(s, 'value') else str(s) 
                    for s in bot_token.scopes
                ] if bot_token.scopes else []
                
                db_manager.store_tokens(
                    user_id=user['id'],
                    access_token=token,
                    refresh_token=refresh_token,
                    expires_in=14400,  # 4 hours
                    scopes=scopes_for_db,
                    token_type='bot',
                    status='valid'
                )
                LOGGER.info(f"✅ Bot token auto-refreshed and saved to DB")
    except Exception as e:
        LOGGER.error(f"❌ Erreur sauvegarde token refreshé: {e}")
```

---

## 4. IRC Client

### 4.1 Initialisation

**Code source** (`irc_client.py` L30-75):
```python
class IRCClient:
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        bot_user_id: str,
        bot_login: str,
        channels: list[str],
        irc_send_timeout: float = 5.0
    ):
        self.twitch = twitch
        self.bus = bus
        self.bot_user_id = bot_user_id
        self.bot_login = bot_login.lower()
        self.channels = channels
        self.irc_send_timeout = irc_send_timeout
        
        self.chat: Optional[Chat] = None
        self._running = False
        self._joined_channels = set()
        
        # Permissions cache
        self._channel_permissions = {}
        self._vip_status_cache = {}
        
        # Health tracking
        self._ping_interval = 120  # Health check toutes les 2 min
        self._last_twitch_ping_time: Optional[float] = None
        self._consecutive_disconnects = 0
        self._max_disconnects_before_restart = 2
        
        # Subscribe aux messages sortants
        self.bus.subscribe("chat.outbound", self._handle_outbound_message)
```

### 4.2 Démarrage et connexion

```
┌─────────────────────────────────────────────────────────────────────┐
│ IRCClient.start()                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Chat(twitch, initial_channel=self.channels)                    │
│     │                                                               │
│     └── pyTwitchAPI crée:                                          │
│         • WebSocket vers irc-ws.chat.twitch.tv                     │
│         • Thread _run_socket() pour receive loop                   │
│         • _join_target = ["el_serda"]  # ← CRITIQUE                │
│                                                                     │
│  2. _apply_monkey_patches()                                        │
│     │                                                               │
│     ├── Patch _handle_ping:                                        │
│     │   → Track self._last_twitch_ping_time = time.time()          │
│     │                                                               │
│     ├── Patch _handle_user_state:                                  │
│     │   → Détecte VIP via badges (pyTwitchAPI ne cache pas VIP)   │
│     │                                                               │
│     └── Patch _handle_base_reconnect:                              │
│         → Vérifie que channels rejoints après reconnect            │
│                                                                     │
│  3. chat.register_event(ChatEvent.READY, _on_ready)                │
│     chat.register_event(ChatEvent.MESSAGE, _on_message)            │
│     chat.register_event(ChatEvent.JOIN, _on_join)                  │
│                                                                     │
│  4. chat.start()                                                   │
│     │                                                               │
│     └── Lance le WebSocket (non-blocking)                          │
│                                                                     │
│  5. _keepalive_task = asyncio.create_task(_keepalive_loop())       │
│     │                                                               │
│     └── Health check toutes les 120 secondes                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Code source** (`irc_client.py` L77-115):
```python
async def start(self) -> None:
    LOGGER.info("🚀 Démarrage IRC Client...")
    
    # CRITICAL: Passer initial_channel pour que pyTwitchAPI rejoigne
    # automatiquement les channels après une reconnexion automatique.
    self.chat = await Chat(self.twitch, initial_channel=self.channels)
    
    # Appliquer les monkey-patches
    await self._apply_monkey_patches()
    LOGGER.info("✅ Tous les monkey-patches installés")
    
    # Register event handlers
    self.chat.register_event(ChatEvent.READY, self._on_ready)
    self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
    self.chat.register_event(ChatEvent.JOIN, self._on_join)
    self.chat.register_event(ChatEvent.LEFT, self._on_left)
    self.chat.register_event(ChatEvent.ROOM_STATE_CHANGE, self._on_room_state_change)
    self.chat.register_event(ChatEvent.NOTICE, self._on_notice)
    
    # Démarrer le chat
    self.chat.start()
    self._running = True
    
    # Démarrer le keepalive
    self._keepalive_task = asyncio.create_task(self._keepalive_loop())
    
    LOGGER.info("✅ IRC Client démarré")
```

### 4.3 Flux de message entrant

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Twitch    │         │ pyTwitchAPI │         │  IRCClient  │
│   IRC WS    │         │   Chat()    │         │             │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  PRIVMSG #el_serda :!gc mario                │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  Parse IRC message    │
       │                       │  → ChatMessage object │
       │                       │                       │
       │                       │  _on_message(msg)     │
       │                       │──────────────────────>│
       │                       │                       │
       │                       │                       │  Ignore si bot
       │                       │                       │  
       │                       │                       │  ChatMessage(
       │                       │                       │    channel="el_serda",
       │                       │                       │    user_login="viewer",
       │                       │                       │    text="!gc mario",
       │                       │                       │    is_mod=False,
       │                       │                       │    badges={...}
       │                       │                       │  )
       │                       │                       │
       │                       │                       │  bus.publish(
       │                       │                       │    "chat.inbound",
       │                       │                       │    chat_msg
       │                       │                       │  )
       │                       │                       │
```

**Code source** (`irc_client.py` L285-320):
```python
async def _on_message(self, msg: TwitchChatMessage) -> None:
    # Ignorer nos propres messages
    if msg.user.name.lower() == self.bot_login:
        return
    
    # Log réception
    LOGGER.info(f"📥 IRC RAW | {msg.user.name} dans #{msg.room.name}: {repr(msg.text[:100])}")
    
    # Créer ChatMessage pour MessageBus
    chat_msg = ChatMessage(
        channel=msg.room.name,
        channel_id=msg.room.room_id,
        user_login=msg.user.name,
        user_id=msg.user.id,
        text=msg.text,
        is_mod=msg.user.mod,
        is_broadcaster=(msg.room.room_id == msg.user.id),
        is_vip=msg.user.vip,
        transport="irc",
        badges=msg.user.badges if msg.user.badges else {}
    )
    
    # Publier sur MessageBus
    await self.bus.publish("chat.inbound", chat_msg)
```

### 4.4 Flux de message sortant

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Command    │         │  IRCClient  │         │   Twitch    │
│  Handler    │         │             │         │   IRC WS    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  bus.publish(         │                       │
       │    "chat.outbound",   │                       │
       │    OutboundMessage(   │                       │
       │      channel="el_serda",                      │
       │      text="🎮 Mario..."                       │
       │    )                  │                       │
       │  )                    │                       │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  _handle_outbound_message()
       │                       │                       │
       │                       │  await asyncio.wait_for(
       │                       │    chat.send_message(channel, text),
       │                       │    timeout=5.0
       │                       │  )                    │
       │                       │──────────────────────>│
       │                       │                       │
       │                       │                       │  PRIVMSG #el_serda :🎮 Mario...
       │                       │                       │
```

### 4.5 Health Check Loop

```
┌─────────────────────────────────────────────────────────────────────┐
│ _keepalive_loop() - Toutes les 120 secondes                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  while self._running:                                               │
│      await asyncio.sleep(120)                                      │
│                                                                     │
│      is_healthy = await _check_connection_health()                 │
│      │                                                              │
│      ├── Check 1: chat.is_connected()                              │
│      │   └── Si False → return False                               │
│      │                                                              │
│      ├── Check 2: Dernier PING Twitch < 6 min                      │
│      │   └── Twitch envoie PING toutes les ~5 min                  │
│      │   └── Si > 360s sans PING → return False                    │
│      │                                                              │
│      └── Check 3: Channels rejoints == Channels attendus           │
│          └── Si manquant → return False                            │
│                                                                     │
│      if is_healthy:                                                 │
│          _consecutive_disconnects = 0                              │
│          LOGGER.info("💓 Health check OK")                         │
│      else:                                                          │
│          _consecutive_disconnects += 1                             │
│                                                                     │
│          if _consecutive_disconnects == 1:                         │
│              # Tenter rejoin                                        │
│              await verify_all_channels()                           │
│                                                                     │
│          elif _consecutive_disconnects >= 2:                       │
│              # Force restart Chat                                   │
│              await _force_restart_chat()                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Code source** (`irc_client.py` L680-755):
```python
async def _check_connection_health(self) -> bool:
    if not self.chat:
        return False
    
    # 1. Vérifier is_connected() - état RÉEL de la socket WebSocket
    is_connected = True
    if hasattr(self.chat, 'is_connected') and callable(self.chat.is_connected):
        is_connected = self.chat.is_connected()
    
    if not is_connected:
        LOGGER.warning("⚠️ is_connected() = False")
        return False
    
    # 2. Vérifier le dernier PING Twitch (doit être < 6 min)
    if self._last_twitch_ping_time is not None:
        time_since_ping = time.time() - self._last_twitch_ping_time
        if time_since_ping > 360:  # > 6 min sans PING = problème
            LOGGER.warning(f"⚠️ Pas de PING Twitch depuis {time_since_ping:.0f}s")
            return False
    
    # 3. Vérifier qu'on est dans les channels attendus (via pyTwitchAPI!)
    # ⚠️ FIX: Utilise is_in_room() au lieu du cache interne _joined_channels
    expected = {c.lower().lstrip('#') for c in self.channels}
    actually_joined = set()
    for channel in expected:
        if self.chat.is_in_room(channel):
            actually_joined.add(channel)
    
    if not expected.issubset(actually_joined):
        missing = expected - actually_joined
        self._joined_channels = actually_joined  # Sync cache
        LOGGER.warning(f"⚠️ Channels manquants (pyTwitchAPI check): {missing}")
        return False
    
    LOGGER.info(f"💓 Health check OK - connected, PING OK, {len(actually_joined)} channels")
    return True
```

> **⚠️ Bug corrigé (2025)**: Avant, `verify_all_channels()` et `_check_connection_health()` 
> utilisaient le cache interne `_joined_channels` qui n'était pas vidé lors d'une déconnexion 
> silencieuse. Résultat: faux positifs "✅ Tous les channels OK" même si la connexion était morte.
> 
> **Fix**: Utiliser `chat.is_connected()` et `chat.is_in_room(channel)` de pyTwitchAPI 
> qui reflètent l'état réel de la connexion WebSocket.

### 4.6 Force Restart Chat

**Code source** (`irc_client.py` L760-810):
```python
async def _force_restart_chat(self) -> None:
    """Dernier recours: destruction et recréation de l'instance Chat."""
    LOGGER.warning("🔄 Force restart Chat - destruction de l'instance...")
    
    # Sauvegarder et stopper
    old_chat = self.chat
    if old_chat:
        try:
            old_chat.stop()
        except Exception as e:
            LOGGER.warning(f"⚠️ Erreur stop ancien Chat: {e}")
    
    # Reset state
    self._joined_channels.clear()
    self._channel_permissions.clear()
    self.chat = None
    
    await asyncio.sleep(2)
    
    # Recréer le Chat
    LOGGER.info("🚀 Création nouvelle instance Chat...")
    self.chat = await Chat(self.twitch, initial_channel=self.channels)
    
    # Réappliquer patches et events
    await self._apply_monkey_patches()
    self.chat.register_event(ChatEvent.READY, self._on_ready)
    self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
    # ... autres events
    
    self.chat.start()
    
    LOGGER.info("✅ Force restart Chat terminé")
```

### 4.7 Timeouts et Reconnexion (inspiré de twitch-rs)

> Référence: [twitch-rs/eventsub_websocket example](https://github.com/twitch-rs/twitch_api/blob/main/examples/eventsub_websocket/src/websocket.rs)

**Stratégie multi-couches:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  Couche 1: pyTwitchAPI receive timeout (7 min)                     │
├─────────────────────────────────────────────────────────────────────┤
│  self.chat = await Chat(                                           │
│      self.twitch,                                                   │
│      initial_channel=self.channels,                                │
│      no_message_reset_time=7  # 7 min (default 10 min)             │
│  )                                                                  │
│                                                                     │
│  → Si aucun message pendant 7 min (même pas PING)                  │
│  → pyTwitchAPI appelle automatiquement _handle_base_reconnect()    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Couche 2: Notre health check PING (6 min) + VRAIE reconnexion    │
├─────────────────────────────────────────────────────────────────────┤
│  _check_connection_health():                                        │
│    - Twitch envoie PING toutes les ~5 min                          │
│    - Si > 6 min sans PING → return False                           │
│                                                                     │
│  1er échec:                                                         │
│    → Appel direct de chat._handle_base_reconnect()                 │
│    → C'est la VRAIE reconnexion native de pyTwitchAPI!             │
│    → Pas un hack, on utilise le même code que la lib               │
│                                                                     │
│  2+ échecs:                                                         │
│    → _force_restart_chat() (dernier recours)                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Couche 3: Force restart Chat (dernier recours seulement)          │
├─────────────────────────────────────────────────────────────────────┤
│  Si reconnexion native échoue aussi:                               │
│    1. Détruire l'instance Chat actuelle                            │
│    2. Créer nouvelle instance Chat                                 │
│    3. Réappliquer monkey-patches                                   │
│    4. Re-register events                                            │
└─────────────────────────────────────────────────────────────────────┘
```

> **🔧 Fix majeur (2025)**: Avant, on tentait juste `verify_all_channels()` au 1er échec,
> ce qui ne faisait que **constater** le problème sans le résoudre. Maintenant on appelle
> directement `_handle_base_reconnect()` de pyTwitchAPI, qui fait la **vraie** reconnexion.

**Comparaison avec twitch-rs (Rust):**

| Aspect | twitch-rs | KissBot (Python) |
|--------|-----------|------------------|
| Keepalive timeout | 10s (EventSub) | 7 min (IRC) |
| Reset à chaque message | Oui | Oui (PING tracking) |
| Pattern reconnexion | Actor model + successor spawn | `_handle_base_reconnect()` natif |
| Fallback | Respawn actor | `_force_restart_chat()` |

**Pourquoi cette approche est meilleure:**

- On utilise le **même code** que pyTwitchAPI utiliserait après 7 min
- Mais on l'appelle **1 minute plus tôt** (6 min vs 7 min)
- Pas de duplication de logique, pas de race condition
- Force restart seulement si la reconnexion native échoue

---

## 5. EventSub

### 5.1 Architecture (Mode Hub - Processus Standalone)

**Le Hub est lancé comme processus INDÉPENDANT**, pas intégré au bot principal.

```
supervisor_v1.py (main orchestrator)
├── HubProcess (eventsub_hub.py)  ← PROCESSUS SÉPARÉ
│   │
│   ├── WebSocket EventSub direct vers Twitch
│   ├── Monitor loop (health check 10s)
│   ├── IPC Server (/tmp/kissbot_hub.sock)
│   └── Event routing (channel_id → bot mapping)
│
├── BotProcess #1 (main.py --channel el_serda)
│   └── HubEventSubClient (IPC client)
│       └── Connect à /tmp/kissbot_hub.sock
│
├── BotProcess #2 (main.py --channel other_channel)
│   └── HubEventSubClient (IPC client)
│       └── Connect à /tmp/kissbot_hub.sock
│
└── Health check loop (30s)
    └── Vérifie tous les processus + restart si crash
```

**Avantages de l'architecture standalone**:
- ✅ Hub isolation: une panne Hub n'affecte que EventSub
- ✅ Futur Rust portage: Hub en Rust pur (pas de Python EventSub)
- ✅ Scalabilité: N bots partagent 1 Hub
- ✅ IPC simplicity: Unix socket + JSON (pas de async, pas de event loop complexe)

```
                              ┌───────────────────────────────────────┐
                              │           eventsub_hub.py             │
                              │                                       │
                              │   ┌─────────────────────────────┐    │
                              │   │    EventSubWebsocket        │    │
  ┌─────────────┐             │   │    (pyTwitchAPI)            │    │
  │   Twitch    │◄───────────►│   │                             │    │
  │  EventSub   │  1 WebSocket│   │   • Auto-reconnect         │    │
  │   Server    │             │   │   • Resubscribe            │    │
  └─────────────┘             │   │   • Keepalive              │    │
                              │   └─────────────────────────────┘    │
                              │                 │                     │
                              │                 ▼                     │
                              │   ┌─────────────────────────────┐    │
                              │   │      Event Router           │    │
                              │   │                             │    │
                              │   │   channel_id → bot mapping  │    │
                              │   └─────────────────────────────┘    │
                              │           │           │              │
                              │           ▼           ▼              │
                              │   ┌─────────────────────────────┐    │
                              │   │      IPC Server             │    │
                              │   │   /tmp/kissbot_hub.sock     │    │
                              │   └─────────────────────────────┘    │
                              └───────────────────────────────────────┘
                                          │           │
                              Unix Socket │           │ Unix Socket
                                          ▼           ▼
                              ┌──────────────┐  ┌──────────────┐
                              │   Bot #1     │  │   Bot #2     │
                              │  el_serda    │  │  pelerin_    │
                              │              │  │              │
                              │ HubEventSub  │  │ HubEventSub  │
                              │ Client       │  │ Client       │
                              └──────────────┘  └──────────────┘
```

### 5.2 Protocol IPC

```
Bot → Hub:
───────────

HELLO (à la connexion):
{
    "type": "hello",
    "channel": "el_serda",
    "channel_id": "44456636",
    "topics": ["stream.online", "stream.offline"]
}

SUBSCRIBE (dynamique):
{
    "type": "subscribe",
    "channel_id": "44456636",
    "topic": "stream.online"
}

PING (keepalive):
{
    "type": "ping",
    "timestamp": 1733407200
}


Hub → Bot:
───────────

ACK (confirmation):
{
    "type": "ack",
    "cmd": "hello",
    "channel_id": "44456636",
    "topic": "stream.online",
    "status": "pending"
}

EVENT (notification):
{
    "type": "event",
    "topic": "stream.online",
    "channel_id": "44456636",
    "twitch_event_id": "abc-123",
    "payload": {
        "broadcaster_user_id": "44456636",
        "broadcaster_user_login": "el_serda",
        "type": "live",
        "started_at": "2025-12-05T10:30:00Z"
    }
}

PONG (keepalive response):
{
    "type": "pong",
    "timestamp": 1733407200
}
```

### 5.3 pyTwitchAPI EventSubWebsocket - Reconnexion auto

**Ce que pyTwitchAPI gère automatiquement** (inspecté via code source):

```python
# twitchAPI/eventsub/websocket.py

class EventSubWebsocket:
    reconnect_delay_steps = [1, 2, 4, 8, 16, 32, 64]  # Backoff exponentiel
    
    async def _connect(self, is_startup: bool = False):
        """Connexion avec retry automatique"""
        retry = 0
        need_retry = True
        
        while need_retry and retry < len(self.reconnect_delay_steps):
            need_retry = False
            try:
                self._connection = await self._session.ws_connect(self.connection_url)
            except Exception:
                LOGGER.warning(f'retry in {self.reconnect_delay_steps[retry]}s...')
                await asyncio.sleep(self.reconnect_delay_steps[retry])
                retry += 1
                need_retry = True
    
    async def _handle_reconnect(self, data: dict):
        """Gère le message 'reconnect' de Twitch"""
        # Twitch nous demande de nous reconnecter à une nouvelle URL
        new_session = Session.from_twitch(session)
        new_connection = await self._session.ws_connect(new_session.reconnect_url)
        # ... swap connections
    
    def _run_socket(self):
        """Boucle principale avec tasks de reconnexion"""
        self._tasks = [
            asyncio.ensure_future(self._task_receive()),
            asyncio.ensure_future(self._task_reconnect_handler())  # ← Gère les reconnects
        ]
```

**Conclusion**: pyTwitchAPI gère la reconnexion EventSub automatiquement. Notre health check dans le Hub est une sécurité supplémentaire.

### 5.4 Fix: Erreur 4003 - WebSocket Monitor Loop (Dec 2025)

**Problème identifié**:
- pyTwitchAPI auto-reconnect crée une **nouvelle `session_id`** mais les subscriptions restent liées à **l'ancienne `session_id`**
- Twitch envoie erreur **4003** ("Client failed to maintain heartbeat") sur toutes les subscriptions orphelines
- Boucle infinie: reconnect → nouvelle session → vieilles subs 4003 → reconnect...

**Root cause**:
```
Twitch envoie RECONNECT → pyTwitchAPI.session_id = new_id
Mais les subscriptions restent: subscription.condition.broadcaster_user_id liée à OLD session_id
→ Twitch 4003: "cette subscription appartient à une session morte"
```

**Solution (implémentée)**:

```python
class EventSubHub:
    def __init__(self):
        self._created_subscriptions: List[Dict] = []  # Track subscriptions
        self._ws_monitor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        # Démarrer WebSocket ET le monitor loop
        self._ws_monitor_task = asyncio.create_task(
            self._ws_monitor_loop(skip_monitor=False)  # skip=False pour permettre le monitoring
        )
    
    async def _ws_monitor_loop(self, skip_monitor: bool = False):
        """
        Health check détecte les vrais problèmes de connexion.
        Appelle FORCE reconnect AVEC re-création des subscriptions.
        """
        await asyncio.sleep(15)  # Stabilisation initiale
        
        while self._running:
            await asyncio.sleep(10)  # Check toutes les 10s
            
            if not self._websocket._running:
                LOGGER.warning("⚠️ WS monitor: WebSocket not running, forcing reconnect...")
                await self._force_reconnect_with_subscriptions()
            elif self._websocket._last_message_time and \
                 time.time() - self._websocket._last_message_time > 300:
                LOGGER.warning("⚠️ WS monitor: No message in 5 min, forcing reconnect...")
                await self._force_reconnect_with_subscriptions()
    
    async def _force_reconnect_with_subscriptions(self):
        """Force clean reconnect ET re-create subscriptions"""
        try:
            # 1. Arrêter l'ancien WebSocket
            old_ws = self._websocket
            if old_ws:
                old_ws._running = False
            
            # 2. Créer nouvelle connexion
            await asyncio.sleep(2)
            await self._connect_websocket(skip_monitor=True)  # skip_monitor=True pour éviter recursion
            
            # 3. RE-CRÉER toutes les subscriptions
            LOGGER.info(f"🔄 Re-creating {len(self._created_subscriptions)} subscriptions...")
            for sub_info in self._created_subscriptions:
                await self._create_subscription(
                    broadcaster_id=sub_info['broadcaster_id'],
                    topic=sub_info['topic'],
                    skip_monitor=True
                )
        
        except Exception as e:
            LOGGER.error(f"❌ Force reconnect failed: {e}")
    
    async def _create_subscription(self, broadcaster_id: str, topic: str, skip_monitor: bool = False):
        """Créer subscription ET tracker pour future re-création"""
        try:
            sub_id = await self._websocket.subscribe(broadcaster_id, topic)
            
            # Track pour le monitor loop
            self._created_subscriptions.append({
                'broadcaster_id': broadcaster_id,
                'topic': topic,
                'subscription_id': sub_id
            })
            
            LOGGER.info(f"✅ Subscription created: {broadcaster_id} / {topic}")
        
        except Exception as e:
            LOGGER.error(f"❌ Subscription failed: {e}")
```

**Validation**: 
- Production uptime: **5h31m** avec **0 erreurs 4003**
- Monitor loop détecte tous les vrais problèmes de connexion (WS dead, keepalive timeout)
- Re-create subs crée une **nouvelle session propre** au lieu d'avoir des subs orphelines

**Architecture**:
```
┌──────────────────────────────────────────────────────────────────┐
│ eventsub_hub.py (Standalone process)                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── WebSocket EventSub ────────────────────┐                 │
│  │ • pyTwitchAPI auto-reconnect              │                 │
│  │ • _last_message_time tracking             │                 │
│  └────────────────────────────────────────────┘                 │
│                 ▲          │                                    │
│                 │ force    │                                    │
│                 │ reconnect│                                    │
│  ┌─── Monitor Loop (10s) ─┘                                    │
│  │ • Vérifie WS._running                                       │
│  │ • Vérifie keepalive (~5 min)                                │
│  │ • Appelle _force_reconnect_with_subscriptions()             │
│  └────────────────────────────────────────────────────────────┘                 │
│                                                                  │
│  ┌─── Created Subscriptions Tracker ──────────────────────────┐ │
│  │ [ { broadcaster_id, topic, subscription_id }, ... ]        │ │
│  │  ↓ Re-used après chaque force reconnect                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─── IPC Server → Bots ─────────────────────────────────────┐ │
│  │ /tmp/kissbot_hub.sock (Unix socket)                        │ │
│  │ Events forwarded to bots (el_serda, etc.)                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Database Manager

### 6.1 Initialisation

```python
class DatabaseManager:
    def __init__(self, db_path: str = "kissbot.db", key_file: str = ".kissbot.key"):
        self.db_path = db_path
        self.encryptor = TokenEncryptor(key_file=key_file)  # Fernet
        
        # Configuration SQLite optimisée
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")      # Write-Ahead Logging
            conn.execute("PRAGMA busy_timeout = 5000")     # 5s timeout
            conn.execute("PRAGMA synchronous = NORMAL")    # Performance
```

### 6.2 Chiffrement des tokens

```
┌─────────────────────────────────────────────────────────────────────┐
│ TokenEncryptor (Fernet)                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  .kissbot.key                                                       │
│  └── Clé Fernet 32 bytes, base64 encoded                           │
│      └── Générée une fois: Fernet.generate_key()                   │
│                                                                     │
│  encrypt(plaintext) → ciphertext                                   │
│  └── Fernet.encrypt(plaintext.encode())                            │
│  └── Inclut: timestamp, HMAC, IV                                   │
│                                                                     │
│  decrypt(ciphertext) → plaintext                                   │
│  └── Fernet.decrypt(ciphertext)                                    │
│  └── Vérifie: HMAC, timestamp (TTL optionnel)                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Gestion des échecs de refresh

```python
def increment_refresh_failures(self, user_id: int, token_type: str = 'bot') -> int:
    """
    Incrémente le compteur d'échecs.
    Après 3 échecs → needs_reauth = 1 (humain doit re-OAuth)
    """
    with self._get_connection() as conn:
        cursor = conn.execute("""
            UPDATE oauth_tokens
            SET refresh_failures = refresh_failures + 1
            WHERE user_id = ? AND token_type = ?
            RETURNING refresh_failures
        """, (user_id, token_type))
        
        failures = cursor.fetchone()[0]
        
        # Auto-mark needs_reauth après 3 échecs
        if failures >= 3:
            conn.execute("""
                UPDATE oauth_tokens 
                SET needs_reauth = 1, status = 'expired'
                WHERE user_id = ? AND token_type = ?
            """, (user_id, token_type))
            
            self._log_audit(
                event_type="tokens_max_failures",
                user_id=user_id,
                details={"failures": failures},
                severity="error"
            )
            
            logger.error(f"🚨 Token a échoué {failures}x - NEEDS_REAUTH activé!")
        
        return failures
```

---

## 7. Supervisor

### 7.1 Boucle de supervision

```python
async def health_check_loop(self):
    """Vérifie la santé des processus toutes les 30 secondes"""
    
    MAX_RESTARTS_BEFORE_BACKOFF = 5
    BACKOFF_DELAY = 60  # secondes
    
    restart_counts = {}  # channel → nombre de restarts récents
    
    while self._running:
        await asyncio.sleep(30)
        
        for channel, bot in self.bots.items():
            # Vérifier si le process est mort
            if bot.process and bot.process.poll() is not None:
                exit_code = bot.process.returncode
                LOGGER.warning(f"⚠️ {channel}: Process mort (exit {exit_code})")
                
                # Incrémenter compteur
                restart_counts[channel] = restart_counts.get(channel, 0) + 1
                
                # Backoff si trop de restarts
                if restart_counts[channel] >= MAX_RESTARTS_BEFORE_BACKOFF:
                    LOGGER.error(f"🚨 {channel}: {MAX_RESTARTS_BEFORE_BACKOFF} restarts - backoff {BACKOFF_DELAY}s")
                    await asyncio.sleep(BACKOFF_DELAY)
                    restart_counts[channel] = 0
                
                # Restart
                bot.start()
```

### 7.2 Signaux

```python
def handle_shutdown(sig, frame):
    """Arrêt graceful sur SIGINT/SIGTERM"""
    LOGGER.info(f"🛑 Signal {sig} reçu, arrêt...")
    
    for channel, bot in self.bots.items():
        bot.stop(timeout=10)  # Graceful stop avec timeout
    
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)
```

---

## 8. Flux de données

### 8.1 MessageBus (Pub/Sub interne)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MessageBus                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Topics:                                                            │
│  ├── chat.inbound      → Messages IRC reçus                        │
│  ├── chat.outbound     → Messages à envoyer                        │
│  ├── system.event      → Events système (stream online/offline)    │
│  ├── command.executed  → Commande exécutée (pour logs)            │
│  └── metrics.update    → Métriques (analytics)                     │
│                                                                     │
│  Subscribers:                                                       │
│  ├── MessageHandler    → chat.inbound (traite commandes)          │
│  ├── IRCClient         → chat.outbound (envoie messages)          │
│  ├── ChatLogger        → chat.inbound (log messages)              │
│  ├── CommandLogger     → command.executed (log commandes)         │
│  └── AnalyticsHandler  → metrics.update (métriques)               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Exemple: Commande !gc

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Viewer    │         │    IRC      │         │  MessageBus │
│             │         │   Client    │         │             │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  "!gc mario"          │                       │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  publish("chat.inbound", ChatMessage)
       │                       │──────────────────────>│
       │                       │                       │
       │                       │                       │
       │                       │                       │
┌──────┴──────┐         ┌──────┴──────┐         ┌──────┴──────┐
│  Message    │         │   Command   │         │  Game       │
│  Handler    │         │   Registry  │         │  Lookup     │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  Parse "!gc mario"    │                       │
       │  → prefix="!"         │                       │
       │  → command="gc"       │                       │
       │  → args="mario"       │                       │
       │                       │                       │
       │  registry.get("gc")   │                       │
       │──────────────────────>│                       │
       │                       │                       │
       │  GameCommand handler  │                       │
       │<──────────────────────│                       │
       │                       │                       │
       │  await handler.execute(args="mario")          │
       │──────────────────────────────────────────────>│
       │                       │                       │
       │                       │                       │  1. Rust cache search
       │                       │                       │  2. Python fallback
       │                       │                       │  3. Format response
       │                       │                       │
       │  "🎮 Super Mario Bros..."                     │
       │<──────────────────────────────────────────────│
       │                       │                       │
       │  publish("chat.outbound", OutboundMessage)   │
       │──────────────────────>│                       │
       │                       │                       │
       │                       │  await chat.send_message()
       │                       │──────────────────────>│
       │                       │                       │
```

---

## 9. Gestion des erreurs

### 9.1 Matrice de robustesse

| Composant | Reconnexion Auto | Token Refresh | Health Check | Backoff | Force Restart |
|-----------|------------------|---------------|--------------|---------|---------------|
| **Supervisor** | ✅ Process restart | N/A | ✅ 30s | ✅ 60s après 5 | N/A |
| **main.py** | N/A | ✅ Callback | N/A | N/A | N/A |
| **IRC Client** | ⚠️ Besoin patches | ✅ Via main | ✅ 2 min | ✅ 2 échecs | ✅ Chat restart |
| **EventSub WS** | ✅ pyTwitchAPI | ✅ Callback | ✅ 15s | ✅ 2^n (max 64s) | ⚠️ Via Hub |
| **Database** | N/A | ✅ Store/load | N/A | N/A | N/A |
| **IPC Client** | ✅ 5 retries | N/A | Via ping/pong | ✅ 2^n | N/A |

### 9.2 Scénarios de panne

#### Scénario A: Token expire
```
1. Token expire (~4h après refresh)
2. Prochain API call → 401 Unauthorized
3. pyTwitchAPI détecte → auto-refresh
4. user_auth_refresh_callback() appelé
5. save_refreshed_token() → DB mise à jour
6. Retry API call → 200 OK

Si refresh échoue:
7. increment_refresh_failures()
8. Après 3 échecs → needs_reauth = 1
9. Au prochain démarrage → Bot refuse (humain doit re-OAuth)
```

#### Scénario B: IRC déconnecte silencieusement
```
1. Twitch coupe la connexion (réseau, maintenance, etc.)
2. Health check (_keepalive_loop) détecte après max 2 min:
   - is_connected() = False, OU
   - Pas de PING Twitch depuis > 6 min, OU
   - Channels manquants
3. _consecutive_disconnects = 1 → tente rejoin
4. Si échec → _consecutive_disconnects = 2 → force_restart_chat()
5. Nouveau Chat créé avec initial_channel
6. Channels rejoints automatiquement

Délai max de détection: ~4 minutes
```

#### Scénario C: EventSub WebSocket meurt
```
1. Connexion WS perdue
2. pyTwitchAPI _task_reconnect_handler() détecte
3. _connect() avec retry (backoff: 1, 2, 4, 8, 16, 32, 64s)
4. Après reconnect → _resubscribe() automatique
5. Hub health check (15s) vérifie _running en backup

Délai max: ~2 minutes (somme des backoffs)
```

#### Scénario D: Process crash
```
1. Bot crashe (exception non catchée, OOM, SIGKILL)
2. Supervisor health_check_loop() détecte après max 30s
3. restart_counts[channel] += 1
4. Si < 5 restarts → redémarre immédiatement
5. Si >= 5 restarts → backoff 60s puis restart
6. restart_counts reset après backoff

Délai max: 30s + éventuel backoff
```

#### Scénario E: Hub IPC indisponible
```
1. Bot démarre mais Hub pas encore up
2. HubEventSubClient.start() → IPCClient.connect()
3. Retry avec backoff (2, 4, 8, 16, 32s = 62s total)
4. Après 5 échecs → ConnectionError
5. Bot continue sans EventSub (graceful degradation)
6. StreamMonitor utilise polling Helix comme fallback

Délai max: ~62 secondes
```

---

## 10. EventSub Chat vs IRC - Découverte Majeure

### 10.1 Le Problème Fondamental de l'IRC

L'analyse du code Rust `twitch-rs` a révélé une vérité importante :

> **Rust n'utilise PAS IRC pour le chat Twitch. Il utilise EventSub WebSocket.**

Le chatbot Rust officiel (`twitch-rs/examples/chatbot.rs`) utilise :
```rust
let chat_msg = ChannelChatMessageV1::new(event.broadcaster_user_id.clone());
client.subscribe(chat_msg).await?;
```

Ceci est une **subscription EventSub**, pas une connexion IRC !

### 10.2 Comparaison IRC vs EventSub Chat

| Aspect | IRC (actuel) | EventSub Chat |
|--------|--------------|---------------|
| **Keepalive** | PING toutes les ~5 min | Keepalive toutes les ~10 sec |
| **Détection déconnexion** | 6-10 minutes | ~20 secondes |
| **Format messages** | PRIVMSG brut à parser | Objets structurés (JSON) |
| **Reconnexion** | Lente, multi-étapes | Automatique, rapide |
| **User info** | `tags-` IRC à parser | `badges`, `color`, etc. inclus |
| **Historique** | Aucun | Potentiel replay |
| **Rate limit** | 20 msg/30s (mod), 100/30s | Rate limit API unifié |

### 10.3 Pourquoi Rust utilise EventSub pour le Chat

```
IRC PING/PONG:
┌────────────────────────────────────────────────────────────────┐
│  0s        5min       10min      15min      20min (déconnexion)│
│  │          │          │          │          │                 │
│  PING───────PONG───────???????PONG manqué = 5+ min pour détecter│
└────────────────────────────────────────────────────────────────┘

EventSub Keepalive:
┌────────────────────────────────────────────────────────────────┐
│  0s   10s   20s   30s   40s (déconnexion détectée !)           │
│  │     │     │     │     │                                     │
│  KA────KA────KA────?????──RECONNECT (~20 sec pour détecter)    │
└────────────────────────────────────────────────────────────────┘
```

**Ratio de détection: 20 sec vs 5-10 min = EventSub est 15-30x plus rapide**

### 10.4 POC EventSub Chat - Validé ✅

Un proof-of-concept a été créé et testé : `proof-of-concept/eventsub_chat_poc.py`

**Test réel (60 secondes):**
```
✅ EventSub WebSocket démarré
✅ Abonné aux messages chat de #el_serda
💬 [broadcaster,subscriber,clips-leader] El_Serda: test serda_bot
💬 [vip] serda_bot: @el_serda 👋 Salut ! Tout va bien ici
🔹 [el_serda] Keepalive reçu - connexion stable
```

**Code clé pyTwitchAPI:**
```python
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelChatMessageEvent

async def on_chat_message(event: ChannelChatMessageEvent):
    print(f"💬 [{event.event.chatter_user_login}]: {event.event.message.text}")

eventsub = EventSubWebsocket(twitch, callback_loop=asyncio.get_event_loop())
await eventsub.start()
await eventsub.listen_channel_chat_message(broadcaster_id, bot_user_id, on_chat_message)
```

### 10.5 Migration Recommandée

**Phase 1: Coexistence (recommandé maintenant)**
```
┌─────────────┐     ┌─────────────────┐
│   IRC Chat  │────▶│  Envoyer msgs   │  (keep for sending)
└─────────────┘     └─────────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────────┐
│ EventSub WS │────▶│ Recevoir msgs   │  (new, reliable)
└─────────────┘     └─────────────────┘
```

- Garder IRC pour **envoyer** (plus simple, pas de scope supplémentaire)
- Utiliser EventSub pour **recevoir** (keepalive 10s, fiable)

**Phase 2: Full EventSub (futur)**
```python
# Envoyer via Helix API au lieu d'IRC
await twitch.send_chat_message(broadcaster_id, sender_id, "Hello!")
```

### 10.6 Implications pour KissBot

| Composant | Changement |
|-----------|------------|
| `irc_client.py` | Garder pour envoyer uniquement |
| Nouveau: `eventsub_chat_client.py` | À créer pour recevoir |
| `config.yaml` | Ajouter `eventsub_chat: true` |
| `message_handler.py` | Adapter pour EventSub events |
| Health check | Beaucoup plus simple (10s keepalive) |

**Bénéfice attendu: Déconnexion détectée en ~20 sec au lieu de 6-10 min**

---

## 11. Tests de robustesse (A+B)

### Test 1: Validation token refresh

```bash
# Simuler expiration
sqlite3 kissbot.db "UPDATE oauth_tokens SET expires_at = datetime('now', '-1 hour') WHERE token_type = 'bot'"

# Redémarrer le bot
./kissbot.sh restart --use-db

# Vérifier les logs
grep -E "refresh|token" logs/broadcast/el_serda/instance.log
# Attendu: "🔄 Token refreshé pendant validation - sauvegarde en DB..."
```

### Test 2: Validation IRC reconnect

```bash
# Le bot tourne, simuler déconnexion en tuant le process Python child
# (pas le superviseur, juste le bot)
pkill -f "main.py --channel el_serda"

# Après 30s, le superviseur redémarre
# Vérifier les logs
tail -f logs/broadcast/el_serda/instance.log
# Attendu: "✅ IRC Client démarré", "💓 Health check OK"
```

### Test 3: Validation Health Check

```bash
# Attendre 2 minutes après démarrage
sleep 130

# Vérifier health check
grep -E "💓|Health" logs/broadcast/el_serda/instance.log | tail -5
# Attendu: "💓 Health check OK - connected, PING OK, 1 channels"
```

### Test 4: Stress test messages

```bash
# Envoyer 50 messages rapidement via chat Twitch
# Vérifier que le bot ne rate aucun message

grep "📥 IRC RAW" logs/broadcast/el_serda/instance.log | wc -l
# Devrait correspondre au nombre de messages envoyés
```


---

## 📝 Conclusion

### Stack Production-Ready

| Aspect | Score | Commentaire |
|--------|-------|-------------|
| **Token Management** | 9/10 | Callback avant auth, save DB, auto needs_reauth |
| **IRC Resilience** | 7/10 | PING 5 min = détection lente, améliorable via EventSub Chat |
| **EventSub Resilience** | 10/10 | pyTwitchAPI gère tout + keepalive 10s |
| **Process Management** | 9/10 | Supervisor avec backoff intelligent |
| **Error Recovery** | 9/10 | Multi-layer (app → supervisor → manual) |

### Délais de récupération (actuels)

| Panne | Délai max détection | Délai max récupération |
|-------|---------------------|------------------------|
| Token expiré | Instantané | < 5s (auto-refresh) |
| IRC déconnecté | **6-10 min** ⚠️ | 4 min (health + restart) |
| EventSub WS mort | **~20 sec** ✅ | ~2 min (backoff) |
| Process crash | 30s | 30s + éventuel backoff |
| Hub IPC down | Instantané | ~62s (retries) |

### Délais de récupération (avec EventSub Chat)

| Panne | Délai max détection | Amélioration |
|-------|---------------------|--------------|
| Chat déconnecté | **~20 sec** ✅ | **15-30x plus rapide** |

### Évolution recommandée 🎯

```
          Actuel                      Cible (Phase 1)
┌─────────────────────┐         ┌─────────────────────┐
│    IRC (send+recv)  │         │    IRC (send only)  │
│    PING ~5 min      │   ──▶   │                     │
│    Détection lente  │         │  EventSub (receive) │
└─────────────────────┘         │    Keepalive 10s    │
                                │    Détection rapide │
                                └─────────────────────┘
```

### Le bot peut tourner 24/7 ✅

Les déconnexions sont détectées et gérées automatiquement. 

**Amélioration identifiée**: Migrer la réception de messages vers EventSub Chat réduirait le délai de détection de déconnexion de **6-10 minutes à ~20 secondes**.

Le seul cas nécessitant intervention humaine: token révoqué ou refresh échoué 3x → re-OAuth manuel requis.

