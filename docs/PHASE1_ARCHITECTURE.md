# Phase 1 : Architecture App Token Only

## Vue d'ensemble

**Phase 1 = Base solide avec App Token uniquement**

```
┌─────────────────────────────────────────────────────────────┐
│                     PHASE 1 : APP TOKEN                     │
│                    (Lecture seule publique)                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐
│  Twitch API  │  ← App Token (client_id + client_secret)
│  (App Token) │     Pas d'authentification utilisateur
└──────┬───────┘
       │
       ├─────────────────────────┐
       │                         │
       ▼                         ▼
┌─────────────────┐      ┌──────────────┐
│ Helix Read-Only │      │  (Futur)     │
│  - get_stream() │      │  EventSub    │
│  - get_user()   │      │  Public      │
│  - get_game()   │      │              │
│  - top_games()  │      └──────────────┘
└────────┬────────┘
         │
         │ SystemEvent(kind, payload)
         │
         ▼
┌─────────────────┐
│   MessageBus    │  Topic: "system.event"
│  (Pub/Sub)      │
└────────┬────────┘
         │
         │ Subscribe
         │
         ▼
┌──────────────────┐
│ Analytics Handler│  Logger tous les événements
│  - User info     │
│  - Stream info   │
│  - Game info     │
└──────────────────┘
```

## Composants

### 1. App Token (Twitch API)
- **Fichier:** `main.py`
- **Fonction:** Authentification application Twitch
- **Config:** `config/config.yaml` → `twitch.client_id` + `twitch.client_secret`
- **Limitations:** 
  - ✅ Lecture publique (users, streams, games)
  - ❌ Pas d'envoi de messages
  - ❌ Pas d'EventSub avec scopes (déféré Phase 2)

### 2. Helix Read-Only Client
- **Fichier:** `transports/helix_readonly.py`
- **Méthodes:**
  - `get_stream(user_login)` → Info stream (live/offline, viewers, titre, jeu)
  - `get_user(user_login)` → Profil public (display_name, id, created_at)
  - `get_game(game_name)` → Métadonnées jeu/catégorie
  - `get_top_games(limit)` → Top jeux Twitch
- **Output:** Publie `SystemEvent` sur MessageBus
- **Events:**
  - `helix.stream.info`
  - `helix.user.info`
  - `helix.game.info`
  - `helix.top_games`

### 3. MessageBus
- **Fichier:** `core/message_bus.py`
- **Pattern:** Publish/Subscribe décentralisé
- **Topics:** 
  - `system.event` → Événements Helix, EventSub, erreurs
  - `chat.inbound` → Messages reçus (Phase 2)
  - `chat.outbound` → Messages à envoyer (Phase 2)
- **Avantages:** Découplage total entre transports et handlers

### 4. Analytics Handler
- **Fichier:** `core/analytics_handler.py`
- **Rôle:** Subscribe à `system.event`, log tous les événements
- **Routing:**
  - `helix.stream.info` → Log stream (viewers, jeu, titre)
  - `helix.user.info` → Log user (display_name, id, created_at)
  - `helix.game.info` → Log game (name, id)
  - `helix.top_games` → Log top games
- **Stats:** Compteur d'événements traités

### 5. Core (Registry, RateLimiter)
- **Registry:** `core/registry.py` → Résolution dépendances (futur)
- **RateLimiter:** `core/rate_limiter.py` → 18/90/100 messages/30s Twitch

## Flow de données

```
1. main.py démarre
   └─> Twitch API (App Token)
   └─> MessageBus init
   └─> Analytics subscribe à "system.event"
   └─> HelixReadOnlyClient init

2. Test Helix
   └─> get_user("el_serda")
       └─> API Call
       └─> Crée SystemEvent(kind="helix.user.info", payload={...})
       └─> bus.publish("system.event", event)
       └─> Analytics reçoit event
       └─> Log: "📊 [User] El_Serda (ID: 44456636)"

3. Détection stream live
   └─> get_stream("morthycya")
       └─> API Call
       └─> Stream LIVE détecté !
       └─> SystemEvent(kind="helix.stream.info", payload={viewers, title, game})
       └─> Analytics log: "📊 [Stream] morthycya | 15 viewers | Animal Crossing"
```

