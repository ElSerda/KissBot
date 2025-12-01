# KissBot Web Dashboard

Interface web pour la gestion de KissBot.

## Architecture

```
web/
├── backend/          # FastAPI (Python)
│   ├── main.py       # Entry point
│   ├── auth/         # OAuth Twitch
│   ├── api/          # Routes API
│   └── requirements.txt
│
├── frontend/         # SvelteKit ou Next.js
│   ├── src/
│   ├── package.json
│   └── ...
│
└── README.md
```

## Fonctionnalités prévues

### Phase 1 - OAuth Broadcaster
- [ ] Login Twitch OAuth (broadcaster)
- [ ] Stockage tokens chiffrés dans kissbot.db
- [ ] Page "Mon Bot" avec statut connexion

### Phase 2 - Dashboard
- [ ] Gestion banwords (!kbbanword via UI)
- [ ] Liste des commandes actives
- [ ] Logs en temps réel (WebSocket)

### Phase 3 - Configuration
- [ ] Activer/désactiver modules par channel
- [ ] Custom commands (quand implémenté)
- [ ] Personnalité LLM par channel

## Scopes OAuth requis

```
# Modération
moderator:manage:banned_users      # Ban/unban users
moderator:manage:blocked_terms     # Blocked terms
moderator:manage:chat_messages     # Delete messages
moderator:read:chatters            # List viewers

# Channel
channel:read:subscriptions         # Read subs
channel:manage:broadcast           # Title/category
channel:read:redemptions           # Channel points

# Chat
chat:read                          # Read chat
chat:edit                          # Send messages
```

## TODO - Implémentation

Voir `TODO_WEB.md` pour le détail.
