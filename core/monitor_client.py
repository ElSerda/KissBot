#!/usr/bin/env python3
"""
Monitor Client - Client pour l'enregistrement auprès du Monitor

Ce module permet aux bots KissBot de s'enregistrer auprès du Monitor central.
Communication via Unix Socket, non-bloquant, fail-safe.

Architecture:
    - Classe MonitorClient pour la gestion orientée objet
    - Fonctions legacy pour compatibilité backward
    - Protocole JSONL fire-and-forget (pas d'ACK)

Usage (Classe - recommandé):
    from core.monitor_client import MonitorClient
    
    client = MonitorClient(channel="el_serda", pid=os.getpid())
    await client.register(features={"translator": True})
    await client.heartbeat()
    await client.unregister()

Usage (Functions - legacy):
    from core.monitor_client import register_with_monitor, send_heartbeat
    
    register_with_monitor(channel="el_serda", pid=os.getpid(), features={...})
    send_heartbeat(channel="el_serda", pid=os.getpid())
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


# ============================================================================
# CLASS MonitorClient - Interface Orientée Objet (Recommandée)
# ============================================================================

class MonitorClient:
    """
    Client pour communiquer avec le Monitor central via Unix Socket.
    
    Protocole:
        - JSONL (JSON + newline delimiter)
        - Fire-and-forget (pas d'ACK)
        - Chaque message = {"type": "...", ...}
    
    Types de message:
        - register: {"type": "register", "channel": str, "pid": int, "features": dict}
        - heartbeat: {"type": "heartbeat", "channel": str, "pid": int}
        - unregister: {"type": "unregister", "channel": str, "pid": int}
        - llm_usage: {"type": "llm_usage", "channel": str, ...}
    
    Example:
        client = MonitorClient(channel="el_serda", pid=1234)
        await client.register(features={"llm": True})
        await client.heartbeat()
        await client.unregister()
    """
    
    def __init__(self, 
                 channel: str,
                 pid: int,
                 socket_path: str = MONITOR_SOCKET_PATH,
                 timeout: float = SOCKET_TIMEOUT):
        """
        Args:
            channel: Nom du channel Twitch
            pid: PID du processus bot
            socket_path: Chemin du socket Unix du Monitor
            timeout: Timeout pour les connexions (secondes)
        """
        self.channel = channel
        self.pid = pid
        self.socket_path = socket_path
        self.timeout = timeout
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def _send_message(self, message: Dict[str, Any]) -> bool:
        """
        Envoie un message au Monitor (async, fire-and-forget).
        
        Args:
            message: Message à envoyer (dict)
            
        Returns:
            True si envoi réussi, False sinon
        """
        try:
            if not os.path.exists(self.socket_path):
                LOGGER.debug(f"Monitor socket not found: {self.socket_path}")
                return False
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=self.timeout
            )
            
            try:
                # Envoyer avec délimiteur newline (protocole JSONL)
                data = (json.dumps(message) + "\n").encode('utf-8')
                writer.write(data)
                await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                
                # ✅ PAS de read() / PAS d'ACK - fire-and-forget
                return True
                
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
                
        except asyncio.TimeoutError:
            LOGGER.debug(f"Monitor connection timeout for {self.channel}")
            return False
        except ConnectionRefusedError:
            LOGGER.debug("Monitor not running (connection refused)")
            return False
        except Exception as e:
            LOGGER.debug(f"Failed to send message to Monitor: {e}")
            return False
    
    async def register(self, features: Optional[Dict[str, bool]] = None) -> bool:
        """
        Enregistre ce bot auprès du Monitor.
        
        Args:
            features: Dict des features activées (ex: {"llm": True, "translator": False})
            
        Returns:
            True si enregistrement réussi
        """
        if features is None:
            features = {}
        
        message = {
            "type": "register",
            "channel": self.channel,
            "pid": self.pid,
            "features": features
        }
        
        success = await self._send_message(message)
        
        if success:
            LOGGER.info(f"✅ Registered with Monitor: {self.channel} (PID {self.pid})")
        else:
            LOGGER.warning(f"⚠️ Monitor not available, continuing without monitoring")
        
        return success
    
    async def heartbeat(self) -> bool:
        """
        Envoie un heartbeat au Monitor.
        
        Returns:
            True si envoi réussi
        """
        message = {
            "type": "heartbeat",
            "channel": self.channel,
            "pid": self.pid
        }
        
        return await self._send_message(message)
    
    async def unregister(self) -> bool:
        """
        Désenregistre ce bot du Monitor.
        
        Returns:
            True si désenregistrement réussi
        """
        message = {
            "type": "unregister",
            "channel": self.channel,
            "pid": self.pid
        }
        
        success = await self._send_message(message)
        
        if success:
            LOGGER.info(f"👋 Unregistered from Monitor: {self.channel}")
        
        return success
    
    async def log_llm_usage(self,
                           model: str,
                           feature: str,
                           tokens_in: int,
                           tokens_out: int,
                           latency_ms: Optional[int] = None) -> bool:
        """
        Enregistre un usage LLM auprès du Monitor.
        
        Args:
            model: Nom du modèle (ex: "gpt-4", "claude-3")
            feature: Feature qui a utilisé le LLM (ex: "jokes", "translator")
            tokens_in: Tokens en entrée
            tokens_out: Tokens en sortie
            latency_ms: Latence en millisecondes (optionnel)
            
        Returns:
            True si envoi réussi
        """
        message = {
            "type": "llm_usage",
            "channel": self.channel,
            "model": model,
            "feature": feature,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out
        }
        
        if latency_ms is not None:
            message["latency_ms"] = latency_ms
        
        return await self._send_message(message)
    
    async def start_heartbeat(self, interval: int = HEARTBEAT_INTERVAL):
        """
        Démarre une tâche de heartbeat périodique.
        
        Args:
            interval: Intervalle entre les heartbeats (secondes)
        """
        async def _heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.heartbeat()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    LOGGER.debug(f"Heartbeat error for {self.channel}: {e}")
        
        self._heartbeat_task = asyncio.create_task(_heartbeat_loop())
        LOGGER.debug(f"💓 Heartbeat loop started for {self.channel}")
    
    async def stop_heartbeat(self):
        """Arrête la tâche de heartbeat périodique."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            LOGGER.debug(f"💔 Heartbeat loop stopped for {self.channel}")


# ============================================================================
# FONCTIONS LEGACY - Backward Compatibility
# ============================================================================


def _send_message_sync(message: Dict[str, Any], socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Envoie un message au Monitor via Unix Socket (synchrone).
    
    LEGACY: Préférer MonitorClient pour les nouveaux codes.
    
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
        
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(SOCKET_TIMEOUT)
        
        try:
            client.connect(socket_path)
            data = (json.dumps(message) + "\n").encode('utf-8')
            client.sendall(data)
            return True
        finally:
            try:
                client.close()
            except:
                pass
            
    except socket.timeout:
        LOGGER.debug("Monitor connection timeout (sync)")
        return False
    except ConnectionRefusedError:
        LOGGER.debug("Monitor not running")
        return False
    except Exception as e:
        LOGGER.debug(f"Failed to send message: {e}")
        return False


async def _send_message_async(message: Dict[str, Any], 
                               socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """
    Envoie un message au Monitor via Unix Socket (async).
    
    LEGACY: Préférer MonitorClient pour les nouveaux codes.
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
            data = (json.dumps(message) + "\n").encode('utf-8')
            writer.write(data)
            await asyncio.wait_for(writer.drain(), timeout=SOCKET_TIMEOUT)
            return True
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            
    except asyncio.TimeoutError:
        LOGGER.debug("Monitor connection timeout (async)")
        return False
    except ConnectionRefusedError:
        LOGGER.debug("Monitor not running")
        return False
    except Exception as e:
        LOGGER.debug(f"Failed to send message (async): {e}")
        return False


def register_with_monitor(channel: str, pid: int, features: Dict[str, bool],
                          socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """LEGACY: Préférer await MonitorClient(channel, pid).register(features)"""
    message = {"type": "register", "channel": channel, "pid": pid, "features": features}
    success = _send_message_sync(message, socket_path)
    if success:
        LOGGER.info(f"✅ Registered with Monitor: {channel} (PID {pid})")
    else:
        LOGGER.warning(f"⚠️ Monitor not available, continuing without monitoring")
    return success


async def register_with_monitor_async(channel: str, pid: int, features: Dict[str, bool],
                                       socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """LEGACY: Préférer await MonitorClient(channel, pid).register(features)"""
    message = {"type": "register", "channel": channel, "pid": pid, "features": features}
    success = await _send_message_async(message, socket_path)
    if success:
        LOGGER.info(f"✅ Registered with Monitor: {channel} (PID {pid})")
    else:
        LOGGER.warning(f"⚠️ Monitor not available, continuing without monitoring")
    return success


def send_heartbeat(channel: str, pid: int, socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """LEGACY: Préférer await MonitorClient(channel, pid).heartbeat()"""
    message = {"type": "heartbeat", "channel": channel, "pid": pid}
    return _send_message_sync(message, socket_path)


async def send_heartbeat_async(channel: str, pid: int,
                                socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """LEGACY: Préférer await MonitorClient(channel, pid).heartbeat()"""
    message = {"type": "heartbeat", "channel": channel, "pid": pid}
    return await _send_message_async(message, socket_path)


def unregister_from_monitor(channel: str, pid: int, socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """LEGACY: Préférer await MonitorClient(channel, pid).unregister()"""
    message = {"type": "unregister", "channel": channel, "pid": pid}
    success = _send_message_sync(message, socket_path)
    if success:
        LOGGER.info(f"👋 Unregistered from Monitor: {channel}")
    return success


async def unregister_from_monitor_async(channel: str, pid: int,
                                         socket_path: str = MONITOR_SOCKET_PATH) -> bool:
    """LEGACY: Préférer await MonitorClient(channel, pid).unregister()"""
    message = {"type": "unregister", "channel": channel, "pid": pid}
    success = await _send_message_async(message, socket_path)
    if success:
        LOGGER.info(f"👋 Unregistered from Monitor: {channel}")
    return success



class HeartbeatTask:
    """
    DEPRECATED: Préférer MonitorClient.start_heartbeat()
    
    Task pour envoyer des heartbeats périodiques au Monitor.
    """
    
    def __init__(self, channel: str, pid: int, 
                 interval: int = HEARTBEAT_INTERVAL,
                 socket_path: str = MONITOR_SOCKET_PATH):
        self.channel = channel
        self.pid = pid
        self.interval = interval
        self.socket_path = socket_path
        self._running = False
    
    async def start(self):
        """Démarre la tâche de heartbeat"""
        self._running = True
        while self._running:
            await asyncio.sleep(self.interval)
            if self._running:
                await send_heartbeat_async(self.channel, self.pid, self.socket_path)
    
    async def stop(self):
        """Arrête la tâche de heartbeat"""
        self._running = False



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
