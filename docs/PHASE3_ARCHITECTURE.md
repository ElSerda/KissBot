# Phase 3 - Advanced Features Architecture

**Date**: 2025-10-31  
**Status**: Phase 3.1 Complete ✅ | Phase 3.2-3.3 In Progress  
**Architecture**: pyTwitchAPI (Phase 2) + Advanced Commands

---

## 📋 Table of Contents

- [Overview](#overview)
- [Phase 3.1: Game Lookup Commands](#phase-31-game-lookup-commands)
- [Phase 3.2: LLM Integration](#phase-32-llm-integration-planned)
- [Phase 3.3: EventSub Integration](#phase-33-eventsub-integration-planned)

---

## Overview

Phase 3 builds advanced features on top of Phase 2's solid pyTwitchAPI foundation:

- **Phase 3.1**: Game information commands (!gi, !gc) ✅
- **Phase 3.2**: LLM integration (!ask) 🚧
- **Phase 3.3**: EventSub notifications (stream.online/offline) 🚧

**Architecture Principle**: Reuse existing backends (GameLookup, future LLMHandler), wire them into MessageHandler cleanly.

---

## Phase 3.1: Game Lookup Commands

### ✅ Status: COMPLETE & VALIDATED

**Commands Added**:
- `!gi <game>` - Search any game with full enrichment
- `!gc` - Auto-detect and enrich streamer's current game

**Production Validated**: 2025-10-31 on #pelerin_ with 5 viewers

---

### 🎯 Command: !gi (Game Info)

**Usage**: `!gi <game name>`

**Purpose**: Search for any game and display enriched information from multiple sources.

**Example**:
```
User: !gi elden ring
Bot:  🎮 Elden Ring (2022) - 🏆 95/100 - 🕹️ PC, PlayStation 5, Xbox One - 🔥 HIGH (2 sources)
```

**Flow**:
```
1. User sends "!gi elden ring"
2. MessageHandler routes to _cmd_game_info()
3. GameLookup.search_game("elden ring")
   ├─ RAWG API search
   ├─ Steam API search
   └─ Merge + reliability scoring
4. format_result(game, compact=False)
5. Publish OutboundMessage to IRC
```

**Format** (standard):
```
🎮 {name} ({year}) - 🏆 {metacritic}/100 - 🕹️ {platforms} - {confidence_icon} {confidence} ({sources} sources)
```

**Data Sources**:
- **RAWG API**: Rating, metacritic, platforms, genres
- **Steam API**: Metacritic (backup), platforms, description (FR/EN)
- **Confidence**: HIGH (2 sources) / MEDIUM (1 source) / LOW (uncertain)

**Error Handling**:
- Game not found → "❌ Jeu '{name}' non trouvé"
- API timeout → "❌ Error searching game" (logs details)
- No GameLookup → "❌ Service de jeux non disponible"

---

### 🎯 Command: !gc (Game Current)

**Usage**: `!gc` (no arguments)

**Purpose**: Auto-detect what the streamer is currently playing and enrich with full game info.

**Example (Live)**:
```
User: !gc
Bot:  🎮 pelerin_ joue actuellement à 🎮 Whisper Mountain Outbreak - 🕹️ PC | Un mélange d'escape game et de jeu de tir en coop post-apocalyptique ! Nous sommes en 1998...
```

**Example (Offline)**:
```
User: !gc
Bot:  💤 el_serda est offline actuellement
```

**Flow**:
```
1. User sends "!gc"
2. MessageHandler routes to _cmd_game_current()
3. HelixReadOnlyClient.get_stream(channel)
   ├─ If offline → return None
   └─ If live → return {game_name, viewer_count, ...}
4. If live:
   ├─ GameLookup.enrich_game_from_igdb_name(game_name)
   ├─ format_result(game, compact=True)  # No confidence/sources
   ├─ Add description (Steam FR → EN → RAWG fallback)
   └─ Smart truncation to fit Twitch 500 char limit
5. Publish OutboundMessage to IRC
```

**Format** (compact for space):
```
🎮 {channel} joue actuellement à 🎮 {name} ({year}) - 🏆 {metacritic}/100 - 🕹️ {platforms} | {description}
```

**Key Differences from !gi**:
- ✅ **Compact format**: No confidence/sources → saves ~30 chars
- ✅ **Description priority**: Shows game summary instead of just metadata
- ✅ **Smart truncation**: Cuts at sentence (.) or word boundary
- ✅ **Twitch limit**: Max 450 chars (safety margin)
- ✅ **Offline detection**: Returns friendly message

**Description Fallback Hierarchy**:
1. **Steam FR** 🇫🇷 (priority, typically shorter & better)
2. **Steam EN** 🇬🇧 (fallback if FR empty or <10 chars)
3. **RAWG EN** 🇬🇧 (last resort)
4. **No description** → Show `({viewer_count} viewers)` instead

**Truncation Logic**:
```python
prefix = f"@{user} 🎮 {channel} joue actuellement à {game_info} | "
max_summary_len = 450 - len(prefix)

# Smart cut at sentence or word boundary
if len(description) > max_summary_len:
    if last_dot > 70% of max_len:
        cut_at_dot()
    elif last_space > 80% of max_len:
        cut_at_space()
    else:
        hard_cut_with_ellipsis()
```

**Error Handling**:
- Helix not injected → "❌ Helix client not available"
- Stream offline → "💤 {channel} est offline actuellement"
- Game enrichment fails → Fallback to basic format with viewers
- No GameLookup → Show game name + viewers only

---

### 🏗️ Architecture

#### Component Integration

```
┌─────────────────────────────────────────────────────────────┐
│                      MessageHandler                         │
│  (Phase 3.1 - Game Commands Added)                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  __init__(bus, config):                                     │
│    └─ self.game_lookup = GameLookup(config)  # Init backend│
│    └─ self.helix = None  # Injected later                   │
│                                                              │
│  set_helix(helix):                                          │
│    └─ self.helix = helix  # Dependency injection            │
│                                                              │
│  async def _handle_chat_message(msg):                       │
│    ├─ if command == "!gi": _cmd_game_info()                │
│    └─ if command == "!gc": _cmd_game_current()             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
          │                                     │
          │ search_game()                      │ get_stream()
          │ enrich_from_igdb()                 │
          ▼                                     ▼
┌─────────────────────┐           ┌─────────────────────────┐
│   GameLookup        │           │  HelixReadOnlyClient    │
│   (Backend)         │           │  (Transport)            │
├─────────────────────┤           ├─────────────────────────┤
│ • RAWG API          │           │ • Twitch Helix API      │
│ • Steam API         │           │ • App Token auth        │
│ • Multi-source      │           │ • Get stream info       │
│ • FR/EN fallback    │           │ • Timeout handling (8s) │
│ • Smart merging     │           └─────────────────────────┘
└─────────────────────┘
```

#### Dependency Injection Pattern

**Problem**: Helix client created AFTER MessageHandler in main.py

**Solution**: Two-phase initialization
```python
# main.py
message_handler = MessageHandler(bus, config)  # Phase 1: Create
helix = HelixReadOnlyClient(twitch_app, bus)   # Create Helix
message_handler.set_helix(helix)                # Phase 2: Inject
```

**Benefits**:
- ✅ No circular dependencies
- ✅ Clean separation of concerns
- ✅ MessageHandler can work without Helix (degrades gracefully)
- ✅ Easy to test in isolation

---

### 🔍 GameLookup Backend

**File**: `backends/game_lookup.py`

**Key Features**:
- Multi-source aggregation (RAWG + Steam)
- Reliability scoring
- Cache support (GameCache optional)
- Timeout handling (10s default, configurable)
- French/English description fallback

**Methods Used**:

#### `search_game(query: str) -> GameResult | None`
Used by `!gi` command for user searches.

**Flow**:
1. Parallel fetch: RAWG + Steam
2. Fuzzy matching (user input may have typos)
3. Merge data with reliability scoring
4. Return best match

**Confidence Levels**:
- **HIGH**: 2 sources, high rating, exact match
- **MEDIUM**: 1 source, or partial match
- **LOW**: Uncertain, possible typo

#### `enrich_game_from_igdb_name(igdb_name: str) -> GameResult | None`
Used by `!gc` command for stream categories.

**Flow**:
1. IGDB name = ground truth (no fuzzy search)
2. Parallel fetch: RAWG + Steam
3. Merge data (prioritize exact match)
4. Return IGDB_VERIFIED result

**Difference vs search_game()**:
- No typo detection (IGDB name is reliable)
- Exact match prioritized
- Confidence = IGDB_VERIFIED (special flag)

#### `format_result(result: GameResult, compact: bool = False) -> str`
Formats game data for Twitch chat.

**Standard Format** (compact=False):
```
🎮 {name} ({year}) - 🏆 {metacritic}/100 - 🕹️ {platforms} - 🔥 HIGH (2 sources)
```

**Compact Format** (compact=True):
```
🎮 {name} ({year}) - 🏆 {metacritic}/100 - 🕹️ {platforms}
```

**Space Saved**: ~30 characters by removing confidence/sources

---

### 🌐 Steam Description Fallback

**Implementation** (`_fetch_steam()` in game_lookup.py):

```python
# Try French first
details_params = {"appids": app_id, "l": "french", "cc": "fr"}
steam_description = fetch_short_description(params)

# Fallback to English if empty or too short (<10 chars)
if not steam_description or len(steam_description.strip()) < 10:
    details_params_en = {"appids": app_id, "l": "english", "cc": "us"}
    steam_description = fetch_short_description(params_en)
```

**Why French First?**
- Steam FR descriptions are typically **shorter** and **more concise**
- Better fit for Twitch's 500 char limit
- Audience preference for French community

**Examples**:
- **Whisper Mountain** → Steam FR (270 chars) ✅
- **Stardew Valley** → Steam EN (240 chars, FR not available) ✅
- **Elden Ring** → Steam FR (189 chars) ✅

---

### 📊 Message Length Optimization

**Twitch Limit**: 500 characters (IRC message limit)

**Strategy**:
1. **Compact format** for !gc (no confidence) → saves ~30 chars
2. **Smart truncation** of descriptions → fit within limit
3. **Prefix calculation** → measure exact space available
4. **Safety margin** → target 450 chars max

**Example Calculation**:
```python
# Whisper Mountain Outbreak on #pelerin_
prefix = "@el_serda 🎮 pelerin_ joue actuellement à 🎮 Whisper Mountain Outbreak - 🕹️ PC | "
# Length: 79 chars

max_summary = 450 - 79 = 371 chars
description_length = 270 chars  # Fits perfectly!

final_message = 349 chars
margin = 500 - 349 = 151 chars ✅
```

**Truncation Logic**:
```python
if len(summary) > max_len:
    # Try to cut at sentence ending
    last_dot = summary.rfind('. ')
    if last_dot > max_len * 0.7:  # Within 70% of max
        return summary[:last_dot + 1]
    
    # Fallback: cut at word boundary
    last_space = summary.rfind(' ')
    if last_space > max_len * 0.8:  # Within 80% of max
        return summary[:last_space] + "..."
    
    # Last resort: hard cut
    return summary[:max_len] + "..."
```

---

### 🧪 Testing & Validation

#### Test Scripts

**`test_gc_format.py`**:
```bash
python3 test_gc_format.py
```
Tests multiple games with different description lengths:
- Whisper Mountain Outbreak (long FR)
- Elden Ring (medium with metacritic)
- Baldur's Gate 3 (medium)
- Hades (short)
- Stardew Valley (EN fallback)

**`test_whisper_mountain.py`**:
```bash
python3 test_whisper_mountain.py
```
Detailed analysis of single game:
- Step-by-step enrichment
- Format comparison (standard vs compact)
- Truncation simulation
- Message length validation

**`test_steam_fallback.py`**:
```bash
python3 test_steam_fallback.py
```
Validates FR→EN fallback logic with games likely to have/not have French descriptions.

**`test_desc_language.py`**:
```bash
python3 test_desc_language.py
```
Language detection to verify which Steam language was used (FR vs EN).

#### Production Tests

**Test Date**: 2025-10-31  
**Test Channel**: #pelerin_ (5 viewers, live stream)

**!gc Test Results**:
```
Command: !gc
Stream: Live (Whisper Mountain Outbreak)
Response: @el_serda 🎮 pelerin_ joue actuellement à 🎮 Whisper Mountain Outbreak - 🕹️ PC | Un mélange d'escape game et de jeu de tir en coop post-apocalyptique ! Nous sommes en 1998. Une ancienne malédiction vient d'être libérée au Mont Bisik. En solo ou en équipe de 2 à 4, explorez divers environnements, découvrez des indices... et échappez aux abominations.
Length: 349 chars
Status: ✅ SUCCESS (under 500 limit)
```

**!gi Test Results**:
```
Command: !gi hades
Response: @el_serda 🎮 Hades (2020) ⭐ 4.4/5 | PC, PlayStation 5, Xbox One | MC: 93
Status: ✅ SUCCESS
APIs: RAWG + Steam called
Cache: Miss (first query)
```

**Offline Test**:
```
Command: !gc
Stream: Offline
Response: @el_serda 💤 el_serda est offline actuellement
Status: ✅ SUCCESS
```

---

### 🐛 Error Handling

#### Graceful Degradation

**Scenario 1**: Helix not injected
```python
if not self.helix:
    response = "❌ Helix client not available"
    # Log error but don't crash
```

**Scenario 2**: Game enrichment fails
```python
if not game:
    # Fallback to basic format
    response = f"🎮 {channel} joue actuellement à **{game_name}** ({viewers} viewers)"
```

**Scenario 3**: No GameLookup configured
```python
if not self.game_lookup:
    # Still show game name from Helix
    response = f"🎮 {channel} joue actuellement à **{game_name}** ({viewers} viewers)"
```

**Scenario 4**: API timeout (inherited from Phase 2.6)
```python
# Timeout at Helix level (8s)
# Timeout at GameLookup level (10s)
# Both return None on timeout → graceful fallback
```

---

### 🔄 Future Enhancements

**Potential Improvements** (not in Phase 3.1):
- [ ] Genre filtering (show genres in compact format?)
- [ ] Twitch category link (direct link to game page)
- [ ] User preferences (language, format style)
- [ ] Game comparison (!compare <game1> <game2>)
- [ ] Top games command (!top games)
- [ ] Stream history (!history shows last 5 games played)

---

## Phase 3.2: LLM Integration (PLANNED)

### 🚧 Status: NOT STARTED

**Target**: Add `!ask` command with OpenAI integration

**Requirements**:
- OpenAI API key in config
- Timeout handling (30s configured in Phase 2.6)
- Rate limiting per user
- Context awareness (channel + user info)
- Personality from config.yaml

**Architecture Plan**:
```python
class LLMHandler:
    def __init__(self, config):
        self.openai_client = AsyncOpenAI(api_key=config['apis']['openai_key'])
        self.timeout = config['timeouts']['llm_inference']  # 30s
    
    async def ask(self, question: str, context: dict) -> str:
        # Call OpenAI with timeout
        # Include channel context, user info, personality
        pass
```

---

## Phase 3.3: EventSub Integration (PLANNED)

### 🚧 Status: NOT STARTED

**Target**: Auto-announce when stream goes live/offline

**Requirements**:
- Broadcaster OAuth token (not just bot token)
- EventSub subscription (stream.online, stream.offline)
- WebSocket or Webhook implementation
- Auto-message in chat on events

**Example**:
```
[Bot detects stream.online event]
Bot: 🔴 @everyone Le stream est LIVE ! Venez vite ! 🎮
```

---

## 📁 File Structure

```
KissBot-standalone/
├── core/
│   └── message_handler.py      # Phase 3.1: !gi and !gc routing
├── backends/
│   ├── game_lookup.py          # Phase 3.1: Multi-source game search
│   └── game_cache.py           # Optional cache for GameLookup
├── twitchapi/
│   └── transports/
│       └── helix_readonly.py   # Phase 3.1: Used by !gc for stream info
├── test_gc_format.py           # Phase 3.1: Multi-game validation
├── test_whisper_mountain.py    # Phase 3.1: Detailed single-game test
├── test_steam_fallback.py      # Phase 3.1: FR→EN fallback test
├── test_desc_language.py       # Phase 3.1: Language detection
└── docs/
    ├── PHASE3_ARCHITECTURE.md  # This file
    └── PHASE2_ARCHITECTURE.md  # Phase 2 docs
```

---

## 🎯 Summary

**Phase 3.1 Achievements**:
- ✅ Two production-ready game commands (!gi, !gc)
- ✅ Multi-source enrichment (RAWG + Steam)
- ✅ Smart description fallback (FR → EN → RAWG)
- ✅ Compact format for space optimization
- ✅ Twitch limit compliance (< 450 chars)
- ✅ Offline detection and friendly messages
- ✅ Graceful error handling
- ✅ Production validated on live stream

**Next Steps**:
- 🚧 Phase 3.2: LLM integration (!ask)
- 🚧 Phase 3.3: EventSub notifications

**Key Design Principles**:
1. **Reuse Phase 2 foundation** (pyTwitchAPI, MessageBus, timeout handling)
2. **Clean dependency injection** (Helix via set_helix())
3. **Backend separation** (GameLookup is independent, reusable)
4. **Graceful degradation** (work even if APIs fail)
5. **Production-first** (tested on real stream, Twitch limits respected)

---

**Last Updated**: 2025-10-31  
**Author**: GitHub Copilot + ElSerda  
**Version**: 3.1.0
