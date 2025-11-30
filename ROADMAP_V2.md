# 🗺️ KissBot V2 — Roadmap

> **Objectif** : Architecture modulaire propre  
> **Timeline** : Flexible, par features  
> **Philosophie** : Itératif, ship quand c'est prêt

---

## 📅 Phases principales

```
Phase 1 : Core isolation        ████████░░░░░░░░
Phase 2 : Modules essentiels    ░░░░░░░░████████
Phase 3 : Polish & doc          ░░░░░░░░░░░░████
```

---

## 🚀 Phase 1 : Core KISS Isolation

### Étape 1 : Audit & Restructuration
**Objectif** : Identifier ce qui appartient au core vs modules

- [ ] **Audit fichiers actuels**
  ```bash
  # Lister tous les fichiers Python
  find . -name "*.py" -not -path "./kissbot-venv/*" | sort
  
  # Identifier les dépendances (import graphs)
  pipdeptree -p kissbot
  ```

- [ ] **Créer nouvelle structure `core/`**
  ```
  core/
  ├── __init__.py
  ├── irc_client.py           # Déjà existe (avec keepalive)
  ├── eventsub_hub.py         # Déjà existe (WebSocket)
  ├── message_handler.py      # Nouveau (parsing pur)
  ├── command_router.py       # Nouveau (dispatch)
  ├── rate_limiter.py         # Existe, à nettoyer
  ├── security.py             # Nouveau (validation)
  └── types.py                # Nouveau (BotEvent, BotResponse)
  ```

- [ ] **Définir interfaces core**
  ```python
  # core/types.py
  
  from dataclasses import dataclass
  from typing import Optional, Dict, Any
  
  @dataclass
  class BotEvent:
      """Événement entrant normalisé"""
      type: str              # "chat_message" | "subscription" | "raid"
      channel_id: str
      channel_name: str
      user_id: str
      user_name: str
      message: Optional[str]
      metadata: Dict[str, Any]
      timestamp: float
  
  @dataclass
  class BotResponse:
      """Réponse sortante normalisée"""
      text: str
      targets: list[str]     # ["chat", "tts", "obs"]
      metadata: Dict[str, Any]
  ```

**Critères de succès** :
- ✅ `core/` contient UNIQUEMENT le strict nécessaire
- ✅ Zéro import de `intelligence/`, `backends/`, `commands/`
- ✅ Tests unitaires passent (`pytest tests/core/`)

---

### Jour 3-4 : Extraction Modules Existants
**Objectif** : Déplacer features dans `modules/`

- [ ] **Créer `modules/` structure**
  ```
  modules/
  ├── __init__.py
  ├── base_module.py          # Interface abstraite
  ├── intelligence/           # Ancien intelligence/
  │   ├── __init__.py
  │   ├── quantum_classifier.py
  │   ├── reflex_center.py
  │   └── cloud_synapse.py
  ├── game_lookup/            # Ancien backends/game_lookup*
  │   ├── __init__.py
  │   ├── rust_engine.py
  │   └── python_fallback.py
  └── classic_commands/       # Ancien commands/
      ├── __init__.py
      ├── user_commands/
      ├── mod_commands/
      └── admin_commands/
  ```

- [ ] **Implémenter `BaseModule` interface**
  ```python
  # modules/base_module.py
  
  from abc import ABC, abstractmethod
  from typing import Optional
  from core.types import BotEvent, BotResponse
  
  class BaseModule(ABC):
      def __init__(self, config: dict):
          self.enabled = config.get("enabled", False)
          self.config = config
      
      @abstractmethod
      async def handle(self, event: BotEvent) -> Optional[BotResponse]:
          """
          Traite un événement.
          Retourne None si le module ne gère pas cet événement.
          """
          pass
      
      async def on_load(self):
          """Hook appelé au chargement du module"""
          pass
      
      async def on_unload(self):
          """Hook appelé au déchargement (cleanup)"""
          pass
  ```

- [ ] **Migrer modules existants**
  - `intelligence/` → `modules/intelligence/`
  - `backends/` → `modules/integrations/`
  - `commands/` → `modules/classic_commands/`

