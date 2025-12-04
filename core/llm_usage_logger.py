#!/usr/bin/env python3
"""
LLM Usage Logger - Logging de l'utilisation LLM

Module pour logger chaque appel LLM (tokens in/out, latence, modèle).
Écrit directement dans SQLite (kissbot_monitor.db) pour éviter la dépendance au Monitor.

Usage:
    from core.llm_usage_logger import log_llm_usage, LLMUsageLogger
    
    # Simple (fonction)
    log_llm_usage(
        channel="el_serda",
        model="gpt-4.1-mini",
        feature="ask",
        tokens_in=150,
        tokens_out=50,
        latency_ms=234.5
    )
    
    # Ou avec context manager
    async with LLMUsageLogger.track("el_serda", "gpt-4", "mention") as tracker:
        response = await call_llm(prompt)
        tracker.set_tokens(prompt_tokens=100, completion_tokens=50)

Features:
    - Écriture WAL pour éviter les locks
    - Estimation de coût (optionnel)
    - Stats agrégées par channel/jour
    - Compatible avec le Monitor central
"""

import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

LOGGER = logging.getLogger(__name__)

# Configuration
DEFAULT_DB_PATH = "kissbot_monitor.db"

# Prix par 1M tokens (approximatifs, à ajuster)
MODEL_PRICING = {
    # OpenAI
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4.1-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Mistral
    "mistral-7b-instruct": {"input": 0.0, "output": 0.0},  # Local = gratuit
    # Default
    "default": {"input": 1.0, "output": 2.0},
}


@dataclass
class LLMCall:
    """Représente un appel LLM loggé"""
    channel: str
    model: str
    feature: str
    tokens_in: int
    tokens_out: int
    latency_ms: Optional[float] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out
    
    def estimate_cost(self) -> float:
        """Estime le coût en USD"""
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING["default"])
        cost_in = (self.tokens_in / 1_000_000) * pricing["input"]
        cost_out = (self.tokens_out / 1_000_000) * pricing["output"]
        return cost_in + cost_out


