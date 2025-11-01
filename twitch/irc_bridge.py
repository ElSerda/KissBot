#!/usr/bin/env python3
"""
🔌 IRC Bridge Twitch - Client IRC minimal pour KissBot
Connexion TLS, auto-reconnect, throttling, queue d'envoi
Compatible avec TwitchIO 3.x (EventSub) en parallèle
"""

import asyncio
import ssl
import time
import logging
from collections import deque
from typing import Optional, Iterable

LOGGER = logging.getLogger(__name__)

TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT_TLS = 6697   # TLS conseillé
CAPS = "CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands"


class TwitchIRCBridge:
    """
    Minuscule client IRC Twitch pour envoyer (et recevoir si besoin) des messages.
    - Connexion TLS
    - Auto-reconnect
    - Queue + throttling simple (par défaut 18 msgs / 30s)
    - join dynamique de channels
    - send_privmsg(channel, text)
    """

    def __init__(
        self,
        nick: str,
        oauth: str,                  # format: "oauth:xxxxxxxx"
        channels: Iterable[str] = (),
        max_msgs_per_30s: int = 18,  # safe par défaut (non-verified)
        use_tls: bool = True,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.nick = nick
        self.passwd = oauth if oauth.startswith("oauth:") else f"oauth:{oauth}"
        self.channels = set(ch.lstrip("#").lower() for ch in channels)
        self.max_msgs = max_msgs_per_30s
        self.loop = loop or asyncio.get_event_loop()

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._send_q: "asyncio.Queue[tuple[str,str]]" = asyncio.Queue()
        self._joined = set()
        self._running = False
        self._throttle = deque()  # timestamps des envois récents
        self._main_task: Optional[asyncio.Task] = None

    # ---------- API publique ----------
    async def start(self):
        if self._running:
            return
        self._running = True
        self._main_task = self.loop.create_task(self._run())
        LOGGER.info(f"🔌 IRC Bridge started: {self.nick}")

    async def stop(self):
        self._running = False
        if self._main_task:
            self._main_task.cancel()
        await self._close()
        LOGGER.info("🔌 IRC Bridge stopped")

    async def ensure_joined(self, channel: str):
        ch = channel.lstrip("#").lower()
        self.channels.add(ch)
        if self._writer and ch not in self._joined:
            await self._send_raw(f"JOIN #{ch}")
            self._joined.add(ch)
            LOGGER.info(f"✅ IRC joined: #{ch}")

    async def send_privmsg(self, channel: str, text: str):
        """Thread-safe côté async: push dans la queue."""
        await self.ensure_joined(channel)
        await self._send_q.put((channel, text))

    def is_connected(self) -> bool:
        return self._writer is not None

    # ---------- Boucles internes ----------
    async def _run(self):
        backoff = 1
        while self._running:
            try:
                await self._connect()
                await self._hello()
                # Join initial
                for ch in list(self.channels):
                    await self._send_raw(f"JOIN #{ch}")
                    self._joined.add(ch)

                # Deux tâches: lecture et envoi
                reader_t = self.loop.create_task(self._reader_loop())
                sender_t = self.loop.create_task(self._sender_loop())
                await asyncio.wait(
                    {reader_t, sender_t},
                    return_when=asyncio.FIRST_COMPLETED
                )
                for t in (reader_t, sender_t):
                    if not t.done():
                        t.cancel()
                await self._close()
                backoff = 1  # reset si nous étions connectés
            except Exception as e:
                LOGGER.error(f"❌ IRC error: {e}")
                await self._close()
            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _connect(self):
        ssl_ctx = ssl.create_default_context()
        self._reader, self._writer = await asyncio.open_connection(
            TWITCH_IRC_HOST, TWITCH_IRC_PORT_TLS, ssl=ssl_ctx
        )
        LOGGER.info(f"🔌 IRC connected to {TWITCH_IRC_HOST}:{TWITCH_IRC_PORT_TLS}")

    async def _hello(self):
        await self._send_raw(f"PASS {self.passwd}", flush=True)
        await self._send_raw(f"NICK {self.nick}", flush=True)
        await self._send_raw(CAPS, flush=True)

    async def _reader_loop(self):
        while self._running and self._reader:
            line = await self._reader.readline()
            if not line:
                break
            msg = line.decode("utf-8", errors="ignore").rstrip("\r\n")
            # PING → PONG
            if msg.startswith("PING"):
                await self._send_raw("PONG :tmi.twitch.tv")
            # Log JOIN confirmations
            elif " JOIN #" in msg:
                LOGGER.debug(f"IRC: {msg}")

    async def _sender_loop(self):
        while self._running and self._writer:
            channel, text = await self._send_q.get()
            await self._rate_limit()
            await self._send_raw(f"PRIVMSG #{channel.lstrip('#')} :{text}")
            LOGGER.info(f"📤 IRC sent to #{channel}: {text}")

    async def _send_raw(self, data: str, flush: bool = False):
        if not self._writer:
            return
        self._writer.write((data + "\r\n").encode("utf-8"))
        if flush:
            await self._writer.drain()
        # Marqueur throttle si c'est un PRIVMSG
        if data.startswith("PRIVMSG "):
            now = time.monotonic()
            self._throttle.append(now)

    async def _rate_limit(self):
        # Twitch (non verified): ~20 msgs / 30s; on joue safe à 18/30s
        window = 30.0
        now = time.monotonic()
        # purge
        while self._throttle and now - self._throttle[0] > window:
            self._throttle.popleft()
        if len(self._throttle) >= self.max_msgs:
            sleep_for = window - (now - self._throttle[0]) + 0.05
            await asyncio.sleep(max(0.0, sleep_for))

    async def _close(self):
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._joined.clear()
