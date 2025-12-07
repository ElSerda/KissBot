#!/usr/bin/env python3
"""
Test: Vérifier que le bot peut utiliser le token broadcaster de el_serda
pour envoyer des annonces
"""
import asyncio
import sys
import random
import time
from pathlib import Path

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).parent))

from database.manager import DatabaseManager
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope

async def test_broadcaster_token():
    """Test d'envoi d'annonce avec le token broadcaster de el_serda"""
    
    # 1. Charger la config (credentials depuis config.yaml)
    import yaml
    with open("config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    client_id = config['twitch']['client_id']
    client_secret = config['twitch']['client_secret']
    
    print(f"✅ Config chargée (client_id: {client_id[:10]}...)")
    
    # 2. Charger le token broadcaster de el_serda depuis la DB
    db = DatabaseManager('kissbot.db', '.kissbot.key')
    
    el_serda_user = db.get_user_by_login('el_serda')
    if not el_serda_user:
        print("❌ User el_serda non trouvé en DB")
        return
    
    broadcaster_token = db.get_tokens(el_serda_user['id'], token_type='broadcaster')
    if not broadcaster_token:
        print("❌ Token broadcaster non trouvé pour el_serda")
        return
    
    print(f"✅ Token broadcaster chargé pour el_serda")
    
    # Scopes stockés comme JSON array string '["scope1", "scope2", ...]'
    import json
    scopes_str = broadcaster_token['scopes']
    if isinstance(scopes_str, str):
        scopes_list = json.loads(scopes_str)
    else:
        scopes_list = scopes_str
    
    print(f"   Scopes: {len(scopes_list)}")
    print(f"   Has moderator:manage:announcements: {'moderator:manage:announcements' in scopes_list}")
    
    # 3. Créer instance Twitch avec token broadcaster
    twitch = Twitch(client_id, client_secret)
    
    # Convertir scopes string en AuthScope enum
    scope_enums = []
    for scope_str in scopes_list:
        try:
            # Essayer de trouver l'enum correspondant
            for auth_scope in AuthScope:
                if auth_scope.value == scope_str:
                    scope_enums.append(auth_scope)
                    break
        except Exception:
            print(f"⚠️ Scope inconnu: {scope_str}")
    
    print(f"   Converted to {len(scope_enums)} AuthScope enums")
    
    # 4. Set authentication avec le token broadcaster
    await twitch.set_user_authentication(
        token=broadcaster_token['access_token'],
        scope=scope_enums,
        refresh_token=broadcaster_token['refresh_token'],
        validate=True
    )
    
    print("✅ Authentification configurée avec token broadcaster")
    
    # 5. Récupérer l'ID de el_serda
    broadcaster_id = None
    async for user in twitch.get_users(logins=['el_serda']):
        broadcaster_id = user.id
        print(f"✅ Broadcaster ID: {broadcaster_id}")
        break
    
    if not broadcaster_id:
        print("❌ Impossible de récupérer l'ID de el_serda")
        return
    
    # 6. TEST: Envoyer une annonce de test puis un message chat simple
    try:
        # Générer un timestamp/random pour éviter les messages dupliqués
        random_id = random.randint(1000, 9999)
        timestamp = int(time.time())
        
        print(f"\n📢 Envoi annonce test...")
        print(f"   broadcaster_id: {broadcaster_id}")
        print(f"   moderator_id: {broadcaster_id}  (SAME = broadcaster agit sur son propre channel)")

        await twitch.send_chat_announcement(
            broadcaster_id=broadcaster_id,
            moderator_id=broadcaster_id,  # ← CRITICAL: broadcaster agit sur SON channel
            message=f"🧪 TEST: KissBot utilise le token broadcaster ! 🎉 [#{random_id}]",
            color="purple"
        )

        print("✅ SUCCÈS ! Annonce envoyée avec token broadcaster")

        # 7. Envoyer le même message en chat classique (Helix send_chat_message)
        #    pour vérifier la visibilité sans le format /announcements.
        try:
            await twitch.send_chat_message(
                broadcaster_id=broadcaster_id,
                sender_id=broadcaster_id,  # le broadcaster parle dans son propre chat
                message=f"🧪 TEST: KissBot utilise le token broadcaster ! 🎉 [#{random_id}]"
            )
            print("✅ SUCCÈS ! Message chat envoyé (hors /announcement)")
        except Exception as chat_err:
            print(f"⚠️ Échec envoi message chat: {chat_err}")
            print("   Vérifie les scopes (user:write:chat, chat:edit) et le statut channel:bot/mod.")

        print("\n🎯 Résultat:")
        print("   Le bot PEUT utiliser le token broadcaster de el_serda")
        print("   pour envoyer des annonces SANS être /mod !")
        print("   Et le message texte classique est envoyé juste après.")

    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        if "403" in str(e):
            print("\n💡 Erreur 403 = Permissions manquantes")
            print("   Vérifie que le token broadcaster a bien le scope")
            print("   'moderator:manage:announcements'")
        elif "401" in str(e):
            print("\n💡 Erreur 401 = Token invalide ou expiré")

    # 8. TEST: Envoyer un message via le token BOT (serda_bot) pour vérifier l'affichage sous le compte bot
    try:
        bot_user = db.get_user_by_login('serda_bot')
        bot_token = db.get_tokens(bot_user['id'], token_type='bot') if bot_user else None
        if not bot_user or not bot_token:
            print("⚠️ Impossible de charger le token bot serda_bot depuis la DB")
        else:
            print("\n🤖 Envoi via token BOT (serda_bot)...")
            print(f"   Bot user_id: {bot_user['twitch_user_id']}")
            print(f"   Target broadcaster_id: {broadcaster_id}")
            
            import json
            bot_scopes = bot_token['scopes']
            bot_scopes_list = json.loads(bot_scopes) if isinstance(bot_scopes, str) else bot_scopes
            print(f"   Bot scopes ({len(bot_scopes_list)}): {bot_scopes_list}")
            
            bot_scope_enums = []
            for scope_str in bot_scopes_list:
                for auth_scope in AuthScope:
                    if auth_scope.value == scope_str:
                        bot_scope_enums.append(auth_scope)
                        break

            twitch_bot = Twitch(client_id, client_secret)
            
            # Enable debug logging
            import logging
            logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
            
            await twitch_bot.set_user_authentication(
                token=bot_token['access_token'],
                scope=bot_scope_enums,
                refresh_token=bot_token['refresh_token'],
                validate=True
            )
            
            print(f"   Auth configurée, envoi du message...")

            bot_sender_id = bot_user['twitch_user_id']
            
            # Capture la réponse HTTP complète
            try:
                response = await twitch_bot.send_chat_message(
                    broadcaster_id=broadcaster_id,
                    sender_id=bot_sender_id,
                    message=f"🧪 TEST (BOT): KissBot envoie ce message via le token bot serda_bot ! [#{random_id}@{timestamp}]"
                )
                print(f"✅ SUCCÈS ! Message chat envoyé sous le compte serda_bot")
                print(f"   Response: {response}")
            except Exception as send_error:
                print(f"❌ Erreur lors de send_chat_message: {send_error}")
                print(f"   Type: {type(send_error)}")
                print(f"   Details: {send_error.__dict__ if hasattr(send_error, '__dict__') else 'N/A'}")
                
                # Try to extract HTTP status if available
                if hasattr(send_error, 'status'):
                    print(f"   HTTP Status: {send_error.status}")
                if hasattr(send_error, 'response'):
                    print(f"   HTTP Response: {send_error.response}")
                raise
                
            await twitch_bot.close()
    except Exception as e:
        print(f"⚠️ Échec envoi via token BOT: {e}")
        import traceback
        traceback.print_exc()
        if "403" in str(e):
            print("   💡 Erreur 403 = Le bot n'est pas autorisé à parler sur ce channel")
            print("   Solutions:")
            print("      1. Ajouter serda_bot comme mod: /mod serda_bot")
            print("      2. OU autoriser le bot via le dashboard OAuth (scope channel:bot)")
        elif "401" in str(e):
            print("   💡 Erreur 401 = Token bot invalide ou expiré")
    
    finally:
        await twitch.close()

if __name__ == "__main__":
    asyncio.run(test_broadcaster_token())
