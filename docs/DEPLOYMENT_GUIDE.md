# 🚀 Monitor Deployment Guide

Production deployment checklist for KissBot monitoring stack.

---

## 📋 Pre-Deployment Checklist

### Local Verification

- [ ] Pull latest code from `refactor/v2-modular` branch
- [ ] Verify syntax: `python3 -m py_compile core/monitor.py core/monitor_client.py main.py`
- [ ] Run test suite: `python3 test_new_monitor.py` (should see ✅ all tests pass)
- [ ] Check imports: `python3 -c "from core.monitor_client import MonitorClient; print('✅ OK')"`

### Code Review

- [ ] Review `main.py` monitor integration (lines 33-35, 1013-1017)
- [ ] Check `core/monitor.py` event queue implementation
- [ ] Verify `core/monitor_client.py` has no breaking changes
- [ ] Confirm `core/bot_types.py` rename applied correctly

### Dependencies

- [ ] Python 3.10+ (`python3 --version`)
- [ ] All requirements installed: `pip list | grep -E "asyncio|psutil"`
- [ ] Virtual environment activated: `source kissbot-venv/bin/activate`

---

## 🔧 Installation Steps

### 1. Backup Current Monitor

```bash
cd /home/serda/Project/KissBot-standalone

# Backup database
cp kissbot_monitor.db kissbot_monitor.db.backup_$(date +%s)
ls -lh kissbot_monitor.db*
```

### 2. Pull Latest Code

```bash
git fetch origin refactor/v2-modular
git pull origin refactor/v2-modular

# Verify key files exist
ls -la core/monitor.py core/monitor_client.py core/bot_types.py
```

### 3. Verify File Integrity

```bash
# Check Monitor
python3 -c "
from core.monitor import KissBotMonitor
print('✅ Monitor loads')
"

# Check Client
python3 -c "
from core.monitor_client import MonitorClient
print('✅ MonitorClient loads')
"

# Check Main
python3 -c "
import main
print('✅ main.py loads')
"
```

### 4. Test Monitor Standalone

```bash
# Terminal 1: Start Monitor
timeout 10 python3 core/monitor.py 2>&1 | tee /tmp/monitor_deploy_test.log &
MONITOR_PID=$!
sleep 2

# Terminal 2: Run test
python3 test_new_monitor.py

# Stop monitor
kill $MONITOR_PID

# Check logs
echo "=== Monitor Logs ===" && tail -30 /tmp/monitor_deploy_test.log
```

Expected output:
```
✅ Monitor started
📊 Metrics loop started
🔄 Event worker started
▶️ Test 1: Register
  ✅ Bot in monitor.bots: ['test_chan']
▶️ Test 2: Heartbeat
  ✅ Heartbeat recorded
▶️ Test 3: LLM Usage
  ✅ LLM usage logged
✨ TOUS LES TESTS PASSENT!
```

---

## 🚀 Deployment on VPS

### 1. SSH to VPS

```bash
ssh debian@51.38.51.222
cd /home/serda/Project/KissBot-standalone
```

### 2. Pull and Verify

```bash
# Pull code
git pull origin refactor/v2-modular

# Verify syntax
source kissbot-venv/bin/activate
python3 -m py_compile core/monitor.py core/monitor_client.py main.py

# Check for circular imports
python3 -c "from core.monitor_client import MonitorClient; print('✅')"
```

### 3. Start Monitor

```bash
# Create log directory
mkdir -p logs

# Start monitor in background
source kissbot-venv/bin/activate
nohup python3 core/monitor.py > logs/monitor.log 2>&1 &

# Verify it's running
sleep 2
ps aux | grep "core/monitor.py" | grep -v grep

# Check socket
ls -la /tmp/kissbot_monitor.sock
```

### 4. Start Supervisor (if multi-process)

```bash
./kissbot.sh start
```

Or for single-bot:

```bash
nohup python3 main.py --channel YOUR_CHANNEL > logs/bot.log 2>&1 &
```

### 5. Verify Startup

```bash
# Check Monitor logs
tail -20 logs/monitor.log

# Should see:
# ✅ Database initialized
# 🚀 Monitor started
# 📊 Metrics loop started
# 🔄 Event worker started

# Check Bot logs
tail -20 logs/bot.log

# Should see:
# ✅ Registered with Monitor
# 💓 Monitor registered and heartbeat started
```

---

## 📊 Post-Deployment Verification

### 1. Database

```bash
# Check monitor database
sqlite3 kissbot_monitor.db

# List tables
.tables

# Check bot status
SELECT * FROM bot_status;

# Check LLM usage
SELECT * FROM llm_usage LIMIT 5;

# Exit
.exit
```

Expected output:
```
channel     | pid   | status  | features           | registered_at
my_channel  | 12345 | online  | {"llm": true, ...} | 2025-12-06 15:40:55
```

### 2. Logs

```bash
# Monitor logs
tail -50 logs/monitor.log | grep -E "Register|heartbeat|LLM|ERROR|stale"

# Bot logs
tail -50 logs/bot.log | grep -E "Monitor|heartbeat|registered"

# Check for errors
grep ERROR logs/*.log
```

### 3. Socket

```bash
# Verify socket exists
ls -la /tmp/kissbot_monitor.sock

# Check permissions (should be 0o777)
stat /tmp/kissbot_monitor.sock | grep Access

# Test connectivity
python3 -c "
from core.monitor_client import MonitorClient
import os
client = MonitorClient('test', os.getpid())
import asyncio
result = asyncio.run(client.heartbeat())
print(f'✅ Socket test: {result}')
"
```

