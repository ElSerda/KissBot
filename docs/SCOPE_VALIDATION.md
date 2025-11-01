# 🔐 Scope Validation & Auto-Fetch Broadcaster ID

## Vue d'ensemble

KissBot valide automatiquement les scopes OAuth et détecte le `broadcaster_id` au démarrage. Cela garantit que le bot a les permissions nécessaires et élimine la configuration manuelle des IDs.

## Fonctionnalités

### ✅ Validation Automatique des Scopes

Au démarrage, le bot :
1. **Valide chaque token OAuth** via l'API Twitch
2. **Vérifie les scopes requis** pour chaque feature
3. **Désactive les features** si scopes manquants
4. **Bloque le démarrage** si scopes critiques absents

### 🎯 Auto-Fetch Broadcaster ID

Le bot récupère automatiquement le `broadcaster_id` depuis le nom du channel :
- Pas besoin de chercher manuellement l'ID
- Fonctionne chez n'importe quel streamer
- Un seul appel API par channel

## Scopes Requis

### 🔴 CRITIQUES (bot ne démarre pas sans)

| Feature | Scopes | Description |
|---------|--------|-------------|
| **Chat Commands** | `chat:read`<br>`chat:edit` | Lire et envoyer des messages |

### 🟡 OPTIONNELS (features désactivées si absent)

| Feature | Scopes | Description |
|---------|--------|-------------|
| **Stream Events** | `channel:read:stream_key` | Notifications stream online/offline |
| **Follow Events** | `moderator:read:followers` | Notifications nouveaux followers |
| **Raid Events** | `channel:manage:raids` | Notifications de raids |
| **Moderation** | `moderator:manage:banned_users`<br>`moderator:manage:chat_messages` | Timeout/ban, suppression messages |

## Exemple de Sortie

```
============================================================
🔐 ANALYSE DES SCOPES OAUTH
============================================================
👤 User: elserda (ID: 123456789)

📊 Scopes présents (2):
  ✅ chat:edit
  ✅ chat:read

✅ Features disponibles (1):
  ✅ Chat Commands: Lire et envoyer des messages dans le chat

⚠️  Features indisponibles (2):
  ⚠️  OPTIONNEL Stream Events (EventSub): Notifications stream online/offline
      Manquant: ['channel:read:stream_key']
  ⚠️  OPTIONNEL Moderation: Timeout/ban users, supprimer messages
      Manquant: ['moderator:manage:banned_users', 'moderator:manage:chat_messages']

📋 Résumé:
  ✅ Bot opérationnel, mais certaines features sont désactivées.
============================================================

🎯 Auto-detected broadcaster_id for 'elserda': 123456789 (ElSerda)
```

## Configuration

### Avant (avec broadcaster_id hardcodé)

```yaml
twitch:
  broadcaster_id: "123456789"  # Fallait chercher manuellement !
  channel: "elserda"
```

### Après (auto-fetch)

```yaml
twitch:
  channel: "elserda"  # C'est tout ! L'ID est auto-détecté
```

## Gestion des Erreurs

### Token Invalide

```
❌ Token invalide ou expiré
🚨 Le bot ne peut PAS démarrer sans les scopes critiques !
   👉 Reconnecte-toi via Twitch OAuth
```

### Scopes Critiques Manquants

```
❌ CRITIQUE : 'Chat Commands' nécessite ['chat:read', 'chat:edit']
🚨 Le bot ne peut PAS démarrer sans les scopes critiques !
```

Le bot **refuse de démarrer** et affiche un message clair.

### Scopes Optionnels Manquants

```
⚠️  OPTIONNEL : 'Stream Events' nécessite ['channel:read:stream_key']
✅ Bot opérationnel, mais certaines features sont désactivées.
```

Le bot **démarre normalement** mais certaines features sont désactivées.

### Channel Introuvable

```
❌ Channel 'nonexistent' not found
❌ Impossible de récupérer broadcaster_id pour nonexistent
```

Le bot continue mais ne peut pas setup ce channel.

## API Reference

### ScopeValidator.validate_token()

```python
from core.scope_validator import ScopeValidator

analysis = await ScopeValidator.validate_token(
    token="oauth:xxxxx",
    client_id="your_client_id"
)

# Returns:
{
    "valid": bool,              # Token valide ET scopes critiques présents
    "user_id": str,             # Twitch user ID
    "login": str,               # Twitch login name
    "scopes": List[str],        # Scopes présents
    "missing_critical": List[str],    # Scopes critiques manquants
    "missing_optional": List[str],    # Scopes optionnels manquants
    "available_features": List[str],  # Features disponibles
    "unavailable_features": List[str], # Features désactivées
    "warnings": List[str]       # Messages pour l'utilisateur
}
```

### ScopeValidator.fetch_broadcaster_id()

```python
from core.scope_validator import ScopeValidator

broadcaster_id = await ScopeValidator.fetch_broadcaster_id(
    channel_name="elserda",
    client_id="your_client_id",
    token="oauth:xxxxx"
)

# Returns: "123456789" or None if not found
```

### ScopeValidator.print_scope_report()

```python
from core.scope_validator import ScopeValidator

# Print formatted report to console
ScopeValidator.print_scope_report(analysis)
```

## Multi-Instance Support

Pour un SaaS multi-instances :

```python
# User input
channel_name = "elserda"  # Juste le nom !

# Auto-fetch broadcaster_id
broadcaster_id = await ScopeValidator.fetch_broadcaster_id(
    channel_name=channel_name,
    client_id=client_id,
    token=user_token
)

# Setup bot instance
bot = BotInstance(
    channel=channel_name,
    broadcaster_id=broadcaster_id  # Auto-fetched !
)
```

**Zéro configuration manuelle** → L'utilisateur entre juste le nom de son channel.

## Tests

```bash
# Tests unitaires
pytest tests/test_scope_validator.py -v

# Tous les tests
pytest tests-ci/ -q
```

**Couverture :**
- ✅ 14 tests scope_validator
- ✅ 224 tests CI (aucune régression)
- ✅ Total : 238 tests

## Implémentation dans bot.py

Le ScopeValidator est appelé automatiquement dans `setup_hook()` :

```python
async def setup_hook(self) -> None:
    # 1. Validate scopes
    from core.scope_validator import ScopeValidator
    
    for account in tokens:
        analysis = await ScopeValidator.validate_token(...)
        
        if not analysis["valid"]:
            raise ValueError("Scopes critiques manquants")
    
    # 2. Auto-fetch broadcaster IDs
    for channel in channels:
        broadcaster_id = await ScopeValidator.fetch_broadcaster_id(...)
        self.broadcaster_ids[channel] = broadcaster_id
    
    # 3. Setup rest of bot...
```

## Avantages

### Pour l'Utilisateur
- ✅ **Zero config** : Juste le nom du channel
- ✅ **Messages clairs** : Comprend exactement ce qui manque
- ✅ **Pas de debug** : Les erreurs sont explicites

### Pour le Développeur
- ✅ **Portable** : Fonctionne chez n'importe qui
- ✅ **Scalable** : Multi-instance ready
- ✅ **Maintenable** : Scopes centralisés dans un seul fichier

### Pour le SaaS
- ✅ **Onboarding simple** : User entre juste le nom du channel
- ✅ **Oauth flow** : Validation automatique des scopes
- ✅ **Support facile** : Logs clairs pour debugging

## Roadmap Future

- [ ] OAuth re-authorization flow (si scopes manquants)
- [ ] Scope upgrade UI (dashboard)
- [ ] Per-feature scope requirements dynamiques
- [ ] Webhook pour expiration token
