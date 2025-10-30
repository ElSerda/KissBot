#!/usr/bin/env python3
"""
🚀 KissBotV3 WORKING - TwitchIO 3.x Based on REAL Examples
Basé sur les exemples officiels GitHub PythonistaGuild/TwitchIO
"""

import asyncio
import logging
import time
from typing import Any

import yaml
import twitchio
from twitchio import eventsub
from twitchio.ext import commands

# Setup logging comme dans les exemples
LOGGER = logging.getLogger(__name__)


def load_config():
    """Load configuration from YAML file."""
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class KissBotV3Working(commands.Bot):
    """🎯 TwitchIO 3.x Bot QUI MARCHE - Basé sur les vrais exemples !"""

    def __init__(self, **kwargs: Any) -> None:
        config = load_config()
        twitch_config = config.get("twitch", {})

        # TwitchIO 3.x: EventSub WebSocket + IRC Fallback
        # 🎯 STRATÉGIE:
        #   - Primary: EventSub WebSocket (moderne, powerful)
        #   - Fallback: IRC (pragmatique, fiable, marche même sans bons scopes)
        # 📡 Les deux tournent en parallèle - meilleur des 2 mondes !

        super().__init__(
            client_id=twitch_config.get("client_id", ""),
            client_secret=twitch_config.get("client_secret", ""),
            bot_id=twitch_config.get("bot_id", ""),
            owner_id=twitch_config.get("bot_id", ""),  # Même compte = autorisation totale
            prefix=twitch_config.get("prefix", "!"),
            # TwitchIO 3.x: Plus de initial_channels - on utilise IRC direct via connect_channels
        )

        self.config = config

        # 🎯 INITIALISER LES DÉPENDANCES KISSBOT
        from backends.game_cache import GameCache

        self.start_time = time.time()
        self.bot_display_name = ""
        self.bot_login_name = ""
        self.game_cache = GameCache(config)  # Passer la config

        LOGGER.info("🎯 KissBotV3Working créé avec TwitchIO 3.x + KissBot components")

    async def setup_hook(self) -> None:
        """Setup hook - BASÉ SUR LES EXEMPLES OFFICIELS"""
        LOGGER.info("🔧 Setup hook - Ajout des components...")

        # 🔑 CRUCIAL: Charger les User Access Tokens depuis .tio.tokens.json
        # TwitchIO 3.x nécessite les tokens POUR LES DEUX COMPTES:
        #   1. Bot token (pour recevoir les messages)
        #   2. Broadcaster token (pour les subscriptions EventSub)
        # 🔑 Charger les tokens depuis config.yaml
        try:
            tokens_config = self.config.get("twitch", {}).get("tokens", {})

            if not tokens_config:
                LOGGER.warning("⚠️ Aucun token trouvé dans config.yaml!")
            else:
                print(f"🔍 DEBUG: Tokens dans config: {list(tokens_config.keys())}")

                for account_name, token_info in tokens_config.items():
                    user_id = token_info.get("user_id")
                    token = token_info.get("access_token", "").replace("oauth:", "")
                    refresh = token_info.get("refresh_token", "")

                    print(f"🔍 DEBUG: Processing {account_name} (user_id={user_id})")
                    print(f"🔍 DEBUG: token={token[:20]}... (len: {len(token)})")
                    print(f"🔍 DEBUG: refresh={refresh[:20]}... (len: {len(refresh)})")

                    if token:
                        LOGGER.info(f"🔑 Ajout du token pour {account_name} ({user_id})...")
                        await self.add_token(token, refresh)
                        LOGGER.info(f"✅ Token ajouté pour {account_name}")
                    else:
                        LOGGER.warning(f"⚠️ Token vide pour {account_name}")

                print(f"✅ Tokens chargés: {len(tokens_config)} comptes")
                LOGGER.info(f"✅ {len(tokens_config)} tokens chargés depuis config.yaml")
        except Exception as e:
            LOGGER.error(f"❌ Erreur lors du chargement des tokens: {e}")

        # 🎯 IMPORTER NOS COMMANDES TWITCHIO 3.x !
        from commands.utils_commands import UtilsCommands
        from commands.game_commands import GameCommands
        from commands.intelligence_commands import IntelligenceCommands
        from commands.translation import TranslationCommands
        from commands.quantum_commands import QuantumCommands

        # Ajouter nos components TwitchIO 3.x (passer config pour cooldowns)
        await self.add_component(UtilsCommands())
        await self.add_component(GameCommands())
        await self.add_component(IntelligenceCommands(config=self.config))
        await self.add_component(TranslationCommands(config=self.config))
        await self.add_component(QuantumCommands())
        LOGGER.info("✅ Commandes KissBot TwitchIO 3.x ajoutées")

        # 🔍 DEBUG : Lister les commandes enregistrées
        print(f"🔍 Commandes enregistrées: {list(self.commands.keys())}")
        LOGGER.info(f"🔍 Total commandes: {len(self.commands)}")

        # 🎯 RÉCUPÉRER LE NOM DU BOT VIA L'API HELIX
        try:
            # Utiliser l'API Helix pour récupérer les infos du bot
            users = await self.fetch_users(ids=[self.bot_id])
            if users:
                self.bot_display_name = users[0].display_name
                bot_name = users[0].name
                self.bot_login_name = (bot_name.lower() if bot_name else "kissbot")
                LOGGER.info(
                    f"🤖 Bot nom récupéré via API: "
                    f"{self.bot_display_name} ({self.bot_login_name})"
                )
                print(f"🤖 Bot identifié: {self.bot_display_name} (@{self.bot_login_name})")
            else:
                # Fallback sur la config
                self.bot_display_name = self.config.get("bot", {}).get("name", "KissBot")
                self.bot_login_name = self.bot_display_name.lower()
                LOGGER.warning(f"⚠️ Fallback config bot: {self.bot_display_name}")
        except Exception as e:
            # Fallback sur la config en cas d'erreur API
            self.bot_display_name = self.config.get("bot", {}).get("name", "KissBot")
            self.bot_login_name = self.bot_display_name.lower()
            LOGGER.error(f"❌ Erreur API bot name, fallback config: {e}")

        # 🎯 CONFIGURATION CHANNELS + EventSub WebSocket SUBSCRIPTIONS
        # 🔑 CRUCIAL : TwitchIO 3.x nécessite des subscriptions EXPLICITES !
        # Sinon : Bot connecté mais "MUET" - les messages n'arrivent pas !
        try:
            # Récupérer les channels de la config
            channels = self.config.get("twitch", {}).get("channels", [])
            LOGGER.info(f"📋 Channels configurés: {channels}")
            LOGGER.info(f"🤖 Bot ID configuré: {self.bot_id}")

            # 🔥 ÉTAPE CRITIQUE : Créer les subscriptions EventSub pour les messages du chat
            # Basé sur : TWITCHIO3_EVENTSUB_GUIDE_COMPLET.md
            for channel_name in channels:
                try:
                    # Récupérer l'ID du channel
                    users = await self.fetch_users(logins=[channel_name])
                    if not users:
                        LOGGER.warning(f"❌ Channel {channel_name} non trouvé")
                        continue

                    broadcaster = users[0]
                    broadcaster_id = broadcaster.id

                    # 🔥 DEBUG: Vérifier les types
                    LOGGER.info(f"🔍 broadcaster_id: {broadcaster_id} (type: {type(broadcaster_id).__name__})")
                    LOGGER.info(f"🔍 bot_id: {self.bot_id} (type: {type(self.bot_id).__name__})")

                    # 🎯 Créer la subscription ChatMessage pour EventSub WebSocket
                    # QUOI : S'abonner aux messages du channel
                    # BROADCASTER : Le channel (ex: el_serda)
                    # USER : Le bot qui reçoit (ex: serda_bot, même compte si broadcaster=bot)
                    # 🔑 CRUCIAL: Utiliser le token du BROADCASTER pour les EventSub subscriptions!
                    chat_sub = eventsub.ChatMessageSubscription(
                        broadcaster_user_id=broadcaster_id,
                        user_id=self.bot_id
                    )

                    # 🔥 FIX: Convertir broadcaster_id en STRING pour matcher les clés du dictionnaire de tokens!
                    broadcaster_id_str = str(broadcaster_id)
                    LOGGER.info(f"🔍 token_for value: {broadcaster_id_str} (type: {type(broadcaster_id_str).__name__})")

                    # Debug: Voir quels tokens sont disponibles
                    LOGGER.info(f"🔍 ManagedHTTPClient tokens: {list(self._http._tokens.keys()) if hasattr(self._http, '_tokens') else 'N/A'}")
                    LOGGER.info(f"🔍 WebSockets avant: {list(self._websockets.keys())}")

                    # Utiliser le token du broadcaster pour la subscription
                    await self.subscribe_websocket(chat_sub, token_for=broadcaster_id_str)

                    LOGGER.info(f"🔍 WebSockets après: {list(self._websockets.keys())}")
                    LOGGER.info(
                        f"✅ EventSub ChatMessageSubscription créée pour: "
                        f"{broadcaster.display_name} ({broadcaster_id})"
                    )
                    print(f"✅ EventSub Subscribe: {broadcaster.display_name} → Messages incoming!")

                except Exception as e:
                    LOGGER.error(f"❌ Erreur EventSub subscription pour {channel_name}: {e}")
                    print(f"❌ Erreur subscription {channel_name}: {e}")
                    import traceback
                    traceback.print_exc()

            LOGGER.info("✅ EventSub WebSocket subscriptions configurées - Bot prêt à recevoir messages")

        except Exception as e:
            LOGGER.error(f"❌ Erreur setup channels: {e}")

        LOGGER.info("✅ Setup hook terminé!")

    async def event_ready(self) -> None:
        """Event ready - COMME DANS LES EXEMPLES"""
        LOGGER.info("🚀 Bot connecté: %s", self.user)
        print(f"🎉 TwitchIO 3.x Bot Ready: {self.user}")

        # 🎯 EventSub WebSocket est déjà actif (configuré dans setup_hook)
        # Plus besoin d'IRC fallback avec TwitchIO 3.x EventSub !
        LOGGER.info("✅ Bot Ready - EventSub WebSocket opérationnel")

        # 🎯 ENVOI MESSAGE DE COUCOU AUTOMATIQUE !
        await self.send_hello_message()

    async def send_hello_message(self) -> None:
        """Envoie un message de coucou au broadcaster"""
        try:
            # Récupérer les channels configurés
            channels = self.config.get("twitch", {}).get("channels", ["el_serda"])

            for channel_name in channels:
                print(f"📤 Envoi coucou vers channel: {channel_name}")

                # TwitchIO 3.x: Syntaxe correcte pour fetch_users (sans 'names')
                users = await self.fetch_users(logins=[channel_name])

                if not users:
                    print(f"❌ User {channel_name} non trouvé")
                    continue

                broadcaster = users[0]

                # Message de coucou personnalisé
                message = (
                    f"🤖 Coucou {broadcaster.display_name} ! "
                    f"C'est ici le stream de el_serda ?! 🚀"
                )

                # TwitchIO 3.x: Envoyer le message
                result = await broadcaster.send_message(
                    sender=self.bot_id,
                    message=message
                )

                print("✅ MESSAGE ENVOYÉ !")
                print(f"📋 Résultat: {result}")
                print(f"📋 Type: {type(result)}")

                # TwitchIO 3.x donne de vraies infos !
                if hasattr(result, 'id'):
                    print(f"📋 Message ID: {result.id}")

                LOGGER.info(
                    "✅ Coucou envoyé à %s: %s",
                    broadcaster.display_name,
                    message
                )

        except Exception as e:
            print(f"❌ Erreur envoi coucou: {e}")
            LOGGER.error("❌ Erreur coucou: %s", e)

    async def event_oauth_authorized(
        self, payload: twitchio.authentication.UserTokenPayload
    ) -> None:
        """OAuth authorized - COMME DANS LES EXEMPLES"""
        LOGGER.info("🔑 OAuth authorized pour user: %s", payload.user_id)

        # Stocker le token
        await self.add_token(payload.access_token, payload.refresh_token)

        if payload.user_id == self.bot_id:
            LOGGER.info("🤖 Bot token récupéré")
            return

        # Subscribe au chat pour ce user
        # 🎯 FULL EventSub WebSocket SOLUTION:
        # Si c'est le bot lui-même (broadcaster = bot), alors autorisation OK !
        chat_sub = eventsub.ChatMessageSubscription(
            broadcaster_user_id=payload.user_id,  # Le bot écoute son propre channel
            user_id=self.bot_id  # Avec son propre bot_id
        )

        try:
            await self.subscribe_websocket(chat_sub)
            LOGGER.info("✅ EventSub Chat Subscription créée pour %s", payload.user_id)
        except Exception as e:
            LOGGER.error("❌ Erreur EventSub subscription: %s", e)

    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        """Event message - FIXED selon TWITCHIO3_EVENTSUB_GUIDE_COMPLET

        🎯 Basé sur la doc : traiter les messages correctement même avec same account (bot=broadcaster)
        """
        # Log le message
        LOGGER.info("[%s]: %s", payload.chatter.name, payload.text)
        print(f"💬 {payload.chatter.name}: {payload.text}")

        # 🔍 DEBUG : Vérifier l'état du message
        print(f"🔍 DEBUG: chatter.id={payload.chatter.id}, bot_id={self.bot_id}")
        is_same_account = payload.chatter.id == self.bot_id
        print(f"🔍 Same account (bot=broadcaster): {is_same_account}")

        # 🎯 FIX CRUCIAL (de la doc) :
        # TwitchIO 3.x ignore les messages du bot par défaut
        # MAIS nous on VEUT traiter nos propres commandes si bot=broadcaster !

        # ✅ SOLUTION : Appel direct de process_commands
        # (Pas super().event_message() qui bloque same account)
        print("� Appel process_commands() directement")
        await self.process_commands(payload)
        print("✅ process_commands() terminé")

        # 🧠 MENTIONS : Vérifier si le bot est mentionné
        # Seulement si ce n'est PAS un message du bot lui-même !
        if is_same_account:
            # Le bot ne doit pas répondre à ses propres mentions
            print("🚫 Message du bot lui-même - pas de mention handling")
            return

        # TwitchIO 3.x : utiliser le nom récupéré via API
        bot_name = getattr(self, 'bot_login_name', self.config.get("bot", {}).get("name", "serda_bot")).lower()

        if (f"@{bot_name}" in payload.text.lower() or
                bot_name in payload.text.lower()):
            print("🧠 DEBUG: Mention détectée !")
            try:
                from commands.intelligence_commands import handle_mention_v3
                response = await handle_mention_v3(self, payload)
                if response:
                    # Envoyer la réponse dans le canal - TwitchIO 3.x
                    # payload a un broadcaster, utilisons ça
                    if hasattr(payload, 'broadcaster'):
                        await payload.broadcaster.send_message(
                            sender=self.bot_id,
                            message=response
                        )
                        print(f"🧠 Réponse mention envoyée: {response}")
                    else:
                        print("❌ Pas de broadcaster disponible pour réponse")
                else:
                    print("🧠 Pas de réponse mention (rate limit ou erreur)")
            except Exception as e:
                print(f"❌ Erreur mention response: {e}")


