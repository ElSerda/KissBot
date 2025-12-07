#!/usr/bin/env python3
"""
KissBot Monitor - Process de monitoring global

Process séparé qui observe et log l'activité de tous les bots KissBot.
Ne se connecte PAS à Twitch, fait uniquement du monitoring.

Usage:
    python -m core.monitor
    # ou
    python core/monitor.py

Architecture:
    - Unix Socket: /tmp/kissbot_monitor.sock
    - SQLite DB: kissbot_monitor.db
    - Metrics toutes les 15s

Messages acceptés:
    - register: Bot s'enregistre au démarrage
    - heartbeat: Bot signale qu'il est vivant
    - unregister: Bot signale son arrêt propre
    - llm_usage: Log d'utilisation LLM (optionnel, peut être direct DB)
"""

import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

# psutil pour les métriques
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

# Configuration
MONITOR_SOCKET_PATH = "/tmp/kissbot_monitor.sock"
MONITOR_DB_PATH = "kissbot_monitor.db"
METRICS_INTERVAL = 15  # secondes
HEARTBEAT_TIMEOUT = 60  # secondes avant de considérer un bot comme stale
LOG_FORMAT = "%(asctime)s %(levelname)-8s [Monitor] %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger(__name__)


@dataclass
class BotInfo:
    """Information sur un bot enregistré"""
    channel: str
    pid: int
    features: Dict[str, bool]
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    process: Optional[Any] = None  # psutil.Process
    
    def __post_init__(self):
        """Initialise le process psutil"""
        if PSUTIL_AVAILABLE and self.process is None:
            try:
                self.process = psutil.Process(self.pid)
            except psutil.NoSuchProcess:
                LOGGER.warning(f"Process {self.pid} not found for {self.channel}")
                self.process = None
    
    def is_alive(self) -> bool:
        """Vérifie si le process est toujours en vie"""
        if not PSUTIL_AVAILABLE or self.process is None:
            return False
        try:
            return self.process.is_running() and self.process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def is_stale(self) -> bool:
        """Vérifie si le bot n'a pas envoyé de heartbeat depuis trop longtemps"""
        return (time.time() - self.last_heartbeat) > HEARTBEAT_TIMEOUT
    
    def get_metrics(self) -> Optional[Dict[str, float]]:
        """Récupère les métriques CPU/RAM"""
        if not self.is_alive():
            return None
        try:
            # CPU percent depuis le dernier appel (non-blocking)
            cpu_pct = self.process.cpu_percent(interval=None)
            # RAM en MB
            mem_info = self.process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            return {
                "cpu_pct": cpu_pct,
                "rss_mb": rss_mb,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None


class MonitorDB:
    """Gestionnaire de la base de données du Monitor"""
    
    def __init__(self, db_path: str = MONITOR_DB_PATH):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self):
        """Initialise la base de données"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # WAL mode pour éviter les locks
        self.conn.execute("PRAGMA journal_mode=WAL")
        
        # Table des métriques bot
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                channel TEXT NOT NULL,
                pid INTEGER NOT NULL,
                rss_mb REAL NOT NULL,
                cpu_pct REAL NOT NULL,
                features_json TEXT NOT NULL
            )
        """)
        
        # Table de statut des bots
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_status (
                channel TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                status TEXT NOT NULL,
                features_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)
        
        # Table d'usage LLM
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                channel TEXT NOT NULL,
                model TEXT NOT NULL,
                feature TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                latency_ms REAL
            )
        """)
        
        # Index pour les queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_metrics_channel_ts 
            ON bot_metrics(channel, ts)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_usage_channel_ts 
            ON llm_usage(channel, ts)
        """)
        
        self.conn.commit()
        LOGGER.info(f"📦 Database initialized: {self.db_path}")
    
    def insert_metrics(self, channel: str, pid: int, rss_mb: float, 
                       cpu_pct: float, features: Dict[str, bool]):
        """Insère une ligne de métriques"""
        ts = datetime.now(timezone.utc).isoformat()
        features_json = json.dumps(features)
        
        self.conn.execute("""
            INSERT INTO bot_metrics (ts, channel, pid, rss_mb, cpu_pct, features_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, channel, pid, rss_mb, cpu_pct, features_json))
        self.conn.commit()
    
    def update_bot_status(self, channel: str, pid: int, status: str,
                          features: Dict[str, bool], registered_at: float):
        """Met à jour le statut d'un bot"""
        ts_now = datetime.now(timezone.utc).isoformat()
        ts_registered = datetime.fromtimestamp(registered_at, tz=timezone.utc).isoformat()
        features_json = json.dumps(features)
        
        self.conn.execute("""
            INSERT OR REPLACE INTO bot_status 
            (channel, pid, status, features_json, registered_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (channel, pid, status, features_json, ts_registered, ts_now))
        self.conn.commit()
    
    def insert_llm_usage(self, channel: str, model: str, feature: str,
                         tokens_in: int, tokens_out: int, latency_ms: Optional[float] = None):
        """Insère un log d'usage LLM"""
        ts = datetime.now(timezone.utc).isoformat()
        
        self.conn.execute("""
            INSERT INTO llm_usage (ts, channel, model, feature, tokens_in, tokens_out, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, channel, model, feature, tokens_in, tokens_out, latency_ms))
        self.conn.commit()
    
    def cleanup_old_metrics(self, days: int = 7):
        """Supprime les métriques plus vieilles que X jours"""
        self.conn.execute("""
            DELETE FROM bot_metrics 
            WHERE ts < datetime('now', ? || ' days')
        """, (f"-{days}",))
        deleted = self.conn.total_changes
        self.conn.commit()
        if deleted > 0:
            LOGGER.info(f"🧹 Cleaned up {deleted} old metrics rows")
    
    def get_stats_summary(self, channel: Optional[str] = None) -> Dict[str, Any]:
        """Récupère un résumé des stats"""
        where_clause = "WHERE channel = ?" if channel else ""
        params = (channel,) if channel else ()
        
        # Stats métriques
        cursor = self.conn.execute(f"""
            SELECT 
                channel,
                COUNT(*) as count,
                AVG(rss_mb) as avg_ram,
                MAX(rss_mb) as max_ram,
                AVG(cpu_pct) as avg_cpu,
                MAX(cpu_pct) as max_cpu
            FROM bot_metrics
            {where_clause}
            GROUP BY channel
        """, params)
        
        metrics = {row['channel']: dict(row) for row in cursor.fetchall()}
        
        # Stats LLM
        cursor = self.conn.execute(f"""
            SELECT 
                channel,
                COUNT(*) as call_count,
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                AVG(latency_ms) as avg_latency
            FROM llm_usage
            {where_clause}
            GROUP BY channel
        """, params)
        
        llm_stats = {row['channel']: dict(row) for row in cursor.fetchall()}
        
        return {"metrics": metrics, "llm": llm_stats}
    
    def close(self):
        """Ferme la connexion"""
        if self.conn:
            self.conn.close()


class KissBotMonitor:
    """
    Process principal de monitoring.
    
    - Écoute les enregistrements de bots via Unix Socket
    - Collecte les métriques RAM/CPU périodiquement
    - Stocke en SQLite
    """
    
    def __init__(self, socket_path: str = MONITOR_SOCKET_PATH,
                 db_path: str = MONITOR_DB_PATH,
                 metrics_interval: int = METRICS_INTERVAL):
        self.socket_path = socket_path
        self.db = MonitorDB(db_path)
        self.metrics_interval = metrics_interval
        self.bots: Dict[str, BotInfo] = {}
        self._running = False
        self._server: Optional[asyncio.AbstractServer] = None
        
        # Queue pour les événements (fire-and-forget pattern)
        self.event_queue: asyncio.Queue = asyncio.Queue()
    
    async def start(self):
        """Démarre le monitor"""
        self._running = True
        
        # Nettoyer l'ancien socket si présent
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Démarrer le serveur Unix Socket
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path
        )
        
        # Permissions pour tous les users
        os.chmod(self.socket_path, 0o777)
        
        LOGGER.info(f"🚀 Monitor started")
        LOGGER.info(f"   Socket: {self.socket_path}")
        LOGGER.info(f"   DB: {self.db.db_path}")
        LOGGER.info(f"   Metrics interval: {self.metrics_interval}s")
        
        # Lancer les tasks
        try:
            await asyncio.gather(
                self._metrics_loop(),
                self._cleanup_loop(),
                self._event_worker(),
                self._server.serve_forever()
            )
        except asyncio.CancelledError:
            LOGGER.info("🛑 Monitor tasks cancelled")
            raise  # Re-raise pour propager proprement
    
    async def stop(self):
        """Arrête le monitor"""
        LOGGER.info("🛑 Stopping monitor...")
        self._running = False
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # Marquer tous les bots comme offline
        for channel, bot in self.bots.items():
            self.db.update_bot_status(
                channel=channel,
                pid=bot.pid,
                status="offline",
                features=bot.features,
                registered_at=bot.registered_at
            )
        
        # Nettoyer le socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.db.close()
        LOGGER.info("✅ Monitor stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, 
                             writer: asyncio.StreamWriter):
        """Gère une connexion client (fire-and-forget)
        
        Lit les messages JSON ligne par ligne et les met en queue.
        Pas d'ACK envoyé - pattern fire-and-forget.
        """
        client_addr = writer.get_extra_info('peername')
        try:
            while True:
                try:
                    # Lire une ligne de JSON (délimitée par \n)
                    line = await asyncio.wait_for(
                        reader.readline(),
                        timeout=30.0
                    )
                    
                    if not line:
                        break
                    
                    # Décoder et parser le JSON
                    message = json.loads(line.decode('utf-8').strip())
                    
                    # Mettre en queue (non-bloquant)
                    await self.event_queue.put(message)
                    LOGGER.debug(f"📨 Event queued from {client_addr}: {message.get('type')}")
                    
                except asyncio.TimeoutError:
                    # Le client a arrêté d'envoyer - fermer la connexion
                    break
                except json.JSONDecodeError as e:
                    LOGGER.error(f"Invalid JSON from {client_addr}: {e}")
                    break
                except Exception as e:
                    LOGGER.error(f"Error reading from {client_addr}: {e}")
                    break
                    
        except Exception as e:
            LOGGER.error(f"Unexpected error in _handle_client: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def _event_worker(self):
        """Worker qui consomme les événements de la queue et les dispatche"""
        LOGGER.info("🔄 Event worker started")
        
        while self._running:
            try:
                # Attendre un événement avec timeout
                message = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )
                
                msg_type = message.get("type")
                
                try:
                    if msg_type == "register":
                        await self._handle_register(message)
                    elif msg_type == "heartbeat":
                        await self._handle_heartbeat(message)
                    elif msg_type == "unregister":
                        await self._handle_unregister(message)
                    elif msg_type == "llm_usage":
                        await self._handle_llm_usage(message)
                    else:
                        LOGGER.warning(f"Unknown message type: {msg_type}")
                except Exception as e:
                    LOGGER.error(f"Error processing event {msg_type}: {e}")
                finally:
                    self.event_queue.task_done()
                    
            except asyncio.TimeoutError:
                # Pas d'événement - continue
                continue
            except Exception as e:
                LOGGER.error(f"Error in event worker: {e}")
                await asyncio.sleep(0.1)
        
        LOGGER.info("🛑 Event worker stopped")
    
    async def _handle_register(self, message: Dict):
        """Gère l'enregistrement d'un bot"""
        channel = message.get("channel")
        pid = message.get("pid")
        features = message.get("features", {})
        
        if not channel or not pid:
            LOGGER.warning(f"Invalid register message: {message}")
            return
        
        # Créer ou mettre à jour le bot
        bot = BotInfo(channel=channel, pid=pid, features=features)
        
        if not bot.is_alive():
            LOGGER.warning(f"Bot {channel} (PID {pid}) is not running")
            return
        
        self.bots[channel] = bot
        
        # Mettre à jour le statut en DB
        self.db.update_bot_status(
            channel=channel,
            pid=pid,
            status="online",
            features=features,
            registered_at=bot.registered_at
        )
        
        # Premier sample CPU (baseline)
        if bot.process:
            try:
                bot.process.cpu_percent(interval=None)
            except:
                pass
        
        enabled_features = [k for k, v in features.items() if v]
        LOGGER.info(f"✅ Bot registered: {channel} (PID {pid})")
        LOGGER.info(f"   Features: {', '.join(enabled_features)}")
    
    async def _handle_heartbeat(self, message: Dict):
        """Gère un heartbeat de bot"""
        channel = message.get("channel")
        pid = message.get("pid")
        
        if channel in self.bots:
            bot = self.bots[channel]
            if bot.pid == pid:
                bot.last_heartbeat = time.time()
                LOGGER.debug(f"💓 Heartbeat: {channel}")
            else:
                LOGGER.warning(f"PID mismatch for {channel}: expected {bot.pid}, got {pid}")
    
    async def _handle_unregister(self, message: Dict):
        """Gère la désinscription d'un bot"""
        channel = message.get("channel")
        pid = message.get("pid")
        
        if channel in self.bots:
            bot = self.bots[channel]
            if bot.pid == pid:
                # Mettre à jour le statut
                self.db.update_bot_status(
                    channel=channel,
                    pid=pid,
                    status="offline",
                    features=bot.features,
                    registered_at=bot.registered_at
                )
                del self.bots[channel]
                LOGGER.info(f"👋 Bot unregistered: {channel} (PID {pid})")
    
    async def _handle_llm_usage(self, message: Dict):
        """Gère un log d'usage LLM"""
        channel = message.get("channel", "unknown")
        model = message.get("model", "unknown")
        feature = message.get("feature", "unknown")
        tokens_in = message.get("tokens_in", 0)
        tokens_out = message.get("tokens_out", 0)
        latency_ms = message.get("latency_ms")
        
        self.db.insert_llm_usage(
            channel=channel,
            model=model,
            feature=feature,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms
        )
        
        LOGGER.debug(f"📊 LLM usage: {channel} | {model} | {tokens_in}→{tokens_out} tokens")
    
    async def _metrics_loop(self):
        """Boucle de collecte des métriques"""
        LOGGER.info(f"📊 Metrics loop started (interval: {self.metrics_interval}s)")
        
        while self._running:
            await asyncio.sleep(self.metrics_interval)
            
            if not self._running:
                break
            
            dead_bots = []
            
            for channel, bot in self.bots.items():
                # Vérifier si le bot est toujours vivant
                if not bot.is_alive():
                    LOGGER.warning(f"💀 Bot {channel} (PID {bot.pid}) died")
                    dead_bots.append(channel)
                    continue
                
                # Vérifier le heartbeat
                if bot.is_stale():
                    LOGGER.warning(f"⚠️ Bot {channel} is stale (no heartbeat)")
                
                # Collecter les métriques
                metrics = bot.get_metrics()
                if metrics:
                    self.db.insert_metrics(
                        channel=channel,
                        pid=bot.pid,
                        rss_mb=metrics["rss_mb"],
                        cpu_pct=metrics["cpu_pct"],
                        features=bot.features
                    )
                    
                    LOGGER.debug(
                        f"📈 {channel}: RAM={metrics['rss_mb']:.1f}MB, "
                        f"CPU={metrics['cpu_pct']:.1f}%"
                    )
            
            # Supprimer les bots morts
            for channel in dead_bots:
                bot = self.bots[channel]
                self.db.update_bot_status(
                    channel=channel,
                    pid=bot.pid,
                    status="dead",
                    features=bot.features,
                    registered_at=bot.registered_at
                )
                del self.bots[channel]
            
            # Log résumé si des bots actifs
            if self.bots:
                total_ram = sum(
                    bot.get_metrics()["rss_mb"] 
                    for bot in self.bots.values() 
                    if bot.get_metrics()
                )
                LOGGER.info(
                    f"📊 Active bots: {len(self.bots)} | "
                    f"Total RAM: {total_ram:.1f}MB"
                )
    
    async def _cleanup_loop(self):
        """Boucle de nettoyage périodique"""
        while self._running:
            # Nettoyer toutes les 24h
            await asyncio.sleep(86400)
            if self._running:
                self.db.cleanup_old_metrics(days=7)


def main(db_path: str = "kissbot_monitor.db", socket_path: str = "/tmp/kissbot_monitor.sock"):
    """Point d'entrée du Monitor"""
    print("=" * 60)
    print("🎛️ KissBot Monitor")
    print("=" * 60)
    
    if not PSUTIL_AVAILABLE:
        print("❌ psutil not available, cannot monitor processes")
        sys.exit(1)
    
    monitor = KissBotMonitor(socket_path=socket_path, db_path=db_path)
    
    # Gestion des signaux
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    shutdown_triggered = False
    
    def signal_handler(sig, frame):
        nonlocal shutdown_triggered
        if shutdown_triggered:
            return  # Éviter double shutdown
        shutdown_triggered = True
        print("\n🛑 Received shutdown signal")
        # Annuler toutes les tâches en cours
        for task in asyncio.all_tasks(loop):
            task.cancel()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        loop.run_until_complete(monitor.start())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass  # Arrêt normal
    finally:
        # Cleanup propre
        try:
            loop.run_until_complete(monitor.stop())
        except Exception:
            pass  # Déjà arrêté
        loop.close()
        print("✅ Monitor shutdown complete")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="KissBot Monitor")
    parser.add_argument("--db", default="kissbot_monitor.db", help="Path to monitor database")
    parser.add_argument("--socket", default="/tmp/kissbot_monitor.sock", help="Path to Unix socket")
    args = parser.parse_args()
    
    main(db_path=args.db, socket_path=args.socket)
