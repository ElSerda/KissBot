#!/usr/bin/env python3
"""
Monitor Client - Client pour l'enregistrement auprès du Monitor

Ce module permet aux bots KissBot de s'enregistrer auprès du Monitor central.
Communication via Unix Socket, non-bloquant, fail-safe.

Usage:
    from core.monitor_client import register_with_monitor, send_heartbeat, unregister_from_monitor
    
    # Au démarrage du bot
    register_with_monitor(
        channel="el_serda",
        pid=os.getpid(),
        features={"translator": True, "llm": False}
    )
    
    # Périodiquement (optionnel, recommandé toutes les 30s)
    send_heartbeat(channel="el_serda", pid=os.getpid())
    
    # À l'arrêt du bot
    unregister_from_monitor(channel="el_serda", pid=os.getpid())
"""

import asyncio
import json
import logging
import os
import socket
from typing import Dict, Optional, Any

LOGGER = logging.getLogger(__name__)

# Configuration
MONITOR_SOCKET_PATH = "/tmp/kissbot_monitor.sock"
SOCKET_TIMEOUT = 2.0  # secondes
HEARTBEAT_INTERVAL = 30  # secondes


def _send_message_sync(message: Dict[str, Any], socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Envoie un message au Monitor via Unix Socket (synchrone).
    
    Args:
        message: Message à envoyer (sera JSON encodé)
        socket_path: Chemin du socket Unix
        
    Returns:
        True si envoi réussi, False sinon
    """
    try:
        # Vérifier que le socket existe
        if not os.path.exists(socket_path):
            LOGGER.debug(f"Monitor socket not found: {socket_path}")
            return False
        
        # Créer le socket client
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(SOCKET_TIMEOUT)
        
        try:
            client.connect(socket_path)
            
            # Envoyer le message
            data = json.dumps(message).encode('utf-8')
            client.sendall(data)
            
            # Attendre l'ACK
            response = client.recv(1024)
            if response:
                ack = json.loads(response.decode('utf-8'))
                return ack.get("status") == "ok"
            return False
            
        finally:
            client.close()
            
    except socket.timeout:
        LOGGER.warning("Monitor connection timeout")
        return False
    except ConnectionRefusedError:
        LOGGER.debug("Monitor not running (connection refused)")
        return False
    except Exception as e:
        LOGGER.warning(f"Failed to send message to Monitor: {e}")
        return False


async def _send_message_async(message: Dict[str, Any], 
                               socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Envoie un message au Monitor via Unix Socket (async).
    
    Args:
        message: Message à envoyer
        socket_path: Chemin du socket Unix
        
    Returns:
        True si envoi réussi, False sinon
    """
    try:
        if not os.path.exists(socket_path):
            LOGGER.debug(f"Monitor socket not found: {socket_path}")
            return False
        
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(socket_path),
            timeout=SOCKET_TIMEOUT
        )
        
        try:
            # Envoyer
            data = json.dumps(message).encode('utf-8')
            writer.write(data)
            await writer.drain()
            
            # Attendre ACK
            response = await asyncio.wait_for(reader.read(1024), timeout=SOCKET_TIMEOUT)
            if response:
                ack = json.loads(response.decode('utf-8'))
                return ack.get("status") == "ok"
            return False
            
        finally:
            writer.close()
            await writer.wait_closed()
            
    except asyncio.TimeoutError:
        LOGGER.warning("Monitor connection timeout (async)")
        return False
    except ConnectionRefusedError:
        LOGGER.debug("Monitor not running (connection refused)")
        return False
    except Exception as e:
        LOGGER.warning(f"Failed to send message to Monitor (async): {e}")
        return False


