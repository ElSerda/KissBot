# TODO - KissBot Web Dashboard

## Phase 1 : Backend OAuth (FastAPI) ✅ DONE

### 1.1 Setup Backend ✅
- [x] Créer `web/backend/` avec structure FastAPI
- [x] `main.py` - Entry point avec Jinja2 templates
- [x] `requirements.txt` - fastapi, uvicorn, httpx, jinja2
- [x] Intégration avec `database/manager.py` existant

### 1.2 OAuth Twitch ✅
- [x] Route `GET /auth/twitch` - Redirect vers Twitch
- [x] Route `GET /auth/callback` - Échange code → tokens
- [x] Route `GET /auth/me` - Info user connecté
- [x] Route `POST /auth/logout` - Déconnexion
- [x] Stockage tokens chiffrés via DatabaseManager

### 1.3 API Broadcaster ✅
- [x] Route `GET /api/banwords/{channel}` - Liste banwords
- [x] Route `POST /api/banwords/{channel}` - Ajouter banword
- [x] Route `DELETE /api/banwords/{channel}/{word}` - Supprimer

---

## Phase 2 : Frontend (HTML + Alpine.js + Tailwind) ✅ DONE

### 2.1 Templates Jinja2 ✅
- [x] `base.html` - Layout avec Tailwind + Alpine CDN
- [x] `index.html` - Landing page + bouton "Login with Twitch"
- [x] `dashboard.html` - Dashboard avec gestion banwords

---

## Phase 3 : À faire

### 3.1 Tests
- [x] Tester le flow OAuth complet
- [x] Vérifier stockage tokens en BDD
- [x] Tester API banwords depuis dashboard

### 3.2 Production ✅
- [x] Configuration HTTPS
- [x] Variables d'environnement production
- [x] Reverse proxy Nginx
- [x] Correction config nginx pour transmission body POST

### 3.3 Améliorations futures
- [ ] **Statut bot dynamique** : Détecter si le bot (main.py/supervisor) tourne réellement
  - Option 1 : Vérifier PID dans `pids/*.pid` ou `kissbot.pid`
  - Option 2 : Health check endpoint exposé par le bot
  - Option 3 : Vérifier connexion IRC/EventSub active
  - Mettre à jour `bot_active` dans `api/router.py` (actuellement hardcodé à `True`)
- [ ] Stats temps réel (messages traités, bans auto)
- [ ] Gestion des commandes custom depuis le dashboard
- [ ] Logs du bot consultables via l'interface