## Tests validés

✅ **App Token:** Connexion API Twitch stable  
✅ **Helix get_user():** El_Serda + Morthycya récupérés  
✅ **Helix get_stream():** Offline détecté (el_serda), Live détecté (morthycya 15 viewers)  
✅ **Helix get_top_games():** Top 5 Twitch (Just Chatting, ARC Raiders, Minecraft...)  
✅ **MessageBus:** Events publiés et reçus par Analytics  
✅ **Analytics Handler:** 3+ événements traités avec logs propres  

## Limitations Phase 1

| Fonctionnalité | Phase 1 | Phase 2 | Phase 3 |
|----------------|---------|---------|---------|
| App Token | ✅ | ✅ | ✅ |
| Helix Read-Only | ✅ | ✅ | ✅ |
| User Token Bot | ❌ | ✅ | ✅ |
| IRC Chat Read | ❌ | ✅ | ✅ |
| IRC Chat Send | ❌ | ✅ | ✅ |
| Commandes (!ping) | ❌ | ✅ | ✅ |
| EventSub Public | ❌ | ✅ | ✅ |
| Broadcaster Token | ❌ | ❌ | ✅ |
| Helix Send (Badge) | ❌ | ❌ | ✅ |
| EventSub channel.chat | ❌ | ❌ | ✅ |

## Architecture 3 couches

```
┌───────────────────────────────────────────────────────────┐
│ LAYER 1 : APP TOKEN (Phase 1)                            │
│ → Helix public, analytics, monitoring                    │
│ → Pas d'interaction chat                                 │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ LAYER 2 : BOT TOKEN (Phase 2)                            │
│ → serda_bot user token                                   │
│ → IRC read/write (chat natif)                            │
│ → Commandes basiques (!ping, !uptime, !gc, !ask)         │
│ → EventSub public (stream.online/offline/channel.update) │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ LAYER 3 : BROADCASTER TOKEN (Phase 3)                    │
│ → el_serda user token                                    │
│ → Helix send_chat_message (Badge vérifié)                │
│ → EventSub channel.chat.message (réception alternative)  │
│ → Modération avancée                                     │
└───────────────────────────────────────────────────────────┘
```

## Prochaines étapes

**Phase 2.1 - AuthManager:**
- Créer `core/auth_manager.py`
- Gérer multi user tokens (bot + broadcasters)
- Load/save tokens depuis config
- Refresh automatique OAuth

**Phase 2.2 - IRC Client:**
- `transports/irc_client.py` avec bot token
- Scopes: `user:read:chat` + `user:bot`
- Subscribe IRC → Publish `chat.inbound`

**Phase 2.3 - MessageHandler:**
- Subscribe `chat.inbound`
- Parser commandes (!ping, !uptime)
- Publish `chat.outbound`

**Phase 2.4 - IRC Send:**
- IRC Client envoie messages
- Rate limiting strict
- Validation bot fonctionnel sans badge

## Logs de validation

```
2025-10-31 18:30:42 INFO AnalyticsHandler initialisé
2025-10-31 18:30:42 INFO 📊 [User] El_Serda (ID: 44456636) | Créé: 2013-06-07
2025-10-31 18:30:43 INFO 📊 [User] Morthycya (ID: 454155247) | Créé: 2019-08-12
2025-10-31 18:30:43 INFO 📊 [Stream] morthycya | 15 viewers | Animal Crossing: New Horizons
2025-10-31 18:30:44 INFO 📊 [TopGames] 5 jeux récupérés

📊 Analytics: 3 événements traités
✅ Phase 1.3 validée ! Helix + Analytics fonctionnel.
```

## Commandes de test

```bash
# Lancer le bot
python main.py

# Valider le code
ruff check main.py transports/helix_readonly.py core/analytics_handler.py

# Test avec timeout
timeout 30 python main.py
```

---

**Phase 1 COMPLÈTE ✅**  
**Ready for Phase 2 : Bot Token + IRC + Commandes 🚀**
