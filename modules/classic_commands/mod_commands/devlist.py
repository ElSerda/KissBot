#!/usr/bin/env python3
"""
Commandes de gestion de la whitelist dev
!adddev <username> - Ajoute un dev (mod/broadcaster only)
!rmdev <username> - Retire un dev (mod/broadcaster only)
!listdevs - Liste les devs whitelistés
"""

import logging
from twitchAPI.chat import ChatCommand
from backends.translator import get_dev_whitelist

LOGGER = logging.getLogger(__name__)


async def handle_adddev(bot, cmd: ChatCommand):
    """
    !adddev <username> - Ajoute un développeur à la whitelist auto-trad
    
    Mod/Broadcaster only
    """
    # Check permissions
    if not (cmd.user.mod or cmd.room.name == cmd.user.name.lower()):
        return  # Silently ignore
    
    if not cmd.parameter:
        await cmd.reply(f"@{cmd.user.name} Usage: !adddev <username>")
        return
    
    username = cmd.parameter.strip().lstrip('@')
    whitelist = get_dev_whitelist()
    
    added = whitelist.add_dev(username)
    
    if added:
        await cmd.reply(
            f"@{cmd.user.name} ✅ {username} added to dev whitelist (auto-trad enabled)"
        )
        LOGGER.info(f"👥 {cmd.user.name} added {username} to dev whitelist")
    else:
        await cmd.reply(
            f"@{cmd.user.name} ℹ️ {username} already in dev whitelist"
        )


async def handle_rmdev(bot, cmd: ChatCommand):
    """
    !rmdev <username> - Retire un développeur de la whitelist
    
    Mod/Broadcaster only
    """
    # Check permissions
    if not (cmd.user.mod or cmd.room.name == cmd.user.name.lower()):
        return  # Silently ignore
    
    if not cmd.parameter:
        await cmd.reply(f"@{cmd.user.name} Usage: !rmdev <username>")
        return
    
    username = cmd.parameter.strip().lstrip('@')
    whitelist = get_dev_whitelist()
    
    removed = whitelist.remove_dev(username)
    
    if removed:
        await cmd.reply(
            f"@{cmd.user.name} ✅ {username} removed from dev whitelist"
        )
        LOGGER.info(f"👥 {cmd.user.name} removed {username} from dev whitelist")
    else:
        await cmd.reply(
            f"@{cmd.user.name} ℹ️ {username} not in dev whitelist"
        )


async def handle_listdevs(bot, cmd: ChatCommand):
    """
    !listdevs - Liste les développeurs whitelistés pour auto-trad
    
    Public command
    """
    whitelist = get_dev_whitelist()
    devs = whitelist.list_devs()
    
    if not devs:
        await cmd.reply(f"@{cmd.user.name} ℹ️ No devs in whitelist")
        return
    
    dev_list = ", ".join(devs)
    await cmd.reply(
        f"@{cmd.user.name} 👥 Devs (auto-trad): {dev_list}"
    )
