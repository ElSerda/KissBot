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
- [ ] Tester le flow OAuth complet
- [ ] Vérifier stockage tokens en BDD
- [ ] Tester API banwords depuis dashboard

### 3.2 Production
- [ ] Configuration HTTPS
- [ ] Variables d'environnement production
- [ ] Reverse proxy Nginx
