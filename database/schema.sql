-- KissBot V5 Database Schema
-- SQLite avec WAL mode pour concurrent reads/writes

-- Table des utilisateurs/channels
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    twitch_user_id TEXT NOT NULL UNIQUE,
    twitch_login TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_bot BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour recherche rapide par login
CREATE INDEX IF NOT EXISTS idx_users_login ON users(twitch_login);

-- Table des tokens OAuth (chiffrés avec Fernet)
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_type TEXT NOT NULL CHECK(token_type IN ('bot','broadcaster')),  -- Type de token
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT NOT NULL,
    scopes TEXT NOT NULL,  -- JSON array des scopes (requis, rempli à l'OAuth)
    expires_at TIMESTAMP NOT NULL,
    last_refresh INTEGER,  -- Timestamp UNIX du dernier refresh
    status TEXT NOT NULL DEFAULT 'valid' CHECK(status IN ('valid','expired','revoked')),
    key_version INTEGER NOT NULL DEFAULT 1,  -- Version de la clé de chiffrement (rotation)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    needs_reauth BOOLEAN DEFAULT 0,  -- Flag si refresh a échoué 3x
    refresh_failures INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, token_type)  -- Un seul token de chaque type par user
);

-- Index pour recherche par user_id
CREATE INDEX IF NOT EXISTS idx_oauth_user ON oauth_tokens(user_id);

-- Index pour recherche par type de token
CREATE INDEX IF NOT EXISTS idx_oauth_type ON oauth_tokens(token_type);

-- Index pour recherche par statut
CREATE INDEX IF NOT EXISTS idx_oauth_status ON oauth_tokens(status);

-- Index pour scan des tokens expirant bientôt
CREATE INDEX IF NOT EXISTS idx_oauth_expires ON oauth_tokens(expires_at);

-- Table des instances de bot actives
CREATE TABLE IF NOT EXISTS instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,  -- user_id du channel
    bot_user_id INTEGER NOT NULL,  -- user_id du bot
    status TEXT NOT NULL DEFAULT 'stopped',  -- running, stopped, crashed
    pid INTEGER,
    start_time TIMESTAMP,
    last_heartbeat TIMESTAMP,
    crash_count INTEGER DEFAULT 0,
    config_overrides TEXT,  -- JSON des overrides de config
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (bot_user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(channel_id, bot_user_id)
);

-- Index pour recherche par channel
CREATE INDEX IF NOT EXISTS idx_instances_channel ON instances(channel_id);

-- Index pour recherche par statut
CREATE INDEX IF NOT EXISTS idx_instances_status ON instances(status);

-- Table d'audit log (pour tracking des opérations)
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,  -- token_refresh, bot_start, bot_stop, bot_crash, etc.
    user_id INTEGER,
    channel_id INTEGER,
    details TEXT,  -- JSON avec détails de l'événement
    severity TEXT DEFAULT 'info',  -- debug, info, warning, error, critical
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (channel_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Index pour recherche par type d'événement
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type);

-- Index pour recherche par timestamp (pour cleanup des vieux logs)
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- Index pour recherche par sévérité
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);

-- Table de configuration globale (clé-valeur)
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insérer les configs par défaut
INSERT OR IGNORE INTO config (key, value, description) VALUES
    ('encryption_key_version', '1', 'Version de la clé de chiffrement Fernet'),
    ('token_refresh_interval', '60', 'Intervalle de refresh des tokens (secondes avant expiration)'),
    ('health_check_interval', '30', 'Intervalle des health checks (secondes)'),
    ('max_crash_count', '3', 'Nombre max de crashes avant désactivation auto'),
    ('log_retention_days', '30', 'Durée de rétention des audit logs (jours)'),
    ('app_token_cache_ttl', '3600', 'TTL du cache pour app access token (secondes)'),
    ('eventsub_reconcile_interval', '60', 'EventSub Hub: Intervalle de réconciliation (secondes)'),
    ('eventsub_req_rate_per_s', '2', 'EventSub Hub: Rate limit pour créations de subs (req/s)'),
    ('eventsub_req_jitter_ms', '200', 'EventSub Hub: Jitter entre requêtes (ms)'),
    ('eventsub_ws_backoff_base', '2', 'EventSub Hub: Base pour backoff exponentiel (secondes)'),
    ('eventsub_ws_backoff_max', '60', 'EventSub Hub: Backoff max pour reconnexion WS (secondes)');

-- ============================================================================
-- EventSub Hub Tables (v5.0)
-- ============================================================================

