#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KissBot - Database Manager

Copyright (c) 2025 Sεrda - Tous droits réservés
License: Voir LICENSE et EULA_FR.md
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

from database.crypto import TokenEncryptor

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestionnaire principal de la base de données.
    
    Gère :
    - Utilisateurs Twitch et bots
    - Tokens OAuth chiffrés
    - Instances de bot
    - Logs d'audit
    - Configuration système
    """
    
    def __init__(self, db_path: str = "kissbot.db", key_file: str = ".kissbot.key"):
        """
        Initialise le gestionnaire de base de données.
        
        Args:
            db_path: Chemin vers le fichier SQLite
            key_file: Chemin vers la clé de chiffrement
        """
        self.db_path = db_path
        self.encryptor = TokenEncryptor(key_file=key_file)
        
        # Vérifier que la DB existe
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database file not found: {db_path}\n"
                f"Run: python database/init_db.py --db {db_path}"
            )
        
        # Configurer SQLite
        self._setup_connection()
        logger.info(f"DatabaseManager initialized: {db_path}")
    
    def _setup_connection(self):
        """Configure les paramètres SQLite."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA synchronous = NORMAL")
    
    @contextmanager
    def _get_connection(self):
        """
        Context manager pour les connexions SQLite.
        
        Usage:
            with manager._get_connection() as conn:
                cursor = conn.execute(...)
        """
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    # ==================== USERS ====================
    
    def get_user(self, twitch_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un utilisateur par son Twitch user ID.
        
        Args:
            twitch_user_id: ID Twitch de l'utilisateur
        
        Returns:
            Dict avec les données utilisateur ou None si introuvable
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE twitch_user_id = ?",
                (twitch_user_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_user_by_login(self, twitch_login: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un utilisateur par son login Twitch.
        
        Args:
            twitch_login: Login Twitch (nom en minuscules)
        
        Returns:
            Dict avec les données utilisateur ou None si introuvable
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE twitch_login = ?",
                (twitch_login.lower(),)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def create_user(self, twitch_user_id: str, twitch_login: str, 
                   display_name: str, is_bot: bool = False) -> int:
        """
        Crée un nouvel utilisateur.
        
        Args:
            twitch_user_id: ID Twitch de l'utilisateur
            twitch_login: Login Twitch (sera converti en minuscules)
            display_name: Nom affiché sur Twitch
            is_bot: True si c'est un compte bot
        
        Returns:
            L'ID de l'utilisateur créé
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (twitch_user_id, twitch_login, display_name, is_bot)
                VALUES (?, ?, ?, ?)
                """,
                (twitch_user_id, twitch_login.lower(), display_name, is_bot)
            )
            user_id = cursor.lastrowid
            
            # Log audit
            self._log_audit(
                conn=conn,
                event_type="user_created",
                user_id=user_id,
                details={"twitch_user_id": twitch_user_id, "twitch_login": twitch_login}
            )
            
            logger.info(f"User created: {twitch_login} (ID: {user_id})")
            return user_id
    
    def update_user(self, user_id: int, display_name: Optional[str] = None,
                   is_bot: Optional[bool] = None) -> bool:
        """
        Met à jour les données d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur en base
            display_name: Nouveau nom affiché (optionnel)
            is_bot: Nouveau statut bot (optionnel)
        
        Returns:
            True si modifié, False sinon
        """
        updates = []
        params = []
        
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        
        if is_bot is not None:
            updates.append("is_bot = ?")
            params.append(is_bot)
        
        if not updates:
            return False
        
        params.append(user_id)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                params
            )
            
            if cursor.rowcount > 0:
                self._log_audit(
                    conn=conn,
                    event_type="user_updated",
                    user_id=user_id,
                    details={"display_name": display_name, "is_bot": is_bot}
                )
                logger.info(f"User updated: ID {user_id}")
                return True
            
            return False
    
    # ==================== OAUTH TOKENS ====================
    
    def get_tokens(self, user_id: int, token_type: str = 'bot') -> Optional[Dict]:
        """
        Récupère et déchiffre les tokens OAuth d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur en base
            token_type: Type de token ('bot' ou 'broadcaster')
        
        Returns:
            Dict avec access_token, refresh_token, expires_at, etc.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM oauth_tokens WHERE user_id = ? AND token_type = ?",
                (user_id, token_type)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            data = dict(row)
            
            # Déchiffrer les tokens
            try:
                data['access_token'] = self.encryptor.decrypt(data['access_token_encrypted'])
                data['refresh_token'] = self.encryptor.decrypt(data['refresh_token_encrypted'])
                del data['access_token_encrypted']
                del data['refresh_token_encrypted']
            except Exception as e:
                logger.error(f"Failed to decrypt tokens for user {user_id} (type={token_type}): {e}")
                return None
            
            return data
    
    def store_tokens(self, user_id: int, access_token: str, refresh_token: str,
                    expires_in: int, scopes: Optional[List[str]] = None, 
                    token_type: str = 'bot', status: str = 'valid') -> bool:
        """
        Stocke ou met à jour les tokens OAuth d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur en base
            access_token: Token d'accès OAuth
            refresh_token: Token de rafraîchissement
            expires_in: Durée de validité en secondes
            scopes: Liste des scopes OAuth (obligatoire en v4.0.1)
            token_type: Type de token ('bot' ou 'broadcaster')
            status: Statut du token ('valid', 'expired', 'revoked')
        
        Returns:
            True si succès
        """
        # Chiffrer les tokens
        access_encrypted = self.encryptor.encrypt(access_token)
        refresh_encrypted = self.encryptor.encrypt(refresh_token)
        
        # Calculer la date d'expiration
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Sérialiser les scopes (requis en v4.0.1)
        if scopes is None:
            scopes = []  # Liste vide si pas fourni (pour compatibilité)
        scopes_json = json.dumps(scopes)
        
        # Timestamp UNIX du refresh
        last_refresh = int(datetime.now().timestamp())
        
        with self._get_connection() as conn:
            # Vérifier si des tokens existent déjà pour ce type
            cursor = conn.execute(
                "SELECT id FROM oauth_tokens WHERE user_id = ? AND token_type = ?",
                (user_id, token_type)
            )
            existing = cursor.fetchone()
            
            if existing:
                # UPDATE
                conn.execute(
                    """
                    UPDATE oauth_tokens
                    SET access_token_encrypted = ?,
                        refresh_token_encrypted = ?,
                        expires_at = ?,
                        scopes = ?,
                        last_refresh = ?,
                        status = ?,
                        needs_reauth = 0,
                        refresh_failures = 0
                    WHERE user_id = ? AND token_type = ?
                    """,
                    (access_encrypted, refresh_encrypted, expires_at, scopes_json, 
                     last_refresh, status, user_id, token_type)
                )
                action = "updated"
            else:
                # INSERT
                conn.execute(
                    """
                    INSERT INTO oauth_tokens
                    (user_id, token_type, access_token_encrypted, refresh_token_encrypted,
                     expires_at, scopes, last_refresh, status, key_version, needs_reauth, refresh_failures)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0)
                    """,
                    (user_id, token_type, access_encrypted, refresh_encrypted, expires_at, 
                     scopes_json, last_refresh, status)
                )
                action = "created"
            
            # Log audit
            self._log_audit(
                conn=conn,
                event_type=f"tokens_{action}",
                user_id=user_id,
                details={
                    "token_type": token_type,
                    "expires_at": expires_at.isoformat(), 
                    "scopes": scopes,
                    "status": status
                }
            )
            
            logger.info(f"Tokens {action} for user {user_id} (type={token_type}), expires: {expires_at}")
            return True
    
    def mark_tokens_expired(self, user_id: int, token_type: str = 'bot', reason: str = "manual") -> bool:
        """
        Marque les tokens comme nécessitant une réautorisation.
        
        Args:
            user_id: ID de l'utilisateur
            token_type: Type de token ('bot' ou 'broadcaster')
            reason: Raison de l'expiration
        
        Returns:
            True si modifié
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE oauth_tokens SET needs_reauth = 1, status = 'expired' WHERE user_id = ? AND token_type = ?",
                (user_id, token_type)
            )
            
            if cursor.rowcount > 0:
                self._log_audit(
                    conn=conn,
                    event_type="tokens_expired",
                    user_id=user_id,
                    details={"reason": reason, "token_type": token_type},
                    severity="warning"
                )
                logger.warning(f"Tokens expired for user {user_id} (type={token_type}): {reason}")
                return True
            
            return False
    
    def increment_refresh_failures(self, user_id: int, token_type: str = 'bot') -> int:
        """
        Incrémente le compteur d'échecs de refresh.
        
        Args:
            user_id: ID de l'utilisateur
            token_type: Type de token ('bot' ou 'broadcaster')
        
        Returns:
            Nouveau nombre d'échecs
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE oauth_tokens
                SET refresh_failures = refresh_failures + 1
                WHERE user_id = ? AND token_type = ?
                RETURNING refresh_failures
                """,
                (user_id, token_type)
            )
            row = cursor.fetchone()
            failures = row[0] if row else 0
            
            if failures >= 3:
                conn.execute(
                    "UPDATE oauth_tokens SET needs_reauth = 1, status = 'expired' WHERE user_id = ? AND token_type = ?",
                    (user_id, token_type)
                )
    
    def increment_refresh_failures(self, user_id: int) -> int:
        """
        Incrémente le compteur d'échecs de refresh.
        
        Args:
            user_id: ID de l'utilisateur
        
        Returns:
            Nouveau nombre d'échecs
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE oauth_tokens
                SET refresh_failures = refresh_failures + 1
                WHERE user_id = ?
                RETURNING refresh_failures
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            failures = row[0] if row else 0
            
            if failures >= 3:
                # Marquer comme nécessitant réautorisation après 3 échecs
                conn.execute(
                    "UPDATE oauth_tokens SET needs_reauth = 1 WHERE user_id = ?",
                    (user_id,)
                )
                self._log_audit(
                    conn=conn,
                    event_type="tokens_max_failures",
                    user_id=user_id,
                    details={"failures": failures},
                    severity="error"
                )
            
            return failures
    
    def get_tokens_needing_refresh(self, buffer_minutes: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les tokens qui expirent bientôt.
        
        Args:
            buffer_minutes: Nombre de minutes avant expiration pour déclencher le refresh
        
        Returns:
            Liste de dicts avec user_id, expires_at, etc.
        """
        threshold = datetime.now() + timedelta(minutes=buffer_minutes)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT user_id, expires_at, refresh_failures, needs_reauth
                FROM oauth_tokens
                WHERE expires_at < ?
                  AND needs_reauth = 0
                  AND refresh_failures < 3
                ORDER BY expires_at ASC
                """,
                (threshold,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== INSTANCES ====================
    
    def get_active_instances(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les instances actives.
        
        Returns:
            Liste de dicts avec channel_login, bot_login, pid, status, etc.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT i.*,
                       u_channel.twitch_login as channel_login,
                       u_bot.twitch_login as bot_login
                FROM instances i
                JOIN users u_channel ON i.channel_id = u_channel.id
                JOIN users u_bot ON i.bot_user_id = u_bot.id
                WHERE i.status IN ('running', 'starting')
                ORDER BY i.start_time DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def register_instance(self, channel_login: str, bot_login: str, pid: int) -> int:
        """
        Enregistre une nouvelle instance de bot.
        
        Args:
            channel_login: Login du canal Twitch
            bot_login: Login du bot
            pid: PID du processus
        
        Returns:
            ID de l'instance créée
        """
        # Récupérer les IDs utilisateurs
        channel_user = self.get_user_by_login(channel_login)
        bot_user = self.get_user_by_login(bot_login)
        
        if not channel_user or not bot_user:
            raise ValueError(f"User not found: channel={channel_login}, bot={bot_login}")
        
        with self._get_connection() as conn:
            # Désactiver les anciennes instances pour ce canal
            conn.execute(
                """
                UPDATE instances
                SET status = 'stopped', stop_time = ?
                WHERE channel_id = ? AND status IN ('running', 'starting')
                """,
                (datetime.now(), channel_user['id'])
            )
            
            # Créer nouvelle instance
            cursor = conn.execute(
                """
                INSERT INTO instances
                (channel_id, bot_user_id, status, pid, start_time, last_heartbeat, crash_count)
                VALUES (?, ?, 'starting', ?, ?, ?, 0)
                """,
                (channel_user['id'], bot_user['id'], pid, datetime.now(), datetime.now())
            )
            instance_id = cursor.lastrowid
            
            self._log_audit(
                conn=conn,
                event_type="instance_started",
                user_id=bot_user['id'],
                channel_id=channel_user['id'],
                details={"pid": pid, "instance_id": instance_id}
            )
            
            logger.info(f"Instance registered: {channel_login} (PID {pid})")
            return instance_id
    
    def update_instance_heartbeat(self, instance_id: int, status: str = 'running') -> bool:
        """
        Met à jour le heartbeat d'une instance.
        
        Args:
            instance_id: ID de l'instance
            status: Nouveau statut ('running', 'stopping', etc.)
        
        Returns:
            True si modifié
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE instances
                SET last_heartbeat = ?, status = ?
                WHERE id = ?
                """,
                (datetime.now(), status, instance_id)
            )
            return cursor.rowcount > 0
    
    def stop_instance(self, instance_id: int, crash: bool = False) -> bool:
        """
        Marque une instance comme arrêtée.
        
        Args:
            instance_id: ID de l'instance
            crash: True si crash, False si arrêt normal
        
        Returns:
            True si modifié
        """
        with self._get_connection() as conn:
            # Récupérer crash_count actuel
            cursor = conn.execute(
                "SELECT crash_count FROM instances WHERE id = ?",
                (instance_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            
            crash_count = row[0]
            if crash:
                crash_count += 1
            
            # Mettre à jour
            cursor = conn.execute(
                """
                UPDATE instances
                SET status = 'stopped', stop_time = ?, crash_count = ?
                WHERE id = ?
                """,
                (datetime.now(), crash_count, instance_id)
            )
            
            if cursor.rowcount > 0:
                event_type = "instance_crashed" if crash else "instance_stopped"
                self._log_audit(
                    conn=conn,
                    event_type=event_type,
                    details={"instance_id": instance_id, "crash_count": crash_count},
                    severity="error" if crash else "info"
                )
                return True
            
            return False
    
    # ==================== CONFIG ====================
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration.
        
        Args:
            key: Clé de configuration
            default: Valeur par défaut si introuvable
        
        Returns:
            La valeur (convertie depuis JSON si nécessaire)
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except (json.JSONDecodeError, TypeError):
                    return row[0]
            return default
    
    def set_config(self, key: str, value: Any, description: Optional[str] = None) -> bool:
        """
        Définit une valeur de configuration.
        
        Args:
            key: Clé de configuration
            value: Valeur (sera sérialisée en JSON si nécessaire)
            description: Description optionnelle
        
        Returns:
            True si succès
        """
        # Sérialiser la valeur
        if isinstance(value, (dict, list, bool)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO config (key, value, description)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    description = COALESCE(excluded.description, description)
                """,
                (key, value_str, description)
            )
            logger.info(f"Config updated: {key} = {value}")
            return True
    
    # ==================== AUDIT LOG ====================
    
    def _log_audit(self, conn: sqlite3.Connection, event_type: str,
                   user_id: Optional[int] = None, channel_id: Optional[int] = None,
                   details: Optional[Dict[str, Any]] = None, severity: str = "info"):
        """
        Enregistre un événement d'audit (usage interne).
        
        Args:
            conn: Connexion SQLite active
            event_type: Type d'événement
            user_id: ID utilisateur concerné (optionnel)
            channel_id: ID canal concerné (optionnel)
            details: Détails JSON de l'événement
            severity: Sévérité (info, warning, error)
        """
        details_json = json.dumps(details) if details else None
        
        conn.execute(
            """
            INSERT INTO audit_log (event_type, user_id, channel_id, details, severity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_type, user_id, channel_id, details_json, severity)
        )
    
    def get_audit_log(self, limit: int = 100, event_type: Optional[str] = None,
                     user_id: Optional[int] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère les logs d'audit.
        
        Args:
            limit: Nombre maximum de résultats
            event_type: Filtrer par type d'événement
            user_id: Filtrer par utilisateur
            severity: Filtrer par sévérité
        
        Returns:
            Liste de dicts avec les événements d'audit
        """
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== MAINTENANCE ====================
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """
        Supprime les logs d'audit trop anciens.
        
        Args:
            days: Nombre de jours à conserver
        
        Returns:
            Nombre de logs supprimés
        """
        threshold = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM audit_log WHERE timestamp < ?",
                (threshold,)
            )
            deleted = cursor.rowcount
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old audit logs (>{days} days)")
            
            return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère des statistiques sur la base de données.
        
        Returns:
            Dict avec users_count, tokens_count, instances_count, etc.
        """
        with self._get_connection() as conn:
            stats = {}
            
            # Compter les utilisateurs
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            stats['users_count'] = cursor.fetchone()[0]
            
            # Compter les tokens
            cursor = conn.execute("SELECT COUNT(*) FROM oauth_tokens")
            stats['tokens_count'] = cursor.fetchone()[0]
            
            # Compter les instances actives
            cursor = conn.execute(
                "SELECT COUNT(*) FROM instances WHERE status IN ('running', 'starting')"
            )
            stats['active_instances'] = cursor.fetchone()[0]
            
            # Compter les logs d'audit
            cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
            stats['audit_logs_count'] = cursor.fetchone()[0]
            
            # Taille de la base
            cursor = conn.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
            stats['db_size_bytes'] = cursor.fetchone()[0]
            
            return stats


if __name__ == "__main__":
    # Test rapide
    print("Testing DatabaseManager...")
    
    # Créer une DB de test
    import os
    test_db = "kissbot_test.db"
    test_key = ".kissbot_test.key"
    
    # Cleanup
    for f in [test_db, f"{test_db}-wal", f"{test_db}-shm", test_key]:
        if os.path.exists(f):
            os.remove(f)
    
    # Initialiser
    print("\n1. Initializing database...")
    os.system(f"python database/init_db.py --db {test_db}")
    
    # Créer manager
    print("\n2. Creating DatabaseManager...")
    manager = DatabaseManager(db_path=test_db, key_file=test_key)
    
    # Créer utilisateur
    print("\n3. Creating test user...")
    user_id = manager.create_user(
        twitch_user_id="123456789",
        twitch_login="testuser",
        display_name="TestUser"
    )
    print(f"   User created: ID={user_id}")
    
    # Stocker tokens
    print("\n4. Storing OAuth tokens...")
    manager.store_tokens(
        user_id=user_id,
        access_token="test_access_token_1234567890",
        refresh_token="test_refresh_token_0987654321",
        expires_in=3600,
        scopes=["chat:read", "chat:edit"]
    )
    print("   Tokens stored and encrypted")
    
    # Récupérer tokens
    print("\n5. Retrieving tokens...")
    tokens = manager.get_tokens(user_id)
    print(f"   Access token: {tokens['access_token']}")
    print(f"   Refresh token: {tokens['refresh_token']}")
    print(f"   Expires at: {tokens['expires_at']}")
    print(f"   Scopes: {tokens['scopes']}")
    
    # Vérifier chiffrement
    print("\n6. Verifying encryption...")
    assert tokens['access_token'] == "test_access_token_1234567890"
    assert tokens['refresh_token'] == "test_refresh_token_0987654321"
    print("   ✅ Tokens decrypted correctly!")
    
    # Statistiques
    print("\n7. Database stats...")
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Audit log
    print("\n8. Audit log (last 5 events)...")
    logs = manager.get_audit_log(limit=5)
    for log in logs:
        print(f"   [{log['timestamp']}] {log['event_type']} (severity: {log['severity']})")
    
    print("\n✅ All tests passed!")
    
    # Cleanup
    print("\nCleaning up test files...")
    for f in [test_db, f"{test_db}-wal", f"{test_db}-shm", test_key]:
        if os.path.exists(f):
            os.remove(f)
    
    print("Done!")
