# ⚡ NiftyBot Quick Start Guide

## 🎯 Who's in Charge?

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR COMPUTER                            │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  niftybot.py (THE BOSS - 100% Autonomous)             │    │
│  │  ════════════════════════════════════════              │    │
│  │                                                         │    │
│  │  ✅ Analyzes market data every 10 seconds             │    │
│  │  ✅ Calculates VWAP, EMA, RSI, ATR                    │    │
│  │  ✅ Detects if market is TRENDING or SIDEWAYS         │    │
│  │  ✅ DECIDES when to enter trades                      │    │
│  │  ✅ DECIDES which option to buy (CE/PE)               │    │
│  │  ✅ Places BUY orders                                 │────┼───┐
│  │  ✅ Monitors positions continuously                    │    │   │
│  │  ✅ AUTOMATICALLY exits at stop-loss or target        │    │   │
│  │  ✅ Places SELL orders                                │────┼───┤
│  │  ✅ Tracks P&L and trade count                        │    │   │
│  │  ✅ Stops at max 5 trades or 5% daily loss            │    │   │
│  │  ✅ Auto squares-off at 3:15 PM                       │    │   │
│  │                                                         │    │   │
│  └────────────────────────────────────────────────────────┘    │   │
│                                                                 │   │
│  You control:                                                  │   │
│  • Start: python niftybot.py                                  │   │
│  • Stop: Ctrl+C (auto-closes positions)                       │   │
│  • Configure: Edit Config class before starting               │   │
│                                                                 │   │
└─────────────────────────────────────────────────────────────────┘   │
                                                                      │
                                                                      ▼
                                                    ┌─────────────────────────┐
                                                    │   Zerodha Kite API      │
                                                    │   ═══════════════       │
                                                    │   (Just the Broker)     │
                                                    │                         │
                                                    │   ❌ Makes NO decisions │
                                                    │   ✅ Only executes      │
                                                    │      orders from bot    │
                                                    │   ✅ Provides data      │
                                                    │   ✅ Shows positions    │
                                                    └─────────────────────────┘
```

---

## 🚀 First Time Setup (5 Minutes)

### Step 1: Install Dependencies

```bash
cd NiftyBot
pip install -r requirements.txt
```

### Step 2: Get Kite API Credentials

1. Go to https://kite.trade/
2. Create app or use existing
3. Copy your **API Key**
4. Generate **Access Token** (expires daily)

### Step 3: Configure Credentials

```bash
cp .env.example .env
nano .env  # or use any text editor
```

Add your credentials:
```
KITE_API_KEY=your_actual_api_key_here
KITE_ACCESS_TOKEN=your_actual_access_token_here
```

### Step 4: Configure Trading Parameters (Optional)

Edit `niftybot.py` if you want to change defaults:

```python
class Config:
    MAX_TRADES_PER_DAY = 5      # Default: 5 trades max
    LOT_SIZE = 75               # Default: 1 lot (75 qty)
    RISK_PER_TRADE_PCT = 2.0    # Default: Risk 2% per trade
    MAX_DAILY_LOSS_PCT = 5.0    # Default: Stop at 5% loss
    ATR_MULTIPLIER_SL = 1.5     # Default: SL at 1.5x ATR
    ATR_MULTIPLIER_TARGET = 2.5 # Default: Target at 2.5x ATR
```

---

## 🎮 Daily Usage (Recommended Setup)

### Morning Routine (Before 9:15 AM)

```bash
# 1. Generate NEW access token (expires daily)
# Go to Kite, regenerate token, update .env

# 2. Start the main bot
python niftybot.py
```

### Monitoring (Optional but Recommended)

Open **2 additional terminal windows**:

```bash
# Terminal 2: Live Dashboard (updates every 5 seconds)
python monitor.py

# Terminal 3: Keep Kite web open
# https://kite.zerodha.com
```

---

## 📊 What You'll See

### Terminal 1: Main Bot

```
═══════════════════════════════════════════════════════════
🚀 NIFTYBOT STARTED
═══════════════════════════════════════════════════════════
Configuration:
  Max Trades/Day: 5
  Lot Size: 75
  Risk per Trade: 2.0%
  ...

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
2025-11-28 10:43:07 - INFO - Order placed: BUY 75 NIFTY25JAN0224000CE
2025-11-28 10:43:09 - INFO - Position added @ 150.0, SL: 127.5, TGT: 187.5

... (bot continues monitoring) ...

2025-11-28 10:58:34 - INFO - Target hit: LTP 190.0 >= TGT 187.5
2025-11-28 10:58:36 - INFO - Position closed, P&L: 3000.00
```

### Terminal 2: Live Monitor

```
════════════════════════════════════════════════════════════
              🤖 NIFTYBOT LIVE MONITOR
════════════════════════════════════════════════════════════
🟢 Status: RUNNING
🕐 Last Update: 2025-11-28 10:58:36

────────────────────────────────────────────────────────────
MARKET MODE
────────────────────────────────────────────────────────────
📈 TRENDING

