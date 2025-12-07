"""
Registre central des commandes KissBot.

Ce module mappe les commandes (ex: "!ask") vers leurs handlers dans modules/classic_commands/.
Le MessageHandler utilise ce registre pour dispatcher les commandes.

Architecture:
    message_handler.py → command_registry.py → modules/classic_commands/{category}/handler.py
"""
import logging
from typing import Callable, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

LOGGER = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Catégories de commandes (permissions)"""
    USER = "user"           # Tout le monde
    MOD = "mod"             # Modérateurs
    ADMIN = "admin"         # Admins / Broadcaster
    BOT = "bot"             # Commandes système


@dataclass
class CommandInfo:
    """Métadonnées d'une commande"""
    name: str                           # Nom sans le ! (ex: "ask")
    handler: Callable                   # Fonction async handler
    category: CommandCategory           # Permissions requises
    description: str = ""               # Description pour !help
    cooldown: float = 0.0               # Cooldown en secondes
    enabled: bool = True                # Commande active ?
    aliases: tuple = ()                 # Alias (ex: ("a",) pour !a → !ask)


class CommandRegistry:
    """
    Registre singleton des commandes.
    
    Usage:
        registry = CommandRegistry()
        registry.register("ask", handle_ask, CommandCategory.USER, cooldown=60)
        
        handler = registry.get("ask")
        if handler:
            await handler.handler(msg, args)
    """
    _instance: Optional["CommandRegistry"] = None
    
    def __new__(cls) -> "CommandRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._commands: Dict[str, CommandInfo] = {}
            cls._instance._initialized = False
        return cls._instance
    
    def register(
        self,
        name: str,
        handler: Callable,
        category: CommandCategory = CommandCategory.USER,
        description: str = "",
        cooldown: float = 0.0,
        aliases: tuple = ()
    ) -> None:
        """Enregistre une commande"""
        cmd_info = CommandInfo(
            name=name,
            handler=handler,
            category=category,
            description=description,
            cooldown=cooldown,
            aliases=aliases
        )
        
        # Enregistrer le nom principal
        self._commands[name.lower()] = cmd_info
        
        # Enregistrer les alias
        for alias in aliases:
            self._commands[alias.lower()] = cmd_info
        
        LOGGER.debug(f"📝 Registered command: !{name} ({category.value})")
    
    def get(self, name: str) -> Optional[CommandInfo]:
        """Récupère une commande par son nom (sans le !)"""
        return self._commands.get(name.lower())
    
    def has(self, name: str) -> bool:
        """Vérifie si une commande existe"""
        return name.lower() in self._commands
    
    def list_commands(self, category: Optional[CommandCategory] = None) -> list[CommandInfo]:
        """Liste les commandes (optionnel: par catégorie)"""
        # Dédupliquer (alias pointent vers même CommandInfo)
        seen = set()
        commands = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                if category is None or cmd.category == category:
                    commands.append(cmd)
                    seen.add(cmd.name)
        return sorted(commands, key=lambda c: c.name)
    
    def initialize(self) -> None:
        """Charge toutes les commandes depuis modules/classic_commands/"""
        if self._initialized:
            return
        
        LOGGER.info("📦 Initializing command registry...")
        
        # Import et enregistrement des commandes
        self._register_user_commands()
        self._register_mod_commands()
        self._register_admin_commands()
        self._register_bot_commands()
        
        self._initialized = True
        LOGGER.info(f"✅ Command registry initialized: {len(self.list_commands())} commands")
    
    def _register_user_commands(self) -> None:
        """Enregistre les commandes utilisateur"""
        try:
            # Test command (debug)
            from modules.classic_commands.user_commands.test import handle_test
            self.register("test", handle_test, CommandCategory.USER,
                         description="Send a test message (debug EventSub)", cooldown=5.0)
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load test command: {e}")
        
        try:
            # Intelligence (ask, joke)
            from modules.classic_commands.user_commands.intelligence import handle_ask, handle_joke
            self.register("ask", handle_ask, CommandCategory.USER, 
                         description="Pose une question à l'IA", cooldown=60.0)
            self.register("joke", handle_joke, CommandCategory.USER,
                         description="Le bot raconte une blague", cooldown=30.0)
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load intelligence commands: {e}")
        
        try:
            # Wiki
            from modules.classic_commands.user_commands.wiki_basic import handle_wiki
            self.register("wiki", handle_wiki, CommandCategory.USER,
                         description="Recherche Wikipedia", cooldown=10.0)
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load wiki commands: {e}")
        
        try:
            # Traduction
            from modules.classic_commands.user_commands.trad import handle_trad
            self.register("trad", handle_trad, CommandCategory.USER,
                         description="Traduit un texte", cooldown=10.0)
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load trad commands: {e}")
        
        try:
            # Game lookup
            from modules.classic_commands.user_commands.game import handle_gi, handle_gs, handle_gc
            self.register("gi", handle_gi, CommandCategory.USER,
                         description="Info sur un jeu (IGDB)", cooldown=5.0)
            self.register("gs", handle_gs, CommandCategory.USER,
                         description="Info sur un jeu (Steam)", cooldown=5.0)
            self.register("gc", handle_gc, CommandCategory.USER,
                         description="Catégorie du jeu actuel", cooldown=5.0)
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load game commands: {e}")
        
        try:
            # KissAnniv
            from modules.classic_commands.user_commands.kissanniv import cmd_kissanniv
            self.register("kissanniv", cmd_kissanniv, CommandCategory.USER,
                         description="Anniversaires des devs KissBot")
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load kissanniv command: {e}")
    
    def _register_mod_commands(self) -> None:
        """Enregistre les commandes modérateur"""
        try:
            from modules.classic_commands.mod_commands.debug_eventsub import handle_debug_eventsub, handle_debug_send
            self.register("debug_eventsub", handle_debug_eventsub, CommandCategory.MOD,
                         description="Display EventSub session & metrics (mods only)")
            self.register("debug_send", handle_debug_send, CommandCategory.MOD,
                         description="Test message send via EventSub (mods only)")
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load debug commands: {e}")
        
        try:
            from modules.classic_commands.mod_commands.devlist import handle_adddev, handle_rmdev, handle_listdevs
            self.register("adddev", handle_adddev, CommandCategory.MOD,
                         description="Ajoute un développeur")
            self.register("rmdev", handle_rmdev, CommandCategory.MOD,
                         description="Retire un développeur")
            self.register("listdevs", handle_listdevs, CommandCategory.MOD,
                         description="Liste les développeurs")
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load mod commands: {e}")
    
    def _register_admin_commands(self) -> None:
        """Enregistre les commandes admin"""
        # TODO: Migrer les commandes admin
        pass
    
    def _register_bot_commands(self) -> None:
        """Enregistre les commandes système du bot"""
        try:
            from modules.classic_commands.user_commands.system import handle_ping, handle_uptime, handle_stats
            self.register("ping", handle_ping, CommandCategory.BOT,
                         description="Vérifie que le bot est en ligne")
            self.register("uptime", handle_uptime, CommandCategory.BOT,
                         description="Temps de fonctionnement du bot")
            self.register("stats", handle_stats, CommandCategory.BOT,
                         description="Statistiques du bot")
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load bot commands: {e}")
        
        try:
            from modules.classic_commands.broadcaster_commands.broadcast import cmd_kisscharity, cmd_kbupdate
            self.register("kisscharity", cmd_kisscharity, CommandCategory.BOT,
                         description="Annonce charity")
            self.register("kbupdate", cmd_kbupdate, CommandCategory.BOT,
                         description="Annonce mise à jour")
        except ImportError as e:
            LOGGER.warning(f"⚠️ Could not load broadcast commands: {e}")


# Singleton global
_registry: Optional[CommandRegistry] = None

def get_command_registry() -> CommandRegistry:
    """Récupère le registre singleton"""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry
