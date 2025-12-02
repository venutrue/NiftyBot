# Paper Trading Quick Start Guide
## Test Your Strategy Without Risk

---

## What is Paper Trading?

**Paper trading = Practice trading with fake money**

- ✅ Real market prices
- ✅ Real signals from your strategy
- ✅ Simulated order execution
- ✅ Tracks P&L, win rate, Sharpe ratio
- ❌ **NO real money at risk**

Think of it like a flight simulator for traders.

---

## Quick Start (3 Steps)

### Step 1: Start Paper Trading

```bash
# Easy way (recommended)
./start_paper_trading.sh

# Or directly
python run.py --paper --bot nifty
```

### Step 2: Let It Run

- Bot will scan for signals every 5 minutes
- When it finds a signal, it will "execute" (simulate)
- You'll see logs like:

```
📄 Paper trade executed: BUY 50 x NIFTY24500CE @ ₹125.50
```

- Let it run for at least 2-4 weeks

### Step 3: Check Results

```bash
python scripts/show_performance.py --mode paper
```

---

## What You'll See

### During Trading

```
2025-12-02 10:15:30 | INFO | PAPER_EXEC | 📄 Paper trade executed: BUY 50 x NIFTY24500CE @ ₹125.50
2025-12-02 10:45:22 | INFO | PAPER_EXEC | 📄 Paper position closed: NIFTY24500CE | P&L: ₹2,450 | Total: ₹2,450
2025-12-02 11:30:15 | INFO | PAPER_EXEC | 📄 Paper trade executed: BUY 50 x NIFTY24600CE @ ₹98.75
```

### End of Day Summary

```
======================================================================
PAPER TRADING PERFORMANCE SUMMARY
======================================================================

💰 CAPITAL:
  Initial: ₹2,00,000
  Current: ₹2,04,500
  P&L: ₹4,500 (+2.25%)

📊 TRADES:
  Total: 5
  Winners: 3 (60.0%)
  Losers: 2
  Open: 0

📈 PERFORMANCE:
  Avg Win: ₹2,450
  Avg Loss: ₹-1,200
  Profit Factor: 1.53
  Max Drawdown: 3.25%
```

---

## Important Settings

### Starting Capital
Default: ₹2,00,000 (matches live capital)

To change:
```python
# In run.py line 285
executor = PaperTradeExecutor(initial_capital=100000)  # ₹1L
```

### Which Bot to Run

```bash
# Just NIFTY (recommended to start)
python run.py --paper --bot nifty

# Just BANKNIFTY
python run.py --paper --bot banknifty

# Both
python run.py --paper --bot nifty,banknifty
```

### Scan Interval

```bash
# Check every 5 minutes (default)
python run.py --paper --bot nifty --interval 300

# Check every 1 minute (more signals, more data)
python run.py --paper --bot nifty --interval 60
```

---

## Daily Routine

### Morning (Before Market Opens)

```bash
# Check yesterday's results
python scripts/show_performance.py --mode paper
```

### During Market Hours

```bash
# Start paper trading
./start_paper_trading.sh

# Let it run, monitor the logs
# Don't need to do anything - just watch
```

### Evening (After Market Closes)

```bash
# Review performance
python scripts/show_performance.py --mode paper

# Update your journal
# Note: What worked? What didn't?
```

---

## What to Track

Keep a simple spreadsheet:

| Date | Trades | P&L | Win Rate | Notes |
|------|--------|-----|----------|-------|
| 2025-12-02 | 5 | ₹4,500 | 60% | Good trending day |
| 2025-12-03 | 3 | ₹-1,200 | 33% | Choppy market |
| ... | ... | ... | ... | ... |

---

## Success Criteria (After 2-4 Weeks)

**Ready for live trading if:**

| Metric | Target | Your Result |
|--------|--------|-------------|
| **Win Rate** | > 40% | ___% |
| **Total Trades** | > 20 | ___ |
| **Profit Factor** | > 1.2 | ___ |
| **Max Drawdown** | < 30% | ___% |
| **Sharpe Ratio** | > 1.0 | ___ |

**If you hit all targets:**
- ✅ Consider going live with 10% capital
- ✅ Read LIVE_TRADING_GUIDE.md first

**If you miss targets:**
- ❌ Keep paper trading
- 🔧 Adjust strategy parameters
- 📊 Analyze what went wrong

---

## Common Questions

### Q: How long should I paper trade?
**A:** Minimum 2 weeks, recommended 4 weeks. You need at least 20 trades to have meaningful data.

