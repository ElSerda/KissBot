# 📢 Stream Announcements Configuration

Configuration pour les annonces automatiques stream online/offline (Phase 3.3).

## 📋 Configuration complète

```yaml
# config/config.yaml

announcements:
  # 📡 Paramètres de monitoring
  monitoring:
    enabled: true  # Active/désactive tout le monitoring (polling + EventSub)
    method: auto   # Méthode de détection (voir ci-dessous)
    polling_interval: 60  # Intervalle polling en secondes (mode fallback)
  
  # 🔴 Annonces stream ONLINE
  stream_online:
    enabled: true  # Active/désactive les annonces online
    message: "🔴 @{channel} est maintenant en live ! 🎮 {title}"
  
  # 💤 Annonces stream OFFLINE
  stream_offline:
    enabled: false  # Active/désactive les annonces offline
    message: "💤 @{channel} est maintenant hors ligne. À bientôt !"
```

---

## 🎛️ Options Détaillées

### `monitoring.enabled`

**Type:** `boolean`  
**Défaut:** `true`  
**Description:** Active ou désactive tout le système de monitoring stream.

- `true` : Le bot surveille les transitions online/offline
- `false` : Aucun monitoring, aucune annonce

**Use Case:** Désactiver temporairement les annonces sans supprimer la config.

---

### `monitoring.method`

**Type:** `string`  
**Défaut:** `"auto"`  
**Options:** `"auto"`, `"eventsub"`, `"polling"`

**Description:** Méthode de détection des transitions stream.

#### `"auto"` (Recommandé)
- **EventSub primary** : Real-time (<1s latency) si broadcaster OAuth disponible
- **Polling fallback** : Si EventSub indisponible, bascule sur polling Helix (60s latency)
- **Meilleur des deux mondes** : Real-time quand possible, fallback automatique

#### `"eventsub"`
- **EventSub uniquement** : WebSocket Twitch EventSub
- **Latency** : <1 seconde (real-time)
- **Requis** : Broadcaster OAuth token avec scope `moderator:read:followers`
- **Fail mode** : Si EventSub échoue, pas de fallback → pas d'annonces

#### `"polling"`
- **Polling uniquement** : Poll Helix API toutes les N secondes
- **Latency** : 30-60 secondes (dépend de `polling_interval`)
- **Avantage** : Pas besoin de broadcaster OAuth
- **API calls** : 1 call toutes les N secondes par channel

---

### `monitoring.polling_interval`

**Type:** `integer` (seconds)  
**Défaut:** `60`  
**Min recommandé:** `30`  
**Description:** Intervalle entre chaque vérification Helix API (mode polling).

**Exemples :**
- `30` : Détection rapide, plus d'API calls (OK pour <5 channels)
- `60` : Équilibre latency/API calls (recommandé)
- `120` : Économise API calls, latency acceptable

**Calcul API calls :**
- Channels surveillés : 3
- Interval : 60s
- **API calls/jour** : 3 × (86400 / 60) = **4320 calls/jour**
- Limite Twitch : 800 calls/minute = OK ✅

---

### `stream_online.enabled`

**Type:** `boolean`  
**Défaut:** `true`  
**Description:** Active/désactive les annonces quand stream passe online.

**Use Cases :**
- `true` : Auto-announce "🔴 Stream live !" dans le chat
- `false` : Silencieux, pas d'annonce (monitoring reste actif)

---

### `stream_online.message`

**Type:** `string` (avec variables)  
**Défaut:** `"🔴 @{channel} est maintenant en live ! 🎮 {title}"`

**Variables disponibles :**
- `{channel}` : Nom du channel (ex: `el_serda`)
- `{title}` : Titre du stream (ex: `"Coding session Python"`)
- `{game_name}` : Catégorie/jeu (ex: `"Science & Technology"`)
- `{viewer_count}` : Nombre de viewers actuels (ex: `42`)

**Exemples :**

```yaml
# Simple
message: "🔴 @{channel} est en live !"

# Avec titre
message: "🔴 @{channel} stream maintenant : {title}"

# Avec jeu
message: "🎮 @{channel} joue à {game_name} ! Venez voir 🔴"

# Complet
message: "🔴 LIVE ! @{channel} - {game_name} - {title} - {viewer_count} viewers 👀"

# Sans @mention (moins intrusif)
message: "🔴 Stream live : {title} sur {game_name}"
```

**Limite Twitch :** 500 caractères max (auto-tronqué si dépassé)

---

### `stream_offline.enabled`

**Type:** `boolean`  
**Défaut:** `false`  
**Description:** Active/désactive les annonces quand stream passe offline.

**⚠️ Attention Spam !**

Les annonces offline peuvent être perçues comme du **spam** :
- Stream crashe → Annonce offline
- Streamer redémarre → Annonce online
- Crash à nouveau → Annonce offline...

**Recommandé :** Laisser `false` sauf si vraiment nécessaire.

**Use Cases :**
- `false` : Pas d'annonce offline (recommandé)
- `true` : Annonce "💤 Stream terminé" (risque spam)

---

### `stream_offline.message`

**Type:** `string` (avec variables)  
**Défaut:** `"💤 @{channel} est maintenant hors ligne. À bientôt !"`

**Variables disponibles :**
- `{channel}` : Nom du channel

**Exemples :**

