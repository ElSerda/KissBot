"""See docs/api/handlers.md"""

from typing import Optional


class PingHandler:
    """Handler pour la commande ping"""

    def __init__(self, start_time: float):
        self.start_time = start_time

    def get_ping_response(self) -> str:
        """Génère réponse ping avec uptime"""
        import time

        elapsed = time.time() - self.start_time

        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)

        if hours > 0:
            uptime = f"{hours}h{minutes}m{seconds}s"
        elif minutes > 0:
            uptime = f"{minutes}m{seconds}s"
        else:
            uptime = f"{seconds}s"

        return f"Pong! 🏓 Uptime: {uptime}"


class StatsHandler:
    """Handler pour les statistiques"""

    def __init__(self, start_time: float):
        self.start_time = start_time

    def get_stats_response(self, cache_stats: dict | None = None) -> str:
        """Génère réponse stats complète"""
        import time

        elapsed = time.time() - self.start_time

        stats = []

        hours = int(elapsed // 3600)
        if hours > 0:
            uptime = f"{hours}h{int((elapsed % 3600) // 60)}m"
        else:
            uptime = f"{int(elapsed // 60)}m{int(elapsed % 60)}s"

        stats.append(f"⏱️ Uptime: {uptime}")

        if cache_stats:
            if "hits" in cache_stats and "misses" in cache_stats:
                total = cache_stats["hits"] + cache_stats["misses"]
                hit_rate = (cache_stats["hits"] / max(1, total)) * 100
                stats.append(f"📊 Cache: {hit_rate:.1f}% hit rate")
            else:
                stats.append(f"📊 Cache: {cache_stats.get('size', 0)} entrées")

        return " | ".join(stats)


class CacheHandler:
    """Handler pour les commandes cache"""

    def get_cache_response(self, cache_stats: dict | None = None) -> str:
        """Génère réponse cache détaillée"""
        if not cache_stats:
            return "📦 Cache indisponible"

        if "hits" in cache_stats and "misses" in cache_stats:
            total = cache_stats["hits"] + cache_stats["misses"]
            hit_rate = (cache_stats["hits"] / max(1, total)) * 100
            return f"📦 Cache: {cache_stats.get('size', 0)} entrées | {hit_rate:.1f}% hit rate | {cache_stats['hits']} hits / {cache_stats['misses']} miss"
        else:
            cache_size = cache_stats.get("size", 0)
            return f"📦 Cache: {cache_size} entrées stockées"


class HelpHandler:
    """Handler pour l'aide"""

    def get_help_response(self) -> str:
        """Génère liste des commandes"""
        commands_list = [
            "!gameinfo <nom>: Info jeu",
            "!gc: Jeu actuel du stream",
            "!ask <question>: IA",
            "@mention: IA conversationnelle",
            "!ping: Test latence",
            "!stats: Stats bot",
            "!cache: Stats cache",
            "!qgame: Recherche quantique",
            "!quantum: Stats quantiques",
            "!trad <texte>: Traduction",
            "!serdagit: Code source",
        ]

        return f"Commandes: {' | '.join(commands_list)}"


class GameInfoHandler:
    """Handler pour les infos de jeu"""

    def __init__(self, config: dict):
        self.config = config

    def validate_game_query(self, message_content: str) -> tuple[bool, str | None, str]:
        """See docs/api/handlers.md"""
        parts = message_content.strip().split(maxsplit=1)

        if len(parts) < 2:
            return False, None, "Usage: !gameinfo <nom_du_jeu>"

        game_name = parts[1]

        if len(game_name.strip()) == 0:
            return False, None, "Usage: !gameinfo <nom_du_jeu>"

        if len(game_name) > 100:
            return False, None, "Nom de jeu trop long (max 100 caractères)"

        return True, game_name, ""

    async def search_game_info(self, game_name: str) -> tuple[bool, str]:
        """See docs/api/handlers.md"""
        try:
            from modules.integrations.game_engine.python_fallback import GameLookup

            game_lookup = GameLookup(self.config)
            result = await game_lookup.search_game(game_name)

            if not result:
                return False, f"Jeu non trouvé : {game_name}"

            if result.confidence == "LOW":
                return (
                    False,
                    f"Résultat trop imprécis pour '{game_name}'. Essaye le nom complet ou une suite spécifique",
                )

            query_words = set(game_name.lower().split())
            result_words = set(result.name.lower().split())
            shared_words = query_words.intersection(result_words)

            if len(query_words) >= 2 and len(shared_words) == 0:
                return (
                    False,
                    f"Aucun résultat pertinent pour '{game_name}'. Vérifie l'orthographe ou essaye un autre nom",
                )

            response = self._format_game_response(result, game_name)
            return True, response

        except Exception as e:
            return False, f"Erreur recherche jeu: {str(e)[:50]}..."

    def _format_game_response(self, result, original_query: str = "") -> str:
        """Formate la réponse de jeu"""
        return f"🎮 {result.name} - Game found!"


class TranslationHandler:
    """Handler pour la traduction"""

    def validate_translation_query(self, message_content: str) -> tuple[bool, str | None, str]:
        """See docs/api/handlers.md"""
        parts = message_content.strip().split(maxsplit=1)

        if len(parts) < 2:
            return False, None, "Usage: !trad <texte>"

        text = parts[1]

        if len(text.strip()) == 0:
            return False, None, "Usage: !trad <texte>"

        if len(text) > 500:
            return False, None, "Texte trop long (max 500 caractères)"

        return True, text, ""

    async def translate_text(self, text: str) -> tuple[bool, str]:
        """See docs/api/handlers.md"""
        try:
            import aiohttp

            url = "https://translate.googleapis.com/translate_a/single"
            params = {"client": "gtx", "sl": "auto", "tl": "fr", "dt": "t", "q": text}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        translated = data[0][0][0]
                        return True, f"🌍 {translated}"
                    else:
                        return False, "❌ Erreur service traduction"

        except Exception:
            return False, "❌ Erreur traduction"


class LatencyHandler:
    """See docs/api/handlers.md"""

    def __init__(self, start_time: float):
        """See docs/api/handlers.md"""
        self.start_time = start_time

    def get_latency_response(self) -> str:
        """See docs/api/handlers.md"""
        import time

        end_time = time.time()
        latency_us = (end_time - self.start_time) * 1_000_000

        return f"⚡ Latence: {latency_us:.1f}μs (input→output)"


class QuantumPipelineHandler:
    """Handler pour le pipeline quantique"""

    def __init__(self):
        self.pipeline_stats = {
            "total_users_observed": 0,
            "active_superpositions": 0,
            "total_observations": 0,
            "entangled_users": 0,
            "quantum_enabled": True,
        }

    def observe_user_message(self, username: str, message_content: str) -> dict:
        """See docs/api/handlers.md"""
        user_state = {"username": username, "state": "superposition", "confidence": 0.5}

        if message_content.startswith("!"):
            user_state["state"] = "command_mode"
            user_state["confidence"] = 0.9
        elif "?" in message_content:
            user_state["state"] = "question_mode"
            user_state["confidence"] = 0.8
        else:
            user_state["state"] = "chat_mode"
            user_state["confidence"] = 0.7

        self.pipeline_stats["total_observations"] += 1

        return user_state

    def get_quantum_pipeline_response(self, pipeline_stats: dict | None = None) -> str:
        """See docs/api/handlers.md"""
        stats = pipeline_stats or self.pipeline_stats

        return (
            f"🔬 Pipeline Quantique: "
            f"{stats['total_users_observed']} users observés | "
            f"{stats['active_superpositions']} superpositions actives | "
            f"{stats['total_observations']} observations | "
            f"{stats['entangled_users']} intrications | "
            f"Quantum: {'✅' if stats['quantum_enabled'] else '❌'}"
        )


class HandlersFactory:
    """See docs/api/handlers.md"""

    @staticmethod
    def create_ping_handler(start_time: Optional[float] = None) -> PingHandler:
        import time

        return PingHandler(start_time or time.time())

    @staticmethod
    def create_stats_handler(start_time: Optional[float] = None) -> StatsHandler:
        import time

        return StatsHandler(start_time or time.time())

    @staticmethod
    def create_cache_handler() -> CacheHandler:
        return CacheHandler()

    @staticmethod
    def create_help_handler() -> HelpHandler:
        return HelpHandler()

    @staticmethod
    def create_gameinfo_handler(config: dict) -> GameInfoHandler:
        return GameInfoHandler(config)

    @staticmethod
    def create_translation_handler() -> TranslationHandler:
        return TranslationHandler()

    @staticmethod
    def create_latency_handler(start_time: float) -> LatencyHandler:
        return LatencyHandler(start_time)

    @staticmethod
    def create_quantum_pipeline_handler() -> QuantumPipelineHandler:
        return QuantumPipelineHandler()