### 4. Health Checks

```bash
# Monitor is running
ps aux | grep "core/monitor.py" | grep -v grep && echo "✅ Monitor running"

# Bot is running
ps aux | grep "main.py" | grep -v grep && echo "✅ Bot running"

# Socket is accessible
[ -S /tmp/kissbot_monitor.sock ] && echo "✅ Socket exists"

# Database is accessible
sqlite3 kissbot_monitor.db "SELECT COUNT(*) FROM bot_status;" && echo "✅ Database OK"

# No recent errors
tail -100 logs/monitor.log | grep ERROR && echo "⚠️  Errors found" || echo "✅ No errors"
```

---

## 🔄 Rolling Back

If issues occur:

### 1. Stop Services

```bash
./kissbot.sh stop
pkill -f core/monitor.py
pkill -f main.py
```

### 2. Restore Previous Version

```bash
git checkout HEAD~1 core/monitor.py core/monitor_client.py main.py
```

### 3. Restore Database

```bash
cp kissbot_monitor.db.backup_* kissbot_monitor.db
```

### 4. Restart

```bash
./kissbot.sh start
```

---

## 📈 Monitoring & Maintenance

### Daily Checks

```bash
# Check bot status
sqlite3 kissbot_monitor.db "SELECT channel, status, strftime('%s', 'now') - strftime('%s', last_heartbeat) as seconds_since_heartbeat FROM bot_status;"

# Look for stale bots
grep "is stale" logs/monitor.log | tail -10

# Check LLM usage (cost tracking)
sqlite3 kissbot_monitor.db "SELECT channel, model, COUNT(*) as calls, SUM(tokens_in) as total_in FROM llm_usage GROUP BY channel, model;"
```

### Weekly Reports

```bash
# LLM cost (if you have pricing)
sqlite3 kissbot_monitor.db "
SELECT 
  channel,
  model,
  COUNT(*) as calls,
  SUM(tokens_in) + SUM(tokens_out) as total_tokens,
  AVG(latency_ms) as avg_latency_ms
FROM llm_usage
WHERE timestamp > datetime('now', '-7 days')
GROUP BY channel, model
ORDER BY total_tokens DESC;
"

# Bot uptime
grep "registered at" logs/monitor.log | tail
```

### Log Rotation

```bash
# Archive logs monthly
gzip logs/broadcast/*/instance.log.*
tar czf logs/broadcast_$(date +%Y%m%d).tar.gz logs/broadcast/

# Clean old backups
find . -name "kissbot_monitor.db.backup_*" -mtime +30 -delete
```

---

## 🐛 Troubleshooting

### Monitor Hangs

**Symptom:** Monitor not processing messages, bots timeout  
**Cause:** Event queue blocked (should not happen with async)  
**Fix:**

```bash
# Restart monitor
pkill -9 core/monitor.py
python3 core/monitor.py &

# Check event worker logs
grep "_event_worker" logs/monitor.log
```

### Socket Connection Fails

**Symptom:** `ConnectionRefusedError` or `No such file or directory`  
**Cause:** Monitor not running or socket stale  
**Fix:**

```bash
# Check if monitor running
ps aux | grep core/monitor.py

# Remove stale socket
rm /tmp/kissbot_monitor.sock

# Restart monitor
python3 core/monitor.py &

# Verify socket
ls -la /tmp/kissbot_monitor.sock
```

### Circular Import Error

**Symptom:** `cannot import name 'GenericAlias' from types`  
**Cause:** Old `core/types.py` still exists  
**Fix:**

```bash
# Verify file was renamed
ls -la core/bot_types.py
rm -f core/types.py
python3 -m py_compile core/monitor.py
```

### High Memory Usage

**Symptom:** Monitor process grows to 500MB+  
**Cause:** Event queue backing up (rare)  
**Fix:**

```bash
# Check queue size in logs
grep "Queue size:" logs/monitor.log

# Restart to clear
pkill -9 core/monitor.py
python3 core/monitor.py &
```

---

## 📞 Support & Escalation

| Issue | Check | Action |
|-------|-------|--------|
| Bot shows as "stale" | `sqlite3 ... SELECT last_heartbeat` | Restart bot |
| Monitor using high CPU | Event queue size, slow handlers | Restart monitor |
| Socket permission denied | `ls -la /tmp/kissbot_monitor.sock` | `chmod 0777` |
| Database locked | Other processes accessing it | Restart monitor |
| OOM (out of memory) | `free -h`, `ps aux \| sort -k4 -rn` | Investigate queue overflow |

---

## 🎉 Success Criteria

After deployment, you should see:

✅ Monitor running and accepting connections  
✅ Bots registering and sending heartbeats  
✅ No deadlock (bots stay "online" for > 24h)  
✅ LLM usage logged to database  
✅ Logs clean (no repeated ERROR messages)  
✅ Zero stale warnings for stable bots  

---

## 📋 Sign-Off Checklist

- [ ] Code pulled and verified
- [ ] Tests pass locally
- [ ] Deployed to VPS
- [ ] Monitor running
- [ ] Bots registering
- [ ] Heartbeats logged
- [ ] Database has data
- [ ] Logs are clean
- [ ] Ran for > 1 hour without errors
- [ ] Documented any issues

---

**Deployment Date:** _______________  
**Deployed By:** _______________  
**Notes:** _______________

---

**Last Updated:** 2025-12-06  
**Status:** ✅ **Ready for Production**
