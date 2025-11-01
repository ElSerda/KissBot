# 🔄 EventSub Cost Limit - Retry Mechanism

**Status:** ✅ Implemented in v3.4.2  
**Module:** `twitchapi/transports/eventsub_client.py`  
**Priority:** HIGH (Production resilience for 7+ channels)

---

## 📋 Problem Context

### Twitch EventSub WebSocket Cost Limit

**Limitation:** EventSub WebSocket has a maximum **10 cost** per connection.

**Cost per event:**
- `stream.online` = **1 cost**
- `stream.offline` = **1 cost**

**Example with 7 channels:**
```
7 channels × 2 events (online + offline) = 14 cost total
Max allowed: 10 cost
Result: 10 subscriptions succeed, 4 fail with "cost exceeded"
```

### Impact Before v3.4.2

```
❌ 4 stream.offline subscriptions lost
⚠️  Permanent error logs (red errors in console)
⚠️  No automatic recovery
⚠️  Manual intervention required (reduce channels or disable offline)
```

---

## 🔧 Solution: Intelligent Retry Mechanism

### Architecture

```
EventSubClient
├── _failed_offline_subs: List[Dict]     # Queue for failed subscriptions
├── _retry_task: asyncio.Task            # Background retry task
├── _subscribe_channel()                 # Detects "cost exceeded"
├── start()                              # Launches retry if failures
├── _retry_failed_subscriptions()        # Retry logic (NEW)
└── stop()                               # Cancel retry gracefully
```

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. STARTUP (t=0s)                                           │
├─────────────────────────────────────────────────────────────┤
│  ├── Subscribe 7× stream.online → ✅ Success (7 cost)      │
│  ├── Subscribe 4× stream.offline → ✅ Success (11 cost)    │
│  └── Subscribe 3× stream.offline → ❌ Cost exceeded        │
│       → Added to _failed_offline_subs queue                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. RETRY TASK START (t=0s)                                  │
├─────────────────────────────────────────────────────────────┤
│  ├── Detect 3 failed subscriptions in queue                 │
│  ├── Log: "🔄 Starting retry task for 3 failed..."         │
│  └── Create asyncio.create_task() background                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. WAIT PERIOD (t=0-30s)                                    │
├─────────────────────────────────────────────────────────────┤
│  └── Bot continues normally                                 │
│       ├── IRC Client: ✅ Active (messages received)         │
│       └── EventSub: ✅ 10 subscriptions active              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. FIRST RETRY (t+30s)                                      │
├─────────────────────────────────────────────────────────────┤
│  ├── Log: "🔄 Retrying 3 failed subscriptions..."          │
│  ├── For each failed subscription:                          │
│  │    ├── Try eventsub.listen_stream_offline()             │
│  │    ├── Success → Remove from queue + Log success        │
│  │    └── Fail → Keep in queue for next retry              │
│  └── Update retry_delay: 30s → 60s (exponential)           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. SUBSEQUENT RETRIES (t+60s, t+120s, t+240s)              │
├─────────────────────────────────────────────────────────────┤
│  ├── Exponential backoff: 30s → 60s → 120s → 240s → 300s   │
│  ├── Max 3 attempts per subscription                        │
│  ├── After 3 failures: Remove from queue (give up)         │
│  └── When queue empty: Task completes                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 💻 Implementation Details

### 1. Failed Subscription Queue

```python
# __init__
self._failed_offline_subs: List[Dict[str, str]] = []
self._retry_task: Optional[asyncio.Task] = None

# Structure of failed subscription
{
    "channel": "pelerin_",
    "broadcaster_id": "135500767",
    "event": "stream.offline"
}
```

### 2. Error Detection

