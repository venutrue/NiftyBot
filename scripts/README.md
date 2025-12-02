# Utility Scripts

Quick reference for managing your live trading system.

## Daily Operations

### Check System Status
```bash
python scripts/check_status.py
```
Shows:
- Trading enabled/disabled
- Kill switch status
- Circuit breaker status
- Today's P&L and trades
- Open positions

**Run this:** Every morning before market opens

---

### Show Performance
```bash
python scripts/show_performance.py
```
Shows:
- Daily and weekly P&L
- Win rate and trade count
- Recent trades
- Performance metrics

**Run this:** After market closes each day

---

### Reset Daily Stats
```bash
python scripts/reset_daily.py
```
Resets:
- Daily P&L to ₹0
- Daily trade count
- Consecutive loss counter

**Run this:** Start of each trading day (automatically done by bot, but can run manually if needed)

---

## Emergency Operations

### Emergency Exit All Positions
```bash
# Exit all positions
python scripts/emergency_exit.py --all

# Exit specific position
python scripts/emergency_exit.py --symbol NIFTY24500CE
```

**Use when:**
- System malfunction
- Need to close everything quickly
- Market crash scenario

---

### Activate Kill Switch
```bash
python scripts/activate_kill_switch.py
```

**Effect:**
- STOPS all trading immediately
- Disables all bots
- Requires manual reactivation

**Use when:**
- Catastrophic losses
- System issues
- Need to stop everything NOW

---

## Quick Commands

```bash
# Morning routine
python scripts/check_status.py
python run_bot.py --mode live

# During market
# (Just monitor, let bot run)

# Evening routine
python scripts/show_performance.py
# Review logs
# Update journal
```

---

## Notes

- All scripts are safe to run (they confirm before destructive actions)
- Scripts work with both live and paper trading modes
- Check logs in `logs/` directory for detailed info
- Emergency operations log to `data/risk/emergency_log.txt`
