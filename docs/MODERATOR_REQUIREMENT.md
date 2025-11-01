# Twitch Bot Moderator/VIP Requirement

## 🚨 Important: Twitch Bot Policy

**Les bots Twitch non-vérifiés DOIVENT être modérateurs ou VIP pour envoyer des messages !**

## Pourquoi cette restriction ?

### Twitch Policy: Verified vs Non-Verified Bots

| Bot Type | Can Send Without Mod/VIP? | Rate Limit | Verification Process |
|----------|---------------------------|------------|---------------------|
| **Non-verified** | ❌ **NON** | 20 msg/30s | Aucun (default) |
| **Verified** | ✅ **OUI** | 2000 msg/30s | [Application Twitch](https://dev.twitch.tv/docs/irc#verified-bots) |

### Pourquoi Twitch filtre les bots non-vérifiés ?

**Protection anti-spam** : Twitch veut éviter :
- Bots malveillants qui spamment tous les channels
- Bots créés pour harceler/troll
- Bots non-contrôlés envoyant du contenu inapproprié

**Solution Twitch** :
1. **Courts terme** : Bot doit avoir la confiance du broadcaster (mod/VIP)
2. **Long terme** : Bot devient vérifié après historique propre

## Comment ça marche techniquement ?

### 1. IRC envoie le message avec SUCCÈS

```python
# Ton code bot
await chat.send_message("el_serda", "@user Pong! 🏓")

# pyTwitchAPI logs
✅ Sent to #el_serda: @user Pong!...

# Pas d'erreur IRC ! Message envoyé au serveur Twitch
```

### 2. Twitch filtre SILENCIEUSEMENT côté serveur

```
Bot (non-mod) → IRC PRIVMSG → Twitch Server
                              ↓
                         [Filter Check]
                              ↓
                         Is bot mod/VIP?
                         ├─ YES → Message appears in chat ✅
                         └─ NO  → Message DROPPED (silent) ❌
```

**Aucune erreur retournée** - C'est une politique Twitch, pas un bug technique !

### 3. Résultat visible dans Twitch

- **Bot mod/VIP** : Message apparaît normalement
- **Bot non-mod/VIP** : Message invisible (comme s'il n'avait jamais été envoyé)

## Expérience utilisateur

### Scenario A : Bot NON-mod (❌ Message invisible)

```
[User Twitch chat]
18:45:30 | el_serda: !ping
18:45:30 | (rien...)

[Bot logs]
18:45:30 | INFO 📤 Tentative envoi IRC à #el_serda
18:45:30 | INFO ✅ Sent to #el_serda: @el_serda Pong!...

[Twitch web chat]
(message serda_bot n'apparaît JAMAIS)
```

### Scenario B : Bot MOD ou VIP (✅ Message visible)

```
[User Twitch chat]
18:47:15 | el_serda: !ping
18:47:15 | serda_bot: @el_serda Pong! 🏓  ← Visible !

[Bot logs]
18:47:15 | INFO 📤 Tentative envoi IRC à #el_serda
18:47:15 | INFO ✅ Sent to #el_serda: @el_serda Pong!...

[Twitch web chat]
18:47:15 | serda_bot: @el_serda Pong! 🏓  ← Apparaît !
```

## Solutions

### Solution 1 : Donner le statut Mod/VIP (Immédiat)

**Modérateur** (recommandé pour ton propre bot) :
```
# Dans le chat Twitch du broadcaster
/mod serda_bot
```

**VIP** (si pas modérateur) :
```
# Dans le chat Twitch du broadcaster
/vip serda_bot
```

**Avantages** :
- ✅ Immédiat (0 délai)
- ✅ Fonctionne sur n'importe quel channel
- ✅ Pas de démarches administratives

**Inconvénients** :
- ⚠️ Doit être fait manuellement sur **chaque channel**
- ⚠️ Le broadcaster doit faire confiance au bot
- ⚠️ Rate limit reste 20 msg/30s (non-verified)

### Solution 2 : Demander la vérification Twitch (Long terme)

**Process officiel** : https://dev.twitch.tv/docs/irc#verified-bots

**Étapes** :
1. Créer un historique bot propre (pas de spam, respecte TOS)
2. Bot actif sur plusieurs channels (preuve d'utilité)
3. Soumettre application Twitch (formulaire + justification)
4. Twitch review (quelques semaines)
5. Si approuvé : Bot devient vérifié

**Avantages après vérification** :
- ✅ **Envoie sans être mod/VIP** sur n'importe quel channel
- ✅ Rate limit élevé : **2000 msg/30s** (vs 20)
- ✅ Badge "Verified Bot" sur Twitch
- ✅ Pas de setup manuel par broadcaster

**Inconvénients** :
- ⏳ Process long (semaines/mois)
- 📝 Dossier à constituer
- ⚖️ Twitch peut refuser si bot pas assez utilisé

### Solution 3 : Système d'auto-request (Phase 3+)

**Idée** : Bot demande automatiquement le statut au join

```python
# Pseudo-code Phase 3
async def on_channel_join(self, channel):
    if not self.chat.is_mod(channel):
        # Option A: Message public discret
        await self.send_message(channel, 
            f"⚠️ @{broadcaster} Pour activer toutes mes fonctionnalités, "
            f"tape /mod serda_bot ou /vip serda_bot 😊"
        )
        
        # Option B: Log pour l'admin
        LOGGER.warning(f"Bot not mod/VIP on #{channel} - Limited functionality")
```

**Avantages** :
- ✅ Automatise la communication avec broadcasters
- ✅ Réduit le support manuel
- ✅ Education des nouveaux utilisateurs

**Inconvénients** :
- ⚠️ Peut être vu comme spam par certains broadcasters
- ⚠️ Nécessite implémentation (Phase 3+)

## Détection du statut Mod/VIP

### pyTwitchAPI provides built-in detection

```python
# Dans IRC Client
is_mod = self.chat.is_mod("el_serda")
is_vip = self.chat.is_subscriber("el_serda")  # (VIP included)

if is_mod:
    print("✅ Bot is moderator on #el_serda")
else:
    print("⚠️ Bot is NOT moderator on #el_serda")
```

### Twitch envoie les badges avec chaque message

```python
# Badge parsing dans ChatMessage
badges = {
    "broadcaster": "1",  # Owner du channel
    "moderator": "1",    # Modérateur
    "vip": "1",          # VIP
    "subscriber": "12"   # Sub (12 mois)
}
```

## Documentation pyTwitchAPI

### Chat.__init__() parameter: `is_verified_bot`

```python
from twitchAPI.chat import Chat

chat = Chat(
    twitch=twitch,
    is_verified_bot=False  # ← False pour bots non-vérifiés (default)
)

# Impacts:
# - is_verified_bot=False → Rate limit 20 msg/30s
# - is_verified_bot=True  → Rate limit 2000 msg/30s
```

### Rate Limiting automatique

```python
# pyTwitchAPI gère automatiquement les buckets
self._join_bucket = RateLimitBucket(
    10,                               # 10 joins
    2000 if is_verified_bot else 20,  # 2000 ou 20 channels
    'channel_join',
    self.logger
)

# Bucket par channel pour messages
bucket = RateLimitBucket(
    30,                    # 30 messages
    20,                    # Dans 20 secondes (non-verified)
    channel_name,
    logger
)
```

## Tests de validation

### Test 1 : Bot NON-mod

```bash
# 1. Retirer le mod
# Dans Twitch chat: /unmod serda_bot

# 2. Lancer le bot
python main.py

# 3. Taper !ping
# Expected: Logs montrent "✅ Sent" mais message invisible dans chat

# 4. Vérifier les logs
tail -f kissbot_production.log
# ✅ Sent to #el_serda: @user Pong!...
# (mais rien dans Twitch web chat)
```

### Test 2 : Bot MOD

```bash
# 1. Donner le mod
# Dans Twitch chat: /mod serda_bot

# 2. Lancer le bot
python main.py

# 3. Taper !ping
# Expected: Message apparaît dans chat ✅

# 4. Vérifier Twitch web chat
# serda_bot: @user Pong! 🏓 ← Visible !
```

### Test 3 : Bot VIP (autre channel)

```bash
# 1. Sur un autre channel que le tien
# Broadcaster tape: /vip serda_bot

# 2. Bot rejoint ce channel
# Dans config.yaml: channels: ["el_serda", "autre_channel"]

# 3. Taper !ping sur autre_channel
# Expected: Message apparaît ✅
```

## Troubleshooting

### "Bot envoie mais messages invisibles"

✅ **Vérifier le statut mod/VIP** :
```python
# Dans IRC Client logs
is_mod = self.chat.is_mod("el_serda")
print(f"Bot mod status: {is_mod}")

# Si False → Donner /mod ou /vip
```

### "Certains channels marchent, d'autres non"

✅ **Status différent par channel** :
```python
# Bot peut être:
# - Mod sur #el_serda → Messages passent ✅
# - Non-mod sur #morthycya → Messages bloqués ❌

# Solution: /mod serda_bot sur TOUS les channels
```

### "Logs disent 'Sent' mais rien dans chat"

✅ **Normal si non-mod** - C'est le comportement Twitch attendu :
- IRC protocol layers fonctionne (pas d'erreur)
- Twitch server-side filtering appliqué après
- Pas de feedback d'erreur (policy Twitch)

### "Rate limiting errors"

✅ **Trop de messages envoyés** :
```python
# Non-verified: 20 msg/30s maximum
# Solution temporaire: Réduire fréquence commandes
# Solution long terme: Demander vérification (2000 msg/30s)
```

## Recommandations

### Pour développement (channels personnels)

**Recommandé** : `/mod serda_bot` sur tous tes channels
- ✅ Développement sans friction
- ✅ Tests complets possibles
- ✅ Pas besoin de vérification Twitch immédiatement

### Pour production (channels multiples)

**Option A - Court terme** :
1. Créer une page d'onboarding : "Comment ajouter le bot"
2. Expliquer le requirement mod/VIP
3. Broadcaster fait `/mod serda_bot` manuellement

**Option B - Long terme** :
1. Constituer un dossier vérification Twitch
2. Montrer historique bot propre (pas de spam, TOS respecté)
3. Soumettre application officielle
4. Une fois vérifié : Plus besoin de mod/VIP

### Best practice: Documentation utilisateur

**Créer un guide pour broadcasters** :

```markdown
# Ajouter serda_bot à ton channel

## Étape 1: Inviter le bot
Type dans ton chat Twitch:
/mod serda_bot

## Étape 2: Tester
Type:
!ping

Le bot devrait répondre "Pong! 🏓"

## Pourquoi mod/VIP ?
Twitch exige que les bots non-vérifiés soient modérateurs ou VIP
pour envoyer des messages (protection anti-spam).
```

## Références

### Documentation officielle

- **Twitch IRC Docs** : https://dev.twitch.tv/docs/irc
- **Verified Bots** : https://dev.twitch.tv/docs/irc#verified-bots
- **pyTwitchAPI Chat** : https://pytwitchapi.dev/en/stable/modules/twitchAPI.chat.html

### Extraits pyTwitchAPI source

```python
# twitchAPI/chat/__init__.py
class Chat:
    def __init__(self, 
                 twitch: Twitch,
                 is_verified_bot: bool = False,
                 ...):
        """
        :param is_verified_bot: set to true if your bot is verified by twitch
        """
        self._join_bucket = RateLimitBucket(
            10,
            2000 if is_verified_bot else 20,  # ← Rate limit différent
            'channel_join',
            self.logger
        )
```

---

**TL;DR** :
- ⚠️ Bots non-vérifiés = **Mod/VIP obligatoire** pour envoyer
- 🔧 Solution immédiate : `/mod serda_bot` sur chaque channel
- 🏆 Solution long terme : [Demander vérification Twitch](https://dev.twitch.tv/docs/irc#verified-bots)
- 🚀 Après vérification : Envoie partout + 2000 msg/30s
