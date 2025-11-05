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
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT NOT NULL,
    scopes TEXT,  -- JSON array des scopes (optionnel, sera rempli par validate token)
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    needs_reauth BOOLEAN DEFAULT 0,  -- Flag si refresh a échoué 3x
    refresh_failures INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index pour recherche par user_id
CREATE INDEX IF NOT EXISTS idx_oauth_user ON oauth_tokens(user_id);

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
    ('log_retention_days', '30', 'Durée de rétention des audit logs (jours)');

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
