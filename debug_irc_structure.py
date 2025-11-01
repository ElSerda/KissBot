#!/usr/bin/env python3
"""Debug IRC message structure"""
import asyncio
import logging
from pathlib import Path
import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.chat import Chat, ChatMessage as TwitchChatMessage, EventData
from twitchAPI.type import ChatEvent

logging.basicConfig(level=logging.INFO)

async def main():
    config_file = Path("config/config.yaml")
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    app_id = config["twitch"]["client_id"]
    app_secret = config["twitch"]["client_secret"]
    
    # Charger token
    import json
    with open('.tio.tokens.json', 'r') as f:
        tokens = json.load(f)
    
    bot_token = tokens['1209350837']
    
    twitch = await Twitch(app_id, app_secret)
    
    # Valider les scopes
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {bot_token['token']}"}
        ) as resp:
            data = await resp.json()
            scopes = [s for s in data.get('scopes', [])]
    
    from twitchAPI.type import AuthScope
    await twitch.set_user_authentication(
        bot_token['token'],
        [AuthScope(s) for s in scopes],
        bot_token['refresh']
    )
    
    async def on_message(msg: TwitchChatMessage):
        print("\n" + "="*70)
        print("MESSAGE REÇU !")
        print("="*70)
        print(f"Text: {msg.text}")
        print(f"\nUser attributes:")
        for attr in dir(msg.user):
            if not attr.startswith('_') and not callable(getattr(msg.user, attr)):
                val = getattr(msg.user, attr)
                print(f"  msg.user.{attr} = {val}")
        
        print(f"\nRoom attributes:")
        for attr in dir(msg.room):
            if not attr.startswith('_') and not callable(getattr(msg.room, attr)):
                val = getattr(msg.room, attr)
                print(f"  msg.room.{attr} = {val}")
        
        print("\nÉcris 'quit' pour arrêter")
    
    chat = await Chat(twitch)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    chat.start()
    
    await chat.join_room('el_serda')
    print("\n✅ Bot connecté ! Écris un message dans le chat...")
    
    await asyncio.sleep(300)  # 5 min
    await twitch.close()

asyncio.run(main())
