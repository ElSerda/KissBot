# KissBot Web Dashboard

> ⚠️ **Ce dossier n'est pas inclus dans le repo public.**
> 
> Le dashboard web est déployé séparément sur un VPS privé.

## Pour les contributeurs

Si vous souhaitez développer votre propre dashboard pour KissBot, voici l'architecture attendue :

### API Endpoints

Le bot expose les données suivantes (via `kissbot.db`) :

- **Users** : `users` table (twitch_user_id, twitch_login, display_name)
- **Tokens** : `oauth_tokens` table (chiffrés avec `.kissbot.key`)
- **Banwords** : `banwords` table (channel_id, word)
- **Config** : `config` table (key/value)

### Authentification

- OAuth 2.0 Twitch avec les scopes définis dans `config.yaml`
- Tokens stockés chiffrés en BDD (AES-256-GCM)
- Session cookie simple pour le frontend

### Stack suggérée

- **Backend** : FastAPI + Jinja2 (ou autre)
- **Frontend** : Tailwind CSS + Vanilla JS (CSP-safe)
- **Auth** : OAuth Twitch → stockage tokens chiffrés

## Contact

Pour accès au dashboard privé, contactez le mainteneur du projet.