class LLMUsageDB:
    """Gestionnaire de la base de données pour l'usage LLM"""
    
    _instance: Optional['LLMUsageDB'] = None
    
    def __new__(cls, db_path: str = DEFAULT_DB_PATH):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        if self._initialized:
            return
        
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._initialized = True
    
    def _init_db(self):
        """Initialise la connexion et la table"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # WAL mode pour éviter les locks
        self.conn.execute("PRAGMA journal_mode=WAL")
        
        # Créer la table si elle n'existe pas
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                channel TEXT NOT NULL,
                model TEXT NOT NULL,
                feature TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                latency_ms REAL,
                cost_usd REAL
            )
        """)
        
        # Table pour les totaux cumulatifs (simple compteur)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_totals (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tokens_in_total INTEGER NOT NULL DEFAULT 0,
                tokens_out_total INTEGER NOT NULL DEFAULT 0,
                calls_total INTEGER NOT NULL DEFAULT 0,
                last_updated TEXT
            )
        """)
        
        # Initialiser le compteur si vide
        self.conn.execute("""
            INSERT OR IGNORE INTO llm_totals (id, tokens_in_total, tokens_out_total, calls_total)
            VALUES (1, 0, 0, 0)
        """)
        
        # Index pour les queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_usage_channel_ts 
            ON llm_usage(channel, ts)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_usage_model 
            ON llm_usage(model)
        """)
        
        self.conn.commit()
        LOGGER.debug(f"LLM Usage DB initialized: {self.db_path}")
    
    def log(self, call: LLMCall):
        """Insère un log d'appel LLM et incrémente les totaux"""
        ts = call.timestamp.isoformat() if call.timestamp else datetime.now(timezone.utc).isoformat()
        cost = call.estimate_cost()
        
        # Log détaillé
        self.conn.execute("""
            INSERT INTO llm_usage (ts, channel, model, feature, tokens_in, tokens_out, latency_ms, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, call.channel, call.model, call.feature, 
              call.tokens_in, call.tokens_out, call.latency_ms, cost))
        
        # Incrémenter les totaux
        self.conn.execute("""
            UPDATE llm_totals SET 
                tokens_in_total = tokens_in_total + ?,
                tokens_out_total = tokens_out_total + ?,
                calls_total = calls_total + 1,
                last_updated = ?
            WHERE id = 1
        """, (call.tokens_in, call.tokens_out, ts))
        
        self.conn.commit()
        
        LOGGER.debug(
            f"📊 LLM: {call.channel} | {call.model} | {call.feature} | "
            f"{call.tokens_in}→{call.tokens_out} tokens | ${cost:.6f}"
        )
    
    def increment_tokens(self, tokens_in: int, tokens_out: int):
        """Incrémente simplement les compteurs de tokens"""
        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            UPDATE llm_totals SET 
                tokens_in_total = tokens_in_total + ?,
                tokens_out_total = tokens_out_total + ?,
                calls_total = calls_total + 1,
                last_updated = ?
            WHERE id = 1
        """, (tokens_in, tokens_out, ts))
        self.conn.commit()
    
    def get_totals(self) -> Dict[str, int]:
        """Récupère les totaux cumulatifs"""
        cursor = self.conn.execute("""
            SELECT tokens_in_total, tokens_out_total, calls_total, last_updated
            FROM llm_totals WHERE id = 1
        """)
        row = cursor.fetchone()
        if row:
            return {
                "tokens_in": row[0],
                "tokens_out": row[1],
                "tokens_total": row[0] + row[1],
                "calls": row[2],
                "last_updated": row[3]
            }
        return {"tokens_in": 0, "tokens_out": 0, "tokens_total": 0, "calls": 0}
    
    def get_channel_stats(self, channel: str, days: int = 30) -> Dict[str, Any]:
        """Récupère les stats d'un channel"""
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as call_count,
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                SUM(cost_usd) as total_cost,
                AVG(latency_ms) as avg_latency,
                model,
                feature
            FROM llm_usage
            WHERE channel = ? AND ts >= datetime('now', ? || ' days')
            GROUP BY model, feature
        """, (channel, f"-{days}"))
        
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        
        # Totaux
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total_calls,
                SUM(tokens_in + tokens_out) as total_tokens,
                SUM(cost_usd) as total_cost
            FROM llm_usage
            WHERE channel = ? AND ts >= datetime('now', ? || ' days')
        """, (channel, f"-{days}"))
        
        totals = dict(cursor.fetchone())
        
        return {
            "channel": channel,
            "period_days": days,
            "totals": totals,
            "by_model_feature": results
        }
    
    def get_daily_summary(self, channel: Optional[str] = None) -> list:
        """Récupère un résumé journalier"""
        where = "WHERE channel = ?" if channel else ""
        params = (channel,) if channel else ()
        
        cursor = self.conn.execute(f"""
            SELECT 
                date(ts) as day,
                channel,
                SUM(tokens_in) as tokens_in,
                SUM(tokens_out) as tokens_out,
                SUM(cost_usd) as cost,
                COUNT(*) as calls
            FROM llm_usage
            {where}
            GROUP BY date(ts), channel
            ORDER BY day DESC
            LIMIT 30
        """, params)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Ferme la connexion"""
        if self.conn:
            self.conn.close()
            self._initialized = False
            LLMUsageDB._instance = None


# === API Publique ===

def log_llm_usage(channel: str, model: str, feature: str,
                  tokens_in: int, tokens_out: int,
                  latency_ms: Optional[float] = None,
                  db_path: str = DEFAULT_DB_PATH):
    """
    Log un appel LLM.
    
    Args:
        channel: Channel Twitch
        model: Nom du modèle (ex: "gpt-4", "gpt-3.5-turbo")
        feature: Type d'utilisation ("ask", "mention", "persona", etc.)
        tokens_in: Nombre de tokens en entrée (prompt)
        tokens_out: Nombre de tokens en sortie (completion)
        latency_ms: Latence en millisecondes (optionnel)
        db_path: Chemin de la base de données
    """
    try:
        db = LLMUsageDB(db_path)
        call = LLMCall(
            channel=channel,
            model=model,
            feature=feature,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms
        )
        db.log(call)
    except Exception as e:
        LOGGER.error(f"Failed to log LLM usage: {e}")


def get_channel_llm_stats(channel: str, days: int = 30,
                          db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Récupère les statistiques LLM d'un channel.
    
    Args:
        channel: Channel Twitch
        days: Nombre de jours à considérer
        db_path: Chemin de la base de données
        
    Returns:
        Dict avec les statistiques
    """
    try:
        db = LLMUsageDB(db_path)
        return db.get_channel_stats(channel, days)
    except Exception as e:
        LOGGER.error(f"Failed to get LLM stats: {e}")
        return {}


