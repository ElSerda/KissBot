-- Migration: Add personality table
-- Date: 2024-12-01

-- Table des préférences de personnalité par channel
CREATE TABLE IF NOT EXISTS channel_personality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL UNIQUE,      -- Twitch broadcaster_user_id
    channel_login TEXT NOT NULL,           -- Twitch login (pour affichage)
    preset TEXT NOT NULL DEFAULT 'normal', -- Preset actif: soft, normal, spicy, unhinged
    custom_rules TEXT,                     -- JSON: règles custom optionnelles
    nsfw_allowed BOOLEAN DEFAULT 0,        -- Autoriser contenu 18+
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour recherche rapide par channel_id
CREATE INDEX IF NOT EXISTS idx_personality_channel ON channel_personality(channel_id);

-- Index pour recherche par preset (stats)
CREATE INDEX IF NOT EXISTS idx_personality_preset ON channel_personality(preset);
