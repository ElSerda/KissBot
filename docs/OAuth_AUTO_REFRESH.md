# 🔐 OAuth Token Auto-Refresh - Technical Documentation

**Status:** ✅ Implemented in v3.4.1  
**Module:** `twitchapi/auth_manager.py`  
**Priority:** CRITICAL (Bot cannot start without valid token)

---

## 📋 Overview

KissBot automatically refreshes expired Twitch OAuth tokens using the refresh token flow. This ensures zero-downtime operation and eliminates manual token regeneration.

### Problem Context

**Before v3.4.1:**
- Token refresh was TODO stub since Phase 2.1
- When access token expired (4h validity), bot couldn't start
- Error: `❌ Validation token échouée: 401 - {"status":401,"message":"invalid access token"}`
- Manual token regeneration required via OAuth flow

**After v3.4.1:**
- ✅ Automatic refresh on 401 Unauthorized
- ✅ Transparent operation (no user intervention)
- ✅ Token saved to `.tio.tokens.json`
- ✅ Bot continues startup automatically

---

## 🔧 Implementation

### Architecture

```
AuthManager
├── load_token_from_file()       # Load token from .tio.tokens.json
├── _validate_and_update()       # Validate token + auto-refresh on 401
├── _refresh_token_direct()      # Refresh during validation (no self.tokens)
├── _refresh_token()             # Refresh for loaded tokens
└── _save_token_to_file()        # Save refreshed token
```

### Workflow

```
1. Bot starts
   ↓
2. AuthManager.load_token_from_file(user_id)
   ↓
3. _validate_and_update(token_info)
   ├── Call Twitch /oauth2/validate
   ├── Status 200 → ✅ Token valid
   └── Status 401 → 🔄 Token expired
       ↓
4. _refresh_token_direct(token_info)
   ├── Call Twitch /oauth2/token
   ├── grant_type=refresh_token
   ├── Update access_token + refresh_token
   └── _save_token_to_file()
       ↓
5. Re-validate with new token
   ↓
6. ✅ Token valid, bot continues
```

### Code Flow

#### 1. Validation Detection (401 → Refresh)

```python
async def _validate_and_update(self, token_info: TokenInfo) -> None:
    """
    Valide un token via API Twitch et met à jour user_login + scopes
    Si le token est expiré (401), tente automatiquement le refresh.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {token_info.access_token}"}
        ) as resp:
            if resp.status == 200:
                # Token valid
                data = await resp.json()
                token_info.user_login = data.get("login", "")
                # ... update scopes, expires_at
            
            elif resp.status == 401:
                # Token expired - Auto-refresh
                LOGGER.warning(f"⚠️ Token expiré (401), tentative refresh automatique...")
                await self._refresh_token_direct(token_info)
                await self._validate_and_update(token_info)  # Re-validate
```

#### 2. Direct Refresh (During Validation)

```python
async def _refresh_token_direct(self, token_info: TokenInfo) -> None:
    """
    Refresh un token directement (sans lookup dans self.tokens)
    Utilisé lors de la validation initiale si le token est expiré.
    """
    LOGGER.info(f"🔄 Refresh token direct via Twitch OAuth...")
    
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
```

#### 3. Refresh for Loaded Tokens

```python
async def _refresh_token(self, user_login: str) -> None:
    """
    Refresh un token expiré via Twitch OAuth refresh endpoint
    Utilisé par get_token() pour tokens déjà dans self.tokens.
    """
    token_info = self.tokens[user_login]
    
    # Same refresh logic as _refresh_token_direct
    # + Update Twitch instance auth
    await self.twitch.set_user_authentication(
        token_info.access_token,
        token_info.scopes,
        token_info.refresh_token
    )
```

#### 4. Save to File

```python
async def _save_token_to_file(self, token_info: TokenInfo) -> None:
    """
    Sauvegarde un token dans .tio.tokens.json
    """
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
    
    LOGGER.info(f"✅ Token {token_info.user_login} sauvegardé")
```

---

## 🔐 Security Considerations

### Token Storage

**File:** `.tio.tokens.json`

```json
{
  "1209350837": {
    "token": "abc123...",
    "refresh": "def456..."
  }
}
```

**Security measures:**
- ✅ File in `.gitignore` (never committed)
- ✅ Refresh token stored securely (required for auto-refresh)
- ✅ Access token updated on refresh (old token invalidated)
- ⚠️ File permissions: Ensure only bot user can read (chmod 600)

### Token Lifecycle

```
Initial OAuth Flow (Manual)
   ↓
access_token (valid 4h)
refresh_token (valid indefinitely)
   ↓
After 4h → Auto-refresh
   ↓
NEW access_token (valid 4h)
NEW refresh_token (old one invalidated)
   ↓
Cycle continues automatically
```