-- Table des subscriptions désirées (source de vérité)
-- Contient les subscriptions que les bots veulent activer
CREATE TABLE IF NOT EXISTS desired_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,           -- Twitch broadcaster_user_id (ex: "44456636")
    topic TEXT NOT NULL,                -- EventSub topic (ex: "stream.online", "stream.offline")
    version TEXT NOT NULL DEFAULT '1',  -- Version du topic EventSub (ex: "1", "2")
    transport TEXT NOT NULL DEFAULT 'websocket',  -- Transport type: websocket|webhook
    created_at INTEGER NOT NULL,        -- Timestamp UNIX de création
    updated_at INTEGER NOT NULL,        -- Timestamp UNIX de dernière mise à jour
    UNIQUE(channel_id, topic)           -- Une seule sub par channel+topic
);

-- Index pour recherche rapide par channel
CREATE INDEX IF NOT EXISTS idx_desired_channel ON desired_subscriptions(channel_id);

-- Index pour recherche par topic
CREATE INDEX IF NOT EXISTS idx_desired_topic ON desired_subscriptions(topic);

-- Table des subscriptions actives (état observé de Twitch)
-- Synchronisée via GET /eventsub/subscriptions
CREATE TABLE IF NOT EXISTS active_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    twitch_sub_id TEXT NOT NULL UNIQUE, -- ID de la subscription Twitch (ex: "abc-123-def")
    channel_id TEXT NOT NULL,           -- Twitch broadcaster_user_id
    topic TEXT NOT NULL,                -- EventSub topic
    status TEXT NOT NULL,               -- enabled|webhook_callback_verification_pending|webhook_callback_verification_failed|notification_failures_exceeded|authorization_revoked|moderator_removed|user_removed|version_removed|websocket_disconnected|websocket_failed_ping_pong|websocket_received_inbound_traffic|websocket_connection_unused|websocket_internal_error|websocket_network_timeout|websocket_network_error
    cost INTEGER DEFAULT 1,             -- Coût de la subscription (1 pour la plupart)
    created_at INTEGER NOT NULL,        -- Timestamp UNIX de création
    updated_at INTEGER NOT NULL,        -- Timestamp UNIX de dernière sync
    UNIQUE(channel_id, topic)           -- Dédupe: une seule sub active par channel+topic
);

-- Index pour recherche rapide par channel
CREATE INDEX IF NOT EXISTS idx_active_channel ON active_subscriptions(channel_id);

-- Index pour recherche par status (pour identifier les subs en erreur)
CREATE INDEX IF NOT EXISTS idx_active_status ON active_subscriptions(status);

-- Index pour recherche par twitch_sub_id (pour updates rapides)
CREATE INDEX IF NOT EXISTS idx_active_twitch_id ON active_subscriptions(twitch_sub_id);

-- Table d'état du Hub EventSub (key-value store)
-- Stocke l'état de santé et les métriques du Hub
CREATE TABLE IF NOT EXISTS hub_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL         -- Timestamp UNIX de mise à jour
);

-- Clés standards du hub_state:
-- - ws_state: "connected"|"connecting"|"reconnecting"|"down"
-- - last_ws_connect_ts: timestamp UNIX de dernière connexion
-- - last_reconcile_ts: timestamp UNIX de dernière réconciliation
-- - error_burst_level: niveau d'erreurs en rafale (int)
-- - total_events_routed: compteur total d'events routés
-- - ws_reconnect_count: nombre de reconnexions WS

INSERT OR IGNORE INTO hub_state (key, value, updated_at) VALUES
    ('ws_state', 'down', strftime('%s', 'now')),
    ('last_ws_connect_ts', '0', strftime('%s', 'now')),
    ('last_reconcile_ts', '0', strftime('%s', 'now')),
    ('error_burst_level', '0', strftime('%s', 'now')),
    ('total_events_routed', '0', strftime('%s', 'now')),
    ('ws_reconnect_count', '0', strftime('%s', 'now'));

-- Trigger pour mettre à jour updated_at automatiquement
CREATE TRIGGER IF NOT EXISTS update_users_timestamp 
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_oauth_timestamp 
AFTER UPDATE ON oauth_tokens
BEGIN
    UPDATE oauth_tokens SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_instances_timestamp 
AFTER UPDATE ON instances
BEGIN
    UPDATE instances SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_config_timestamp 
AFTER UPDATE ON config
BEGIN
    UPDATE config SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
END;
