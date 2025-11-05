# Audit Log Event Types

Documentation des types d'événements (`event_type`) utilisés dans la table `audit_log`.

## Bot Management Events

| Event Type | Description | Details (JSON) |
|------------|-------------|----------------|
| `bot_start` | Bot démarré | `{"channel": "el_serda", "pid": 12345}` |
| `bot_stop` | Bot arrêté proprement | `{"channel": "el_serda", "reason": "manual"}` |
| `bot_crash` | Bot crashé | `{"channel": "el_serda", "exit_code": 1, "error": "..."}` |
| `bot_restart` | Bot redémarré | `{"channel": "el_serda", "attempt": 1}` |

## Token Management Events

| Event Type | Description | Details (JSON) |
|------------|-------------|----------------|
| `token_refresh` | Token refreshed avec succès | `{"user": "serda_bot", "token_type": "bot", "expires_in": 3600}` |
| `token_refresh_failed` | Échec du refresh | `{"user": "serda_bot", "token_type": "bot", "error": "invalid_grant", "attempt": 1}` |
| `token_revoked` | Token révoqué | `{"user": "serda_bot", "token_type": "bot", "reason": "user_action"}` |
| `token_needs_reauth` | Token nécessite une ré-auth | `{"user": "serda_bot", "token_type": "broadcaster", "failures": 3}` |

## EventSub Hub Events (NEW v5.0)

| Event Type | Description | Details (JSON) |
|------------|-------------|----------------|
| `eventsub_hub_start` | Hub EventSub démarré | `{"socket_path": "/tmp/kissbot_hub.sock", "pid": 12345}` |
| `eventsub_hub_stop` | Hub EventSub arrêté | `{"reason": "manual", "uptime_s": 3600}` |
| `eventsub_ws_connect` | WebSocket EventSub connecté | `{"session_id": "abc-123", "attempt": 1}` |
| `eventsub_ws_disconnect` | WebSocket EventSub déconnecté | `{"session_id": "abc-123", "reason": "keepalive_timeout"}` |
| `eventsub_ws_reconnect` | Tentative de reconnexion WS | `{"attempt": 1, "backoff_s": 2}` |
| `eventsub_create` | Subscription créée | `{"channel_id": "44456636", "topic": "stream.online", "twitch_sub_id": "abc-123", "status": "enabled"}` |
| `eventsub_create_failed` | Échec création subscription | `{"channel_id": "44456636", "topic": "stream.online", "error": "cost_exceeded", "http_status": 400}` |
| `eventsub_delete` | Subscription supprimée | `{"twitch_sub_id": "abc-123", "channel_id": "44456636", "topic": "stream.online"}` |
| `eventsub_delete_failed` | Échec suppression subscription | `{"twitch_sub_id": "abc-123", "error": "not_found", "http_status": 404}` |
| `eventsub_reconcile` | Réconciliation desired/active | `{"desired_count": 12, "active_count": 10, "to_create": 2, "to_delete": 0, "duration_ms": 150}` |
| `eventsub_event_received` | Event reçu du WebSocket | `{"channel_id": "44456636", "topic": "stream.online", "event_id": "xyz-789"}` |
| `eventsub_event_routed` | Event routé vers bot | `{"channel_id": "44456636", "topic": "stream.online", "bot_socket": "el_serda", "latency_ms": 2}` |
| `eventsub_event_routing_failed` | Échec routing event | `{"channel_id": "44456636", "topic": "stream.online", "error": "bot_disconnected"}` |

## IPC Events (Hub ↔ Bots)

| Event Type | Description | Details (JSON) |
|------------|-------------|----------------|
| `ipc_bot_connected` | Bot connecté au Hub | `{"channel": "el_serda", "socket_fd": 5}` |
| `ipc_bot_disconnected` | Bot déconnecté du Hub | `{"channel": "el_serda", "reason": "timeout"}` |
| `ipc_subscribe_request` | Bot demande subscription | `{"channel": "el_serda", "channel_id": "44456636", "topic": "stream.online"}` |
| `ipc_unsubscribe_request` | Bot demande unsubscribe | `{"channel": "el_serda", "channel_id": "44456636", "topic": "stream.online"}` |
| `ipc_hello_received` | Bot envoie hello | `{"channel": "el_serda", "channel_id": "44456636", "topics": ["stream.online", "stream.offline"]}` |

## Severity Guidelines

| Severity | Usage |
|----------|-------|
| `debug` | Événements verbeux pour debugging (ex: `eventsub_event_received`) |
| `info` | Opérations normales (ex: `eventsub_create`, `bot_start`) |
| `warning` | Situations anormales non-critiques (ex: `eventsub_ws_reconnect`, `token_refresh_failed` attempt 1) |
| `error` | Erreurs nécessitant attention (ex: `eventsub_create_failed`, `bot_crash`) |
| `critical` | Erreurs critiques système (ex: `eventsub_hub_stop` unexpected, `token_needs_reauth`) |

## Example Queries

### Voir les erreurs EventSub des dernières 24h
```sql
SELECT * FROM audit_log 
WHERE event_type LIKE 'eventsub_%' 
  AND severity IN ('error', 'critical')
  AND timestamp > datetime('now', '-1 day')
ORDER BY timestamp DESC;
```

### Compter les events routés par channel (dernière heure)
```sql
SELECT 
    json_extract(details, '$.channel_id') AS channel_id,
    COUNT(*) AS event_count
FROM audit_log
WHERE event_type = 'eventsub_event_routed'
  AND timestamp > datetime('now', '-1 hour')
GROUP BY channel_id
ORDER BY event_count DESC;
```

### Voir les reconnexions WS
```sql
SELECT 
    timestamp,
    json_extract(details, '$.attempt') AS attempt,
    json_extract(details, '$.backoff_s') AS backoff
FROM audit_log
WHERE event_type = 'eventsub_ws_reconnect'
ORDER BY timestamp DESC
LIMIT 10;
```

### Analyser les échecs de création de subs
```sql
SELECT 
    json_extract(details, '$.channel_id') AS channel_id,
    json_extract(details, '$.topic') AS topic,
    json_extract(details, '$.error') AS error,
    COUNT(*) AS fail_count
FROM audit_log
WHERE event_type = 'eventsub_create_failed'
  AND timestamp > datetime('now', '-1 day')
GROUP BY channel_id, topic, error
ORDER BY fail_count DESC;
```
