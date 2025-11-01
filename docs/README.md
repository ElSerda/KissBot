# 📚 KissBot Documentation

## 🗂️ Documentation Structure

### 🏗️ Architecture Documents

| Document | Description | Status |
|----------|-------------|--------|
| [**PHASE1_ARCHITECTURE.md**](PHASE1_ARCHITECTURE.md) | Phase 1: App Token + Helix Read-Only + Analytics | ✅ Complete |
| [**PHASE2_ARCHITECTURE.md**](PHASE2_ARCHITECTURE.md) | Phase 2: Bot Token + IRC Bidirectional + Commands | ✅ Complete |
| [**PHASE3_ARCHITECTURE.md**](PHASE3_ARCHITECTURE.md) | Phase 3: Game Lookup + LLM + EventSub | 🚧 Phase 3.1 Complete |

### 🔧 Technical Guides

| Document | Description | Status |
|----------|-------------|--------|
| [**MODERATOR_REQUIREMENT.md**](MODERATOR_REQUIREMENT.md) | Twitch bot mod/VIP requirement explained | ✅ Complete |
| [**TIMEOUT_HANDLING.md**](TIMEOUT_HANDLING.md) | Timeout handling for IRC/Helix/LLM (Phase 2.6) | ✅ Complete |
| [**PHASE2.6_VALIDATION_REPORT.md**](PHASE2.6_VALIDATION_REPORT.md) | Phase 2.6 validation & deduplication | ✅ Complete |

### 📖 Full Documentation (Legacy)

See [main README.md](../README.md) for complete project documentation including:
- Installation & Setup
- Commands reference
- LLM integration
- Game lookup system
- Quantum cache system

---

## 🎯 Quick Navigation

### By Development Phase

**Phase 1 - Monitoring Layer (App Token)**
```
[PHASE1_ARCHITECTURE.md] ← Start here
├─ App Token setup
├─ Helix Read-Only client
├─ Analytics Handler
└─ MessageBus foundation
```

**Phase 2 - Bot Layer (Bot Token)**
```
[PHASE2_ARCHITECTURE.md] ← Then here
├─ AuthManager (multi-user tokens)
├─ IRC Client (bidirectional)
├─ MessageHandler (commands)
├─ Full chat interaction cycle
└─ [Phase 2.6] Timeout handling + Deduplication

⚠️ [MODERATOR_REQUIREMENT.md] ← IMPORTANT: Read this!
   Explains why bot needs mod/VIP status

⏱️ [TIMEOUT_HANDLING.md] ← NEW: Phase 2.6
   asyncio.wait_for() pattern for all transports
   
📊 [PHASE2.6_VALIDATION_REPORT.md] ← Validation
   Timeout tests + Deduplication proof
```

**Phase 3 - Advanced Features**
```
[PHASE3_ARCHITECTURE.md] ← NEW: Phase 3.1 Complete ✅
├─ [Phase 3.1] Game Lookup Commands ✅
│   ├─ !gi <game> - Search any game
│   ├─ !gc - Auto-detect streamer's game
│   ├─ Multi-source: RAWG + Steam
│   └─ Smart descriptions: FR → EN → RAWG
│
├─ [Phase 3.2] LLM Integration 🚧
│   └─ !ask - OpenAI chat integration
│
└─ [Phase 3.3] EventSub Integration 🚧
    └─ stream.online/offline notifications
```

### By Topic

**🔧 Setup & Configuration**
- [Main README](../README.md) - Installation, config.yaml, API keys
- [PHASE1_ARCHITECTURE.md](PHASE1_ARCHITECTURE.md) - App Token setup
- [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) - Bot Token setup

**🏗️ Architecture**
- [PHASE1_ARCHITECTURE.md](PHASE1_ARCHITECTURE.md) - Monitoring layer design
- [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) - Bot layer design
- MessageBus pub/sub pattern (both phases)

**🤖 Bot Behavior**
- [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) - Command handling
- [MODERATOR_REQUIREMENT.md](MODERATOR_REQUIREMENT.md) - Twitch policies
- [Main README](../README.md) - Commands reference

