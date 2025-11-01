#!/usr/bin/env python3
"""
🔌 IRC Client Léger pour KissBot
Utilise pydle pour se connecter à l'IRC Twitch en parallèle d'EventSub
Permet d'envoyer des messages sur ANY channel sans nécessiter channel:bot
"""

import asyncio
import logging
from typing import Optional, List

import pydle

LOGGER = logging.getLogger(__name__)


class KissBotIRC(pydle.Client):
    """Client IRC Twitch simple pour envoyer des messages partout"""
    
    def __init__(self, nickname: str, channels: List[str], **kwargs):
        super().__init__(nickname, **kwargs)
        self.channels_to_join = channels
        self.ready = False
        
    async def on_connect(self):
        """Connexion établie - demander capabilities et join channels"""
        LOGGER.info("🔌 IRC connecté à Twitch")
        
        # Demander les capabilities Twitch IRC
        await self.raw('CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands')
        
        # Rejoindre tous les channels
        for channel in self.channels_to_join:
            channel_name = channel if channel.startswith('#') else f'#{channel}'
            await self.join(channel_name)
            LOGGER.info(f"✅ IRC joint: {channel_name}")
        
        self.ready = True
        LOGGER.info(f"✅ IRC prêt sur {len(self.channels_to_join)} channels")
    
    async def on_disconnect(self, expected):
        """Déconnexion IRC"""
        self.ready = False
        if not expected:
            LOGGER.warning("⚠️  IRC déconnecté de manière inattendue")
        else:
            LOGGER.info("🔌 IRC déconnecté proprement")
    
    async def send_message_to(self, channel: str, message: str) -> bool:
        """
        Envoyer un message sur un channel IRC
        
        Args:
            channel: Nom du channel (avec ou sans #)
            message: Message à envoyer
            
        Returns:
            True si envoyé, False sinon
        """
        if not self.ready:
            LOGGER.error("❌ IRC pas prêt - impossible d'envoyer")
            return False
        
        try:
            channel_name = channel if channel.startswith('#') else f'#{channel}'
            await self.message(channel_name, message)
            LOGGER.info(f"✅ IRC message envoyé à {channel_name}: {message}")
            return True
        except Exception as e:
            LOGGER.error(f"❌ Erreur envoi IRC à {channel}: {e}")
            return False


class IRCManager:
    """Gestionnaire du client IRC pour KissBot"""
    
    def __init__(self):
        self.client: Optional[KissBotIRC] = None
        self.task: Optional[asyncio.Task] = None
        
    async def start(self, nickname: str, oauth_token: str, channels: List[str]):
        """
        Démarrer le client IRC
        
        Args:
            nickname: Nick du bot (ex: serda_bot)
            oauth_token: Token OAuth Twitch (format: oauth:xxxxx)
            channels: Liste des channels à rejoindre
        """
        if self.client:
            LOGGER.warning("⚠️  IRC déjà démarré")
            return
        
        # Formater le token OAuth
        if not oauth_token.startswith('oauth:'):
            oauth_token = f'oauth:{oauth_token}'
        
        LOGGER.info(f"🚀 Démarrage IRC client: {nickname} sur {len(channels)} channels")
        
        # Créer le client
        self.client = KissBotIRC(
            nickname=nickname,
            channels=channels,
            realname="KissBot IRC",
        )
        
        # Connecter en background
        async def run_irc():
            try:
                await self.client.connect(
                    hostname='irc.chat.twitch.tv',
                    port=6667,
                    tls=False,
                    password=oauth_token
                )
                await self.client.handle_forever()
            except Exception as e:
                LOGGER.error(f"❌ Erreur IRC client: {e}")
        
        self.task = asyncio.create_task(run_irc())
        LOGGER.info("✅ IRC client task créée")
        
        # Attendre que le client soit prêt (max 5s)
        for _ in range(50):  # 5 secondes max
            if self.client.ready:
                LOGGER.info("✅ IRC client prêt !")
                return
            await asyncio.sleep(0.1)
        
        LOGGER.warning("⚠️  IRC client démarré mais pas encore prêt")
    
    async def send(self, channel: str, message: str) -> bool:
        """
        Envoyer un message via IRC
        
        Args:
            channel: Nom du channel (avec ou sans #)
            message: Message à envoyer
            
        Returns:
            True si envoyé, False sinon
        """
        if not self.client or not self.client.ready:
            LOGGER.error("❌ IRC client pas prêt")
            return False
        
        return await self.client.send_message_to(channel, message)
    
    async def stop(self):
        """Arrêter le client IRC proprement"""
        if self.client:
            LOGGER.info("🛑 Arrêt IRC client...")
            await self.client.quit("Bot shutdown")
            self.client = None
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        
        LOGGER.info("✅ IRC client arrêté")
    
    @property
    def is_ready(self) -> bool:
        """Vérifier si l'IRC est prêt"""
        return self.client is not None and self.client.ready
