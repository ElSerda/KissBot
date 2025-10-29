"""Commands for quantum cache system interaction. See: docs/api/quantum_commands.md"""

import logging

from twitchio.ext import commands

from core.quantum_cache import QuantumCache


class QuantumCommands(commands.Component):
    """Commandes pour interaction avec le système quantique."""

    def __init__(self):
        # TwitchIO 3.x: bot auto-injecté via ctx.bot
        self.logger = logging.getLogger(__name__)

    @commands.command(name="quantum", aliases=["q"])
    async def quantum_status(self, ctx: commands.Context):
        """
        !quantum - Affiche l'état du système quantique

        ANALOGIE: Comme mesurer l'état d'un laboratoire quantique
        """
        if not ctx.bot.quantum_cache:
            await ctx.send("🚫 Système quantique non initialisé")
            return

        stats = ctx.bot.quantum_cache.get_quantum_stats()

        # Formatting pour Twitch (limite caractères)
        message = (
            f"🔬 Système Quantique: {stats['total_keys']} clés, "
            f"{stats['superposition_keys']} superpositions actives, "
            f"{stats['verified_states']}/{stats['total_states']} états collapsed, "
            f"{stats['entangled_pairs']} intrications"
        )

        await ctx.send(message)
        self.logger.info(f"📊 Stats quantiques demandées par {ctx.author.name}")

    @commands.command(name="observe", aliases=["obs"])
    async def observe_state(self, ctx: commands.Context, *, key: str = ""):
        """
        !observe <clé> - Observer un état quantique spécifique

        SUPERPOSITION → COLLAPSE: L'observation peut changer l'état !
        """
        if not ctx.bot.quantum_cache:
            await ctx.send("🚫 Système quantique non initialisé")
            return

        if not key:
            await ctx.send("❓ Usage: !observe <clé> (ex: !observe game:hades)")
            return

        # Observer l'état (influence quantique !)
        observer = ctx.author.name
        value = ctx.bot.quantum_cache.get(key, observer=observer)

        if value is None:
            await ctx.send(f"🚫 État quantique '{key}' non trouvé ou évaporé")
            return

        # Visualisation de l'état
        visualization = ctx.bot.quantum_cache.visualize_quantum_state(key)

        # Format pour Twitch (résumé)
        lines = visualization.split("\n")
        summary = lines[0] if lines else f"🔍 {key} observé"

        await ctx.send(f"{summary} par @{observer}")
        self.logger.info(f"🔍 Observation quantique: {key} par {observer}")

    @commands.command(name="collapse", aliases=["fix"])
    async def collapse_state(self, ctx: commands.Context, key: str = "", state_index: str = "0"):
        """
        !collapse <clé> [index] - Fixer un état quantique (effondrement)

        COLLAPSE DE LA FONCTION D'ONDE: Transforme superposition → état figé
        """
        if not ctx.bot.quantum_cache:
            await ctx.send("🚫 Système quantique non initialisé")
            return

        if not key:
            await ctx.send("❓ Usage: !collapse <clé> [index] (ex: !collapse game:hades 0)")
            return

        try:
            index = int(state_index)
        except ValueError:
            index = 0

        observer = ctx.author.name
        success = ctx.bot.quantum_cache.collapse_state(key, observer=observer, state_index=index)

        if success:
            await ctx.send(f"💥 @{observer} a fait COLLAPSE l'état '{key}' → État figé !")
            self.logger.info(f"💥 Collapse quantique: {key} par {observer}")
        else:
            await ctx.send(f"❌ Impossible de fixer '{key}' (état inexistant ou déjà collapsed)")

    @commands.command(name="entangle", aliases=["link"])
    async def entangle_states(self, ctx: commands.Context, key1: str = "", key2: str = ""):
        """
        !entangle <clé1> <clé2> - Créer intrication quantique entre deux états

        INTRICATION: Modifications de l'un affectent l'autre instantanément
        """
        if not ctx.bot.quantum_cache:
            await ctx.send("🚫 Système quantique non initialisé")
            return

        if not key1 or not key2:
            await ctx.send("❓ Usage: !entangle <clé1> <clé2> (ex: !entangle game:hades game:doom)")
            return

        ctx.bot.quantum_cache.entangle(key1, key2)

        observer = ctx.author.name
        await ctx.send(f"🔗 @{observer} a créé une intrication: {key1} ↔ {key2}")
        self.logger.info(f"🔗 Intrication créée: {key1} ↔ {key2} par {observer}")

    @commands.command(name="decoherence", aliases=["clean"])
    async def trigger_decoherence(self, ctx: commands.Context):
        """
        !decoherence - Déclencher évaporation des états non-vérifiés

        DÉCOHÉRENCE: Nettoyage des "particules virtuelles" expirées
        """
        if not ctx.bot.quantum_cache:
            await ctx.send("🚫 Système quantique non initialisé")
            return

        # Vérifier permissions (mods only ou cooldown)
        if not self._can_trigger_decoherence(ctx):
            await ctx.send("⚠️ Décohérence limitée aux modérateurs ou cooldown actif")
            return

        cleaned_count = ctx.bot.quantum_cache.cleanup_expired()

        observer = ctx.author.name
        await ctx.send(
            f"💨 @{observer} a déclenché la décohérence → " f"{cleaned_count} états évaporés"
        )
        self.logger.info(f"💨 Décohérence manuelle: {cleaned_count} états par {observer}")

    @commands.command(name="superposition", aliases=["multi"])
    async def create_superposition(self, ctx: commands.Context, key: str = "", *, value: str = ""):
        """
        !superposition <clé> <valeur> - Créer un nouvel état en superposition

        SUPERPOSITION: Ajoute une possibilité sans effondrer les autres
        """
        if not ctx.bot.quantum_cache:
            await ctx.send("🚫 Système quantique non initialisé")
            return

        if not key or not value:
            await ctx.send("❓ Usage: !superposition <clé> <valeur>")
            return

        # Vérifier permissions (éviter spam)
        if not self._can_create_superposition(ctx):
            await ctx.send("⚠️ Création de superposition limitée (cooldown)")
            return

        observer = ctx.author.name
        confidence = 0.3  # États créés manuellement = confiance faible

        ctx.bot.quantum_cache.set(
            key=key, value=value, source=f"user:{observer}", creator=observer, confidence=confidence
        )

        await ctx.send(
            f"⚛️ @{observer} a créé superposition '{key}' " f"(confiance: {confidence:.1f})"
        )
        self.logger.info(f"⚛️ Superposition créée: {key} par {observer}")

    def _can_trigger_decoherence(self, ctx: commands.Context) -> bool:
        """Vérifie si l'utilisateur peut déclencher la décohérence."""
        # Check modérateur ou broadcaster
        if ctx.author.is_mod or ctx.author.is_broadcaster:
            return True

        # TODO: Ajouter cooldown global pour éviter spam
        # Pour l'instant, autoriser pour tous (démo)
        return True

    def _can_create_superposition(self, ctx: commands.Context) -> bool:
        """Vérifie si l'utilisateur peut créer des superpositions."""
        # TODO: Ajouter rate limiting par utilisateur
        # Pour l'instant, autoriser pour tous (démo)
        return True


def prepare(bot):
    """Prépare le cog pour TwitchIO."""
    bot.add_cog(QuantumCommands(bot))
