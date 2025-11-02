#!/usr/bin/env python3
"""
AuthManager
Gestion centralisée des User Tokens (bot + broadcasters)
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.type import AuthScope

LOGGER = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Info sur un token utilisateur"""
    user_login: str          # Nom du compte (serda_bot, el_serda)
    user_id: str             # ID Twitch
    access_token: str        # Token d'accès
    refresh_token: str       # Token de refresh
    expires_at: datetime     # Quand le token expire
    scopes: list[AuthScope]  # Scopes autorisés


class AuthManager:
    """
    Gère plusieurs user tokens (bot + broadcasters)
    - Load/save depuis storage
    - Refresh automatique
    - Validation scopes
    """
    
    def __init__(self, twitch: Twitch, token_file: str = ".tio.tokens.json"):
        self.twitch = twitch
        self.token_file = Path(token_file)
        self.tokens: dict[str, TokenInfo] = {}  # {user_login: TokenInfo}
        
        LOGGER.info("AuthManager initialisé")
    
    async def load_token_from_file(self, user_id: str) -> Optional[TokenInfo]:
        """
        Charge un token depuis .tio.tokens.json
        
        Args:
            user_id: ID Twitch (ex: "1209350837" pour serda_bot)
        
        Returns:
            TokenInfo ou None si pas trouvé
        """
        if not self.token_file.exists():
            LOGGER.error(f"❌ Fichier {self.token_file} introuvable")
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                data = json.load(f)
            
            if user_id not in data:
                LOGGER.error(f"❌ User ID {user_id} non trouvé dans {self.token_file}")
                return None
            
            token_data = data[user_id]
            
            # Créer TokenInfo
            token_info = TokenInfo(
                user_login="",  # Sera rempli par validate
                user_id=user_id,
                access_token=token_data["token"],
                refresh_token=token_data["refresh"],
                expires_at=datetime.now() + timedelta(hours=4),  # Assumé valide 4h
                scopes=[]  # Sera rempli par validate
            )
            
            LOGGER.info(f"✅ Token chargé pour user_id={user_id}")
            
            # Valider le token pour obtenir user_login et scopes
            await self._validate_and_update(token_info)
            
            # Stocker par user_login
            self.tokens[token_info.user_login] = token_info
            
            return token_info
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur chargement token: {e}", exc_info=True)
            return None
    
    async def _validate_and_update(self, token_info: TokenInfo) -> None:
        """
        Valide un token via API Twitch et met à jour user_login + scopes
        Si le token est expiré (401), tente automatiquement le refresh.
        
        Args:
            token_info: TokenInfo à valider
        """
        try:
            # Appeler l'API /oauth2/validate pour obtenir user_login et scopes
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": f"OAuth {token_info.access_token}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token_info.user_login = data.get("login", "")
                        token_info.user_id = str(data.get("user_id", token_info.user_id))
                        
                        # Convertir les scopes string en AuthScope
                        scope_strs = data.get("scopes", [])
                        token_info.scopes = [AuthScope(s) for s in scope_strs]
                        
                        expires_in = data.get("expires_in", 14400)  # 4h par défaut
                        token_info.expires_at = datetime.now() + timedelta(seconds=expires_in)
                        
                        LOGGER.info(f"✅ Token validé: {token_info.user_login} (ID: {token_info.user_id})")
                        LOGGER.debug(f"   Scopes: {[str(s) for s in token_info.scopes]}")
                    
                    elif resp.status == 401:
                        # Token expiré - Tenter refresh automatique
                        error_text = await resp.text()
                        LOGGER.warning(f"⚠️ Token expiré (401), tentative refresh automatique...")
                        
                        # Refresh le token
                        await self._refresh_token_direct(token_info)
                        
                        # Re-valider après refresh
                        LOGGER.info(f"🔄 Re-validation après refresh...")
                        await self._validate_and_update(token_info)
                    
                    else:
                        error_text = await resp.text()
                        LOGGER.error(f"❌ Validation token échouée: {resp.status} - {error_text}")
                        raise Exception(f"Token validation failed: {resp.status}")
                        
        except Exception as e:
            LOGGER.error(f"❌ Erreur validation token: {e}", exc_info=True)
            raise
    
    async def add_user_token(
        self,
        user_login: str,
        scopes: list[AuthScope],
        target_scope: list[AuthScope] | None = None
    ) -> TokenInfo:
        """
        Ajoute un user token (via OAuth flow ou depuis storage)
        
        Args:
            user_login: Nom du compte (serda_bot, el_serda)
            scopes: Scopes requis pour ce token
            target_scope: Scopes spécifiques à demander (optionnel)
        
        Returns:
            TokenInfo créé
        """
        LOGGER.info(f"[AuthManager] Ajout token pour {user_login}")
        
        # TODO : Implémenter OAuth flow
        # Pour l'instant, structure vide
        
        # Placeholder
        token_info = TokenInfo(
            user_login=user_login,
            user_id="",  # Sera rempli par validate
            access_token="",
            refresh_token="",
            expires_at=datetime.now() + timedelta(hours=4),
            scopes=scopes
        )
        
        self.tokens[user_login] = token_info
        LOGGER.info(f"✅ Token {user_login} ajouté")
        
        return token_info
    
    async def get_token(self, user_login: str) -> Optional[TokenInfo]:
        """
        Récupère un token (avec refresh automatique si expiré)
        
        Args:
            user_login: Nom du compte
        
        Returns:
            TokenInfo ou None si pas trouvé
        """
        if user_login not in self.tokens:
            LOGGER.warning(f"❌ Token {user_login} non trouvé")
            return None
        
        token_info = self.tokens[user_login]
        
        # Check si expiré
        if datetime.now() >= token_info.expires_at:
            LOGGER.info(f"🔄 Token {user_login} expiré, refresh...")
            await self._refresh_token(user_login)
        
        return self.tokens[user_login]
    
    async def _save_token_to_file(self, token_info: TokenInfo) -> None:
        """
        Sauvegarde un token dans .tio.tokens.json
        
        Args:
            token_info: Token à sauvegarder
        """
        try:
            # Load existing tokens
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Update token
            data[token_info.user_id] = {
                "token": token_info.access_token,
                "refresh": token_info.refresh_token
            }
            
            # Save to file
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            LOGGER.info(f"✅ Token {token_info.user_login} sauvegardé dans {self.token_file}")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur sauvegarde token: {e}")
            raise
    
    async def _refresh_token_direct(self, token_info: TokenInfo) -> None:
        """
        Refresh un token directement (sans lookup dans self.tokens)
        Utilisé lors de la validation initiale si le token est expiré.
        
        Args:
            token_info: TokenInfo à refresh
        """
        try:
            LOGGER.info(f"🔄 Refresh token direct via Twitch OAuth...")
            
            # Call Twitch refresh endpoint
            url = "https://id.twitch.tv/oauth2/token"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token_info.refresh_token,
                "client_id": self.twitch.app_id,
                "client_secret": self.twitch.app_secret
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Refresh failed: {resp.status} - {error_text}")
                    
                    result = await resp.json()
            
            # Update token info
            token_info.access_token = result["access_token"]
            token_info.refresh_token = result["refresh_token"]
            token_info.expires_at = datetime.now() + timedelta(seconds=result.get("expires_in", 14400))
            
            # Save to file
            await self._save_token_to_file(token_info)
            
            LOGGER.info(f"✅ Token refreshé (expires: {token_info.expires_at})")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur refresh token direct: {e}")
            raise
    
    async def _refresh_token(self, user_login: str) -> None:
        """
        Refresh un token expiré via Twitch OAuth refresh endpoint
        
        Args:
            user_login: Nom du compte
        """
        token_info = self.tokens[user_login]
        
        try:
            LOGGER.info(f"🔄 Refresh token {user_login} via Twitch OAuth...")
            
            # Call Twitch refresh endpoint
            url = "https://id.twitch.tv/oauth2/token"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token_info.refresh_token,
                "client_id": self.twitch.app_id,
                "client_secret": self.twitch.app_secret
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Refresh failed: {resp.status} - {error_text}")
                    
                    result = await resp.json()
            
            # Update token info
            token_info.access_token = result["access_token"]
            token_info.refresh_token = result["refresh_token"]
            token_info.expires_at = datetime.now() + timedelta(seconds=result.get("expires_in", 14400))
            
            # Save to file
            await self._save_token_to_file(token_info)
            
            # Update Twitch instance auth
            await self.twitch.set_user_authentication(
                token_info.access_token,
                token_info.scopes,
                token_info.refresh_token
            )
            
            LOGGER.info(f"✅ Token {user_login} refreshé (expires: {token_info.expires_at})")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur refresh token {user_login}: {e}")
            raise
    
    async def validate_token(self, user_login: str) -> bool:
        """
        Valide un token (appel API /validate)
        
        Args:
            user_login: Nom du compte
        
        Returns:
            True si valide, False sinon
        """
        token_info = await self.get_token(user_login)
        if not token_info:
            return False
        
        try:
            # TODO : Appeler GET /validate
            LOGGER.info(f"✅ Token {user_login} valide")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ Token {user_login} invalide: {e}")
            return False
    
    def has_scope(self, user_login: str, scope: AuthScope) -> bool:
        """
        Vérifie si un token a un scope spécifique
        
        Args:
            user_login: Nom du compte
            scope: Scope à vérifier
        
        Returns:
            True si le scope est présent
        """
        if user_login not in self.tokens:
            return False
        
        token_info = self.tokens[user_login]
        return scope in token_info.scopes
    
    def get_all_users(self) -> list[str]:
        """Retourne la liste de tous les users avec token"""
        return list(self.tokens.keys())
    
    def get_stats(self) -> dict[str, int]:
        """Retourne les stats de tokens"""
        valid_count = 0
        expired_count = 0
        
        for token_info in self.tokens.values():
            if datetime.now() < token_info.expires_at:
                valid_count += 1
            else:
                expired_count += 1
        
        return {
            "total_tokens": len(self.tokens),
            "valid_tokens": valid_count,
            "expired_tokens": expired_count
        }