def increment_llm_tokens(tokens_in: int, tokens_out: int, 
                         db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Incrémente simplement les compteurs de tokens (sans détails).
    
    Args:
        tokens_in: Tokens prompt
        tokens_out: Tokens completion
        db_path: Chemin de la base de données
    """
    try:
        db = LLMUsageDB(db_path)
        db.increment_tokens(tokens_in, tokens_out)
    except Exception as e:
        LOGGER.error(f"Failed to increment tokens: {e}")


def get_llm_totals(db_path: str = DEFAULT_DB_PATH) -> Dict[str, int]:
    """
    Récupère les totaux cumulatifs de tokens.
    
    Returns:
        Dict avec tokens_in, tokens_out, tokens_total, calls
    """
    try:
        db = LLMUsageDB(db_path)
        return db.get_totals()
    except Exception as e:
        LOGGER.error(f"Failed to get LLM totals: {e}")
        return {"tokens_in": 0, "tokens_out": 0, "tokens_total": 0, "calls": 0}


class LLMCallTracker:
    """
    Tracker pour mesurer un appel LLM.
    
    Usage:
        tracker = LLMCallTracker("el_serda", "gpt-4", "ask")
        tracker.start()
        # ... appel LLM ...
        tracker.set_tokens(100, 50)
        tracker.stop()
    """
    
    def __init__(self, channel: str, model: str, feature: str,
                 db_path: str = DEFAULT_DB_PATH):
        self.channel = channel
        self.model = model
        self.feature = feature
        self.db_path = db_path
        self._start_time: Optional[float] = None
        self._tokens_in = 0
        self._tokens_out = 0
    
    def start(self):
        """Démarre le timer"""
        self._start_time = time.perf_counter()
    
    def set_tokens(self, tokens_in: int, tokens_out: int):
        """Définit les tokens utilisés"""
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
    
    def stop(self):
        """Arrête le timer et log"""
        if self._start_time is None:
            LOGGER.warning("LLMCallTracker.stop() called without start()")
            return
        
        latency_ms = (time.perf_counter() - self._start_time) * 1000
        
        log_llm_usage(
            channel=self.channel,
            model=self.model,
            feature=self.feature,
            tokens_in=self._tokens_in,
            tokens_out=self._tokens_out,
            latency_ms=latency_ms,
            db_path=self.db_path
        )


@asynccontextmanager
async def track_llm_call(channel: str, model: str, feature: str,
                         db_path: str = DEFAULT_DB_PATH):
    """
    Context manager async pour tracker un appel LLM.
    
    Usage:
        async with track_llm_call("el_serda", "gpt-4", "ask") as tracker:
            response = await call_openai(prompt)
            tracker.set_tokens(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )
    """
    tracker = LLMCallTracker(channel, model, feature, db_path)
    tracker.start()
    try:
        yield tracker
    finally:
        tracker.stop()


# === Estimation de tokens (fallback) ===

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estime le nombre de tokens d'un texte.
    
    Utilise tiktoken si disponible, sinon approximation.
    
    Args:
        text: Texte à analyser
        model: Modèle pour l'encodage
        
    Returns:
        Nombre estimé de tokens
    """
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Approximation: ~4 caractères par token en moyenne
        return len(text) // 4