def register_with_monitor(channel: str, pid: int, features: Dict[str, bool],
                          socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Enregistre un bot auprès du Monitor (synchrone).
    
    Appelé au démarrage du bot, après initialisation du FeatureManager.
    Ne fait JAMAIS crasher le bot si le Monitor n'est pas disponible.
    
    Args:
        channel: Nom du channel Twitch
        pid: PID du process bot
        features: Dict des features activées
        socket_path: Chemin du socket Monitor
        
    Returns:
        True si enregistrement réussi, False sinon
    """
    message = {
        "type": "register",
        "channel": channel,
        "pid": pid,
        "features": features
    }
    
    success = _send_message_sync(message, socket_path)
    
    if success:
        LOGGER.info(f"✅ Registered with Monitor: {channel} (PID {pid})")
    else:
        LOGGER.warning(f"⚠️ Monitor not available, continuing without monitoring")
    
    return success


async def register_with_monitor_async(channel: str, pid: int, features: Dict[str, bool],
                                       socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """Version async de register_with_monitor"""
    message = {
        "type": "register",
        "channel": channel,
        "pid": pid,
        "features": features
    }
    
    success = await _send_message_async(message, socket_path)
    
    if success:
        LOGGER.info(f"✅ Registered with Monitor: {channel} (PID {pid})")
    else:
        LOGGER.warning(f"⚠️ Monitor not available, continuing without monitoring")
    
    return success


def send_heartbeat(channel: str, pid: int,
                   socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Envoie un heartbeat au Monitor (synchrone).
    
    Args:
        channel: Nom du channel
        pid: PID du process
        socket_path: Chemin du socket
        
    Returns:
        True si envoi réussi
    """
    message = {
        "type": "heartbeat",
        "channel": channel,
        "pid": pid
    }
    return _send_message_sync(message, socket_path)


async def send_heartbeat_async(channel: str, pid: int,
                                socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """Version async de send_heartbeat"""
    message = {
        "type": "heartbeat",
        "channel": channel,
        "pid": pid
    }
    return await _send_message_async(message, socket_path)


def unregister_from_monitor(channel: str, pid: int,
                            socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Désenregistre un bot du Monitor (synchrone).
    
    Appelé à l'arrêt propre du bot.
    
    Args:
        channel: Nom du channel
        pid: PID du process
        socket_path: Chemin du socket
        
    Returns:
        True si désenregistrement réussi
    """
    message = {
        "type": "unregister",
        "channel": channel,
        "pid": pid
    }
    
    success = _send_message_sync(message, socket_path)
    
    if success:
        LOGGER.info(f"👋 Unregistered from Monitor: {channel}")
    
    return success


async def unregister_from_monitor_async(channel: str, pid: int,
                                         socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """Version async de unregister_from_monitor"""
    message = {
        "type": "unregister",
        "channel": channel,
        "pid": pid
    }
    
    success = await _send_message_async(message, socket_path)
    
    if success:
        LOGGER.info(f"👋 Unregistered from Monitor: {channel}")
    
    return success


class HeartbeatTask:
    """
    Task pour envoyer des heartbeats périodiques au Monitor.
    
    Usage:
        heartbeat = HeartbeatTask(channel="el_serda", pid=os.getpid())
        asyncio.create_task(heartbeat.start())
        
        # À l'arrêt
        await heartbeat.stop()
    """
    
    def __init__(self, channel: str, pid: int, 
                 interval: int = HEARTBEAT_INTERVAL,
                 socket_path: str = MONITOR_SOCKET_PATH):
        self.channel = channel
        self.pid = pid
        self.interval = interval
        self.socket_path = socket_path
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Démarre la tâche de heartbeat"""
        self._running = True
        LOGGER.debug(f"💓 Starting heartbeat task for {self.channel}")
        
        while self._running:
            await asyncio.sleep(self.interval)
            if self._running:
                await send_heartbeat_async(self.channel, self.pid, self.socket_path)
    
    async def stop(self):
        """Arrête la tâche de heartbeat"""
        self._running = False
        LOGGER.debug(f"💔 Stopping heartbeat task for {self.channel}")


# === Fonction utilitaire pour FeatureManager ===

def features_to_dict(feature_manager) -> Dict[str, bool]:
    """
    Convertit un FeatureManager en dict pour l'enregistrement.
    
    Args:
        feature_manager: Instance de FeatureManager
        
    Returns:
        Dict {feature_name: is_enabled}
    """
    from core.feature_manager import Feature
    
    return {
        feature.config_key: feature_manager.is_enabled(feature)
        for feature in Feature
    }
