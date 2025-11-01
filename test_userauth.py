#!/usr/bin/env python3
"""Debug User Auth"""
import asyncio
from twitchAPI.twitch import Twitch

async def test():
    t = await Twitch('a', 'b')
    print(f'has_user_auth before: {t.has_user_auth()}')
    await t.set_user_authentication('tok', [], 'ref')
    print(f'has_user_auth after: {t.has_user_auth()}')
    await t.close()

asyncio.run(test())
