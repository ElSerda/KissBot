#!/usr/bin/env python3
"""
Translation Backend - Auto-translate non-French messages
Uses deep-translator (Google Translate + language detection)
"""

import logging
from typing import Optional, Tuple
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class TranslationService:
    """Service de traduction avec détection automatique de langue"""
    
    def __init__(self):
        self.translator = GoogleTranslator(source='auto', target='fr')
        self._cache = {}  # Cache simple {text: (lang, translation)}
        logger.info("🌍 TranslationService initialized (deep-translator)")
    
    async def detect_language(self, text: str) -> Optional[str]:
        """
        Détecte la langue du texte
        Returns: code langue ISO (en, fr, es, etc.) ou None si erreur
        """
        try:
            loop = asyncio.get_event_loop()
            lang_code = await loop.run_in_executor(None, detect, text)
            logger.debug(f"🔍 Detected language: {lang_code}")
            return lang_code
        except LangDetectException as e:
            logger.error(f"❌ Language detection failed: {e}")
            return None
    
    async def translate(
        self, 
        text: str, 
        target_lang: str = 'fr',
        source_lang: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Traduit le texte vers la langue cible
        
        Args:
            text: Texte à traduire
            target_lang: Langue cible (défaut: fr)
            source_lang: Langue source (auto-detect si None)
        
        Returns:
            Tuple (langue_source, texte_traduit) ou None si erreur
        """
        try:
            # Check cache
            cache_key = f"{text}:{target_lang}"
            if cache_key in self._cache:
                logger.debug(f"💾 Translation cache HIT")
                return self._cache[cache_key]
            
            # Detect source language first
            detected_lang = source_lang
            if not detected_lang:
                detected_lang = await self.detect_language(text)
                if not detected_lang:
                    return None
            
            # Skip translation if already target language
            if detected_lang == target_lang:
                logger.debug(f"⏭️ Already in target language: {target_lang}")
                return (detected_lang, text)
            
            # Translate
            loop = asyncio.get_event_loop()
            translator = GoogleTranslator(source=detected_lang, target=target_lang)
            translation = await loop.run_in_executor(None, translator.translate, text)
            
            # Cache result
            self._cache[cache_key] = (detected_lang, translation)
            
            logger.info(f"✅ Translated {detected_lang} → {target_lang}: {text[:50]}...")
            return (detected_lang, translation)
            
        except Exception as e:
            logger.error(f"❌ Translation failed: {e}")
            return None
    
    async def is_french(self, text: str) -> bool:
        """
        Vérifie si le texte est en français
        Returns: True si français, False sinon
        """
        lang = await self.detect_language(text)
        return lang == 'fr' if lang else True  # Par défaut français si erreur
    
    def get_language_name(self, lang_code: str) -> str:
        """Retourne le nom complet de la langue"""
        lang_names = {
            'en': 'English',
            'fr': 'Français',
            'es': 'Español',
            'de': 'Deutsch',
            'it': 'Italiano',
            'pt': 'Português',
            'ru': 'Русский',
            'ja': '日本語',
            'zh-cn': '中文',
            'ko': '한국어',
            'ar': 'العربية',
            'nl': 'Nederlands',
            'pl': 'Polski',
            'tr': 'Türkçe',
            'sv': 'Svenska',
            'da': 'Dansk',
            'no': 'Norsk',
            'fi': 'Suomi'
        }
        return lang_names.get(lang_code, lang_code.upper())


class DevWhitelist:
    """Gestion de la whitelist des développeurs pour auto-traduction"""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
        self._whitelist = set()  # Cache en mémoire
        self._load_whitelist()
        logger.info("👥 DevWhitelist initialized")
    
    def _load_whitelist(self):
        """Charge la whitelist depuis la DB"""
        if not self.db:
            return
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT username FROM dev_whitelist
                    WHERE enabled = 1
                """)
                self._whitelist = {row[0].lower() for row in cursor.fetchall()}
                logger.info(f"📋 Loaded {len(self._whitelist)} devs from whitelist")
        except Exception as e:
            logger.error(f"❌ Failed to load whitelist: {e}")
    
    def add_dev(self, username: str) -> bool:
        """
        Ajoute un dev à la whitelist
        Returns: True si ajouté, False si déjà présent ou erreur
        """
        username_lower = username.lower()
        
        if username_lower in self._whitelist:
            logger.debug(f"ℹ️ {username} already in whitelist")
            return False
        
        if not self.db:
            self._whitelist.add(username_lower)
            return True
        
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO dev_whitelist (username, added_at, enabled)
                    VALUES (?, datetime('now'), 1)
                    ON CONFLICT(username) DO UPDATE SET enabled = 1
                """, (username_lower,))
                conn.commit()
            
            self._whitelist.add(username_lower)
            logger.info(f"✅ Added {username} to dev whitelist")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add {username} to whitelist: {e}")
            return False
    
    def remove_dev(self, username: str) -> bool:
        """
        Retire un dev de la whitelist
        Returns: True si retiré, False si absent ou erreur
        """
        username_lower = username.lower()
        
        if username_lower not in self._whitelist:
            logger.debug(f"ℹ️ {username} not in whitelist")
            return False
        
        if not self.db:
            self._whitelist.discard(username_lower)
            return True
        
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE dev_whitelist
                    SET enabled = 0
                    WHERE username = ?
                """, (username_lower,))
                conn.commit()
            
            self._whitelist.discard(username_lower)
            logger.info(f"✅ Removed {username} from dev whitelist")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to remove {username} from whitelist: {e}")
            return False
    
    def is_dev(self, username: str) -> bool:
        """Vérifie si un user est dans la whitelist"""
        return username.lower() in self._whitelist
    
    def list_devs(self) -> list[str]:
        """Retourne la liste des devs whitelistés"""
        return sorted(self._whitelist)


# Singleton instances
_translator = None
_dev_whitelist = None


def get_translator() -> TranslationService:
    """Retourne l'instance singleton du traducteur"""
    global _translator
    if _translator is None:
        _translator = TranslationService()
    return _translator


def get_dev_whitelist(db_manager=None) -> DevWhitelist:
    """Retourne l'instance singleton de la whitelist"""
    global _dev_whitelist
    if _dev_whitelist is None:
        _dev_whitelist = DevWhitelist(db_manager)
    return _dev_whitelist