```yaml
# Simple
message: "💤 Stream terminé ! À bientôt 👋"

# Avec mention
message: "💤 @{channel} est hors ligne. Merci d'avoir regardé !"

# Fun
message: "⚡ @{channel} a quitté la matrice. Retour bientôt ! 🤖"
```

---

## 🎯 Configurations Recommandées

### Configuration Standard (Recommandée)

```yaml
announcements:
  monitoring:
    enabled: true
    method: auto  # EventSub + polling fallback
    polling_interval: 60
  
  stream_online:
    enabled: true
    message: "🔴 @{channel} est maintenant en live ! 🎮 {title}"
  
  stream_offline:
    enabled: false  # Désactivé pour éviter spam
```

**Avantages :**
- ✅ Real-time avec EventSub si disponible
- ✅ Fallback polling automatique
- ✅ Annonce online uniquement (pas de spam)
- ✅ Message clair avec titre du stream

---

### Configuration Minimaliste (Sans Broadcaster OAuth)

```yaml
announcements:
  monitoring:
    enabled: true
    method: polling  # Polling uniquement (pas besoin broadcaster OAuth)
    polling_interval: 60
  
  stream_online:
    enabled: true
    message: "🔴 @{channel} est en live !"
  
  stream_offline:
    enabled: false
```

**Avantages :**
- ✅ Pas besoin de broadcaster OAuth
- ✅ Setup simple
- ⚠️ Latency 30-60s (acceptable)

---

### Configuration Silencieuse (Monitoring Seulement)

```yaml
announcements:
  monitoring:
    enabled: true
    method: auto
    polling_interval: 60
  
  stream_online:
    enabled: false  # Pas d'annonce
  
  stream_offline:
    enabled: false
```

**Use Case :** Monitoring actif pour analytics, mais pas d'annonces chat.

---

### Configuration Désactivée

```yaml
announcements:
  monitoring:
    enabled: false  # Tout désactivé
```

**Use Case :** Désactiver temporairement sans supprimer la config.

---

## 🔧 Exemples de Messages Créatifs

### Style Hype

```yaml
message: "🔥🔥🔥 @{channel} DÉMARRE LE STREAM ! 🎮 {title} 🔥🔥🔥"
```

### Style Informatif

```yaml
message: "📺 Stream en cours : {game_name} - {title} par @{channel}"
```

### Style Minimaliste

```yaml
message: "🔴 @{channel} live"
```

### Style Fun/Geek

```yaml
message: "⚡ @{channel} vient d'entrer dans la matrice ! 🤖 {title}"
```

### Style Communautaire

```yaml
message: "🎉 @{channel} est en live ! Rejoignez-nous pour {game_name} ! 👥"
```

---

## 📊 Impact Performance

### Polling (60s interval, 3 channels)

- **CPU:** Négligeable (<0.1% avg)
- **RAM:** +5-10 MB
- **Network:** 4320 API calls/jour (~3 calls/min)
- **Latency:** 30-60 secondes

### EventSub (WebSocket)

- **CPU:** Négligeable (<0.1% avg)
- **RAM:** +10-15 MB (WebSocket connection)
- **Network:** Persistent WebSocket (keep-alive), 0 polling
- **Latency:** <1 seconde (real-time)

---

## ⚠️ Limitations et Notes

### Limite Twitch API

- **Rate limit:** 800 calls/minute (polling OK même avec 10+ channels)
- **EventSub:** Pas de rate limit (push events)

### Message Twitch

- **Longueur max:** 500 caractères
- **Auto-truncate:** Le bot coupe automatiquement à 497 chars + "..."

### Broadcaster OAuth

- **Requis pour EventSub:** Oui (scope `moderator:read:followers`)
- **Requis pour Polling:** Non (bot token suffit)

### Multiple Channels

- Le monitoring surveille **tous les channels** listés dans `twitch.channels`
- Annonce dans le chat du channel concerné uniquement
- Pas d'annonce croisée (el_serda online ≠ annonce dans #morthycya)

---

## 🚀 Quick Start

### 1. Activer les annonces (polling simple)

```yaml
announcements:
  monitoring:
    enabled: true
    method: polling
    polling_interval: 60
  
  stream_online:
    enabled: true
    message: "🔴 @{channel} est en live ! 🎮 {title}"
```

### 2. Redémarrer le bot

```bash
python3 main.py
```

### 3. Vérifier les logs

```
📡 StreamMonitor initialized - Monitoring 3 channels, interval=60s
✅ StreamMonitor started
📢 StreamAnnouncer initialized - online=True, offline=False
```

### 4. Tester (passer stream online)

Le bot annoncera automatiquement dans le chat après détection (30-60s).

---

## 🔍 Troubleshooting

### Pas d'annonce détectée

1. Vérifier `monitoring.enabled: true`
2. Vérifier `stream_online.enabled: true`
3. Checker les logs pour "🔴 STREAM ONLINE"
4. Vérifier que le channel est dans `twitch.channels`

### Latency trop élevée

1. Réduire `polling_interval` (ex: 30s)
2. Ou activer EventSub avec broadcaster OAuth

### Spam offline

1. Désactiver `stream_offline.enabled: false`
2. Ou augmenter `polling_interval` pour réduire fréquence

---

## 📚 Voir Aussi

- [Phase 3.3 Architecture](PHASE3_ARCHITECTURE.md#phase-33)
- [EventSub Setup Guide](../twitchapi/EVENTSUB_SETUP.md) (à venir)
- [Broadcaster OAuth](../twitchapi/BROADCASTER_OAUTH.md) (à venir)
