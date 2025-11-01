#!/usr/bin/env python3
"""Test rapide du nouveau token"""
import asyncio
from pathlib import Path
from twitchAPI.twitch import Twitch
from twitchapi.auth_manager import AuthManager
import yaml

async def test():
    config = yaml.safe_load(open('config/config.yaml'))
    twitch = await Twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    auth = AuthManager(twitch)
    token = await auth.load_token_from_file('1209350837')
    print(f'✅ User: {token.user_login}')
    print(f'🔑 Scopes: {[str(s) for s in token.scopes]}')
    await twitch.close()

asyncio.run(test())