```python
async def _subscribe_channel(self, channel: str, broadcaster_id: str):
    # Subscribe stream.offline
    try:
        sub_id = await self.eventsub.listen_stream_offline(
            broadcaster_user_id=broadcaster_id,
            callback=self._handle_stream_offline
        )
        self._subscription_ids.append(sub_id)
        LOGGER.info(f"✅ Subscribed stream.offline: {channel}")
    
    except Exception as e:
        error_msg = str(e).lower()
        
        # Detect "cost exceeded" errors
        if "cost exceeded" in error_msg or "cost" in error_msg:
            LOGGER.warning(f"⚠️  Cost limit reached for {channel} stream.offline - Added to retry queue")
            
            # Add to retry queue (not error)
            self._failed_offline_subs.append({
                "channel": channel,
                "broadcaster_id": broadcaster_id,
                "event": "stream.offline"
            })
        else:
            # Other errors: Log as error
            LOGGER.error(f"❌ Failed to subscribe stream.offline for {channel}: {e}")
```

### 3. Retry Task Launch

```python
async def start(self):
    # ... subscription logic ...
    
    self._running = True
    LOGGER.info(f"✅ EventSub started ({len(self._subscription_ids)} subscriptions)")
    
    # Launch retry task if failures detected
    if self._failed_offline_subs:
        LOGGER.info(f"🔄 Starting retry task for {len(self._failed_offline_subs)} failed subscriptions...")
        self._retry_task = asyncio.create_task(self._retry_failed_subscriptions())
```

### 4. Retry Logic with Exponential Backoff

```python
async def _retry_failed_subscriptions(self):
    """
    Background task: Retry failed subscriptions with exponential backoff.
    """
    retry_attempts = {}  # {channel: attempt_count}
    max_attempts = 3
    retry_delay = 30  # Initial delay: 30 seconds
    
    while self._running and self._failed_offline_subs:
        await asyncio.sleep(retry_delay)
        
        LOGGER.info(f"🔄 Retrying {len(self._failed_offline_subs)} failed subscriptions...")
        
        # Copy list to iterate safely
        failed_subs = self._failed_offline_subs.copy()
        
        for sub_info in failed_subs:
            channel = sub_info["channel"]
            broadcaster_id = sub_info["broadcaster_id"]
            
            # Track attempts
            attempt = retry_attempts.get(channel, 0) + 1
            retry_attempts[channel] = attempt
            
            # Give up after max attempts
            if attempt > max_attempts:
                LOGGER.warning(f"⚠️  Max retry attempts reached for {channel}, giving up")
                self._failed_offline_subs.remove(sub_info)
                continue
            
            # Retry subscription
            try:
                sub_id = await self.eventsub.listen_stream_offline(
                    broadcaster_user_id=broadcaster_id,
                    callback=self._handle_stream_offline
                )
                self._subscription_ids.append(sub_id)
                LOGGER.info(f"✅ Retry SUCCESS: {channel} stream.offline (attempt {attempt})")
                
                # Remove from failed queue
                self._failed_offline_subs.remove(sub_info)
            
            except Exception as e:
                error_msg = str(e).lower()
                
                if "cost exceeded" in error_msg:
                    # Still cost exceeded, keep in queue
                    LOGGER.debug(f"🔄 Retry {channel}: Still cost exceeded (attempt {attempt}/{max_attempts})")
                else:
                    # Other error, remove from queue
                    LOGGER.error(f"❌ Retry {channel} failed: {e}")
                    self._failed_offline_subs.remove(sub_info)
        
        # Exponential backoff: 30s → 60s → 120s → 240s → 300s (max)
        retry_delay = min(retry_delay * 2, 300)
    
    LOGGER.info("✅ Retry task finished (no more failed subscriptions)")
```

### 5. Graceful Shutdown

```python
async def stop(self):
    """Stop EventSub WebSocket and cancel retry task."""
    if not self._running:
        return
    
    LOGGER.info("🛑 Stopping EventSub WebSocket...")
    
    # Cancel retry task if running
    if self._retry_task and not self._retry_task.done():
        LOGGER.info("🛑 Cancelling retry task...")
        self._retry_task.cancel()
        
        try:
            await self._retry_task
        except asyncio.CancelledError:
            pass
    
    # ... stop eventsub websocket ...
    
    self._running = False
    self._subscription_ids.clear()
    self._failed_offline_subs.clear()
    self.eventsub = None
```

---

## 📊 Production Testing Results

### Test Environment