### Q: Can I paper trade outside market hours?
**A:** No, needs real market data. Only runs 9:15 AM - 3:30 PM.

### Q: Will my paper trading results match live?
**A:** Probably not exactly. Paper trading is optimistic because:
- No slippage (simulated as 0.5%)
- Perfect fills
- No emotional decisions

Expect live results to be 10-20% worse.

### Q: Can I paper trade multiple strategies at once?
**A:** Yes! Run multiple instances:
```bash
# Terminal 1
python run.py --paper --bot nifty

# Terminal 2
python run.py --paper --bot banknifty
```

Each tracks separately.

### Q: Where is the data stored?
**A:** `data/paper_trading/paper_session.json`

To reset and start fresh:
```bash
rm data/paper_trading/paper_session.json
```

### Q: Can I change parameters mid-session?
**A:** Yes, but better to finish current session and start fresh with new parameters.

---

## Troubleshooting

### Problem: No trades happening

**Possible causes:**
- Market not trending (ADX < threshold)
- Already hit daily trade limit
- No signals meeting criteria

**Solution:**
```bash
# Check last 50 log entries for rejected signals
tail -50 logs/bot.log | grep -i "signal\|reject"
```

### Problem: All trades are losses

**Possible causes:**
- Stop losses too tight
- Poor market conditions
- Strategy not suitable for current market

**Solution:**
- Review each losing trade
- Check if stops are reasonable (15-20%)
- Consider adjusting ADX threshold

### Problem: Bot crashes

**Check logs:**
```bash
tail -100 logs/error.log
```

Most common issue: Internet connection dropped

---

## Next Steps

After 2-4 weeks of successful paper trading:

1. **Review Results**
   - Win rate > 40%? ✅
   - Profit factor > 1.2? ✅
   - Comfortable with the strategy? ✅

2. **Read Live Trading Guide**
   - `LIVE_TRADING_GUIDE.md` (MUST READ!)

3. **Start Small**
   - 10% of capital only
   - 1 trade per day
   - Manual confirmation ON

4. **Scale Gradually**
   - 20% increase per month
   - Only if profitable
   - Never rush

---

## Tips for Success

**DO:**
- ✅ Let paper trading run for full 2-4 weeks
- ✅ Track every metric in spreadsheet
- ✅ Note market conditions daily
- ✅ Be honest about results
- ✅ Adjust strategy if needed

**DON'T:**
- ❌ Cherry-pick good days
- ❌ Stop after one bad day
- ❌ Skip to live trading too early
- ❌ Expect 100% win rate
- ❌ Ignore warning signs

---

## Commands Cheat Sheet

```bash
# Start paper trading
./start_paper_trading.sh

# Or with custom settings
python run.py --paper --bot nifty --interval 300

# Check performance
python scripts/show_performance.py --mode paper

# Check system status
python scripts/check_status.py

# View logs
tail -f logs/bot.log

# Reset paper trading data
rm data/paper_trading/paper_session.json
```

---

## Example Session

**Day 1:**
```bash
$ ./start_paper_trading.sh
Starting bots...

📄 PAPER TRADING MODE - NO REAL MONEY AT RISK

2025-12-02 09:45:30 | Signal from NIFTYBOT: BUY NIFTY24500CE
2025-12-02 09:45:31 | 📄 Paper trade executed: BUY 50 x NIFTY24500CE @ ₹125.50

2025-12-02 10:15:22 | Target hit: NIFTY24500CE
2025-12-02 10:15:23 | 📄 Paper position closed: NIFTY24500CE | P&L: ₹2,450

[End of day]

PAPER TRADING PERFORMANCE SUMMARY
Total Trades: 3
Winners: 2 (66.7%)
P&L: ₹3,250 (+1.63%)
```

**After 2 weeks:**
```bash
$ python scripts/show_performance.py --mode paper

Total Return: +8.5%
Win Rate: 52%
Profit Factor: 1.45
Max Drawdown: 4.2%
Sharpe Ratio: 1.3

✅ All targets met! Ready to consider going live.
```

---

## Remember

**Paper trading is not optional.**

Would you fly a plane without simulator training?
Would you perform surgery without practice?

Same with trading. Test first, trade later.

**Your capital will thank you.** 🙏

---

Need help? Check:
- Main README: `README.md`
- Live trading guide: `LIVE_TRADING_GUIDE.md`
- Scripts help: `scripts/README.md`