**🔍 Troubleshooting**
- [MODERATOR_REQUIREMENT.md](MODERATOR_REQUIREMENT.md) - "Messages not visible"
- [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) - Rate limiting
- [Main README](../README.md) - Common issues

---

## 📊 Phase Progress

| Phase | Components | Status | Documentation |
|-------|------------|--------|---------------|
| **Phase 1** | App Token, Helix, Analytics | ✅ Complete | [PHASE1_ARCHITECTURE.md](PHASE1_ARCHITECTURE.md) |
| **Phase 2.1** | AuthManager | ✅ Complete | [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) |
| **Phase 2.2** | IRC Read | ✅ Complete | [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) |
| **Phase 2.3** | MessageHandler | ✅ Complete | [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) |
| **Phase 2.4** | IRC Send | ✅ Complete | [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md) |
| **Phase 2.5** | Documentation | ✅ Complete | This file + [MODERATOR_REQUIREMENT.md](MODERATOR_REQUIREMENT.md) |
| **Phase 2.6** | Timeout + Dedup | ✅ Complete | [TIMEOUT_HANDLING.md](TIMEOUT_HANDLING.md) + [PHASE2.6_VALIDATION_REPORT.md](PHASE2.6_VALIDATION_REPORT.md) |
| **Phase 2 Final** | Validation Tests | ✅ Complete | All Phase 2 tests passed |
| **Phase 3** | Advanced Features | ⏳ Planned | Coming soon |

---

## 🎓 Learning Path

### For New Developers

1. **Start with Phase 1** - Understand the foundation
   - Read [PHASE1_ARCHITECTURE.md](PHASE1_ARCHITECTURE.md)
   - Run `python main.py` (Phase 1 mode)
   - Observe MessageBus pub/sub pattern

2. **Then Phase 2** - See bot interaction
   - Read [PHASE2_ARCHITECTURE.md](PHASE2_ARCHITECTURE.md)
   - Read [MODERATOR_REQUIREMENT.md](MODERATOR_REQUIREMENT.md) ⚠️ Important!
   - Read [TIMEOUT_HANDLING.md](TIMEOUT_HANDLING.md) - Phase 2.6 updates
   - Test with `/mod your_bot` on your channel

3. **Explore Code** - Understand implementation
   - `core/message_bus.py` - Pub/sub core
   - `twitchapi/transports/irc_client.py` - IRC bidirectional
   - `core/message_handler.py` - Command logic

### For Bot Operators

1. **Read setup guides**
   - [Main README](../README.md) - Installation
   - [MODERATOR_REQUIREMENT.md](MODERATOR_REQUIREMENT.md) - Why mod/VIP needed

2. **Configure your bot**
   - Edit `config.yaml`
   - Generate Twitch tokens
   - Add bot as mod on your channels

3. **Deploy & Monitor**
   - Run `python main.py`
   - Check logs: `tail -f kissbot_production.log`
   - Test commands: `!ping`, `!uptime`, `!help`

---

## 🔗 External Resources

### Twitch Documentation
- [Twitch IRC Guide](https://dev.twitch.tv/docs/irc)
- [Verified Bots](https://dev.twitch.tv/docs/irc#verified-bots)
- [Twitch API Reference](https://dev.twitch.tv/docs/api)

### pyTwitchAPI Documentation
- [pyTwitchAPI Docs](https://pytwitchapi.dev/)
- [Chat Module](https://pytwitchapi.dev/en/stable/modules/twitchAPI.chat.html)
- [Twitch API](https://pytwitchapi.dev/en/stable/modules/twitchAPI.twitch.html)

---

## 📝 Contributing to Documentation

### Adding New Docs

1. Create file in `docs/` directory
2. Add entry to this README.md
3. Follow existing format (see PHASE1/PHASE2)
4. Include:
   - Clear section headers
   - Code examples with comments
   - Diagrams (ASCII art OK)
   - Troubleshooting section

### Documentation Style

- **Use emojis** for visual hierarchy (🎯 ✅ ⚠️ 📊)
- **Code blocks** with language tags
- **Tables** for comparisons
- **Diagrams** for architecture
- **Real examples** from actual bot usage

---

**Questions?** Open an issue or check [main README](../README.md) for contact info! 🚀