- **Date**: 2025-11-01
- **Channels**: 7 (el_serda, morthycya, pelerin_, quartiergaminclub, squallchan, st0uffff, yurekb)
- **Desired subscriptions**: 14 (7 online + 7 offline)
- **Cost limit**: 10

### Startup Results

```
Time: 15:19:49 - EventSub WebSocket connected
Time: 15:19:50-51 - Subscribed 7× stream.online (7 cost) ✅
Time: 15:19:52 - Subscribed 3× stream.offline (10 cost total) ✅

Cost exceeded errors (4 channels):
  ⚠️  Cost limit reached for pelerin_ stream.offline - Added to retry queue
  ⚠️  Cost limit reached for yurekb stream.offline - Added to retry queue
  ⚠️  Cost limit reached for st0uffff stream.offline - Added to retry queue
  ⚠️  Cost limit reached for morthycya stream.offline - Added to retry queue

Time: 15:19:52.998 - ✅ EventSub started (10 subscriptions)
Time: 15:19:52.998 - 🔄 Starting retry task for 4 failed subscriptions...
```

### First Retry (30s Later)

```
Time: 15:20:23.000 - 🔄 Retrying 4 failed subscriptions...
Delta: 30.002 seconds ✅ PERFECT TIMING

Bot status during retry:
  ✅ IRC Client: Active (messages received in #squallchan, #yurekb)
  ✅ EventSub: 10 subscriptions active
  ✅ Zero downtime or disruption
```

### Performance Metrics

- **Retry precision**: 30.002s (0.007% deviation) ✅
- **Bot availability**: 100% (no interruption) ✅
- **Retry overhead**: Non-blocking background task ✅
- **Log clarity**: Warnings (yellow) not errors (red) ✅

---

## 🔍 Monitoring & Logs

### Expected Log Patterns

#### Healthy Startup (All Subscriptions Succeed)

```
INFO EventSubClient ✅ EventSub started (14 subscriptions)
```

#### Cost Limit Reached (Some Subscriptions Fail)

```
WARNING Cost limit reached for pelerin_ stream.offline - Added to retry queue
WARNING Cost limit reached for yurekb stream.offline - Added to retry queue
INFO ✅ EventSub started (10 subscriptions)
INFO 🔄 Starting retry task for 2 failed subscriptions...
```

#### Retry Attempts

```
INFO 🔄 Retrying 2 failed subscriptions...
DEBUG 🔄 Retry pelerin_: Still cost exceeded (attempt 1/3)
INFO ✅ Retry SUCCESS: yurekb stream.offline (attempt 1)
```

#### Max Attempts Reached

```
WARNING ⚠️  Max retry attempts reached for pelerin_, giving up
INFO ✅ Retry task finished (no more failed subscriptions)
```

---

## 💡 Benefits & Trade-offs

### ✅ Benefits

1. **Zero Manual Intervention**
   - Automatic recovery without user action
   - Production-ready resilience

2. **Non-Blocking Operation**
   - Background asyncio.Task
   - Bot continues functioning normally
   - IRC and EventSub online subscriptions unaffected

3. **Intelligent Backoff**
   - Exponential delay: 30s → 60s → 120s → 300s
   - Prevents API spam
   - Gives time for cost quota to potentially free up

4. **Graceful Failure**
   - Max 3 attempts per subscription
   - Prevents infinite retry loops
   - Clean shutdown on bot stop

5. **Clear Monitoring**
   - Warnings (not errors) for cost exceeded
   - Informative retry logs
   - Production-friendly log levels

### ⚠️ Trade-offs

1. **Not All Subscriptions May Recover**
   - If cost limit never frees up, some offline subs remain inactive
   - Acceptable: `stream.online` is more critical (always succeeds)

2. **30s Initial Delay**
   - First retry waits 30s (not immediate)
   - Acceptable: Bot already functional with online subs

3. **Complexity**
   - Additional code for retry logic (~80 lines)
   - Acceptable: Production resilience worth complexity

---

## 🎯 Recommendations

### For < 5 Channels

**Cost calculation:** 5 channels × 2 events = 10 cost ✅

No retry needed, all subscriptions succeed.

