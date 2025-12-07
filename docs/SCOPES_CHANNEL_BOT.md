# 🔐 Scope `channel:bot` - Éviter le /mod

## 🎯 Problème

Par défaut, pour envoyer des messages via `send_chat_message` (EventSub Chat), le bot **doit être mod** sur le channel.

**Symptôme :**
- Le bot reçoit les messages ✅
- Le bot essaie de répondre ❌
- Les messages n'apparaissent PAS dans le chat
- Pas d'erreur visible (silencieux)

## 🔧 Solution : Scope `channel:bot`

Le scope **`channel:bot`** permet au bot d'envoyer des messages **sans être mod** !

### Scopes requis pour EventSub Chat:

```python
# Bot account (serda_bot):
- user:read:chat       # Lire le chat
- user:write:chat      # Envoyer des messages
- user:bot             # Apparaître comme bot dans la liste
- channel:bot          # 🎉 ENVOYER SANS /mod !
```

### Comment ajouter le scope:

```bash
# 1. Lancer le script OAuth
python scripts/update_bot_scopes.py --bot serda_bot

# 2. Se connecter avec le compte BOT (serda_bot)
#    Le navigateur s'ouvre automatiquement

# 3. Le broadcaster (el_serda) doit approuver le scope channel:bot
#    (Twitch affichera une demande d'autorisation)

# 4. Redémarrer le bot
./kissbot.sh restart --use-db
```

## 📚 Référence Twitch API

**Endpoint:** `POST /helix/chat/messages`

**Authorization:**
- User access token avec `user:write:chat` scope
- **SI le bot n'est pas mod:** Requiert `channel:bot` scope (approuvé par le broadcaster)
- **SI le bot est mod:** Pas besoin de `channel:bot`

**Docs officielles:**
https://dev.twitch.tv/docs/api/reference/#send-chat-message

---

## ⚠️ Alternative simple

Si tu ne veux pas gérer le scope `channel:bot`, tu peux simplement:

```
/mod serda_bot
```

C'est plus simple et déjà fonctionnel ! 😅

---

## 🔍 Vérifier les scopes en DB

```bash
# Vérifier les scopes du bot
python scripts/check_current_scopes.py serda_bot

# Doit afficher:
# ✅ channel:bot présent !
```

## 📝 Notes

- Le scope `channel:bot` doit être **approuvé par chaque broadcaster**
- Si tu rejoins un nouveau channel, le broadcaster doit approuver le scope
- Le scope `user:bot` est différent (pour apparaître comme bot, pas pour les permissions)
