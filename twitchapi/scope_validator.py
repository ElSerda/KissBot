"""
🔐 Scope Validator - Validate OAuth token scopes and broadcaster_id

Ensures bot has required permissions before connecting.
Provides clear feedback for missing scopes.
"""

import logging
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class ScopeRequirement:
    """Required scopes for bot features."""
    name: str
    scopes: Set[str]
    description: str
    critical: bool  # Bot cannot work without these


# Feature -> Required scopes mapping
FEATURE_SCOPES = {
    "chat": ScopeRequirement(
        name="Chat Commands",
        scopes={"chat:read", "chat:edit"},
        description="Lire et envoyer des messages dans le chat",
        critical=True  # Sans ça, le bot est inutile
    ),
    "eventsub_stream": ScopeRequirement(
        name="Stream Events (EventSub)",
        scopes={"channel:read:stream_key"},
        description="Notifications stream online/offline",
        critical=False
    ),
    "eventsub_follow": ScopeRequirement(
        name="Follow Events (EventSub)",
        scopes={"moderator:read:followers"},
        description="Notifications de nouveaux followers",
        critical=False
    ),
    "eventsub_raid": ScopeRequirement(
        name="Raid Events (EventSub)",
        scopes={"channel:manage:raids"},
        description="Notifications de raids",
        critical=False
    ),
    "moderation": ScopeRequirement(
        name="Moderation",
        scopes={"moderator:manage:banned_users", "moderator:manage:chat_messages"},
        description="Timeout/ban users, supprimer messages",
        critical=False
    ),
}