### For 6-10 Channels

**Cost calculation:** 6-10 channels × 2 events = 12-20 cost ❌

**Options:**
1. ✅ **Keep retry mechanism** (current implementation)
   - Prioritizes `stream.online` (always succeeds)
   - Retries `stream.offline` automatically
   - Best of both worlds

2. **Disable offline announcements** (`config.yaml`):
   ```yaml
   announcements:
     online: true
     offline: false  # Reduces cost to 10
   ```

3. **Use EventSub Webhook** (production advanced):
   - No cost limit
   - Requires public HTTPS server
   - More complex setup

### For > 10 Channels

**Cost calculation:** > 10 channels × 2 events = > 20 cost ❌

**Mandatory: EventSub Webhook**
- WebSocket cannot handle 10+ channels with online+offline
- Webhook has no cost limit
- See: `docs/EVENTSUB_WEBHOOK_SETUP.md` (future doc)

---

## 📚 References

### Twitch EventSub Documentation

- **WebSocket Guide**: https://dev.twitch.tv/docs/eventsub/handling-websocket-events
- **Cost Limits**: https://dev.twitch.tv/docs/eventsub/manage-subscriptions/#subscription-limits
- **Webhook Alternative**: https://dev.twitch.tv/docs/eventsub/handling-webhook-events

### Related Modules

- `twitchapi/transports/eventsub_client.py` - EventSub WebSocket wrapper
- `twitchapi/monitors/stream_monitor.py` - Polling fallback (if EventSub fails)
- `core/stream_announcer.py` - Consumes stream events from EventSub

---

## 🔮 Future Improvements

### Potential Enhancements

1. **Dynamic Priority Queue**
   - Prioritize channels by viewer count or activity
   - Retry most important channels first

2. **Cost Prediction**
   - Calculate expected cost before subscribing
   - Warn user if channels > 5 (cost will exceed limit)

3. **Webhook Auto-Fallback**
   - Detect 10+ channels
   - Automatically suggest webhook setup
   - Provide setup wizard

4. **Subscription Health Dashboard**
   - Web UI showing active subscriptions
   - Retry status and history
   - Manual retry trigger

---

## 🐛 Known Issues

### EventSub stream.online with missing broadcaster_user_login

**Issue**: Twitch EventSub sometimes sends `stream.online` events with `broadcaster_user_login: null` during the first seconds of a stream going live.

**Symptoms**:
```
🔴 [EventSub] unknown is now ONLINE (type: live, started: 2025-11-01T20:47:45Z)
⚠️ Missing channel/channel_id in stream.online event
```

**Root Cause**: 
- Twitch EventSub sends event **before** stream metadata is fully indexed
- Event arrives with `broadcaster_user_id` populated but `broadcaster_user_login` missing
- Typically occurs within first 1-2 seconds of stream starting

**Fix Applied** (v3.4.3):
```python
# Fallback: Reverse lookup broadcaster_id -> channel
if not broadcaster_login and broadcaster_id:
    for channel, stored_id in self.broadcaster_ids.items():
        if stored_id == broadcaster_id:
            broadcaster_login = channel
            LOGGER.debug(f"🔍 Resolved broadcaster_id {broadcaster_id} → {channel}")
            break
```

**Expected Logs After Fix**:
```
🔍 [EventSub] Resolved broadcaster_id 135500767 → pelerin_
🔴 [EventSub] pelerin_ is now ONLINE (type: live, started: 2025-11-01T20:47:45Z)
```

**Frequency**: 
- Rare (observed ~2 times over 4h38min production run)
- More common during stream restart/crash recovery
- Not related to reconnections (independent issue)

**Workaround**: 
- Bot now maintains `broadcaster_ids` mapping (channel → ID)
- Reverse lookup resolves missing login automatically
- If ID also unknown: fallback to "unknown" with warning log

**Related**: 
- [Twitch EventSub Issue Tracker](https://github.com/twitchdev/issues/issues)
- Similar reports from other developers using EventSub WebSocket

---

**Last Updated:** 2025-11-01  
**Author:** KissBot Development Team  
**Version:** 3.4.3
