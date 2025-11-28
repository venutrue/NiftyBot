# 🎮 NiftyBot Monitoring & Control Guide

## 📋 Table of Contents
1. [Who Controls Trading?](#who-controls-trading)
2. [How to Monitor](#how-to-monitor)
3. [How to Control](#how-to-control)
4. [Emergency Procedures](#emergency-procedures)

---

## 🤖 Who Controls Trading?

### **THIS BOT (niftybot.py) is 100% autonomous**

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR COMPUTER (Local)                                      │
│  ┌──────────────────────────────────────┐                  │
│  │  niftybot.py (AUTONOMOUS BOT)        │                  │
│  │  ================================     │                  │
│  │  ✅ Decides WHEN to trade            │                  │
│  │  ✅ Decides WHAT to trade            │                  │
│  │  ✅ Calculates entry/exit            │                  │
│  │  ✅ Places orders                    │ ──────────────┐  │
│  │  ✅ Monitors positions               │               │  │
│  │  ✅ Executes stop-loss/targets       │               │  │
│  └──────────────────────────────────────┘               │  │
│         ▲                                                │  │
│         │ You control:                                  │  │
│         │ • Start: python niftybot.py                   ▼  │
│         │ • Stop: Ctrl+C                         ┌──────────┴──────┐
│         │ • Configure: Edit Config class         │  Zerodha Kite   │
└─────────────────────────────────────────────────┤  (Broker API)   │
                                                   │  ═══════════    │
                                                   │  Only executes  │
                                                   │  orders sent    │
                                                   │  by the bot     │
                                                   └─────────────────┘
```

### **What Kite Does:**
- ❌ Does NOT make trading decisions
- ❌ Does NOT generate signals
- ✅ Only EXECUTES orders that YOUR bot sends
- ✅ Provides market data when bot requests it
- ✅ Shows positions/orders in their web/app

**Think of Kite as a waiter at a restaurant:**
- The waiter (Kite) doesn't decide what you eat
- YOU (the bot) decide and tell the waiter
- The waiter just brings what you ordered

---

## 👀 How to Monitor (4 Ways)

### **Method 1: Bot Console (Real-Time, Most Detailed)**

When you run the bot, you see everything live:

```bash
$ python niftybot.py

═══════════════════════════════════════════════════════════
🚀 NIFTYBOT STARTED
═══════════════════════════════════════════════════════════
Configuration:
  Max Trades/Day: 5
  Lot Size: 75
  Risk per Trade: 2.0%
  Max Daily Loss: 5.0%
  Stop-Loss: 1.5x ATR
  Target: 2.5x ATR
═══════════════════════════════════════════════════════════

2025-11-28 09:15:23 - INFO - Trading account: John Doe
2025-11-28 09:35:12 - INFO - Day type detected: TRENDING

═══════════════════════════════════════════════════════════
📊 BOT STATUS SUMMARY
═══════════════════════════════════════════════════════════
Market Mode: TRENDING
Trades Today: 0/5
Open Positions: 0
Daily P&L: ₹0.00
═══════════════════════════════════════════════════════════

2025-11-28 10:43:05 - INFO - Signal: BUY_CE (TRENDING mode) → NIFTY25JAN0224000CE
2025-11-28 10:43:05 - INFO - NIFTY25JAN0224000CE passed liquidity checks - OI: 45000, Spread: 0.5%
2025-11-28 10:43:07 - INFO - Order placed: BUY 75 NIFTY25JAN0224000CE, Order ID: 123456
2025-11-28 10:43:09 - INFO - Position added: NIFTY25JAN0224000CE @ 150.0, SL: 127.5, TGT: 187.5

═══════════════════════════════════════════════════════════
📊 BOT STATUS SUMMARY
═══════════════════════════════════════════════════════════
Market Mode: TRENDING
Trades Today: 1/5
Open Positions: 1
Daily P&L: ₹0.00
────────────────────────────────────────────────────────────
  Position: NIFTY25JAN0224000CE
    Entry: ₹150.00 | SL: ₹127.50 | Target: ₹187.50
    Qty: 75 | Time: 10:43:09
═══════════════════════════════════════════════════════════

2025-11-28 10:58:34 - INFO - Target hit for NIFTY25JAN0224000CE: LTP 190.0 >= TGT 187.5
2025-11-28 10:58:35 - INFO - Order placed: SELL 75 NIFTY25JAN0224000CE, Order ID: 123457
2025-11-28 10:58:36 - INFO - Position closed: NIFTY25JAN0224000CE @ 190.0, Reason: TARGET, P&L: 3000.00
```

**Status Summary Updates Every 5 Minutes Automatically**

---

### **Method 2: Live Monitor Dashboard (NEW!) 📊**

Run this in a **separate terminal window** while bot is running:

```bash
python monitor.py
```

You'll see a live dashboard that updates every 5 seconds:

```
════════════════════════════════════════════════════════════════════════════════
                          🤖 NIFTYBOT LIVE MONITOR
════════════════════════════════════════════════════════════════════════════════

🟢 Status: RUNNING
🕐 Last Update: 2025-11-28 10:58:36

────────────────────────────────────────────────────────────────────────────────
MARKET MODE
────────────────────────────────────────────────────────────────────────────────
📈 TRENDING

────────────────────────────────────────────────────────────────────────────────
TRADING SUMMARY
────────────────────────────────────────────────────────────────────────────────
Trades Today: 1/5
Open Positions: 0
💰 Daily P&L: ₹3000.00

────────────────────────────────────────────────────────────────────────────────
RECENT CLOSED TRADES
────────────────────────────────────────────────────────────────────────────────
1. NIFTY25JAN0224000CE @ 190.0, Reason: TARGET, P&L: 3000.00

────────────────────────────────────────────────────────────────────────────────
LAST SIGNAL
────────────────────────────────────────────────────────────────────────────────
📊 BUY_CE (TRENDING mode) → NIFTY25JAN0224000CE

════════════════════════════════════════════════════════════════════════════════
Press Ctrl+C to exit monitor | Refreshing every 5 seconds...
════════════════════════════════════════════════════════════════════════════════
```

**This doesn't interfere with the bot** - it just reads the log file.

---

### **Method 3: Control Panel (NEW!) 🎮**

Interactive control panel to view AND control positions:

```bash
python control.py
```

Menu:

```
════════════════════════════════════════════════════════════════════════════════
                          🎮 NIFTYBOT CONTROL PANEL
════════════════════════════════════════════════════════════════════════════════

1. View Open Positions
2. View Today's Orders
3. View Account Summary
4. Close All Positions (EMERGENCY)
5. Exit

────────────────────────────────────────────────────────────────────────────────
Enter your choice (1-5):
```

**Example - View Positions:**

```
════════════════════════════════════════════════════════════════════════════════
                              📊 CURRENT POSITIONS
════════════════════════════════════════════════════════════════════════════════

1. NIFTY25JAN0224000CE
   Qty: 75 | Avg Price: ₹150.00 | LTP: ₹165.00
   💰 P&L: ₹1125.00

────────────────────────────────────────────────────────────────────────────────
💰 Total P&L: ₹1125.00
════════════════════════════════════════════════════════════════════════════════
```

---

### **Method 4: Zerodha Kite Web/App**

1. Open https://kite.zerodha.com (or mobile app)
2. Login with your credentials
3. Navigate to:
   - **Positions** tab → See all open positions + P&L
   - **Orders** tab → See all orders (pending/executed)
   - **P&L** tab → See detailed profit/loss

**You can manually close positions from here too!**

---

## 🎛️ How to Control

### **Before Starting the Bot**

#### 1. Configure Trading Parameters

Edit `niftybot.py` (lines 19-54):

```python
class Config:
    # ──────────────────────────────────────────────────
    # 🎚️ CONTROL PANEL - Adjust these before starting
    # ──────────────────────────────────────────────────

    # How many trades maximum per day?
    MAX_TRADES_PER_DAY = 5  # ← Change this (1-10 recommended)

    # How much to trade? (75 = 1 lot Nifty options)
    LOT_SIZE = 75  # ← 75 = 1 lot, 150 = 2 lots, etc.

    # How much % of capital to risk per trade?
    RISK_PER_TRADE_PCT = 2.0  # ← 1-3% recommended

    # What's the maximum daily loss before stopping?
    MAX_DAILY_LOSS_PCT = 5.0  # ← 5-10% recommended

    # How tight should stop-loss be?
    ATR_MULTIPLIER_SL = 1.5  # ← Lower = tighter (1.0-2.0)

    # How far should targets be?
    ATR_MULTIPLIER_TARGET = 2.5  # ← Higher = further (2.0-3.0)

    # Strategy thresholds
    VWAP_DEVIATION_THRESHOLD = 0.005  # 0.5% deviation
    RSI_OVERBOUGHT = 70  # ← Change to 65 for earlier signals
    RSI_OVERSOLD = 30    # ← Change to 35 for earlier signals
```

#### 2. Set Trading Hours

```python
class Config:
    # When to start and stop trading
    MARKET_OPEN_HOUR = 9       # Start at 9:15 AM
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15     # Square off by 3:15 PM
    MARKET_CLOSE_MINUTE = 15
```

---

### **During Trading (Live Control)**

#### ✅ **1. Stop the Bot Completely**

In the terminal where bot is running:

```bash
# Press Ctrl+C
^C

# Bot will:
# 1. Square off all open positions automatically
# 2. Show final P&L
# 3. Exit gracefully
```

Output:
```
2025-11-28 14:30:15 - INFO - Bot stopped by user
2025-11-28 14:30:16 - INFO - Squared off position: NIFTY25JAN0224000CE
═══════════════════════════════════════════════════════════
Bot stopped. Final P&L: ₹3000.00
═══════════════════════════════════════════════════════════
```

---

#### ✅ **2. Manually Close Positions (Override Bot)**

**Option A: Using Control Panel**

```bash
python control.py

# Choose option 4: Close All Positions
# Confirm: yes
```

**Option B: Using Kite Web/App**

1. Go to https://kite.zerodha.com
2. Click "Positions" tab
3. Find the option position
4. Click "Exit" button
5. Confirm

**The bot will detect position is closed and update accordingly.**

---

#### ✅ **3. Pause Trading (Without Stopping Bot)**

Edit Config and set:

```python
MAX_TRADES_PER_DAY = 0  # Bot won't enter new trades
```

Then restart the bot.

---

#### ✅ **4. Monitor Without Interfering**

```bash
# Terminal 1: Run the bot
python niftybot.py

# Terminal 2: Watch live monitor
python monitor.py

# Terminal 3 (optional): Use control panel
python control.py
```

---

## 🚨 Emergency Procedures

### **EMERGENCY: Stop Trading Immediately**

**Method 1: Kill the Bot (FASTEST)**

```bash
# In bot terminal: Press Ctrl+C
^C

# Bot auto-squares off all positions
```

**Method 2: Close Positions via Kite**

1. Open Kite web: https://kite.zerodha.com
2. Positions → Click "Exit All"
3. Confirm

**Method 3: Use Control Panel**

```bash
python control.py
# Choose option 4: Close All Positions
```

---

### **EMERGENCY: Daily Loss Limit Hit**

Bot **automatically stops** when daily loss reaches 5% (configurable):

```
2025-11-28 11:30:00 - ERROR - Daily loss limit breached: -5000.00
2025-11-28 11:30:01 - ERROR - Daily loss limit breached - Stopping bot
2025-11-28 11:30:02 - INFO - Squared off position: NIFTY25JAN0224000CE
═══════════════════════════════════════════════════════════
Bot stopped. Final P&L: ₹-5000.00
═══════════════════════════════════════════════════════════
```

**Bot will NOT trade again until you restart it manually.**

---

### **EMERGENCY: Max Trades Reached**

Bot **automatically stops entering new trades** after 5 trades (configurable):

```
2025-11-28 12:45:00 - INFO - Max trades (5) reached for the day
# Bot continues monitoring existing positions
# But won't open new positions
```

---

## 📊 Complete Monitoring Setup

**Recommended 3-Terminal Setup:**

```bash
# Terminal 1: Main bot (REQUIRED)
cd ~/NiftyBot
python niftybot.py

# Terminal 2: Live monitor (OPTIONAL but recommended)
cd ~/NiftyBot
python monitor.py

# Terminal 3: Kite web in browser (OPTIONAL)
# Open: https://kite.zerodha.com
```

---

## 🔍 Log File Analysis

All activity is logged to `niftybot.log`:

```bash
# View live logs
tail -f niftybot.log

# Search for specific events
grep "Order placed" niftybot.log
grep "Position closed" niftybot.log
grep "P&L" niftybot.log

# See all signals
grep "Signal:" niftybot.log

# Check for errors
grep "ERROR" niftybot.log
```

---

## 📋 Daily Checklist

### **Before Market Open (9:00 AM)**

- [ ] Generate new Kite access token
- [ ] Update `.env` file with new token
- [ ] Review and adjust `Config` if needed
- [ ] Check previous day's `niftybot.log`
- [ ] Clear old log file (optional): `> niftybot.log`

### **Market Open (9:15 AM)**

- [ ] Start bot: `python niftybot.py`
- [ ] Verify authentication successful
- [ ] Open monitor: `python monitor.py` (separate terminal)
- [ ] Open Kite web for backup monitoring

### **During Market Hours**

- [ ] Check monitor dashboard every 30 minutes
- [ ] Verify bot is responding (check last update time)
- [ ] Monitor P&L

### **Market Close (3:15 PM+)**

- [ ] Verify all positions squared off
- [ ] Review `niftybot.log` for the day
- [ ] Note final P&L
- [ ] Stop bot (Ctrl+C if still running)

---

## ❓ FAQ

**Q: Can the bot trade without me watching?**
A: Technically yes, but **NOT RECOMMENDED**. Always monitor during market hours.

**Q: What happens if my internet disconnects?**
A: Bot will crash. Positions remain open in Kite. Close manually via Kite app.

**Q: Can I run this on a cloud server?**
A: Yes! Use a VPS. But ensure it stays running during market hours.

**Q: How do I change strategy mid-day?**
A: Stop bot (Ctrl+C), edit Config, restart bot.

**Q: Does closing position in Kite affect the bot?**
A: Yes. Bot will detect position is closed on next check (~10 seconds).

---

## 🛠️ Troubleshooting

**Monitor shows "Unable to read log file"**
- Check if bot is running
- Check if `niftybot.log` exists in same folder

**Control panel shows "Failed to authenticate"**
- Check `.env` file has valid credentials
- Regenerate access token

**Bot not entering trades despite signals**
- Check if max trades reached (5/5)
- Check if daily loss limit hit
- Check if outside trading hours

---

## 📞 Quick Reference

| Action | Command |
|--------|---------|
| Start bot | `python niftybot.py` |
| Stop bot | Press `Ctrl+C` in bot terminal |
| Monitor live | `python monitor.py` |
| Control panel | `python control.py` |
| View logs | `tail -f niftybot.log` |
| Kite web | https://kite.zerodha.com |

---

**Remember: YOU are always in control. The bot is a tool, not the boss!** 🚀