────────────────────────────────────────────────────────────
TRADING SUMMARY
────────────────────────────────────────────────────────────
Trades Today: 1/5
Open Positions: 0
💰 Daily P&L: ₹3000.00
════════════════════════════════════════════════════════════
```

---

## 🎛️ How to Control

### Stop Trading (Emergency or End of Day)

```bash
# In Terminal 1 (main bot):
Press Ctrl+C

# Bot will:
# ✅ Automatically square off ALL open positions
# ✅ Show final P&L
# ✅ Exit cleanly
```

### Manually Close Positions

**Method 1: Control Panel**
```bash
python control.py
# Choose option 4: Close All Positions
```

**Method 2: Kite Web**
1. Go to https://kite.zerodha.com
2. Positions → Click "Exit" on position
3. Bot detects and updates automatically

### Change Settings Mid-Day

1. Stop bot: `Ctrl+C`
2. Edit `niftybot.py` Config class
3. Restart bot: `python niftybot.py`

---

## 📈 Example Trade Lifecycle

```
9:15 AM  ► Bot starts, collects data

9:35 AM  ► "Day type detected: TRENDING"
          Bot now uses trend continuation strategy

10:42 AM ► Price pulls back to VWAP

10:43 AM ► Signal triggered: "BUY_CE"
          ► Option selected: NIFTY25JAN0224000CE
          ► Liquidity checked: OI 45000 ✅, Spread 0.5% ✅
          ► Order placed: BUY 75 @ ₹150
          ► Stop-loss set: ₹127.5 (1.5x ATR)
          ► Target set: ₹187.5 (2.5x ATR)

10:43-10:58 ► Bot monitors every 10 seconds
              Checks if LTP hits SL or Target

10:58 AM ► Target hit! LTP = ₹190 >= ₹187.5
          ► Order placed: SELL 75 @ ₹190
          ► P&L: +₹3,000 (₹40 × 75)
          ► Trade count: 1/5

          Bot continues looking for next signal...
```

---

## ⚠️ Important Daily Tasks

### Every Morning:
- [ ] Generate NEW Kite access token
- [ ] Update `.env` file
- [ ] Review yesterday's `niftybot.log`
- [ ] Start bot before 9:15 AM

### During Trading:
- [ ] Check monitor dashboard periodically
- [ ] Verify bot is responding (check last update time)
- [ ] Keep Kite web open as backup

### End of Day:
- [ ] Verify all positions squared off (by 3:15 PM)
- [ ] Review `niftybot.log` for the day
- [ ] Note P&L and trade count
- [ ] Stop bot if still running

---

## 🔧 Common Controls

| What You Want | How to Do It |
|---------------|--------------|
| Start bot | `python niftybot.py` |
| Stop bot | Press `Ctrl+C` in bot terminal |
| See live dashboard | `python monitor.py` (separate terminal) |
| Close positions manually | `python control.py` → Option 4 |
| View logs | `tail -f niftybot.log` |
| View in Kite | https://kite.zerodha.com → Positions |
| Change max trades | Edit `Config.MAX_TRADES_PER_DAY` in niftybot.py |
| Change lot size | Edit `Config.LOT_SIZE` in niftybot.py |
| Tighter stop-loss | Lower `Config.ATR_MULTIPLIER_SL` (e.g., 1.0) |
| Further target | Increase `Config.ATR_MULTIPLIER_TARGET` (e.g., 3.0) |

---

## ❓ Quick FAQ

**Q: Does the bot need my permission to trade?**
A: No. Once started, it's 100% autonomous until you stop it.

**Q: Can I leave it running unattended?**
A: Technically yes, but **NOT RECOMMENDED**. Always monitor.

**Q: What if I lose internet connection?**
A: Bot crashes. Positions stay open. Close manually via Kite mobile app.

**Q: How do I stop just new trades but keep monitoring existing?**
A: Set `MAX_TRADES_PER_DAY = 0` in Config, restart bot.

**Q: Can I change stop-loss after trade is placed?**
A: Not automatically. Use `python control.py` or Kite web to modify.

**Q: Does Kite make any decisions?**
A: **NO**. Kite only executes what the bot tells it to do.

---

## 📚 Full Documentation

- **MONITORING_GUIDE.md** - Complete monitoring and control guide
- **README.md** - Full feature documentation
- **niftybot.py** - Well-commented source code

---

## 🚨 Emergency Stop

```bash
# In bot terminal:
Ctrl+C

# Bot immediately:
# 1. Squares off all positions
# 2. Shows final P&L
# 3. Exits

# THAT'S IT!
```

---

## 🎯 Summary

1. **Bot is in charge** - It decides everything
2. **Kite just executes** - No decision-making
3. **You can monitor** - 4 different ways
4. **You can override** - Manual close anytime
5. **You can stop** - Ctrl+C auto-exits safely

**Start simple, monitor closely, adjust as needed!** 🚀
