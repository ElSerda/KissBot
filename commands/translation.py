"""
Translation Commands - !trad
Système de traduction multilingue avec Google API
"""

import json
import os
from datetime import datetime

import aiohttp
from twitchio.ext import commands


class TranslationCommands(commands.Component):
    """Commandes de traduction."""

    def __init__(self):
        # TwitchIO 3.x: bot auto-injecté via ctx.bot
        pass

    @commands.command(name="trad")
    async def translate_text(self, ctx: commands.Context):
        """Traduit n'importe quelle langue → français (config)."""

        # Extract text
        parts = ctx.message.content.strip().split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send("Usage: !trad <texte>")
            return

        text = parts[1]

        # Rate limiting
        if not ctx.bot.rate_limiter.is_allowed(ctx.author.name, cooldown=5.0):
            remaining = ctx.bot.rate_limiter.get_remaining_cooldown(ctx.author.name, cooldown=5.0)
            await ctx.send(f"@{ctx.author.name} Cooldown! Attends {remaining:.1f}s")
            return

        # Google Translate API (gratuit)
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",  # Auto-détecte source
            "tl": "fr",  # Target français
            "dt": "t",
            "q": text,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        translated = data[0][0][0]
                        await ctx.send(f"🌍 {translated}")
                        return
        except Exception as e:
            ctx.bot.logger.error(f"Erreur traduction: {e}")

        await ctx.send("❌ Erreur traduction")

    # ========================================
    # COMMANDES: Devs Whitelist Management
    # ========================================

    @commands.command(name="adddev")
    async def add_dev(self, ctx: commands.Context):
        """Ajoute un dev à la whitelist auto-translate."""

        # Check permissions (broadcaster only)
        if not self._is_broadcaster_or_mod(ctx):
            await ctx.send(f"@{ctx.author.name} ❌ Seuls broadcaster/mods peuvent gérer devs")
            return

        # Extract username
        parts = ctx.message.content.strip().split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send("Usage: !adddev <username>")
            return

        username = parts[1].lower().strip("@")

        # Load devs list
        devs_data = self._load_devs_whitelist()

        if username in devs_data["devs"]:
            await ctx.send(f"@{ctx.author.name} {username} est déjà dans la whitelist devs")
            return

        # Add dev
        devs_data["devs"].append(username)
        devs_data["updated"] = datetime.utcnow().isoformat() + "Z"

        if self._save_devs_whitelist(devs_data):
            await ctx.send(f"✅ {username} ajouté à la whitelist devs (auto-translate activé)")
        else:
            await ctx.send(f"@{ctx.author.name} ❌ Erreur lors de la sauvegarde")

    @commands.command(name="deldev")
    async def del_dev(self, ctx: commands.Context):
        """Retire un dev de la whitelist auto-translate."""

        # Check permissions
        if not self._is_broadcaster_or_mod(ctx):
            await ctx.send(f"@{ctx.author.name} ❌ Seuls broadcaster/mods peuvent gérer devs")
            return

        # Extract username
        parts = ctx.message.content.strip().split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send("Usage: !deldev <username>")
            return

        username = parts[1].lower().strip("@")

        # Load devs list
        devs_data = self._load_devs_whitelist()

        if username not in devs_data["devs"]:
            await ctx.send(f"@{ctx.author.name} {username} n'est pas dans la whitelist devs")
            return

        # Remove dev
        devs_data["devs"].remove(username)
        devs_data["updated"] = datetime.utcnow().isoformat() + "Z"

        if self._save_devs_whitelist(devs_data):
            await ctx.send(f"✅ {username} retiré de la whitelist devs")
        else:
            await ctx.send(f"@{ctx.author.name} ❌ Erreur lors de la sauvegarde")

    @commands.command(name="listdev")
    async def list_devs(self, ctx: commands.Context):
        """Affiche la liste des devs en whitelist."""

        devs_data = self._load_devs_whitelist()

        if not devs_data["devs"]:
            await ctx.send("📋 Aucun dev dans la whitelist auto-translate")
            return

        devs_list = ", ".join(devs_data["devs"])
        await ctx.send(f"📋 Devs whitelist auto-translate: {devs_list}")

    # ========================================
    # UTILS: Devs Management
    # ========================================

    def _load_devs_whitelist(self) -> dict:
        """Charge la whitelist des devs depuis JSON."""
        devs_file = "data/devs_whitelist.json"

        try:
            if os.path.exists(devs_file):
                with open(devs_file, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            # Log error without ctx (static method)
            print(f"⚠️ Erreur lecture devs whitelist: {e}")

        # Default data
        return {"devs": [], "auto_translate": True, "updated": datetime.utcnow().isoformat() + "Z"}

    def _save_devs_whitelist(self, data: dict) -> bool:
        """Sauvegarde la whitelist des devs en JSON."""
        devs_file = "data/devs_whitelist.json"

        try:
            # Créer le dossier data si nécessaire
            os.makedirs("data", exist_ok=True)

            with open(devs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            # Log error without ctx (static method)
            print(f"⚠️ Erreur sauvegarde devs whitelist: {e}")
            return False

    def _is_broadcaster_or_mod(self, ctx: commands.Context) -> bool:
        """Vérifie si l'utilisateur est broadcaster ou modérateur."""
        return ctx.author.is_broadcaster or ctx.author.is_mod


def prepare(bot):
    """Setup function for TwitchIO."""
    bot.add_cog(TranslationCommands(bot))
