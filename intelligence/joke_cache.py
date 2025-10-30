"""
🎭 Joke Cache - Cache dédié aux blagues pré-optimisées

Domaine séparé de game_cache pour isolation et TTL spécifique.

Solution Mistral AI :
- Cache intelligent avec variabilité contrôlée
- User sessions tracking (rotation toutes les 3 blagues)
- Variabilité temporelle (5 minutes)
- Prompts dynamiques pour forcer la diversité
"""

import logging
import random
import time
from collections import defaultdict
from typing import Any


class JokeCache:
    """
    Cache intelligent avec variabilité pour éviter la répétition.
    
    Features:
    - TTL 5 minutes (équilibre performance + variété)
    - User sessions: rotation toutes les 3 blagues
    - Variabilité temporelle: nouvelle blague toutes les 5 min
    - Métriques hit/miss rate
    - Auto-cleanup LRU
    
    Stratégie de clé: base_prompt + user_id + variant
    - variant = "v{session_count // 3}_{time // 300}"
    - Change automatiquement toutes les 3 demandes OU 5 minutes
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 100):
        """
        Args:
            ttl_seconds: Durée de vie cache (défaut 5min = 300s)
            max_size: Taille max cache (défaut 100 blagues)
        """
        self.logger = logging.getLogger(__name__)
        self.ttl = ttl_seconds
        self.max_size = max_size

        # Storage: {cache_key: (timestamp, joke)}
        self.cache: dict[str, tuple[float, str]] = {}
        
        # User sessions tracking: {user_id: joke_counter}
        self.user_sessions = defaultdict(int)

        # Métriques
        self.hits = 0
        self.misses = 0

        self.logger.info(f"🎭 JokeCache initialisé (Mistral AI): TTL={ttl_seconds}s, max_size={max_size}")


    def get_key(self, user_id: str, base_prompt: str) -> str:
        """
        Génère une clé unique avec variabilité intelligente.
        
        Stratégie :
        - Compteur utilisateur: change toutes les 3 blagues (session_count // 3)
        - Timestamp arrondi: change toutes les 5 minutes (time // 300)
        - Clé = base_prompt + user_id + variant
        
        Args:
            user_id: ID Twitch de l'utilisateur
            base_prompt: Prompt de base (sans variant)
            
        Returns:
            Clé cache unique avec variabilité contrôlée
        """
        session_count = self.user_sessions[user_id]
        self.user_sessions[user_id] += 1
        
        # Variabilité : toutes les 3 blagues OU toutes les 5 minutes
        variant = f"v{session_count // 3}_{int(time.time() / 300)}"
        
        cache_key = f"{base_prompt}_{user_id}_{variant}"
        self.logger.debug(f"� Cache key: user={user_id}, session={session_count}, variant={variant}")
        
        return cache_key

    def get(self, cache_key: str) -> str | None:
        """
        Récupère une blague du cache.
        
        Args:
            cache_key: Clé cache générée par get_key()
            
        Returns:
            Blague si cache hit, None si miss ou expired
        """
        if cache_key not in self.cache:
            self.misses += 1
            self.logger.debug(f"💔 Cache MISS: {cache_key[:50]}...")
            return None

        timestamp, joke = self.cache[cache_key]

        # Vérifier TTL
        if time.time() - timestamp > self.ttl:
            del self.cache[cache_key]
            self.misses += 1
            self.logger.debug(f"⏱️ Cache EXPIRED: {cache_key[:50]}...")
            return None

        self.hits += 1
        self.logger.info(f"💾 Cache HIT: {cache_key[:50]}... → {joke[:50]}...")
        return joke

    def set(self, cache_key: str, joke: str):
        """
        Stocke une blague dans le cache.
        
        Args:
            cache_key: Clé cache générée par get_key()
            joke: Réponse du LLM à cacher
        """
        # Cleanup si cache plein
        if len(self.cache) >= self.max_size:
            self._cleanup()
        
        self.cache[cache_key] = (time.time(), joke)
        self.logger.info(f"💾 Cached: {cache_key[:50]}... → {joke[:50]}...")


    def _cleanup(self):
        """Nettoie les entrées expirées ou anciennes (LRU)"""
        current_time = time.time()
        
        # Supprimer entrées expirées
        expired_keys = [
            key for key, (timestamp, _) in self.cache.items()
            if current_time - timestamp > self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        # Si encore trop plein, supprimer les plus anciens (LRU)
        if len(self.cache) >= self.max_size:
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: x[1][0]  # Trier par timestamp
            )
            
            # Garder seulement 80% plus récents
            keep_count = int(self.max_size * 0.8)
            self.cache = dict(sorted_items[-keep_count:])
            
            self.logger.info(f"🧹 Cleanup: {len(sorted_items) - keep_count} entrées supprimées")

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques du cache"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_entries": len(self.cache),
            "total_users": len(self.user_sessions),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl,
            "max_size": self.max_size
        }

    def clear(self):
        """Vide le cache (pour tests ou reset)"""
        self.cache.clear()
        self.user_sessions.clear()
        self.hits = 0
        self.misses = 0
        self.logger.info("🗑️ Cache vidé")


def get_dynamic_prompt(base_prompt: str) -> str:
    """
    Génère un prompt dynamique avec variant aléatoire.
    
    Force le LLM à générer des réponses différentes en ajoutant
    un style/contrainte aléatoire au prompt de base.
    
    Args:
        base_prompt: Prompt de base (ex: "raconte une blague")
        
    Returns:
        Prompt avec variant aléatoire ajouté
        
    Exemple:
        base = "raconte une blague courte"
        dynamic = get_dynamic_prompt(base)
        # → "raconte une blague courte style absurde"
    """
    variants = [
        "style drôle",
        "style absurde", 
        "style court",
        "pour enfants",
        "pour adultes",
        "avec un jeu de mots",
        "surprise-moi"
    ]
    
    variant = random.choice(variants)
    return f"{base_prompt} {variant}"

