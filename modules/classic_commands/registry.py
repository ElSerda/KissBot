"""
Registry central pour toutes les commandes du bot.
Organisation par niveau de permission : bot, user, mod, admin.
"""
import logging
from twitchAPI.chat import Chat

LOGGER = logging.getLogger(__name__)


def register_bot_commands(bot, chat: Chat):
    """
    Commandes système du bot (accessibles à tous, mais gérées par le bot).
    """
    from .bot_commands.system import handle_ping, handle_uptime
    
    # Wrapper async pour chaque commande
    async def cmd_ping(cmd):
        await handle_ping(bot, cmd)
    
    async def cmd_uptime(cmd):
        await handle_uptime(bot, cmd)
    
    chat.register_command('ping', cmd_ping)
    chat.register_command('uptime', cmd_uptime)
    
    LOGGER.info("✅ Bot commands registered: ping, uptime")


def register_user_commands(bot, chat: Chat):
    """
    Commandes utilisateur (accessibles à tous).
    """
    from .user_commands.game import handle_gc, handle_gi
    from .user_commands.intelligence import handle_ask, handle_joke
    from .user_commands.wiki import handle_wiki
    from .user_commands.kissgit import handle_kissgit
    from .user_commands.kofi import handle_kbkofi
    
    # Wrapper async pour chaque commande
    async def cmd_gc(cmd):
        await handle_gc(bot, cmd)
    
    async def cmd_gi(cmd):
        await handle_gi(bot, cmd)
    
    async def cmd_ask(cmd):
        await handle_ask(bot, cmd)
    
    async def cmd_joke(cmd):
        await handle_joke(bot, cmd)
    
    async def cmd_wiki(cmd):
        await handle_wiki(bot, cmd)
    
    async def cmd_kissgit(cmd):
        await handle_kissgit(bot, cmd)
    
    async def cmd_kbkofi(cmd):
        await handle_kbkofi(bot, cmd)
    
    chat.register_command('gc', cmd_gc)
    chat.register_command('gamecategory', cmd_gc)
    chat.register_command('gi', cmd_gi)
    chat.register_command('gameinfo', cmd_gi)
    chat.register_command('ask', cmd_ask)
    chat.register_command('joke', cmd_joke)
    chat.register_command('wiki', cmd_wiki)
    chat.register_command('kissgit', cmd_kissgit)
    chat.register_command('kbkofi', cmd_kbkofi)
    
    LOGGER.info("✅ User commands registered: gc, gi, ask, joke, wiki, kissgit, kbkofi")


def register_mod_commands(bot, chat: Chat):
    """
    Commandes modérateur (permissions requises).
    
    Note: Les commandes banword sont gérées directement dans MessageHandler
    via le pattern !kbbanword, !kbunbanword, !kbbanwords
    """
    # Banword commands are now handled in message_handler.py
    # following the same pattern as !adddev, !rmdev, !listdevs
    
    LOGGER.info("✅ Mod commands registered: (handled in MessageHandler)")


def register_admin_commands(bot, chat: Chat):
    """
    Commandes admin (broadcaster uniquement).
    """
    # Wrapper pour vérifier broadcaster
    async def broadcaster_only(handler):
        async def wrapper(cmd):
            # Check si broadcaster (user.id == room.room_id)
            if str(cmd.user.id) != str(cmd.room.room_id):
                await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Commande réservée au broadcaster")
                return
            await handler(bot, cmd)
        return wrapper
    
    # À implémenter: ban, vip, config, etc.
    # from .admin_commands.administration import handle_ban, handle_vip
    # chat.register_command('ban', broadcaster_only(handle_ban))
    
    LOGGER.info("✅ Admin commands registered: (none yet)")


def register_all_commands(bot, chat: Chat):
    """
    Enregistre TOUTES les commandes du bot.
    Appeler cette fonction unique dans bot.py pour tout enregistrer.
    """
    LOGGER.info("🎮 Enregistrement de toutes les commandes...")
    
    register_bot_commands(bot, chat)
    register_user_commands(bot, chat)
    register_mod_commands(bot, chat)
    register_admin_commands(bot, chat)
    
    LOGGER.info("✅ Toutes les commandes enregistrées !")