class TestCommands(commands.Component):
    """Component de test - BASÉ SUR LES EXEMPLES OFFICIELS"""

    @commands.command(aliases=["hello", "salut"])
    async def hi(self, ctx) -> None:
        """Commande Hi simple - COMME DANS LES EXEMPLES

        !hi, !hello, !salut
        """
        try:
            # Utilisation de ctx.reply comme dans les exemples
            result = await ctx.reply(f"🧪 TwitchIO 3.x fonctionne! Salut {ctx.chatter.mention}!")

            # TwitchIO 3.x: On a un VRAI résultat !
            print(f"✅ Message envoyé avec succès: {result}")
            LOGGER.info("✅ Hi command result: %s", result)

        except Exception as e:
            print(f"❌ Erreur commande hi: {e}")
            LOGGER.error("❌ Hi command error: %s", e)

    @commands.command()
    async def test3(self, ctx) -> None:
        """Test TwitchIO 3.x feedback

        !test3
        """
        try:
            # Test avec ctx.send
            result = await ctx.send("🔬 Test TwitchIO 3.x - Feedback disponible!")

            print(f"🧪 Test3 result: {result}")
            print(f"🧪 Type: {type(result)}")

            # TwitchIO 3.x donne de vraies infos !
            if hasattr(result, 'id'):
                print(f"📋 Message ID: {result.id}")

        except Exception as e:
            print(f"❌ Erreur test3: {e}")

    @commands.command()
    async def say(self, ctx, *, message: str) -> None:
        """Répète un message - COMME DANS LES EXEMPLES

        !say votre message ici
        """
        # TwitchIO 3.x: Vérifier si l'utilisateur est modérateur ou broadcaster
        is_mod = any(badge.name == "moderator" for badge in ctx.chatter.badges) if ctx.chatter.badges else False
        is_broadcaster = ctx.chatter.id == ctx.broadcaster.id if ctx.broadcaster else False

        if not is_mod and not is_broadcaster:
            await ctx.reply("❌ Commande réservée aux mods!")
            return

        try:
            result = await ctx.send(message)
            print(f"🔊 Say result: {result}")
        except Exception as e:
            await ctx.reply(f"❌ Erreur: {e}")


async def main():
    """Point d'entrée principal - COMME DANS LES EXEMPLES"""

    # Setup logging comme dans les exemples officiels
    twitchio.utils.setup_logging(level=logging.INFO)

    print("🚀 KissBot V3 WORKING - TwitchIO 3.x Official Examples")
    print("=" * 60)

    async def runner() -> None:
        # Utilisation du context manager comme dans les exemples
        async with KissBotV3Working() as bot:
            print("🎯 Bot créé, démarrage...")

            # Pour tester, on peut créer des tokens manuellement
            # Ou utiliser le flow OAuth comme dans les exemples

            await bot.start()

    try:
        await runner()
    except KeyboardInterrupt:
        LOGGER.warning("🛑 Arrêt du bot (Keyboard Interrupt)")
        print("🛑 Bot arrêté manuellement")
    except Exception as e:
        LOGGER.error("❌ Erreur bot: %s", e)
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    # Comme dans TOUS les exemples officiels
    asyncio.run(main())
