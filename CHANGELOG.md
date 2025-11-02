# Changelog

All notable changes to KissBot project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.5.0] - 2025-11-02

### 🎉 KILLER FEATURE - Broadcast Command

#### !kisscharity - Multi-Channel Broadcast
- **New command**: `!kisscharity <message>` - Broadcast message to ALL connected channels
  - **Permission**: Broadcaster only (strict security)
  - **Cooldown**: 5 minutes global (anti-spam protection)
  - **Limit**: 500 characters max (Twitch IRC limit)
  - **Source tracking**: Messages show `[Source: channel_name]` on destination channels
  - **Success reporting**: Returns `📢 Message diffusé avec succès sur X/Y channels ! 🎉`

**Use Cases:**
- 🎗️ **Charity events**: Announce charity streams across all channels
- 🎮 **Community raids**: Coordinate multi-streamer raids
- 🤝 **Collaborations**: Announce collabs to all partner channels
- 📢 **Important announcements**: Broadcast news to entire network

**Implementation:**
- `commands/bot_commands/broadcast.py`: Command handler with validation & cooldown
- `twitchapi/transports/irc_client.py`: `broadcast_message()` method
- `core/message_handler.py`: Integration with `!help` command
- `test_kisscharity_quick.py`: 7 comprehensive unit tests

**Security:**
- ✅ Broadcaster-only permission (room_id == user_id)
- ✅ 5-minute cooldown (prevents spam)
- ✅ 500-char limit (Twitch compliance)
- ✅ Channel exclusion (no duplicate on origin channel)
- ✅ Partial failure handling (continues on errors)

