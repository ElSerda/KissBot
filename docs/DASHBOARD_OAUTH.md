# 🎛️ Dashboard OAuth - Broadcaster Authorization

## Vue d'ensemble

KissBot utilise une **architecture à deux niveaux** pour l'authentification OAuth :

1. **Token Bot (serda_bot)** : Pour EventSub et fonctionnalités de base
2. **Token Broadcaster** : Pour les actions de modération spécifiques à chaque channel

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│ EventSub Hub (serda_bot token)           │
│ - stream.online/offline                  │
│ - NO SCOPES required ✅                  │
│ - Badge "Verified Bot"                   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ Moderation APIs (broadcaster tokens)     │
│ - moderator_id = broadcaster_id          │
│ - Token via Dashboard OAuth ✅           │
│ - Broadcaster agit sur son channel       │
│ - PAS besoin /mod serda_bot ✅           │
└──────────────────────────────────────────┘
```

## 🔐 Scopes par Niveau

### Bot Token (serda_bot)

Utilisé pour les fonctionnalités de base :

| Scope | Usage |
|-------|-------|
| `chat:read` | Lire les messages du chat |
| `chat:edit` | Envoyer des messages |
| `channel:bot` | Identifier comme bot |
| `user:bot` | Badge bot vérifié |

**Note** : EventSub `stream.online`/`stream.offline` = **NO SCOPES REQUIRED** ✅

### Broadcaster Token (via Dashboard)

Utilisé pour les actions de modération :

| Scope | Feature | API Endpoint |
|-------|---------|--------------|
| `moderator:manage:announcements` | !kbupdate | POST `/helix/chat/announcements` |
| `moderator:manage:blocked_terms` | Banwords | POST `/helix/moderation/blocked_terms` |
| `moderator:manage:banned_users` | Bans/Timeouts | POST `/helix/moderation/bans` |
| `moderator:manage:chat_messages` | Delete messages | DELETE `/helix/moderation/chat` |

## 📋 Flow OAuth Dashboard

### 1. Broadcaster visite le Dashboard

```
https://dashboard.kissbot.tv/auth
```

### 2. Clique sur "Connecter avec Twitch"

Le Dashboard génère l'URL OAuth avec les scopes requis :

```python
from urllib.parse import urlencode

SCOPES = [
    'moderator:manage:announcements',
    'moderator:manage:blocked_terms',
    'moderator:manage:banned_users',
    'moderator:manage:chat_messages',
]

params = {
    'client_id': CLIENT_ID,
    'redirect_uri': 'https://dashboard.kissbot.tv/oauth/callback',
    'response_type': 'code',
    'scope': ' '.join(SCOPES),
    'force_verify': 'true',  # Force re-approval si scopes changent
}

oauth_url = f"https://id.twitch.tv/oauth2/authorize?{urlencode(params)}"
```

### 3. Twitch affiche la demande d'autorisation

```
┌────────────────────────────────────────┐
│ KissBot veut accéder à votre compte   │
│                                        │
│ Permissions demandées:                 │
│ ✅ Gérer les annonces                 │
│ ✅ Gérer les termes bloqués           │
│ ✅ Gérer les utilisateurs bannis      │
│ ✅ Gérer les messages du chat         │
│                                        │
│        [Autoriser]  [Refuser]          │
└────────────────────────────────────────┘
```

### 4. Callback avec code d'autorisation

```
GET https://dashboard.kissbot.tv/oauth/callback?code=abc123&scope=moderator:manage:announcements+...
```

### 5. Échange code → tokens

```python
import aiohttp

async def exchange_code_for_tokens(code: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post('https://id.twitch.tv/oauth2/token', data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://dashboard.kissbot.tv/oauth/callback',
        }) as resp:
            return await resp.json()

# Returns:
# {
#   "access_token": "xxx",
#   "refresh_token": "yyy",
#   "expires_in": 14400,
#   "scope": ["moderator:manage:announcements", ...],
#   "token_type": "bearer"
# }
```

### 6. Validation du token

```python
from core.scope_validator import ScopeValidator

# Valide le token et récupère les infos user
analysis = await ScopeValidator.validate_token(
    token=access_token,
    client_id=CLIENT_ID
)

if not analysis["valid"]:
    raise ValueError("Token invalide ou scopes manquants")

broadcaster_id = analysis["user_id"]
broadcaster_login = analysis["login"]
```

### 7. Stockage en DB (chiffré)

```python
from database.manager import DatabaseManager

db = DatabaseManager('kissbot.db', '.kissbot.key')

# Créer ou récupérer l'utilisateur
user = db.get_user_by_login(broadcaster_login)
if not user:
    user_id = db.add_user(
        twitch_user_id=broadcaster_id,
        twitch_login=broadcaster_login,
        is_bot=False
    )
else:
    user_id = user['id']

# Stocker le token (chiffré avec Fernet)
db.store_tokens(
    user_id=user_id,
    access_token=access_token,
    refresh_token=refresh_token,
    expires_in=14400,
    scopes=analysis["scopes"],
    token_type='broadcaster',  # ← Important!
    status='valid'
)
```

### 8. Confirmation

```
✅ Autorisation réussie !
Votre channel est maintenant connecté à KissBot.

Features activées:
  ✅ !kbupdate - Annonces de mise à jour
  ✅ Banwords - Gestion des termes bloqués
  ✅ Modération - Bans et timeouts

Vous pouvez fermer cette page.
```

## 🔧 Utilisation des Tokens

### Pour !kbupdate (Announcements)

```python
from twitchAPI.twitch import Twitch

