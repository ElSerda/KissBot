# 🔬 Quantum System Architecture - Phase 3.4

**Revolutionary crowdsourced learning system for Twitch bot content caching**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quantum Commands](#quantum-commands)
4. [Domain Caches](#domain-caches)
5. [Confidence Scoring](#confidence-scoring)
6. [Decoherence](#decoherence)
7. [Future Domains](#future-domains)

---

## Overview

### What is Quantum Game Learning?

The Quantum System is a **crowdsourced learning cache** where:
- Users search content (games, music, etc.)
- Bot returns **multiple suggestions** with confidence scores
- **Mods/Admins confirm** the correct result
- Bot **learns** from confirmations
- Future searches become **more accurate**

### Key Innovation

**Traditional Bot:**
```
User: !gi hades
Bot:  Hades (2020) - 93/100
```
→ Always same result, no learning

**Quantum Bot:**
```
User: !qgame hades
Bot:  1. Hades (2020) - 93/100 (conf: 0.9)
      2. Hades 2 (2024) - 90/100 (conf: 0.7)

Mod: !collapse hades 1
Bot: Bot learns → Next time shows Hades (2020) confirmed ✅
```
→ **Community-driven accuracy**

---

## Architecture

### Multi-Domain Design

```
backends/
  ├── game_cache.py          → QuantumGameCache (Phase 3.4)
  ├── music_cache.py         → QuantumMusicCache (POC)
  └── [future]_cache.py      → Quantum[Future]Cache

core/
  └── message_handler.py     → Quantum commands (!qgame, !collapse, !quantum, !decoherence)
```

### Domain-Specific Pattern

Each domain cache implements:
```python
class QuantumDomainCache(BaseCacheInterface):
    async def search_quantum_{domain}(query: str, observer: str) -> list[dict]:
        """Returns numbered superposition list (1-2-3)"""
    
    def collapse_{domain}(query: str, observer: str, state_index: int) -> dict:
        """Anchors truth via mod confirmation"""
    
    def get_quantum_stats(self) -> dict:
        """Returns domain-specific quantum stats"""
    
    def cleanup_expired(self) -> int:
        """Decoherence: cleanup expired states"""
```

### Storage Format

`cache/quantum_games.json`:
```json
{
  "game:hades": {
    "superpositions": [
      {
        "game": {"name": "Hades", "year": 2020, ...},
        "confidence": 0.9,
        "verified": 1,
        "confirmations": 3,
        "created_by": "user1",
        "last_confirmed_by": "mod1",
        "last_confirmed_at": "2025-11-01T12:00:00"
      },
      {
        "game": {"name": "Hades 2", "year": 2024, ...},
        "confidence": 0.7,
        "verified": 0,
        "confirmations": 0
      }
    ],
    "collapsed": true,
    "created_at": "2025-11-01T10:00:00",
    "last_search": "2025-11-01T12:05:00",
    "search_count": 15
  }
}
```

---

## Quantum Commands

### !qgame <name>

**Quantum game search with superposition**

```
User: !qgame celeste
Bot:  🔬 Superposition pour 'celeste':
      1. ⚛️ Celeste (2018) - 🏆 94/100 (conf: 0.9)
      2. ⚛️ Celeste Classic (2016) - ⭐ 4.5/5 (conf: 0.6)
      → !collapse celeste 1 pour confirmer
```

**Behavior:**
- Returns 1-3 suggestions with confidence scores
- Shows verified states with ✅ badge
- If collapsed, shows confirmed result only
- Updates `last_search` timestamp

**Implementation:** `MessageHandler._cmd_qgame()`

---

### !collapse <name> <number>

**Anchor truth via mod confirmation (Mods/Admins only)**

```
Mod: !collapse celeste 1
Bot: 💥 @ModName a fait collapse 'celeste' → Celeste (2018) ✅ État figé !
```

**Behavior:**
- **Permission check:** `is_mod` or `is_broadcaster`
- Parses `<name> <number>` format
- Marks superposition as `verified: 1`
- Increments `confirmations` counter
- Moves collapsed state to first position
- Sets `collapsed: true` for future searches

**Implementation:** `MessageHandler._cmd_collapse()`

---

### !quantum

**Universal quantum system stats (Multi-Domain)**

```
User: !quantum
Bot:  🔬 Système Quantique | GAME: 42 jeux, 12 superpositions, 60% verified | MUSIC: 5 tracks, 0% verified
```

**Behavior:**
- Aggregates stats from **ALL domains**
- Shows total items, active superpositions, verified percentage
- Scales automatically when new domains added
- **The Flex Command** - showcases unique system

**Stats Format:**
```
DOMAIN: {total} items | {superpositions} superpositions | {verified_pct}% verified
```

**Implementation:** `MessageHandler._cmd_quantum()`

---

### !decoherence [name]

**Manual quantum cleanup (Mods/Admins only)**

**Global cleanup:**
```
Mod: !decoherence
Bot: 💨 @ModName Décohérence globale | GAME: 23 évaporés | MUSIC: 5 évaporés
```

**Specific cleanup:**
```
Mod: !decoherence hades
Bot: 💨 @ModName États supprimés: hades (1 total)

Mod: !decoherence hades,doom,celeste
Bot: 💨 @ModName États supprimés: hades, doom, celeste (3 total)
```

**Behavior:**
- **Permission check:** `is_mod` or `is_broadcaster`
- **Without args:** Cleanup expired states only (automatic decoherence)
- **With name(s):** Force delete specific states (even if not expired)
- **Comma-separated:** Delete multiple states at once
- Returns count per domain (global) or deleted names (specific)
- Useful for cache pollution cleanup or removing problematic states

**Implementation:** `MessageHandler._cmd_decoherence()`

---

## Domain Caches

### QuantumGameCache

**File:** `backends/game_cache.py`

**Features:**
- Integrated with GameLookup (RAWG + Steam APIs)
- Confidence calculation based on multiple factors
- Automatic cleanup after 24h (48h for stale non-verified)
- Domain-specific (game-focused, not generic)

**Key Methods:**
```python
async def search_quantum_game(query: str, observer: str) -> list[dict]:
    # Returns superposition list
    
def collapse_game(query: str, observer: str, state_index: int) -> dict:
    # Anchors truth
    
def get_quantum_stats() -> dict:
    # Returns: total_games, superpositions_active, collapsed_states, verified_percentage
```

---

### QuantumMusicCache

**File:** `backends/music_cache.py`

**Status:** POC (Proof of Concept)

**Features:**
- Same quantum mechanics as game cache
- Mock data only (no external API yet)
- Demonstrates multi-domain architecture
- Ready for Spotify/LastFM integration (Phase 3.5+)

**Purpose:**
- Prove `!quantum` multi-domain aggregation works
- Test architecture scalability
- Foundation for future music features

---

## Confidence Scoring

### Calculation Formula

```python
confidence = 0.3  # Base

# Multiple API sources
if source_count >= 2:
    confidence += 0.3

# Name match quality
if query == game_name:
    confidence += 0.3  # Exact match
elif query in game_name or game_name in query:
    confidence += 0.2  # Partial match

# Quality indicators
if metacritic_score:
    confidence += 0.1
if rawg_rating > 0:
    confidence += 0.1

# Max cap
confidence = min(confidence, 0.95)
```

### Confidence Ranges

| Range | Meaning | User Action |
|-------|---------|-------------|
| 0.9-0.95 | Very high confidence | Likely correct |
| 0.7-0.89 | Good confidence | Worth checking |
| 0.5-0.69 | Medium confidence | Review carefully |
| 0.0-0.49 | Low confidence | Probably wrong |

### Transparency

- All confidence scores **visible to users**
- Users can make informed decisions
- Mods see same info when collapsing

---

## Decoherence

### What is Decoherence?

**Quantum physics:** Loss of quantum coherence (superposition → classical state)

**Bot implementation:** Automatic cleanup of expired non-verified states

### Rules

1. **Expired:** Beyond cache duration (24h default)
2. **Stale:** Non-verified + no searches in 48h
3. **Collapsed states:** Never expire (permanent truth)

### Auto-Cleanup

```python
def cleanup_expired(self) -> int:
    now = datetime.now()
    expired_keys = []
    
    for key, quantum_state in self.quantum_states.items():
        # Check expiration
        if now - created_time >= cache_duration:
            expired_keys.append(key)
            continue
        
        # Check staleness (non-verified only)
        if not collapsed and (now - last_search) >= timedelta(hours=48):
            expired_keys.append(key)
    
    # Evaporate
    for key in expired_keys:
        del self.quantum_states[key]
    
    return len(expired_keys)
```

### Manual Trigger

Mods can force cleanup via `!decoherence` command.

---

## Future Domains

### Ready to Add

The architecture is designed for **infinite scalability**:

```python
# backends/clip_cache.py
class ClipCache(BaseCacheInterface):
    async def search_quantum_clip(query: str, observer: str) -> list[dict]:
        # Search clips with superposition
    
    def collapse_clip(query: str, observer: str, state_index: int) -> dict:
        # Anchor truth
    
    def get_quantum_stats() -> dict:
        # Clip-specific stats

# core/message_handler.py
async def _cmd_qclip(self, msg: ChatMessage, args: str):
    # !qclip command

# !quantum automatically includes CLIP domain
```

### Potential Domains

- **Clips** (`clip_cache.py`) - Twitch clips search
- **VODs** (`vod_cache.py`) - Past broadcast search
- **Emotes** (`emote_cache.py`) - Emote meanings/usage
- **Commands** (`command_cache.py`) - Custom command suggestions
- **Users** (`user_cache.py`) - User info/stats

### Zero Breaking Changes

- Each domain is **independent**
- `!quantum` aggregates **automatically**
- No changes needed to existing domains
- Clean separation of concerns

---

## Technical Notes

### Why "Quantum"?

The system uses **quantum mechanics metaphors**:

| Concept | Metaphor | Implementation |
|---------|----------|----------------|
| Superposition | Multiple possibilities exist | List of suggestions |
| Collapse | Observation fixes state | Mod confirmation |
| Confidence | Wave function probability | 0.0-1.0 scoring |
| Decoherence | Loss of quantum coherence | Expired state cleanup |
| Observer Effect | Measurement changes system | Bot learns from users |

### Why Not Generic Cache?

**Old approach (archived):**
- `QuantumCache` = Generic key-value store
- Works for anything (games, music, etc.)
- Complex, hard to maintain

**New approach (Phase 3.4):**
- Domain-specific caches (`game_cache.py`, `music_cache.py`)
- Each cache tailored to its content type
- Simpler, more maintainable
- Better performance

### Performance

- **Storage:** Newline-delimited JSON (efficient)
- **Memory:** Lazy loading (only active states)
- **Cleanup:** Automatic + manual options
- **Scalability:** Linear O(n) per domain

---

## Summary

### Value Proposition

✅ **Unique** - No other Twitch bot has quantum learning
✅ **Crowdsourced** - Community-driven accuracy
✅ **Transparent** - Confidence scores visible
✅ **Scalable** - Multi-domain architecture
✅ **Self-cleaning** - Automatic decoherence
✅ **Learning** - Gets smarter over time

### Commands Recap

- `!qgame <name>` - Quantum search (superposition)
- `!collapse <name> <number>` - Anchor truth (mods)
- `!quantum` - Universal stats (all domains)
- `!decoherence` - Manual cleanup (mods)

### Marketing Angle

> **"The only Twitch bot with a quantum system"**
>
> Community-driven learning meets quantum mechanics.
> Your mods shape the truth. Your bot gets smarter.

---

**Phase 3.4 - November 1, 2025**
*Revolutionary quantum-inspired crowdsourced learning for Twitch bots*