**Critères de succès** :
- ✅ Chaque module hérite de `BaseModule`
- ✅ Modules isolés (pas d'imports croisés)
- ✅ Config YAML par module (`config/modules/`)

---

### Jour 5-7 : Tests & Documentation Core
**Objectif** : Core 100% testé et documenté

- [ ] **Tests unitaires core**
  ```bash
  pytest tests/core/test_message_handler.py -v
  pytest tests/core/test_rate_limiter.py -v
  pytest tests/core/test_command_router.py -v
  pytest tests/core/test_security.py -v
  
  # Coverage minimum : 80%
  pytest tests/core/ --cov=core --cov-report=html
  ```

- [ ] **Documentation core**
  - Docstrings complets (Google style)
  - Type hints partout
  - Examples dans `docs/CORE_ARCHITECTURE.md`

**Critères de succès** :
- ✅ Coverage > 80%
- ✅ Tous les tests passent
- ✅ Documentation claire et exemples concrets

---

## 🧩 Phase 2 : Modules Essentiels (Semaine 2)

### Jour 8-10 : Module Personality
**Objectif** : PersonalityDB + commande !persona

- [ ] **Schéma DB**
  ```sql
  CREATE TABLE personality (
      id INTEGER PRIMARY KEY,
      channel_id TEXT UNIQUE NOT NULL,
      tone TEXT DEFAULT 'soft',
      energy TEXT DEFAULT 'medium',
      emoji_level TEXT DEFAULT 'some',
      politeness TEXT DEFAULT 'high',
      nsfw_level TEXT DEFAULT 'none',
      temp_profile TEXT,
      temp_expires_at DATETIME,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  ```

- [ ] **PersonalityStore (CRUD)**
  ```python
  # modules/personality/store.py
  
  class PersonalityStore:
      async def get(self, channel_id: str) -> PersonalityProfile
      async def update(self, channel_id: str, **kwargs)
      async def reset(self, channel_id: str)
      async def apply_preset(self, channel_id: str, preset: str)
  ```

- [ ] **Commande !persona**
  ```python
  # modules/personality/commands.py
  
  @mod_only
  async def handle_persona(bot, cmd: ChatCommand):
      # !persona → affiche profil
      # !persona tone cru → modifie
      # !persona preset soir_cru → applique preset
      # !persona reset → défauts
  ```

- [ ] **Style injection dans LLM**
  ```python
  # modules/personality/style_builder.py
  
  def build_style_instructions(profile: PersonalityProfile) -> str:
      # Génère prompt système pour GPT-4
  ```

**Critères de succès** :
- ✅ DB créée avec migration
- ✅ Commande !persona testée en prod
- ✅ Style injecté dans cloud_synapse.py

---

### Jour 11-12 : Module Custom Commands
**Objectif** : Système !addcmd complet

- [ ] **Schéma DB**
  ```sql
  CREATE TABLE custom_commands (
      id INTEGER PRIMARY KEY,
      channel_id TEXT NOT NULL,
      command_name TEXT NOT NULL,
      template TEXT NOT NULL,
      llm_enabled BOOLEAN DEFAULT 0,
      persona_override TEXT,
      output_targets TEXT,  -- JSON: ["chat", "tts"]
      points_cost INTEGER DEFAULT 0,
      cooldown_seconds INTEGER DEFAULT 0,
      usage_count INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(channel_id, command_name)
  );
  ```

- [ ] **Parser de syntaxe**
  ```python
  # modules/custom_commands/parser.py
  
  def parse_addcmd(args: str) -> CustomCommandConfig:
      # !addcmd greet "Hello {user}" LLM:ON OUTPUT:chat+tts
      # → CustomCommandConfig(...)
  ```

- [ ] **Template engine**
  ```python
  # modules/custom_commands/template.py
  
  def render_template(template: str, context: dict) -> str:
      # "Hello {user}" + {"user": "ElSerda"} → "Hello ElSerda"
  ```

- [ ] **Commandes CRUD**
  ```python
  # !addcmd <nom> "<template>" [OPTIONS]
  # !editcmd <nom> <param> <value>
  # !delcmd <nom>
  # !listcmd
  ```

**Critères de succès** :
- ✅ Parsing robuste (edge cases gérés)
- ✅ Templates variables fonctionnelles
- ✅ LLM:ON intégré avec persona

---

### Jour 13-14 : Module Outputs
**Objectif** : Output router multi-target

- [ ] **OutputRouter interface**
  ```python
  # modules/outputs/router.py
  
  class OutputRouter:
      def __init__(self, config: dict):
          self.chat = ChatOutput() if config["chat"] else None
          self.tts = TTSOutput() if config["tts"] else None
          self.obs = OBSOutput() if config["obs"] else None
          self.webhook = WebhookOutput() if config["webhook"] else None
      
      async def send(self, response: BotResponse, targets: list[str]):
          for target in targets:
              await self._route(target, response)
  ```

- [ ] **Implémentations**
  - `chat_output.py` : IRC send (existe déjà)
  - `tts_output.py` : WebSocket vers Streamer.bot
  - `obs_output.py` : OBS WebSocket (trigger scenes/sources)
  - `webhook_output.py` : HTTP POST

**Critères de succès** :
- ✅ Multi-target fonctionne (`OUTPUT:chat+tts`)
- ✅ Graceful degradation (si TTS désactivé, skip silencieusement)
- ✅ Logs clairs pour debugging

---

## 🔗 Phase 3 : Intégrations Externes (Semaine 3)

### Jour 15-17 : Streamer.bot Integration
**Objectif** : Envoyer messages TTS via WebSocket

- [ ] **Reverse-engineer Streamer.bot protocol**
  ```bash
  # Analyser WebSocket frames
  # Port par défaut : 8080
  ```

- [ ] **Client WebSocket**
  ```python
  # modules/outputs/streamerbot_client.py
  
  class StreamerBotClient:
      async def connect(self, host: str, port: int)
      async def send_tts(self, text: str, voice: str = "default")
      async def trigger_action(self, action_id: str, args: dict)
  ```

- [ ] **Tests avec ton setup existant**
  - Vérifier compatibilité avec ton projet TTS séparé

**Critères de succès** :
- ✅ TTS fonctionne depuis KissBot
- ✅ Pas de conflit avec projet TTS existant
- ✅ Fallback gracieux si Streamer.bot offline

---

### Jour 18-19 : OBS WebSocket Integration
**Objectif** : Trigger overlays/scenes depuis bot

- [ ] **OBS WebSocket v5 client**
  ```python
  # modules/outputs/obs_client.py
  
  class OBSClient:
      async def connect(self, host: str, port: int, password: str)
      async def trigger_scene(self, scene_name: str)
      async def show_source(self, source_name: str)
      async def send_browser_event(self, event: dict)
  ```

- [ ] **Events custom**
  ```python
  # Exemple : !hype déclenche animation overlay
  await obs.send_browser_event({
      "event": "hype_mode",
      "duration": 5000,
      "intensity": "high"
  })
  ```

**Critères de succès** :
- ✅ Connexion OBS stable
- ✅ Events custom reçus dans overlay HTML/JS
- ✅ Documentation pour setup overlay

---

### Jour 20-21 : Webhook Router + Points System
**Objectif** : POST vers APIs externes + système de points

- [ ] **Webhook output**
  ```python
  # modules/outputs/webhook_output.py
  
  class WebhookOutput:
      async def post(self, url: str, payload: dict):
          async with aiohttp.ClientSession() as session:
              await session.post(url, json=payload)
  ```

- [ ] **Points system (simple)**
  ```sql
  CREATE TABLE user_points (
      id INTEGER PRIMARY KEY,
      channel_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      points INTEGER DEFAULT 0,
      last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(channel_id, user_id)
  );
  ```

- [ ] **Commandes points**
  ```python
  # !points → voir ses points
  # !addpoints @user 100 → mod only
  # !leaderboard → top 10
  ```

**Critères de succès** :
- ✅ Webhooks testés avec Discord/Slack
- ✅ Points gagnés par présence chat (1pt/5min)
- ✅ Commandes custom coûtent des points

---

## 🎨 Phase 4 : Polish & Release (Semaine 4)

### Jour 22-23 : Documentation Complète
**Objectif** : README + guides utilisateur

- [ ] **README.md refonte totale**
  - Badges (tests, coverage, version)
  - Quickstart 5 minutes
  - Features showcase (GIFs/vidéos)
  - Architecture diagram
  - Comparaison vs concurrence

- [ ] **Guides utilisateur**
  - `docs/QUICKSTART.md` : Installation pas-à-pas
  - `docs/CUSTOM_COMMANDS.md` : Guide !addcmd complet
  - `docs/PERSONALITY.md` : Guide !persona + presets
  - `docs/INTEGRATIONS.md` : Setup TTS/OBS/Streamer.bot
  - `docs/POINTS_SYSTEM.md` : Gamification

- [ ] **Guides développeur**
  - `CONTRIBUTING.md` : Guidelines contribution
  - `docs/MODULE_DEVELOPMENT.md` : Créer un module custom
  - `docs/API_REFERENCE.md` : Types, interfaces, hooks

**Critères de succès** :
- ✅ README clair et sexy (inspiré de projets top GitHub)
- ✅ Guides testés par beta-testeur naïf
- ✅ Vidéo quickstart 3 minutes (optionnel)

---

### Jour 24-25 : CI/CD + Tests E2E
**Objectif** : Pipeline GitHub Actions + tests production-like

- [ ] **GitHub Actions workflow**
  ```yaml
  # .github/workflows/ci.yml
  
  name: CI
  on: [push, pull_request]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - uses: actions/setup-python@v4
        - run: pip install -r requirements-dev.txt
        - run: pytest tests/ --cov=core --cov=modules
        - run: python test_rust_integration.py
  ```

- [ ] **Tests E2E**
  ```python
  # tests/e2e/test_full_pipeline.py
  
  async def test_custom_command_with_llm():
      # Simule : !addcmd test "..." LLM:ON
      # Vérifie : réponse GPT correcte
      # Vérifie : output routing
  ```

- [ ] **Docker support (optionnel)**
  ```dockerfile
  # Dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY . .
  RUN pip install -r requirements.txt
  CMD ["python", "main.py"]
  ```

**Critères de succès** :
- ✅ Tests passent sur GitHub Actions
- ✅ Coverage affiché (badge README)
- ✅ Docker image build et run

---

### Jour 26-28 : Beta Testing + Bug Fixes
**Objectif** : Tester en prod, fixer bugs critiques

- [ ] **Beta testeurs**
  - 3-5 streamers testent sur vraies chaînes
  - Feedback via Discord/GitHub Issues

- [ ] **Bug fixes prioritaires**
  - Crash/stability issues : P0 (fix immédiat)
  - UX confusing : P1 (fix avant release)
  - Nice-to-have : P2 (backlog v2.1)

- [ ] **Performance tuning**
  - Profiling (`cProfile`, `py-spy`)
  - Optimisations critiques (rate limiting, DB queries)
  - Load testing (simulate 100 users spam)

**Critères de succès** :
- ✅ Zéro crash en 24h de prod
- ✅ Beta testeurs "happy" (NPS > 8/10)
- ✅ Performance acceptable (<100ms latency)

---

### Jour 29 : Release v2.0.0
**Objectif** : Ship it! 🚀

- [ ] **Pre-release checklist**
  - [ ] Tous les tests passent
  - [ ] Documentation complète
  - [ ] CHANGELOG.md à jour
  - [ ] Version bump (pyproject.toml)
  - [ ] Git tag v2.0.0

- [ ] **Release GitHub**
  ```bash
  git tag -a v2.0.0 -m "KissBot V2 - Modular Architecture"
  git push origin v2.0.0
  ```

- [ ] **Communication**
  - Post Reddit r/Twitch, r/Python
  - Tweet avec vidéo demo
  - Post Discord serveurs dev Twitch
  - Hacker News (si traction)

**Critères de succès** :
- ✅ Release notes claires
- ✅ Binaries/Docker image disponibles
- ✅ Première vague de feedback positif

---

## 📊 Critères de qualité

### Techniques
- ✅ Core coverage > 80%
- ✅ Stable en prod 24h+
- ✅ Latency raisonnable (<500ms)
- ✅ Memory sous contrôle

### Fonctionnels
- ✅ Docs claires
- ✅ Tests passent
- ✅ Facile à déployer
- ✅ Facile à étendre

---

## 🔥 Quick Wins (à prioriser)

Si le temps manque, focus sur :

1. **!addcmd système** (killer feature) → 3 jours
2. **Personality DB** (différenciation) → 2 jours
3. **Output chat + TTS** (use case concret) → 2 jours
4. **README sexy** (marketing) → 1 jour

= **8 jours** pour MVP impressionnant

---

## 🚧 Risques & Mitigation

### Risque 1 : Scope Creep
**Mitigation** : MVP strict, features avancées → v2.1

### Risque 2 : Breaking Changes
**Mitigation** : Tests E2E, beta testing avant release

### Risque 3 : Performance Rust Engine
**Mitigation** : Déjà testé (93x speedup prouvé)

### Risque 4 : Adoption faible
**Mitigation** : Marketing agressif, vidéo demo, beta testeurs influents

---

## 💡 Idées Futures (Post-v2.0)

### v2.1 : Advanced Features
- Multi-language support (EN, FR, ES)
- Voice commands (Whisper STT)
- Clip auto-generation
- Analytics dashboard (web UI)

### v2.2 : Enterprise
- Multi-channel management UI
- Role-based permissions
- Backup/restore configs
- Cloud hosting option

### v3.0 : Ecosystem
- Module marketplace
- Visual scripting (node editor)
- Mobile app (iOS/Android)
- API for third-party integrations

---

**Next Action** : Commencer Phase 1 (Audit & Restructuration)

**Approche** : Itératif, une feature à la fois, ship quand stable

---

**Auteur** : ElSerda + GitHub Copilot  
**Date** : 30 novembre 2025  
**Version** : 2.0.0-alpha