class ScopeValidator:
    """Validate OAuth token scopes and provide user feedback."""
    
    @staticmethod
    async def validate_token(
        token: str,
        client_id: str
    ) -> Dict[str, any]:
        """
        Validate OAuth token and return scope analysis.
        
        Args:
            token: OAuth token (with or without 'oauth:' prefix)
            client_id: Twitch client ID for API calls
        
        Returns:
            {
                "valid": bool,
                "scopes": List[str],
                "missing_critical": List[str],
                "missing_optional": List[str],
                "available_features": List[str],
                "unavailable_features": List[str],
                "warnings": List[str],
                "user_id": Optional[str],
                "login": Optional[str]
            }
        """
        # Clean token (remove oauth: prefix if present)
        clean_token = token.replace('oauth:', '')
        
        # 1. Validate token avec Twitch API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": f"OAuth {clean_token}"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Token validation failed: {response.status_code}")
                    return {
                        "valid": False,
                        "error": "Token invalide ou expiré",
                        "scopes": [],
                        "missing_critical": [],
                        "missing_optional": [],
                        "available_features": [],
                        "unavailable_features": list(FEATURE_SCOPES.keys()),
                        "warnings": ["❌ Token invalide. Reconnecte-toi via Twitch OAuth."],
                        "user_id": None,
                        "login": None
                    }
                
                data = response.json()
                user_scopes = set(data.get("scopes", []))
                user_id = data.get("user_id")
                login = data.get("login")
                
                logger.info(f"✅ Token validé pour user: {login} (ID: {user_id})")
                logger.debug(f"Scopes présents: {user_scopes}")
        
        except Exception as e:
            logger.error(f"Erreur validation token: {e}")
            return {
                "valid": False,
                "error": f"Erreur réseau: {e}",
                "scopes": [],
                "missing_critical": [],
                "missing_optional": [],
                "available_features": [],
                "unavailable_features": list(FEATURE_SCOPES.keys()),
                "warnings": [f"❌ Erreur validation: {e}"],
                "user_id": None,
                "login": None
            }
        
        # 2. Analyze scopes
        result = {
            "valid": True,
            "scopes": list(user_scopes),
            "missing_critical": [],
            "missing_optional": [],
            "available_features": [],
            "unavailable_features": [],
            "warnings": [],
            "user_id": user_id,
            "login": login
        }
        
        # 3. Check each feature
        for feature_key, requirement in FEATURE_SCOPES.items():
            missing = requirement.scopes - user_scopes
            
            if not missing:
                # Feature available
                result["available_features"].append(feature_key)
                logger.debug(f"✅ Feature '{requirement.name}' disponible")
            else:
                # Feature unavailable
                result["unavailable_features"].append(feature_key)
                
                if requirement.critical:
                    result["missing_critical"].extend(missing)
                    result["warnings"].append(
                        f"❌ CRITIQUE : '{requirement.name}' nécessite {list(missing)}"
                    )
                    logger.error(f"❌ Scopes critiques manquants: {missing}")
                else:
                    result["missing_optional"].extend(missing)
                    result["warnings"].append(
                        f"⚠️  OPTIONNEL : '{requirement.name}' nécessite {list(missing)}"
                    )
                    # Don't log individual missing optional scopes (too verbose)
        
        # 4. Final validation
        if result["missing_critical"]:
            result["valid"] = False
            result["warnings"].insert(0, 
                "🚨 Le bot ne peut PAS démarrer sans les scopes critiques !"
            )
            logger.critical("🚨 SCOPES CRITIQUES MANQUANTS - Bot ne peut pas démarrer")
        elif result["missing_optional"]:
            result["warnings"].insert(0,
                "✅ Bot opérationnel, mais certaines features sont désactivées."
            )
            logger.info("✅ Bot opérationnel avec features limitées")
        else:
            result["warnings"].insert(0,
                "🎉 Tous les scopes sont présents ! Toutes les features disponibles."
            )
            logger.info("🎉 Tous les scopes présents")
        
        return result
    
    @staticmethod
    async def fetch_broadcaster_id(
        channel_name: str,
        client_id: str,
        token: str
    ) -> Optional[str]:
        """
        Auto-fetch broadcaster_id from channel name.
        
        Args:
            channel_name: Twitch channel name (login)
            client_id: Twitch client ID
            token: OAuth token (with or without 'oauth:' prefix)
        
        Returns:
            broadcaster_id (str) or None if not found
        """
        # Clean token
        clean_token = token.replace('oauth:', '')
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.twitch.tv/helix/users",
                    params={"login": channel_name},
                    headers={
                        "Authorization": f"Bearer {clean_token}",
                        "Client-Id": client_id
                    }
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"❌ Fetch broadcaster_id failed: {response.status_code}"
                    )
                    return None
                
                data = response.json()
                users = data.get("data", [])
                
                if not users:
                    logger.error(f"❌ Channel '{channel_name}' not found")
                    return None
                
                broadcaster_id = users[0]["id"]
                display_name = users[0]["display_name"]
                
                logger.info(
                    f"🎯 Auto-detected broadcaster_id for '{channel_name}': "
                    f"{broadcaster_id} ({display_name})"
                )
                
                return broadcaster_id
        
        except Exception as e:
            logger.error(f"❌ Erreur fetch broadcaster_id: {e}")
            return None
    
    @staticmethod
    def print_scope_report(analysis: Dict[str, any]) -> None:
        """
        Print a formatted scope analysis report to console.
        
        Args:
            analysis: Result from validate_token()
        """
        print("\n" + "="*60)
        print("🔐 ANALYSE DES SCOPES OAUTH")
        print("="*60)
        
        if analysis.get("user_id"):
            print(f"👤 User: {analysis['login']} (ID: {analysis['user_id']})")
        
        print(f"\n📊 Scopes présents ({len(analysis['scopes'])}):")
        for scope in sorted(analysis['scopes']):
            print(f"  ✅ {scope}")
        
        if analysis['available_features']:
            print(f"\n✅ Features disponibles ({len(analysis['available_features'])}):")
            for feature_key in analysis['available_features']:
                req = FEATURE_SCOPES[feature_key]
                print(f"  ✅ {req.name}: {req.description}")
        
        if analysis['unavailable_features']:
            print(f"\n⚠️  Features indisponibles ({len(analysis['unavailable_features'])}):")
            for feature_key in analysis['unavailable_features']:
                req = FEATURE_SCOPES[feature_key]
                critical_marker = "❌ CRITIQUE" if req.critical else "⚠️  OPTIONNEL"
                print(f"  {critical_marker} {req.name}: {req.description}")
                missing = req.scopes - set(analysis['scopes'])
                print(f"      Manquant: {list(missing)}")
        
        print("\n📋 Résumé:")
        for warning in analysis['warnings']:
            print(f"  {warning}")
        
        print("="*60 + "\n")