# Récupérer le token broadcaster depuis la DB
broadcaster_token = db.get_tokens(
    user_id=broadcaster_db_id,
    token_type='broadcaster'
)

# Configurer pyTwitchAPI avec le token broadcaster
twitch = Twitch(CLIENT_ID, CLIENT_SECRET)
await twitch.set_user_authentication(
    token=broadcaster_token.access_token,
    scope=broadcaster_token.scopes,
    refresh_token=broadcaster_token.refresh_token
)

# Appel API
await twitch.send_chat_announcement(
    broadcaster_id=broadcaster_id,
    moderator_id=broadcaster_id,  # ← MUST be same as token owner
    message="🔄 Bot mis à jour ! Nouvelle version déployée.",
    color="primary"
)
```

### Pour Banwords

```python
# Même principe, token broadcaster
await twitch.add_blocked_term(
    broadcaster_id=broadcaster_id,
    moderator_id=broadcaster_id,  # ← MUST be same as token owner
    text="badword*"
)
```

## 🔄 Auto-Refresh des Tokens

Les tokens broadcaster sont **automatiquement refreshés** comme le token bot :

```python
# Callback défini dans main.py
async def save_refreshed_broadcaster_token(
    broadcaster_id: str,
    token: str,
    refresh_token: str
):
    user = db.get_user_by_twitch_id(broadcaster_id)
    if user:
        db.store_tokens(
            user_id=user['id'],
            access_token=token,
            refresh_token=refresh_token,
            expires_in=14400,
            scopes=current_scopes,
            token_type='broadcaster',
            status='valid'
        )
```

## 🚨 Gestion des Erreurs

### Scope Manquant

Si broadcaster accepte seulement **une partie** des scopes :

```python
REQUIRED_SCOPES = {
    'kbupdate': ['moderator:manage:announcements'],
    'banwords': ['moderator:manage:blocked_terms'],
}

available_features = []
for feature, scopes in REQUIRED_SCOPES.items():
    if all(s in broadcaster_token.scopes for s in scopes):
        available_features.append(feature)

# Désactiver les features dont les scopes sont absents
```

### Token Révoqué

Si broadcaster révoque son autorisation :

```
❌ Error 401: Token révoqué
→ Rediriger broadcaster vers Dashboard pour ré-autoriser
```

### Rate Limiting

```python
# API Moderation endpoints ont des rate limits spécifiques
# Ex: 10 announcements / 10 secondes max

from core.rate_limiter import APIRateLimiter

limiter = APIRateLimiter()
if not limiter.can_announce(broadcaster_id):
    raise RateLimitError("Trop d'annonces envoyées")
```

## 📊 Table oauth_tokens

```sql
SELECT 
    u.twitch_login,
    ot.token_type,
    ot.scopes,
    ot.status,
    ot.expires_at
FROM oauth_tokens ot
JOIN users u ON u.id = ot.user_id
WHERE ot.token_type = 'broadcaster';

-- Résultat:
-- twitch_login | token_type   | scopes                           | status | expires_at
-- el_serda     | broadcaster  | ["moderator:manage:announcements"| valid  | 2025-12-06 18:00:00
-- pelerin_     | broadcaster  | ["moderator:manage:blocked_terms"| valid  | 2025-12-06 19:30:00
```

## 🎯 Pour les Testeurs

### Comment connecter votre channel au bot :

1. **Visitez le Dashboard** : https://dashboard.kissbot.tv/auth
2. **Cliquez "Connecter avec Twitch"**
3. **Acceptez les permissions** demandées
4. **Confirmez** : Vous verrez "✅ Autorisation réussie"
5. **C'est tout !** Le bot peut maintenant utiliser les features de modération sur votre channel

### Que se passe-t-il si je révoque l'accès ?

- Les features de modération seront **désactivées** pour votre channel
- Les features de base (EventSub, chat basique) continuent de fonctionner
- Pour réactiver : retournez sur le Dashboard et reconnectez-vous

### Puis-je choisir quelles permissions donner ?

- **Non** : Twitch OAuth est tout-ou-rien pour un groupe de scopes
- Si vous refusez, le bot ne pourra pas activer les features correspondantes
- Vous pouvez toujours **révoquer** l'accès plus tard depuis Twitch Settings

## 🔐 Sécurité

### Tokens Chiffrés

Tous les tokens sont chiffrés avec **Fernet** (AES-128) :

```python
from cryptography.fernet import Fernet

# Clé stockée dans .kissbot.key (JAMAIS commit)
cipher = Fernet(encryption_key)
encrypted_token = cipher.encrypt(access_token.encode())
```

### Clé de Chiffrement

```bash
# .kissbot.key MUST be in .gitignore
echo ".kissbot.key" >> .gitignore

# Backup sur serveur sécurisé UNIQUEMENT
scp .kissbot.key backup@secure-server:/backups/
```

### Révocation

Les broadcasters peuvent **toujours** révoquer l'accès depuis :
https://www.twitch.tv/settings/connections

## 📝 TODO

- [ ] Implémenter le Dashboard Web
- [ ] Route `/auth` et `/oauth/callback`
- [ ] UI pour afficher les features disponibles
- [ ] Notification si broadcaster révoque
- [ ] Multi-language support (FR/EN)

## 📚 Références

- [Twitch OAuth Documentation](https://dev.twitch.tv/docs/authentication)
- [Twitch Moderation API](https://dev.twitch.tv/docs/api/reference#send-chat-announcement)
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Vue d'ensemble
- [SCOPE_VALIDATION.md](./SCOPE_VALIDATION.md) - Validation des scopes
