# Live Trading Setup Guide
## NiftyBot - Options Trading System

**⚠️ CRITICAL: Read this ENTIRE document before trading with real money**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Paper Trading Phase](#paper-trading-phase)
3. [Live Trading Setup](#live-trading-setup)
4. [Risk Management](#risk-management)
5. [Daily Operations](#daily-operations)
6. [Emergency Procedures](#emergency-procedures)
7. [Performance Monitoring](#performance-monitoring)
8. [Scaling Up](#scaling-up)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Before You Start

✅ **Capital Requirements:**
- Minimum: ₹50,000 (₹25,000 trading + ₹25,000 buffer)
- Recommended: ₹200,000 (₹150,000 trading + ₹50,000 buffer)
- NEVER trade with money you can't afford to lose

✅ **Knowledge Requirements:**
- Understand options basics (calls, puts, Greeks)
- Know what stop loss and trailing stop mean
- Understand the risks of options trading
- Have traded options manually before

✅ **Technical Requirements:**
- Kite Connect API access
- Stable internet connection
- Computer that can run 24/7 during market hours
- Backup power supply (UPS)

✅ **Psychological Requirements:**
- Can handle losing days without panic
- Won't override bot decisions emotionally
- Can follow rules strictly
- Have realistic expectations (not expecting 4000% returns)

---

## Paper Trading Phase

### Week 1-2: Observation Mode

**Goal:** Understand how the system works

```bash
# Configure for paper trading
vim live_trading_config.py

# Set these values:
LIVE_TRADING_ENABLED = False
PAPER_TRADING_ENABLED = True
REQUIRE_MANUAL_CONFIRMATION = True
```

**Tasks:**
1. Run the bot in paper mode every day
2. Watch every signal it generates
3. Record why each trade was taken
4. Check if signals make sense
5. Verify position sizing is correct

**Success Criteria:**
- ✅ Bot runs without crashes
- ✅ Signals are logical
- ✅ Position sizes are reasonable
- ✅ Stop losses are set correctly

### Week 3-4: Active Paper Trading

**Goal:** Validate strategy performance

```bash
# Run paper trading
python run_bot.py --mode paper
```

**Track These Metrics:**
| Metric | Target | Your Result |
|--------|--------|-------------|
| Win Rate | > 40% | ___% |
| Sharpe Ratio | > 1.0 | ___ |
| Max Drawdown | < 30% | ___% |
| Profit Factor | > 1.2 | ___ |
| Avg Win | > Avg Loss | ___ |

**Success Criteria:**
- ✅ Win rate > 40%
- ✅ At least 20 paper trades executed
- ✅ No system crashes or errors
- ✅ Risk controls working (stop losses hit)
- ✅ Comfortable with the strategy

**If Criteria Not Met:**
- ❌ Don't go live yet
- 📊 Analyze what went wrong
- 🔧 Adjust parameters
- 🔁 Repeat paper trading for 2 more weeks

---

## Live Trading Setup

### Step 1: Configure Risk Limits

Edit `live_trading_config.py`:

```python
# START CONSERVATIVE!
LIVE_RISK_LIMITS = RiskLimits(
    max_loss_per_day=5000,          # ₹5K max loss (2.5% of ₹200K)
    max_trades_per_day=2,           # Max 2 trades
    max_position_size=30000,        # ₹30K per trade
    max_open_positions=1,           # Only 1 position at a time
    max_consecutive_losses=2,       # Stop after 2 losses
)
```

**IMPORTANT:**
- Start with **10% of your capital** (if you have ₹200K, use ₹20K limits)
- Increase limits by 20% per week (ONLY if profitable)
- Never risk more than 2% per trade

### Step 2: Enable Live Trading

```python
# In live_trading_config.py
LIVE_TRADING_ENABLED = True          # ⚠️  REAL MONEY MODE
PAPER_TRADING_ENABLED = False        # Disable paper mode
REQUIRE_MANUAL_CONFIRMATION = True   # Keep this ON for first week
```

### Step 3: Configure Alerts

**Telegram Setup (Recommended):**
1. Create Telegram bot: Talk to @BotFather
2. Get bot token
3. Get your chat ID: Talk to @userinfobot
4. Add to config:

```python
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "your_bot_token_here"
TELEGRAM_CHAT_ID = "your_chat_id_here"
```

### Step 4: Test Connection

```bash
# Test API connection
python -c "from executor.trade_executor import KiteExecutor; \
    executor = KiteExecutor(); \
    print('Connected!' if executor.connect() else 'Failed!')"
```

### Step 5: First Live Trade

**Pre-flight Checklist:**
- [ ] Risk limits are conservative
- [ ] Manual confirmation is ON
- [ ] Alerts are working
- [ ] You're at your computer
- [ ] Market is open
- [ ] You're mentally ready

```bash
# Start live trading
python run_bot.py --mode live

# You'll see:
# 🔴 LIVE TRADING MODE ACTIVE
# ⚠️  Manual confirmation required
```

**When First Signal Appears:**
1. Read the signal details carefully
2. Check if it makes sense
3. Verify position size is correct
4. Verify stop loss is set
5. Type 'yes' to confirm (or 'no' to reject)

---

## Risk Management

### Multi-Layered Protection

The system has **7 layers** of protection:

#### Layer 1: Pre-Trade Validation
Every trade is checked for:
- ✅ Position size within limits
- ✅ Sufficient capital available
- ✅ Not exceeding daily trade limit
- ✅ Stop loss is reasonable
- ✅ Symbol not blocked

**If ANY check fails → Trade rejected**

#### Layer 2: Daily Loss Limit
```python
max_loss_per_day = ₹5,000
```

**What happens:**
- When daily loss hits ₹5K → Trading stops
- Circuit breaker activates
- Cool-off until next day
- No override possible

#### Layer 3: Consecutive Loss Protection
```python
max_consecutive_losses = 2
```

**What happens:**
- After 2 losses in a row → 1 hour pause
- Prevents revenge trading
- Prevents catching falling knife

#### Layer 4: Position Concentration
```python
max_open_positions = 1
max_positions_per_symbol = 1
```

**What happens:**
- Can't have too many positions
- Can't double down on losing position
- Prevents over-leverage

#### Layer 5: Capital Deployment
```python
max_capital_deployed = ₹50,000
```

**What happens:**
- Only 25% of capital deployed at once
- Rest kept as buffer
- Prevents account wipeout

#### Layer 6: Circuit Breaker
**Auto-triggers on:**
- Daily loss limit hit
- Weekly loss limit hit
- Consecutive losses
- Rapid drawdown

**Effect:**
- All trading halts
- Existing positions monitored
- Cool-off period enforced
- Manual restart required

#### Layer 7: Kill Switch
**Nuclear option - use when:**
- Catastrophic losses
- System malfunction
- Market crash
- Need to stop everything NOW

```python
# Activate kill switch
from executor.risk_manager import RiskManager
risk_mgr = RiskManager()
risk_mgr.activate_kill_switch("Market crash")
```

**Effect:**
- EVERYTHING stops
- Existing positions must be closed manually
- Requires manual reactivation
- Logs emergency event

---

## Daily Operations

### Pre-Market Routine (Before 9:15 AM)

**Every Trading Day:**

```bash
# 1. Check system status
python check_status.py

# 2. Review yesterday's performance
python show_performance.py

# 3. Check risk limits
python live_trading_config.py  # Should print config

# 4. Start monitoring
python run_bot.py --mode live
```

**Checklist:**
- [ ] Internet connection stable
- [ ] Kite API working
- [ ] Yesterday's P&L reviewed
- [ ] Risk limits appropriate
- [ ] Ready to monitor

### During Market Hours (9:15 AM - 3:30 PM)

**Monitor Every:**
- ⏰ Every 15 minutes: Check open positions
- ⏰ Every 30 minutes: Check daily P&L
- ⏰ Every hour: Check risk status

**Watch For:**
- 🟢 Positions hitting target (take profit!)
- 🔴 Positions hitting stop loss (accept loss)
- ⚠️  Daily loss approaching limit
- 📊 Unusual market moves

**DO:**
- ✅ Let the system work
- ✅ Monitor but don't interfere
- ✅ Take notes on unusual events
- ✅ Check alerts immediately

**DON'T:**
- ❌ Override stop losses
- ❌ Add to losing positions
- ❌ Disable risk controls
- ❌ Panic on red candles
- ❌ Get greedy on green candles

### Post-Market Routine (After 3:30 PM)

```bash
# 1. Review today's trades
python show_trades.py --date today

# 2. Update trading journal
vim journal/$(date +%Y-%m-%d).md

# 3. Check performance metrics
python show_performance.py --week

# 4. Save state
# (Automatic, but verify logs exist)
ls -la data/risk/
```

**Journaling Template:**

```markdown
# YYYY-MM-DD Trading Journal

## Performance
- Daily P&L: ₹_____
- Trades: ___
- Win Rate: ___%
- Largest Win: ₹_____
- Largest Loss: ₹_____

## Trades
1. Symbol: _____ | Entry: _____ | Exit: _____ | P&L: _____
   - Reason for entry: _____
   - Reason for exit: _____
   - Lessons: _____

## What Went Well
- _____

## What Went Wrong
- _____

## Improvements for Tomorrow
- _____
```

---

## Emergency Procedures

### Scenario 1: Rapid Loss (Position Down > 15%)

**Immediate Actions:**
1. Check if stop loss is set correctly
2. If no stop loss → Exit immediately manually:
   ```bash
   python emergency_exit.py --symbol NIFTY24500CE
   ```
3. Activate circuit breaker if needed
4. Review what went wrong

### Scenario 2: System Crash

**If Bot Crashes:**
1. Check open positions:
   ```bash
   python check_positions.py
   ```
2. Manually set stop losses on open positions via Kite
3. Restart bot:
   ```bash
   python run_bot.py --mode live --recover
   ```
4. Review logs:
   ```bash
   tail -100 logs/error.log
   ```

### Scenario 3: Daily Loss Limit Hit

**Auto-Response:**
- Circuit breaker activates automatically
- All new trading stops
- Open positions monitored
- Cool-off until next day

**Manual Steps:**
1. Let open positions hit stops or targets
2. Don't try to "win it back"
3. Review what went wrong
4. Adjust strategy if needed
5. Come back tomorrow with clear head

### Scenario 4: Internet/Power Outage

**Preparation (Before Outage):**
- Set stop losses on all positions
- Have mobile data backup
- Have UPS for computer

**During Outage:**
1. Use mobile Kite app to check positions
2. Manually close positions if needed
3. Don't panic

**After Outage:**
1. Verify bot state:
   ```bash
   python check_status.py
   ```
2. Verify open positions match bot records
3. Resume trading only if confident

### Scenario 5: Need to Stop Everything NOW

**KILL SWITCH:**

```bash
# Method 1: Via script
python activate_kill_switch.py

# Method 2: Via Python
python -c "from executor.risk_manager import RiskManager; \
    rm = RiskManager(); \
    rm.activate_kill_switch('Manual override')"

# Method 3: Delete risk state file (emergency)
rm data/risk/risk_state.json
```

**After Kill Switch:**
- Trading is DISABLED
- Close all positions manually via Kite
- Review what happened
- Fix issues
- Only reactivate when confident

---

## Performance Monitoring

### Daily Metrics

Track these **every day**:

| Metric | Formula | Target | Warning |
|--------|---------|--------|---------|
| Win Rate | Winners / Total Trades | > 45% | < 40% |
| Profit Factor | Total Wins / Total Losses | > 1.5 | < 1.2 |
| Avg Win:Loss | Avg Win / Avg Loss | > 1.5:1 | < 1:1 |
| Sharpe Ratio | Return / Volatility | > 1.0 | < 0.5 |
| Max Drawdown | Peak to Trough | < 20% | > 30% |

### Weekly Review

Every Sunday:

```bash
# Generate weekly report
python generate_report.py --week

# Check metrics
python show_metrics.py --period week
```

**Questions to Ask:**
1. Was this week profitable?
2. Did I follow the rules?
3. What was my biggest mistake?
4. What worked well?
5. Should I adjust anything?

### Monthly Review

Every month:

**Compare to Targets:**
| Metric | Month 1 | Month 2 | Month 3 | Target |
|--------|---------|---------|---------|--------|
| Total Return | ___% | ___% | ___% | > 5% |
| Win Rate | ___% | ___% | ___% | > 45% |
| Sharpe | ___ | ___ | ___ | > 1.0 |
| Max DD | ___% | ___% | ___% | < 20% |
| Trades | ___ | ___ | ___ | > 20 |

**Decision Point:**
- ✅ **If all targets met:** Continue or scale up 20%
- ⚠️  **If some targets missed:** Review and adjust
- ❌ **If most targets missed:** Stop and restrategize

---

## Scaling Up

### Progression Path

**Week 1:** Paper trading only
**Week 2-3:** Paper trading with confidence
**Week 4:** First live trades (10% capital, 1 trade/day)

**Month 2** (if profitable in Month 1):
- Increase to 20% capital
- 2 trades per day
- Adjust limits:
  ```python
  max_loss_per_day = 7500  # Up from 5000
  max_position_size = 45000  # Up from 30000
  max_open_positions = 2  # Up from 1
  ```

**Month 3** (if Month 2 also profitable):
- Increase to 40% capital
- 3 trades per day
- More aggressive limits

**Month 4+** (consistent profitability):
- Full capital (75% deployed, 25% buffer)
- Use AGGRESSIVE_RISK_LIMITS
- Consider adding second bot (BANKNIFTY)

### Scaling Rules

**NEVER:**
- ❌ Scale up after one lucky week
- ❌ Scale up to recover losses
- ❌ Use full capital in first month
- ❌ Increase risk after losses

**ALWAYS:**
- ✅ Scale up slowly (20% per month max)
- ✅ Scale up only after consistent profits
- ✅ Keep 25% capital as buffer
- ✅ Scale back down if start losing

---

## Troubleshooting

### Problem: No Trades Being Taken

**Possible Causes:**
1. ADX threshold too high
2. Market not trending
3. Risk limits too tight
4. Kill switch active

**Solutions:**
```bash
# Check bot status
python check_status.py

# Check recent signals (even rejected ones)
tail -50 logs/signals.log | grep REJECTED

# Review ADX values
python check_indicators.py --symbol NIFTY
```

### Problem: Too Many Losses

**Possible Causes:**
1. Overfitting to backtest
2. Market conditions changed
3. Stop losses too tight
4. Signals not good

**Solutions:**
- Review each losing trade
- Check if stop losses are reasonable
- Consider tightening entry criteria (higher ADX)
- Take a break, paper trade again

### Problem: Slippage Too High

**Possible Causes:**
1. Low liquidity options
2. Market orders on volatile moves
3. Bad timing

**Solutions:**
```python
# In live_trading_config.py
MIN_OPTION_VOLUME = 500  # Higher volume requirement
MAX_BID_ASK_SPREAD_PERCENT = 2.0  # Tighter spread
```

### Problem: Bot Keeps Stopping

**Possible Causes:**
1. API connection issues
2. Daily loss limit hit
3. Consecutive losses
4. System errors

**Solutions:**
```bash
# Check logs
tail -100 logs/error.log

# Check risk state
cat data/risk/risk_state.json

# Check circuit breaker
python check_risk_manager.py
```

---

## Final Checklist

Before going live, confirm:

### Technical
- [ ] Paper traded for 2+ weeks
- [ ] Win rate > 40% in paper trading
- [ ] Bot runs without crashes
- [ ] Risk controls tested and working
- [ ] Alerts configured and tested
- [ ] Backup plan for outages

### Financial
- [ ] Have minimum ₹50K capital
- [ ] Can afford to lose this money
- [ ] Risk limits set conservatively
- [ ] Starting with 10% of capital
- [ ] Buffer capital reserved

### Psychological
- [ ] Understand this is risky
- [ ] Comfortable with losing days
- [ ] Won't override bot emotionally
- [ ] Have realistic expectations
- [ ] Will follow rules strictly

### Knowledge
- [ ] Read this entire guide
- [ ] Understand options basics
- [ ] Know how stop losses work
- [ ] Know how to use kill switch
- [ ] Know emergency procedures

---

## Support & Resources

### Documentation
- `README.md` - Project overview
- `BACKTEST_ANALYSIS.md` - Backtest results and caveats
- This guide - Live trading setup

### Code
- `live_trading_config.py` - Configuration
- `executor/risk_manager.py` - Risk management
- `executor/paper_trading.py` - Paper trading
- `executor/monitoring.py` - Real-time monitoring

### Commands
```bash
# Show help
python run_bot.py --help

# Check status
python check_status.py

# Show performance
python show_performance.py

# Emergency exit all
python emergency_exit.py --all

# Activate kill switch
python activate_kill_switch.py
```

### Getting Help
- Issues: https://github.com/venutrue/NiftyBot/issues
- Review logs: `logs/error.log`, `logs/trade.log`
- Emergency contacts (in config)

---

## Disclaimer

**⚠️ IMPORTANT:**

1. **No Guarantees:** Past performance (even in paper trading) does NOT guarantee future results
2. **High Risk:** Options trading is extremely risky. You can lose 100% of your capital
3. **Your Responsibility:** You are responsible for your trades. The bot is a tool, not financial advice
4. **Start Small:** Always start with capital you can afford to lose completely
5. **Bugs Exist:** This is software - bugs are possible. Always monitor manually
6. **No Liability:** The creators of this bot are not responsible for your losses

**By going live, you acknowledge:**
- You understand the risks
- You've tested thoroughly in paper mode
- You won't blame the bot for losses
- You'll follow risk management rules strictly
- You can afford to lose the capital you're trading with

---

## Good Luck!

Remember:
- **Slow and steady wins the race**
- **Protect capital first, make profits second**
- **Follow the rules even when it's hard**
- **Learn from every trade**
- **Stay humble**

May your stops be small and your targets be hit! 🎯