**Production Validation:**
- ✅ Tested on 2 channels (#el_serda, #morthycya)
- ✅ Cross-channel broadcast confirmed
- ✅ Source tracking displayed correctly
- ✅ Cooldown enforcement validated
- ✅ Broadcaster detection accurate

**Example:**
```
On #el_serda:
el_serda: !kisscharity 🎮 Event charity ce soir à 20h pour Sidaction !
serda_bot: @el_serda 📢 Message diffusé avec succès sur 1 channels ! 🎉

On #morthycya:
serda_bot: [Source: el_serda] 🎮 Event charity ce soir à 20h pour Sidaction !
```

---

## [3.4.3] - 2025-11-01

### 🐛 Bug Fix
- **EventSub stream.online parsing**: Ajout fallback pour events Twitch incomplets
  - Problème: Twitch envoie parfois `broadcaster_user_login: null` durant premières secondes d'un stream
  - Symptôme: Logs montrant "unknown is now ONLINE" au lieu du vrai channel
  - Fix: Reverse lookup `broadcaster_id → channel` via mapping interne
  - Logs: `🔍 Resolved broadcaster_id 135500767 → pelerin_` si fallback utilisé
  - Fréquence: Rare (~2 fois / 4h38min production), plus fréquent si stream restart/crash
  - Impact: Events `stream.online` maintenant toujours avec bon channel name

### 📊 Production Validation
- Bot run: 4h38min stable (19:51 → 23:10)
- CPU: 0-2% constant
- RAM: 58MB stable
- IRC reconnexions: 6 (normal, ~1/45min)
- EventSub: Aucun crash, retry mechanism fonctionne
- Messages: Centaines traités sans erreur

---

## [3.4.2] - 2025-11-01

### ✨ Added

#### EventSub Cost Limit - Retry Mechanism
- **EventSubClient automatic retry** (`twitchapi/transports/eventsub_client.py`):
  - **Context**: Twitch EventSub WebSocket has 10 cost limit (7 channels × 2 events = 14 cost)
  - **Problem**: 4 `stream.offline` subscriptions fail with "cost exceeded" error
  - **Solution**: Intelligent retry mechanism with exponential backoff
  - Added `_failed_offline_subs: List[Dict]`: Queue for failed subscriptions
  - Added `_retry_task: asyncio.Task`: Background retry task (non-blocking)
  - Enhanced `_subscribe_channel()`: Detects "cost exceeded" errors, adds to retry queue
  - Enhanced `start()`: Launches retry task if failed subscriptions exist
  - Added `_retry_failed_subscriptions()`: Retry logic with exponential backoff
  - Enhanced `stop()`: Gracefully cancels retry task
  - **Workflow**:
    1. Startup: Subscribe all channels (10 succeed, 4 fail with cost exceeded)
    2. Queue: Add 4 failed subscriptions to retry queue
    3. Retry #1 (t+30s): Attempt re-subscribe all failed
    4. Retry #2 (t+60s): Exponential backoff (30s → 60s → 120s → max 5min)
    5. Max 3 attempts per subscription before giving up
  - **Benefits**:
    - ✅ Zero manual intervention
    - ✅ Bot continues functioning (IRC + EventSub online active)
    - ✅ Non-blocking background task
    - ✅ Exponential backoff prevents API spam
    - ✅ Max attempts prevent infinite loops
    - ✅ Graceful shutdown handling

### 📊 Production Validation

#### EventSub Retry Tested Live
- **Test environment**: 7 channels monitored
- **Initial subscriptions**: 10/14 succeeded (7 online + 3 offline)
- **Failed subscriptions**: 4 offline (pelerin_, yurekb, st0uffff, morthycya)
- **Retry task**: Started automatically after startup
- **First retry**: Triggered exactly 30.002s after startup (2025-11-01 15:20:23)
- **Bot status during retry**: ✅ Fully operational (IRC messages received in real-time)
- **Logs format**:
  ```
  ⚠️  Cost limit reached for pelerin_ stream.offline - Added to retry queue
  🔄 Starting retry task for 4 failed subscriptions...
  🔄 Retrying 4 failed subscriptions... (t+30s)
  ```

---

## [3.4.1] - 2025-11-01

### 🐛 Fixed

#### Critical: OAuth Token Auto-Refresh Implementation
- **AuthManager refresh token** (`twitchapi/auth_manager.py`):
  - **CRITICAL BUG**: Refresh token was TODO stub since Phase 2.1
  - Bot couldn't start when access token expired (401 Unauthorized)
  - Implemented `_refresh_token_direct()`: Refresh during validation (no self.tokens lookup)
  - Implemented `_refresh_token()`: Refresh for already loaded tokens
  - Implemented `_save_token_to_file()`: Save refreshed token to `.tio.tokens.json`
  - Enhanced `_validate_and_update()`: Auto-detects 401 and triggers refresh
  - **Workflow**: Validation 401 → Auto-refresh → Re-validate → ✅ Bot continues
  - Token automatically refreshed via Twitch OAuth endpoint (`grant_type=refresh_token`)
  - Transparent refresh: No user intervention required
  - New token expires in 4h (from `expires_in` response)

#### Quantum Commands Permission Checks
- **Fixed permission attributes** (`core/message_handler.py`):
  - Fixed `!collapse`: `msg.user_is_mod` → `msg.is_mod` (line 739)
  - Fixed `!collapse`: `msg.user_is_broadcaster` → `msg.is_broadcaster` (line 739)
  - Fixed `!decoherence`: `msg.user_is_mod` → `msg.is_mod` (line 902)
  - Fixed `!decoherence`: `msg.user_is_broadcaster` → `msg.is_broadcaster` (line 902)
  - Commands now correctly check ChatMessage attributes
  - Matches `core.message_types.ChatMessage` dataclass structure

### ✅ Tested

#### Integration Tests (Phase 3.4)
- **Unit tests** (backends/game_cache.py):
  - ✅ `search_quantum_game()`: Returns superposition with confidence 0.95
  - ✅ `collapse_game()`: Anchors truth, updates stats to 100% verified
  - ✅ `get_quantum_stats()`: Returns correct domain statistics
  - ✅ `cleanup_expired()`: Decoherence cleanup (0 evaporated, collapsed states preserved)

- **Integration tests** (core/message_handler.py):
  - ✅ `!qgame hades`: Returns `@viewer 🔒 Hades (2020) - CONFIRMÉ ✅ (1 confirmations)`
  - ✅ `!collapse hades 1`: Returns `💥 @test_mod a fait collapse 'hades' → Hades (2020) ✅ État figé !`
  - ✅ `!quantum`: Returns `🔬 Système Quantique | GAME: 1 jeux | 100% verified | MUSIC: 0 tracks`
  - ✅ `!decoherence`: Returns `💨 Décohérence globale | GAME: 0 évaporés | MUSIC: 0 évaporés`

- **Production validation**:
  - ✅ Bot starts successfully with expired token (auto-refresh)
  - ✅ Token refreshed: `expires: 2025-11-01 19:18:34`
  - ✅ IRC Client connects after refresh
  - ✅ EventSub WebSocket subscriptions successful
  - ✅ All 4 quantum commands operational in production

---

## [3.4.0] - 2025-11-01

### 🔬 Phase 3.4: Quantum Game Learning (Multi-Domain POC)

Revolutionary quantum-inspired cache system with crowdsourced learning for game searches. Mods/Admins can anchor truth through state collapse, enabling the bot to learn from community confirmations. Multi-domain architecture with game and music caches as proof of concept.

### ✨ Added

#### Quantum Game Cache
- **QuantumGameCache** integrated in `backends/game_cache.py`:
  - Quantum superposition: Multiple game suggestions with confidence scores (0.0-1.0)
  - State collapse: Mods anchor truth by confirming correct game
  - Crowdsourced learning: Bot improves from user confirmations
  - Numbered list interface (1-2-3) for easy selection
  - Automatic confidence calculation based on API sources, name match, ratings
  - Decoherence: Automatic cleanup of expired non-verified states (48h)
  - Domain-specific implementation (game-focused, not generic)

- **QuantumMusicCache** created in `backends/music_cache.py`:
  - POC for multi-domain quantum system
  - Same quantum mechanics as game cache
  - Mock data only (no external API yet)
  - Demonstrates architecture scalability
  - Ready for Spotify/LastFM integration (Phase 3.5+)

#### Quantum Commands
- **!qgame <name>** (`core/message_handler.py`):
  - Quantum game search with superposition display
  - Shows numbered list of suggestions (1-2-3)
  - Format: `1. ⚛️ Hades (2020) - 🏆 93/100 (conf: 0.9) → !collapse hades 1`
  - Displays confidence scores for transparency
  - Shows verified states with ✅ badge
  - Returns collapsed state if already confirmed

- **!collapse <name> <number>** (Mods/Admins only):
  - Anchors quantum state to ground truth
  - Syntax: `!collapse hades 1` (selects option 1)
  - Permission check: `is_mod` or `is_broadcaster`
  - Bot learns from confirmation
  - Format: `💥 @Mod a fait collapse 'hades' → Hades (2020) ✅ État figé !`
  - Moves collapsed state to first position for future searches

- **!quantum** (Universal stats):
  - Multi-domain quantum system statistics
  - Aggregates GAME + MUSIC + future domains
  - Format: `🔬 Système Quantique | GAME: 42 jeux, 12 superpositions, 60% verified | MUSIC: 5 tracks, 0 superpositions, 0% verified`
  - Shows total items, active superpositions, verified percentage
  - Future-proof for clips, VODs, and other domains
  - **THE FLEX COMMAND** - showcases unique quantum system

- **!decoherence** (Mods/Admins only):
  - Manual quantum cleanup across all domains
  - Permission check: `is_mod` or `is_broadcaster`
  - Evaporates expired non-verified states
  - Format: `💨 @Mod a déclenché décohérence → GAME: 23 évaporés | MUSIC: 5 évaporés`
  - Useful for cache pollution cleanup

### 🏗️ Architecture

#### Domain-Specific Quantum Pattern
```
backends/
  game_cache.py → QuantumGameCache
    ├── search_quantum_game() → Superposition (list 1-2-3)
    ├── collapse_game() → Anchor truth (mods)
    ├── get_quantum_stats() → Domain stats
    └── cleanup_expired() → Decoherence

  music_cache.py → QuantumMusicCache (POC)
    ├── search_quantum_music() → Superposition (mock data)
    ├── collapse_music() → Anchor truth (mods)
    ├── get_quantum_stats() → Domain stats
    └── cleanup_expired() → Decoherence

!quantum → Aggregates ALL domain stats
```

#### Future Domains (Ready to Add)
- `clip_cache.py` → QuantumClipCache
- `vod_cache.py` → QuantumVODCache
- `emote_cache.py` → QuantumEmoteCache
- All inherit same quantum interface

### 🗄️ Archived

- **Dormant Quantum Prototype** moved to `_archive/quantum_prototype/`:
  - `quantum_commands.py` (199 lines) - TwitchIO generic commands
  - `quantum_cache.py` (200 lines) - Generic key-value quantum cache
  - `quantum_game_cache.py` (400+ lines) - Old TwitchIO wrapper
  - **Total: 800+ lines** of quality prototype code
  - Reason: Incompatible TwitchIO architecture (bot uses MessageBus)
  - Quantum logic migrated to domain-specific caches

### 📊 Workflow Example

```
User: !qgame hades
Bot:  🔬 Superposition pour 'hades':
      1. ⚛️ Hades (2020) - 🏆 93/100 (conf: 0.9)
      2. ⚛️ Hades 2 (2024) - 🏆 90/100 (conf: 0.7)
      → !collapse hades 1 pour confirmer

Mod: !collapse hades 1
Bot: 💥 @ModName a fait collapse 'hades' → Hades (2020) ✅ État figé !

[Future search after learning]
User: !qgame hades
Bot:  🔒 Hades (2020) - CONFIRMÉ ✅ (3 confirmations)

User: !quantum
Bot:  🔬 Système Quantique | GAME: 42 jeux, 12 superpositions, 60% verified | MUSIC: 5 tracks, 0 superpositions, 0% verified
```

### 🎯 Value Proposition

- **Unique Feature**: No other Twitch bot has quantum game learning
- **Crowdsourced Truth**: Community-driven accuracy
- **Transparency**: Confidence scores visible to users
- **Scalable**: Multi-domain architecture ready for expansion
- **Marketing Angle**: "The only Twitch bot with a quantum system"

### 🔧 Technical Details

- **Confidence Calculation**:
  - Base: 0.3
  - Multiple API sources: +0.3
  - Exact name match: +0.3 / Partial match: +0.2
  - Metacritic score: +0.1
  - RAWG rating: +0.1
  - Max confidence: 0.95

- **Decoherence Rules**:
  - Expired: Beyond cache duration (24h default)
  - Stale: Non-verified + no searches in 48h
  - Collapsed states: Never expire (permanent truth)

- **Storage Format**:
  - `cache/quantum_games.json` - Game quantum states
  - `cache/quantum_music.json` - Music quantum states
  - Newline-delimited JSON with timestamps
  - Automatic cleanup on load

### 🧪 Testing

- Validate !qgame with ambiguous queries (hades, doom, zelda)
- Test !collapse workflow (mod permissions, learning)
- Verify !quantum multi-domain stats accuracy
- Test !decoherence cleanup (mods only)
- Confirm confidence scoring (0.0-1.0 range)
- Production deployment monitoring

---

## [3.3.0] - 2025-11-01

### 🔴 Phase 3.3: Stream Monitoring + System Monitoring + Auto-Announcements

Complete real-time stream monitoring system with EventSub WebSocket (< 1s latency) and automatic announcements. Hybrid architecture with polling fallback for maximum resilience. Added lightweight system monitoring with CPU/RAM metrics and chat command for transparency.

### ✨ Added

#### System Monitoring & !stats Command
- **SystemMonitor** (`core/system_monitor.py`):
  - Lightweight CPU/RAM/Threads monitoring with psutil
  - Logs metrics to `metrics.json` (newline-delimited JSON)
  - Configurable interval (60s default, 5-10s for dev)
  - Automatic alerts if thresholds exceeded (CPU > 50%, RAM > 500MB)
  - Uptime tracking from bot start
  - **< 0.1% CPU overhead**, negligible RAM impact
  - Cache mechanism for instant !stats access (no file I/O)

- **!stats command** (`core/message_handler.py`):
  - Displays real-time system metrics in chat
  - Format: `📊 CPU: 2.3% | RAM: 58MB | Threads: 9 | Uptime: 2h34m`
  - Human-readable uptime (hours/minutes)
  - Shows alerts if thresholds exceeded: `⚠️ HIGH_CPU=65.2%, HIGH_RAM=521MB`
  - Injected via `set_system_monitor()` for clean dependency management
  - Added to !help command list

- **view_metrics.py** (dev tool):
  - Python script to view metrics.json in real-time
  - `--live` flag for tail -f mode
  - `--alerts` flag to filter only alerts
  - Human-readable table format with timestamps
  - Example: `python3 view_metrics.py --live`

- **Production metrics observed**:
  - RAM: **55 MB** (ultra-efficient, lighter than Chrome tab)
  - CPU: **0-1%** idle (no wasted cycles)
  - Threads: **9** (1 main + 8 library threads)
  - Zero alerts in normal operation

#### EventSub Real-Time Monitoring
- **EventSubClient** (`twitchapi/transports/eventsub_client.py`):
  - Native pyTwitchAPI EventSub WebSocket integration
  - Real-time push notifications: **< 1s latency** (vs 60s polling)
  - Subscribes to `stream.online` + `stream.offline` events (2 subs/channel)
  - Publishes to MessageBus: `system.event` with full metadata
  - Parallel subscriptions with `asyncio.gather()`: **~3.5s startup** for 8 subs
  - **0 API requests in runtime** (WebSocket push only)
  - Graceful error handling with fallback to polling
  - Design decision: Always 2 subs/channel for predictable behavior

#### Hybrid Fallback System
- **Intelligent method selection** in `main.py`:
  - `method=auto`: Try EventSub first, fallback to polling if fails
  - `method=eventsub`: Force EventSub only (error if unavailable)
  - `method=polling`: Force polling only (backward compatible)
  - Automatic broadcaster_id resolution for EventSub
  - Clean shutdown for both monitoring systems

#### Monitoring System (Polling Fallback)
- **StreamMonitor** (`twitchapi/monitors/stream_monitor.py`):
  - Polling-based stream status detection via Helix API
  - Monitors multiple channels simultaneously (configurable list)
  - Detects transitions: offline→online, online→offline
  - Publishes events to MessageBus: `system.event` with `stream.online`/`stream.offline`
  - Configurable polling interval (default: 60s)
  - State tracking per channel with last check timestamp
  - Graceful startup/shutdown with asyncio task management

- **StreamAnnouncer** (`core/stream_announcer.py`):
  - Subscribes to `system.event` from StreamMonitor
  - Auto-announces stream transitions in chat
  - Template variables: `{channel}`, `{title}`, `{game_name}`, `{viewer_count}`
  - Configuration-driven messages (enable/disable per event type)
  - Automatic truncation to 500 chars for Twitch limits
  - Silent ignore when disabled via config

#### Configuration
- **announcements** section in `config/config.yaml`:
  ```yaml
  announcements:
    monitoring:
      enabled: true            # Master switch
      method: auto             # auto/eventsub/polling
      polling_interval: 60     # Seconds between checks
    stream_online:
      enabled: true
      message: "🔴 @{channel} est maintenant en live ! 🎮 {title}"
    stream_offline:
      enabled: false           # Usually disabled to avoid spam
      message: "💤 @{channel} est maintenant hors ligne. À bientôt !"
  ```

#### Token Management
- **Auto-refresh support** via pyTwitchAPI native callback:
  - `twitch_bot.user_auth_refresh_callback` configured for long-running bots (10h+)
  - Automatically refreshes tokens before expiration
  - Saves refreshed tokens to `.tio.tokens.json`
  - Prevents 401 errors during extended sessions
  - No manual intervention required

### 🔧 Changed

- **main.py**:
  - Added "🚀 BOT OPERATIONAL" boot message with system status
  - Clear summary of all active systems (IRC, EventSub, Monitoring)
  - Lists all available commands (!ping, !uptime, !stats, !help, !gi, !gc, !ask, @mention)
  - SystemMonitor integration with configurable interval
  - Injection of SystemMonitor into MessageHandler via `set_system_monitor()`

- **MessageHandler** (`core/message_handler.py`):
  - Added !stats command handler
  - Injected SystemMonitor dependency via `set_system_monitor()`
  - Updated !help to include !stats
  - Updated docstring with !stats command

- **Boot sequence clarity**:
  ```
  ======================================================================
  🚀 BOT OPERATIONAL - ALL SYSTEMS BOOTED
  ======================================================================
  📺 Channels: #el_serda, #morthycya, #pelerin_, #badgecollectors
  💬 Commands: !ping !uptime !stats !help !gi !gc !ask @mention
  📊 Monitoring: CPU/RAM metrics logged to metrics.json
  🔌 Transport: IRC Client + EventSub WebSocket
  
  💡 Ready to receive messages!
     Press CTRL+C to shutdown...
  ```

### 📊 Performance Metrics
  - Integrated EventSubClient + StreamMonitor hybrid system
  - Conditional startup: Try EventSub → Fallback polling if fails
  - Added broadcaster_id resolution for EventSub subscriptions
  - Token refresh callback for automatic token renewal (10h+ sessions)
  - Proper shutdown: EventSub + StreamMonitor → IRC
  - Status display shows monitoring method (EventSub/Polling) and config

- **HelixReadOnlyClient**:
  - `get_stream()` method used by StreamMonitor (singular, not plural)
  - Returns dict if online, None if offline
  - Stream info logs moved to DEBUG level to avoid spam

- **StreamMonitor**:
  - Added clean refresh logs: `🔄 [Refresh] channel - Still Live ✅ (viewers)`
  - Silent DEBUG logs for offline channels to avoid spam
  - Now serves as fallback when EventSub unavailable

- **ChatLogger**:
  - Fixed emoji encoding issue (📺 instead of �)
  - Improved UTF-8 handling in print statements

### � Performance

**EventSub (Real-Time)**:
- **Startup**: ~3.5s for 8 subscriptions (4 channels × 2 events)
  - Parallel subscriptions with `asyncio.gather()`
  - 66% faster than sequential (was 10s)
- **Runtime**: 0 API requests (WebSocket push only)
- **Detection latency**: < 1s (real-time push)
- **API cost**: 8-16 points at startup, then 0

**Polling (Fallback)**:
- **API overhead**: ~4 calls/min for 4 channels at 60s interval
- **Detection latency**: Max 60s (configurable via `polling_interval`)
- **Memory footprint**: Minimal state tracking per channel

**Long-running stability**: Token auto-refresh ensures 10h+ operation

**System Monitoring** (Nov 1, 2025):
- **RAM**: 54-55 MB (ultra-efficient, lighter than Chrome tab)
- **CPU**: 0-1% idle, brief spikes during message processing
- **Threads**: 9 (1 main + 8 library threads)
- **Startup time**: ~13s (includes EventSub subscriptions)
- **!stats latency**: < 1ms (cached metrics, no file I/O)
- **Monitoring overhead**: < 0.1% CPU, negligible RAM impact

### ✅ Production Validation

**EventSub WebSocket Test** (Nov 1, 2025):
- **Channels**: 4 (el_serda, morthycya, pelerin_, badgecollectors)
- **Subscriptions**: 8 (4 channels × 2 events: online + offline)
- **Results**:
  - ✅ WebSocket connection: Successful
  - ✅ Subscriptions: 8/8 successful in ~3.5s (parallel)
  - ✅ Polling fallback: Disabled (EventSub active)
  - ✅ Real-time detection: < 1s latency confirmed
  - ✅ Runtime API cost: 0 requests (WebSocket push only)

**!stats Command Test** (Nov 1, 2025):
- **User**: el_serda typed `!stats` in chat
- **Response time**: < 100ms
- **Output**: `@el_serda 📊 CPU: 1.0% | RAM: 54MB | Threads: 9 | Uptime: 0m`
- **Results**:
  - ✅ Metrics accurate (psutil validation)
  - ✅ Format clean and chat-friendly (single line)
  - ✅ No file I/O (cached metrics for instant access)
  - ✅ Uptime human-readable (converts seconds to hours/minutes)
  - ✅ No alerts (thresholds not exceeded)

**Polling Fallback Test** (Nov 1, 2025):
- **Test environment**: Bot with 4 channels (3 offline, 1 live)
- **Live channel**: badgecollectors (263-276 viewers)
- **Results**:
  - ✅ Initial status detection: Instant (online/offline)
  - ✅ Polling cycle: Exactly 60s interval
  - ✅ No announcement spam: Silent refresh for unchanged status
  - ✅ Clean logs: `🔄 [Refresh] channel - Still Live ✅ (viewers)`
  - ✅ Multi-channel: All 4 channels monitored correctly
  - ✅ IRC stable: Messages received from live channels
  - ✅ Emoji encoding: Fixed (📺 displays correctly)

### 🐛 Fixed

- **Emoji encoding**: Fixed `�` character in chat logs (UTF-8 emoji handling)
- **Log verbosity**: Moved Helix stream info to DEBUG level to reduce spam
- **StreamMonitor logs**: Added informative refresh logs with viewer count
- **EventSub startup**: Fixed `start()` call (synchronous, not async)

### 📚 Documentation

- **docs/SYSTEM_MONITORING.md** - Complete system monitoring guide:
  - SystemMonitor architecture and configuration
  - metrics.json format and examples
  - view_metrics.py usage (--live, --alerts flags)
  - jq filtering examples for advanced queries
  - Performance impact analysis (< 0.1% overhead)
  - Alert threshold configuration
  - Production metrics reference

- **STREAM_ANNOUNCEMENTS_CONFIG.md** - Complete configuration guide:
  - All config options explained
  - Template variables reference
  - Example configurations (standard, minimal, silent, creative)
  - EventSub vs Polling comparison table
  - Troubleshooting section
  - Performance metrics

- **EventSubClient docstrings**:
  - Design decision documentation: Why 2 subs/channel
  - Performance characteristics
  - Hybrid architecture explanation

### 🧪 Testing

- **test_stream_monitoring.py**:
  - Unit test for StreamMonitor → StreamAnnouncer flow
  - Mocks Helix API responses (offline→online transition)
  - Validates event publishing and message formatting
  - ✅ All tests passing

### 📝 Notes

- **EventSub WebSocket**: ✅ **PRODUCTION READY**
- **Hybrid fallback**: Ensures resilience even if EventSub fails
- **Design choice**: 2 subs/channel (online+offline) for predictable behavior
  - Avoids random results from missing events
  - 0 API cost in runtime (WebSocket push)
  - Startup overhead (~3.5s) acceptable for reliability

---

## [3.2.0] - 2025-11-01

### 🧠 Phase 3.2: LLM Integration + Bot Mentions

Complete LLM integration with !ask command and @bot_name mention detection. Users can now ask questions or naturally mention the bot for intelligent responses.

### ✨ Added

#### Backend
- **LLMHandler** (`backends/llm_handler.py`):
  - Clean wrapper around NeuralPathwayManager
  - Encapsulates LLM logic for MessageHandler
  - `ask(question, user_name, channel)` method
  - `is_available()` health check
  - Timeout handling via intelligence.core

#### Commands
- **!ask <question>** - Ask the bot anything:
  - Natural language processing via streaming LLM
  - Local LM Studio integration
  - Response time: ~1.5s average
  - Context: "ask" (factual responses)
  - Automatic truncation to 500 chars for Twitch
  - Example: `!ask python` → "@user Python est un langage de programmation très populaire..."

- **@bot_name mention** - Natural conversations:
  - Detects @serda_bot or serda_bot (case-insensitive)
  - Priority over commands (mentions processed first)
  - Context: "mention" (conversational responses)
  - **Rate limiting:** 15s cooldown per user (silent ignore)
  - Formats: `@serda_bot hello`, `serda_bot salut`, `hey @serda_bot`
  - Example: `@serda_bot tu penses quoi de python?` → "@user Python est excellent pour..."

#### Functions
- **extract_mention_message()** (`intelligence/core.py`):
  - Case-insensitive mention detection
  - Regex-based extraction with `@?bot_name` pattern
  - Handles mentions at start, middle, or end of message
  - Returns extracted text or None

### 🔧 Changed

- **MessageHandler** (`core/message_handler.py`):
  - Added LLMHandler initialization (if OpenAI key in config)
  - Implemented `_cmd_ask()` for !ask command
  - Implemented `_handle_mention()` for @bot mentions
  - Added rate limiting state: `_mention_last_time` dict
  - Mention detection before command routing
  - Updated !help to show !ask and mention feature

- **extract_mention_message()** (`intelligence/core.py`):
  - Fixed case-insensitive extraction (was using string.replace)
  - Now uses `re.sub(..., flags=re.IGNORECASE)` for proper matching
  - Handles `@SERDA_BOT`, `serda_bot`, `SerDa_Bot` equally

### 📋 Configuration

```yaml
bot_login_name: "serda_bot"  # Bot name for mention detection

apis:
  openai_key: "your_key"  # Required for LLM features

commands:
  cooldowns:
    mention: 15.0  # Cooldown for @bot mentions (seconds)
```

### ✅ Testing

- **test_mention_detection.py**: Validates extraction logic (9/9 tests ✅)
- **test_mention_ratelimit.py**: Validates 15s cooldown mechanism ✅
- **test_mention_integration.py**: End-to-end flow validation ✅
- **Production validation**: !ask tested live (1.54s response, reward 0.90) ✅

### 📊 Metrics

- **LLM Response Time:** 1.5-3s average
- **Mention Detection:** <0.1ms (regex extraction)
- **Rate Limit Check:** <0.01ms (dict lookup)
- **Context Switching:** "ask" (factual) vs "mention" (conversational)

### 📖 Documentation

- **docs/PHASE3.2_BOT_MENTIONS.md**: Complete architecture and flow diagrams

### 🔄 Migration from TwitchIO

**Before (TwitchIO):**
```python
# Separate function in commands/intelligence_commands.py
async def handle_mention_v3(bot, message):
    # Manual rate limiting, separate handler
```

**Now (pyTwitchAPI):**
```python
# Integrated in MessageHandler
async def _handle_mention(self, msg, mention_text):
    # Native MessageBus integration, clean architecture
```

**Benefits:**
- ✅ Unified MessageBus for all responses
- ✅ Integrated rate limiting (no external dependencies)
- ✅ Silent ignore on cooldown (clean UX)
- ✅ Context distinction (ask vs mention)

---

## [3.1.0] - 2025-10-31

### 🎮 Phase 3.1: Game Lookup Commands

Production-ready game information commands with multi-source enrichment (RAWG + Steam) and intelligent description fallback.

### ✨ Added

#### Commands
- **!gi <game>** - Game Info: Search any game with full details
  - Multi-source: RAWG + Steam APIs
  - Metadata: Name, year, rating, platforms, metacritic
  - Format: Full details with confidence indicator
  - Example: `!gi elden ring` → "🎮 Elden Ring (2022) - 🏆 95/100 - 🕹️ PC, PS5, Xbox | Description..."

- **!gc** - Game Current: Auto-detect streamer's current game
  - Live detection via Twitch Helix API
  - Enriched with GameLookup (same as !gi)
  - Compact format (no confidence/sources to save space)
  - Smart description: Steam FR → Steam EN → RAWG EN fallback
  - Offline handling: "💤 channel est offline actuellement"
  - Example: `!gc` → "🎮 pelerin_ joue actuellement à Whisper Mountain Outbreak - 🕹️ PC | Un mélange d'escape game..."

#### Description Hierarchy (Smart Fallback)
1. **Steam FR** 🇫🇷 (priority, shorter descriptions)
2. **Steam EN** 🇬🇧 (fallback if FR empty/short <10 chars)
3. **RAWG EN** 🇬🇧 (last resort)
4. **No description** → Show viewer count instead

#### Format Optimization
- **Compact mode** for !gc: Removes confidence/sources → saves ~30 chars
- **Smart truncation**: Cuts at sentence (.) or word boundary
- **Twitch limit**: Max 450 chars (safety margin for 500 limit)
- **Example output**: 349/500 chars for Whisper Mountain Outbreak ✅

### 🔧 Changed

- **MessageHandler** (`core/message_handler.py`):
  - Added `config` parameter for GameLookup initialization
  - Added `helix` injection via `set_helix()` method
  - Implemented `_cmd_game_info()` for !gi
  - Implemented `_cmd_game_current()` for !gc with enrichment
  - Updated `!help` to show new game commands

- **GameLookup** (`backends/game_lookup.py`):
  - Added `compact` parameter to `format_result()` (removes confidence/sources)
  - Enhanced `_fetch_steam()` with FR→EN fallback logic
  - Updated `_merge_data()` description priority comments

- **Main** (`main.py`):
  - Pass `config` to MessageHandler
  - Inject Helix client via `message_handler.set_helix(helix)`

### 🧪 Validated

- ✅ !gi: Tested with Hades, Elden Ring, Baldur's Gate 3
- ✅ !gc offline: "💤 el_serda est offline actuellement"
- ✅ !gc live: "🎮 pelerin_ joue actuellement à Whisper Mountain Outbreak... (270 chars description)"
- ✅ Format compact: Saves 31 chars by removing confidence
- ✅ Steam FR: Whisper Mountain → French description
- ✅ Steam EN fallback: Stardew Valley → English description
- ✅ Twitch limit: All messages < 450 chars (151 chars margin)

### 📚 Documentation

- **Test scripts** added:
  - `test_gc_format.py` - Multi-game format validation
  - `test_whisper_mountain.py` - Detailed single-game analysis
  - `test_steam_fallback.py` - FR→EN hierarchy validation
  - `test_desc_language.py` - Language detection verification

---

## [2.6.0] - 2025-10-31

### 🛡️ Phase 2.6: Timeout Handling & Deduplication

Critical production fixes for timeout handling and message deduplication. Prepares bot for Phase 3 (LLM integration) where timeouts are essential.

### ✨ Added

#### Timeout Handling
- **asyncio.wait_for()** pattern on all transports:
  - IRC Client: 5s timeout on `send_message()`
  - Helix Client: 8s timeout on API requests
  - LLM ready: 30s timeout configured for Phase 3
- **Config**: `config/config.yaml` new `timeouts` section
- **Graceful fallback**: Log error + continue on timeout (no bot freeze)

#### Message Deduplication
- **Cache system** in MessageHandler:
  - Stores `user_id:text` for processed messages
  - Max 100 messages (auto-cleanup)
  - Prevents pyTwitchAPI double-fire events
- **Test validation**: 15 spam !ping → 1 processed, 14 skipped ✅

### 🔧 Changed

- **IRC Client** (`twitchapi/transports/irc_client.py`):
  - Added `irc_send_timeout` parameter
  - Wrap `send_message()` in `asyncio.wait_for()`
  - Catch `asyncio.TimeoutError` with explicit log
  
- **Helix Client** (`twitchapi/transports/helix_readonly.py`):
  - Added `helix_timeout` parameter
  - Wrap API calls in `asyncio.wait_for()`
  - Return `None` on timeout (same as offline)

- **MessageHandler** (`core/message_handler.py`):
  - Fixed duplicate imports (cleanup)
  - Added `_processed_messages` set cache
  - Skip duplicate messages silently

- **Main** (`main.py`):
  - Load timeouts from config
  - Pass to IRC/Helix clients
  - Log startup with timeout values

### 📚 Documentation

- **docs/TIMEOUT_HANDLING.md** (7.6K) - Complete timeout guide
- **docs/PHASE2.6_VALIDATION_REPORT.md** (7.7K) - Validation tests
- **docs/PHASE2_ARCHITECTURE.md** - Added Phase 2.6 section
- **docs/README.md** - Updated with Phase 2.6 links

### 🐛 Fixed

- **Message duplication**: pyTwitchAPI fires MESSAGE event 2x → Dedup cache prevents double processing
- **Potential freeze**: No timeout on IRC/Helix → Would crash LLM Phase 3 → Now protected
- **Import cleanup**: Duplicate imports in `message_handler.py` removed

### ⚡ Performance

- **Deduplication overhead**: <0.1ms per message
- **Timeout overhead**: <0.001ms per call (asyncio native)
- **Memory**: Max 100 cached message IDs (~5KB)

### 🧪 Tests

| Test | Before | After | Status |
|------|--------|-------|--------|
| Timeout IRC | Infinite wait | 5s max | ✅ |
| Timeout Helix | Infinite wait | 8s max | ✅ |
| Message dedup | 15 processed | 1 processed | ✅ |
| Bot stability | Freeze on slow API | Graceful timeout | ✅ |

### 🚀 Impact

- **Phase 3 ready**: LLM integration will use same timeout pattern
- **Production safe**: Bot won't freeze on slow networks
- **User experience**: No spam responses from duplicate messages

---

## [1.0.0] - 2025-10-29

### 🎯 Major Milestone: First Official Release 🎉

This is the **first official release** of KissBot featuring Neural V2 architecture, Quantum Code Inference with Shannon Entropy, comprehensive test coverage, and professional CI/CD pipeline.

### ✨ Added

#### Testing Infrastructure
- **tests-ci/** (86 tests) - CI/CD test suite with mocks for GitHub Actions
  - Structure validation tests (imports, instantiation)
  - Unit tests for core, commands, intelligence, backends
  - Integration tests with mocked dependencies
  - 60 passed, 26 skipped (LLM/RAWG API tests)
  
- **tests-local/** (7 tests) - Dev test suite with real API keys
  - RAWG API real integration tests (3 tests)
  - Neural V2 with real LLM tests (4 tests)
  - LocalSynapse + CloudSynapse validation
  - Catches production bugs that mocked tests miss

#### CI/CD Pipeline
- **GitHub Actions workflow** (.github/workflows/ci.yml)
  - Automated test execution on push/PR
  - Multi-Python version testing (3.11, 3.12)
  - Three jobs: test, lint, security
  - Test summary in GitHub UI
  - Ruff linting + MyPy type checking
  - Safety security audit

#### Documentation
- **docs/INDEX.md** - Central navigation hub with quick links
- **docs/ARCHITECTURE.md** - Complete Neural V2 system design with diagrams
- **docs/TESTING.md** - Hybrid test strategy documentation (Shannon/CI/Local)
- **docs/CI_CD.md** - GitHub Actions workflow detailed guide

### 🔧 Changed

#### Intelligence Layer Refactoring (-27.3% code reduction)
- **Before**: 2994 lines across 7 files
- **After**: 2176 lines across 5 files
- **Reduction**: -818 lines (-27.3%)

**Files Changed**:
- Merged `improved_classifier.py` + `static_quantum_classifier.py` → `unified_quantum_classifier.py` (532L)
- Removed `handler.py` (functionality inlined)
- Removed `synapse_protocol.py` (interface inlined)
- Simplified `neural_prometheus.py` (-313L)
- Simplified `quantum_metrics.py` (-236L)

**Preserved**:
- ✅ Shannon Entropy formula: H(X) = -Σ p(x)log₂(p(x))
- ✅ Multi-factor confidence: 0.7*shannon + 0.2*prob + 0.1*dom (SACRED)
- ✅ All classification logic
- ✅ Neural pathway routing
- ✅ Reflexes + Synapses

#### TwitchIO 3.x Component Migration
- Updated all command modules from Cog → Component
- Changed `__init__(self, bot)` → `__init__(self)`
- Updated bot access from `self.bot` → `ctx.bot`
- 26 commands successfully migrated and validated

### 🐛 Fixed

#### Critical Bug: QuantumMetrics API Signature
- **Issue**: `QuantumMetrics.record_classification()` receiving wrong parameters
- **Location**: `intelligence/neural_pathway_manager.py` (lines 119, 148)
- **Symptom**: `TypeError: got an unexpected keyword argument 'result'`
- **Root Cause**: Code was passing entire dict as `result=`, but method expects individual params
- **Fix**: Unpacked `quantum_result` dict into 9 individual parameters:
  ```python
  # BEFORE (BROKEN):
  record_classification(stimulus=stimulus, result=quantum_result, ...)
  
  # AFTER (FIXED):
  record_classification(
      stimulus=stimulus,
      classification=quantum_result['class'],
      confidence=quantum_result['confidence'],
      entropy=quantum_result['entropy'],
      is_certain=quantum_result['is_certain'],
      should_fallback=quantum_result['should_fallback'],
      distribution_type=quantum_result.get('distribution_type', 'unknown'),
      method=quantum_result.get('method', 'quantum'),
      response_time_ms=response_time_ms
  )
  ```
- **Impact**: Fixed broken Neural Pathway Manager classification with real LLM
- **Discovery**: Bug found by tests-local/ (not caught by mocked CI tests)

### 📊 Test Coverage

**Total**: 93 tests (67 passed, 26 intentional skips)

| Suite | Tests | Status | Purpose |
|-------|-------|--------|---------|
| **tests-ci/** | 86 | 60 passed, 26 skipped | CI/CD validation with mocks |
| **tests-local/** | 7 | 7 passed | Dev validation with real APIs |

**Coverage by Module**:
- `intelligence/` → 100% (classifier, pathways, synapses, reflexes)
- `commands/` → 85% (quantum, translation, utils)
- `core/` → 80% (rate_limiter, cache_interface)
- `backends/` → 95% (game_cache, quantum_cache, game_lookup)
- `twitch/` → 75% (module structure, config)

### 🔒 Security
- Added Safety dependency audit in CI
- No high-severity vulnerabilities detected

### 🎯 Performance
- CI test suite: 0.31s execution time
- Local test suite: 3.12s with real APIs
- Total pipeline: < 5 minutes

### 📝 Migration Notes

#### For Developers
1. Run `tests-ci/` for fast structure validation (no API keys needed)
2. Run `tests-local/` before committing (requires config.yaml with real keys)
3. CI will automatically run on push/PR (tests-ci only)

#### For Deployment
1. All tests must pass locally before deployment
2. GitHub Actions will validate structure automatically
3. Monitor logs for any integration issues

---

## Legend

- 🎯 **Major Milestone**: Significant project achievement
- ✨ **Added**: New features
- 🔧 **Changed**: Changes to existing functionality
- 🐛 **Fixed**: Bug fixes
- 🔒 **Security**: Security improvements
- 📊 **Test Coverage**: Testing improvements
- 🎯 **Performance**: Performance improvements
- 📝 **Migration Notes**: Important notes for users

---

<div align="center">

**[⬆️ Back to README](README.md)** | **[Documentation](docs/INDEX.md)** | **[Testing Guide](docs/TESTING.md)**

</div>