### Refresh Token Validity

- **Access token**: Valid 4 hours (`expires_in: 14400`)
- **Refresh token**: Valid indefinitely (until revoked)
- **Revocation scenarios**:
  - User changes password
  - User disconnects app from Twitch settings
  - Manual revocation via Twitch API

**Recovery:** If refresh fails (invalid_grant), bot logs error and requires manual OAuth flow.

---

## 📊 Logs & Monitoring

### Successful Refresh

```
INFO     twitchapi.auth_manager ✅ Token chargé pour user_id=1209350837
WARNING  twitchapi.auth_manager ⚠️ Token expiré (401), tentative refresh automatique...
INFO     twitchapi.auth_manager 🔄 Refresh token direct via Twitch OAuth...
INFO     twitchapi.auth_manager ✅ Token serda_bot sauvegardé dans .tio.tokens.json
INFO     twitchapi.auth_manager ✅ Token refreshé (expires: 2025-11-01 19:18:34)
INFO     twitchapi.auth_manager 🔄 Re-validation après refresh...
INFO     twitchapi.auth_manager ✅ Token validé: serda_bot (ID: 1209350837)
```

### Failed Refresh

```
ERROR    twitchapi.auth_manager ❌ Erreur refresh token direct: 401 - {"error":"invalid_grant"}
```

**Common failure reasons:**
- Refresh token revoked (user action)
- Invalid client_id/client_secret
- Network connectivity issues

---

## 🧪 Testing

### Manual Test (Expire Token)

```bash
# 1. Invalidate current token (optional)
# Via Twitch API or wait for natural expiration

# 2. Start bot
python3 main.py

# 3. Check logs for auto-refresh
grep "Token expiré" logs/kissbot.log
grep "Token refreshé" logs/kissbot.log

# 4. Verify .tio.tokens.json updated
cat .tio.tokens.json  # Should show new tokens
```

### Integration Test

```python
import asyncio
from twitchapi.auth_manager import AuthManager

async def test_refresh():
    # Setup
    auth = AuthManager(twitch_instance)
    token_info = await auth.load_token_from_file("1209350837")
    
    # Simulate expired token
    token_info.access_token = "invalid_token"
    
    # Validate (should trigger refresh)
    await auth._validate_and_update(token_info)
    
    # Assert
    assert token_info.access_token != "invalid_token"
    assert token_info.expires_at > datetime.now()

asyncio.run(test_refresh())
```

---

## 🐛 Troubleshooting

### Bot Won't Start (401)

**Symptom:**
```
ERROR    twitchapi.auth_manager ❌ Validation token échouée: 401
ERROR    twitchapi.transports.irc_client ❌ Erreur démarrage IRC: passed twitch instance is missing User Auth
```

**Diagnosis:**
1. Check refresh token exists in `.tio.tokens.json`
2. Verify client_id/client_secret in config.yaml
3. Check refresh token not revoked

**Solution:**
If refresh fails, regenerate OAuth token:
```bash
# Use OAuth flow script
python3 exchange_oauth_code.py
```

### Refresh Loop (Continuous 401)

**Symptom:**
```
WARNING  twitchapi.auth_manager ⚠️ Token expiré (401), tentative refresh automatique...
ERROR    twitchapi.auth_manager ❌ Erreur refresh token direct: 401 - {"error":"invalid_grant"}
```

**Cause:** Refresh token invalidated by Twitch

**Solution:** Manual OAuth regeneration required

---

## 📚 References

### Twitch OAuth Documentation

- **Token Validation**: https://dev.twitch.tv/docs/authentication/validate-tokens
- **Token Refresh**: https://dev.twitch.tv/docs/authentication/refresh-tokens
- **OAuth Scopes**: https://dev.twitch.tv/docs/authentication/scopes

### Related Modules

- `twitchapi/auth_manager.py` - Token management
- `core/message_types.py` - ChatMessage structure
- `main.py` - Bot initialization with AuthManager

---

## 🎯 Future Improvements

### Potential Enhancements

1. **Proactive Refresh**
   - Refresh 30min before expiration (not wait for 401)
   - Requires background task monitoring expires_at

2. **Multi-User Support**
   - Handle multiple user tokens (bot + broadcasters)
   - Currently supports single bot token

3. **Refresh Retry Logic**
   - Exponential backoff on refresh failure
   - Max 3 retry attempts before manual OAuth

4. **Token Rotation Monitoring**
   - Track refresh frequency
   - Alert on suspicious refresh patterns

---

**Last Updated:** 2025-11-01  
**Author:** KissBot Development Team  
**Version:** 3.4.1
