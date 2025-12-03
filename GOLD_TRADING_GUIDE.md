# Gold Futures Trading Guide

Complete guide to trading MCX Gold Mini using the GoldBot strategy.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Key Differences: Gold vs Index Options](#key-differences)
3. [Strategy Explanation](#strategy)
4. [Prerequisites](#prerequisites)
5. [Quick Start](#quick-start)
6. [Symbol Format Verification](#symbol-verification)
7. [Trading Hours](#trading-hours)
8. [Risk Parameters](#risk-parameters)
9. [Performance Expectations](#expectations)
10. [Troubleshooting](#troubleshooting)

---

## Overview

**GoldBot** trades MCX Gold Mini futures using a trend-following strategy:

- **Commodity:** Gold Mini (100 grams)
- **Exchange:** MCX (Multi Commodity Exchange)
- **Timeframe:** 15-minute candles
- **Strategy:** Supertrend + ADX + EMA confluence
- **Trading Hours:** 9:00 AM - 11:30 PM
- **Max Trades:** 2 per day

---

## Key Differences: Gold vs Index Options

| Aspect | Index Options (NIFTY) | Gold Futures |
|--------|----------------------|--------------|
| **Product Type** | Options (wasting asset) | Futures (no theta decay) |
| **Exchange** | NFO | MCX |
| **Lot Size** | 50 (NIFTY) | 100 grams |
| **Timeframe** | 5-minute candles | 15-minute candles |
| **Entry Indicator** | VWAP + Supertrend + ADX | EMA + Supertrend + ADX |
| **Stop Loss** | 20% of premium | ₹250 absolute |
| **Trailing Stop** | Supertrend flip | ₹150 from high |
| **Trading Hours** | 9:15 AM - 3:30 PM | 9:00 AM - 11:30 PM |
| **Direction** | Buy CE or PE | Buy or Sell futures |
| **Margin** | Premium amount (₹5-10k) | SPAN margin (~₹6-8k) |
| **P&L Calculation** | (Exit - Entry) × Qty | (Exit - Entry) × 100 grams |
| **Expiry** | Weekly/Monthly | Monthly (5th of month) |
| **Theta Decay** | Yes (time value loss) | No |
| **Can Go Short?** | No (only buy options) | Yes (sell futures) |

---

## Strategy

### Entry Conditions (ALL must be true)

**For LONG (BUY):**
1. ✅ Supertrend is **bullish** (green)
2. ✅ ADX > 23 (strong trend)
3. ✅ Current price > 20 EMA (above moving average)

**For SHORT (SELL):**
1. ✅ Supertrend is **bearish** (red)
2. ✅ ADX > 23 (strong trend)
3. ✅ Current price < 20 EMA (below moving average)

### Exit Conditions

**Phase 1: Initial Stop Loss**
- Long: Exit if price drops ₹250 below entry
- Short: Exit if price rises ₹250 above entry

**Phase 2: Trailing Stop**
- Long: Trail ₹150 below highest price seen
- Short: Trail ₹150 above lowest price seen

**Phase 3: Supertrend Flip**
- Long: Exit immediately if Supertrend turns bearish
- Short: Exit immediately if Supertrend turns bullish

**Phase 4: End of Day**
- Force exit all positions at 11:00 PM (before 11:30 PM close)

---

## Prerequisites

### 1. Zerodha Account Setup

**Check MCX Access:**
- Log into Kite
- Go to Settings → Account → Segments
- Verify **MCX (Commodity)** is activated
- If not: Contact Zerodha support to enable MCX trading

**Data Subscription:**
- MCX data may require separate subscription
- Check: https://kite.zerodha.com/market-data
- Cost: ~₹200-300/month (verify with Zerodha)

### 2. Verify Symbol Format

**⚠️ CRITICAL:** The bot assumes symbol format: `GOLDMYYMMM` (e.g., `GOLDM25DEC`)

**Verify this:**
```python
# In Python console:
from kiteconnect import KiteConnect
kite = KiteConnect(api_key="your_key")
kite.set_access_token("your_token")

# Get MCX instruments
instruments = kite.instruments("MCX")

# Find Gold symbols
gold_symbols = [i for i in instruments if 'GOLD' in i['tradingsymbol']]
for g in gold_symbols:
    print(g['tradingsymbol'], g['expiry'])
```

**Common formats:**
- `GOLDM25DEC` (Gold Mini, Dec 2025)
- `GOLD25DECFUT` (Gold standard, Dec 2025)
- `MCX:GOLDM25DEC` (with exchange prefix)

**If format is different:** Edit `bots/goldbot.py` line 156-170 to match actual format.

### 3. Install Dependencies

```bash
cd NiftyBot
source venv/bin/activate  # Activate virtual environment
pip install kiteconnect pandas numpy
```

---

## Quick Start

### Step 1: Configure Credentials

Generate Kite access token:
```bash
python3 generate_token.py
```

This creates `.env` file with your credentials.

### Step 2: Start Paper Trading

**⚠️ MANDATORY:** Paper trade for 2-4 weeks before risking real money!

```bash
./start_gold_paper.sh
```

Or manually:
```bash
python3 run.py --paper --bot gold
```

### Step 3: Monitor Performance

Watch the terminal for:
- Entry signals (BUY/SELL with reasons)
- Position updates (stop loss trails)
- Exit signals (with P&L)

At end of day, you'll see:
```
PAPER TRADING PERFORMANCE SUMMARY
==================================

💰 CAPITAL:
  Initial: ₹2,00,000
  Current: ₹2,03,500
  P&L: ₹3,500 (+1.75%)

📊 TRADES:
  Total: 2
  Winners: 1 (50.0%)
  Losers: 1
  Open: 0

📈 PERFORMANCE:
  Avg Win: ₹5,200
  Avg Loss: ₹1,700
  Profit Factor: 3.06
  Max Drawdown: 0.85%
```

---

## Symbol Verification

### Method 1: Check via Kite Web

1. Log into https://kite.zerodha.com
2. Search for "GOLD" in search bar
3. Check MCX Gold contracts
4. Note the exact symbol format

### Method 2: Via Code

```python
from kiteconnect import KiteConnect

kite = KiteConnect(api_key="your_api_key")
kite.set_access_token("your_access_token")

# List all MCX instruments
mcx = kite.instruments("MCX")

# Filter Gold mini contracts
gold_mini = [i for i in mcx if 'GOLDM' in i['tradingsymbol']]

print("Gold Mini Contracts:")
for contract in gold_mini:
    print(f"Symbol: {contract['tradingsymbol']}")
    print(f"Expiry: {contract['expiry']}")
    print(f"Lot Size: {contract['lot_size']}")
    print("---")
```

### Method 3: Check Logs

When you start GoldBot, it logs:
```
Trading Gold contract: GOLDM25DEC
```

If you see error: **"Symbol not found"**, the format needs adjustment.

**Fix:** Edit `bots/goldbot.py`, function `_get_current_month_symbol()` (line 140-170)

---

## Trading Hours

### MCX Gold Trading Hours

**Regular Session:**
- Monday-Friday: 9:00 AM - 11:30 PM (14.5 hours!)

**Bot Active Hours:**
- Entry signals: 9:00 AM - 10:00 PM
- Position monitoring: 9:00 AM - 11:30 PM
- Force exit: 11:00 PM (30 min before close)

### Advantages of Long Hours

✅ **Flexibility:** Trade evening session (7-11 PM) if you have day job

✅ **More setups:** Longer timeframe = more trend opportunities

✅ **Global alignment:** US market hours overlap (9:30 PM onwards)

⚠️ **Overnight gaps:** Gold follows global markets (London, New York). Can gap at 9 AM based on overnight moves.

---

## Risk Parameters

### Position Sizing

**Conservative (Recommended):**
- Quantity: 1 contract (100 grams)
- Margin required: ~₹6,000-8,000
- Max loss per trade: ₹250 (stop loss)
- Position value: ~₹65,000 (at ₹65,000/100g)

**Aggressive (After 3 months success):**
- Quantity: 2-3 contracts
- Margin required: ~₹18,000-24,000
- Max loss per trade: ₹500-750
- Position value: ~₹1,30,000-1,95,000

### Stop Loss Logic

**Initial SL:** ₹250
- Based on typical Gold ATR (Average True Range)
- ~0.4% of Gold price (₹65,000)
- Prevents whipsaw in normal volatility

**Trailing SL:** ₹150
- Locks in profit as position moves in your favor
- Tighter than initial (let winners run)

### Daily Limits

- **Max trades:** 2 per day
- **Max loss:** ₹5,000 per day
- **Max consecutive losses:** 2 (then stop for the day)
- **Max open positions:** 1 at a time

---

## Performance Expectations

### Realistic Targets (based on trend-following strategies)

**Conservative Estimate:**
- Win rate: 35-45% (lower than backtest!)
- Average win: ₹3,000-5,000 per contract
- Average loss: ₹250-500 per contract
- Profit factor: 2.5-3.5
- Monthly return: 5-12%

**Why lower than index options?**
- Futures have no leverage multiplier like options
- Gold trends are slower (days/weeks, not hours)
- 15-min timeframe filters noise but catches fewer trades

**Good month:** 8-10 trades, 4-5 winners, +₹15,000-25,000

**Bad month:** 6-8 trades, 2-3 winners, -₹2,000 to +₹5,000

**Excellent month:** 12-15 trades, 7-8 winners, +₹30,000-40,000

### When to Go Live

✅ **After paper trading shows:**
- At least 20 completed trades
- Win rate > 35%
- Profit factor > 2.0
- Max drawdown < 10%
- 3-4 weeks of data

❌ **Don't go live if:**
- Less than 2 weeks paper trading
- Win rate < 30%
- Profit factor < 1.5
- You don't understand the strategy
- You haven't verified symbol format works

---

## Troubleshooting

### Issue 1: "Symbol not found" Error

**Cause:** Symbol format mismatch

**Fix:**
1. Verify actual symbol format (see [Symbol Verification](#symbol-verification))
2. Edit `bots/goldbot.py` line 168:
   ```python
   # Change from:
   symbol = f"{GOLD_SYMBOL}{year_code}{month_code}"

   # To match actual format (example):
   symbol = f"{GOLD_SYMBOL}{year_code}{month_code}FUT"
   # or
   symbol = f"MCX:{GOLD_SYMBOL}{month_code}{year_code}"
   ```

### Issue 2: No Data / Empty DataFrame

**Possible causes:**
1. MCX data subscription not active
2. Symbol format wrong (can't fetch data)
3. Outside trading hours
4. Weekend / market holiday

**Fix:**
1. Check if MCX is enabled in your account
2. Verify you have commodity data subscription
3. Check trading hours (9 AM - 11:30 PM weekdays)
4. Verify symbol exists: `kite.instruments("MCX")`

### Issue 3: No Signals Generated

**Causes:**
1. ADX < 23 (no strong trend)
2. Price not above/below EMA (no confirmation)
3. Supertrend neutral/choppy
4. Already have open position
5. Daily limits reached

**This is normal!** Gold trends develop slowly. Some days have zero signals.

**Expected signal frequency:**
- Active trending days: 1-2 signals
- Choppy/ranging days: 0 signals
- Average: 3-5 signals per week

### Issue 4: Positions Not Exiting

**Check:**
1. Is Supertrend still in same direction? (won't exit until flip)
2. Has stop loss been hit? (check logs)
3. Is it before 11 PM? (force exit happens at 11 PM)

**Debug:**
```bash
# Check active positions
grep "Position opened" logs/goldbot_*.log
grep "Position closed" logs/goldbot_*.log
```

### Issue 5: High Slippage

**Gold futures slippage:**
- Expected: ₹10-30 per contract
- High volume times (10 AM - 12 PM): Lower slippage
- Low volume times (2 PM - 5 PM): Higher slippage

**Paper trading simulates 0.5% slippage** (₹325 on ₹65,000)

**If live slippage > ₹100 consistently:**
- Trade only during high-volume hours
- Use limit orders instead of market orders
- Check if you're using Gold mini (lower slippage than standard Gold)

---

## Next Steps

### Phase 1: Paper Trading (Weeks 1-4)

✅ **Week 1:** Run bot, verify it works, understand signal generation

✅ **Week 2:** Monitor stop loss behavior, verify exits work correctly

✅ **Week 3:** Analyze results, check win rate and profit factor

✅ **Week 4:** Review performance summary, decide if strategy is viable

### Phase 2: Live Trading (Month 2+)

**Only if paper trading is successful:**

1. Start with 1 contract only
2. Keep same risk limits (₹250 SL, 2 trades/day)
3. Track performance daily
4. Review weekly (compare to paper trading)
5. Scale up slowly (1 contract → 2 contracts after 2 months)

### Phase 3: Optimization (Month 4+)

**If strategy proves profitable:**
- Adjust stop loss based on actual performance
- Test different timeframes (30-min, 1-hour)
- Consider adding Silver futures (similar strategy)
- Combine with index options (diversification)

---

## Important Reminders

⚠️ **Test symbol format first** - This is the #1 cause of bot failures

⚠️ **Paper trade minimum 2 weeks** - Don't rush to live trading

⚠️ **Gold can gap** - Unlike index options, Gold follows global markets. Overnight gaps are common.

⚠️ **Futures can go negative** - Unlike options (max loss = premium), futures can lose more than margin. That's why we have strict stop losses.

⚠️ **Check MCX holidays** - Commodity markets have different holidays than equity markets

⚠️ **Expiry rollover** - Gold expires 5th of every month. Bot automatically switches to next month contract.

---

## Support & Questions

**Symbol format issues?**
→ Check [Symbol Verification](#symbol-verification) section

**Strategy questions?**
→ Review [Strategy Explanation](#strategy) section

**Performance concerns?**
→ Check [Performance Expectations](#expectations) - lower win rate is normal for futures

**Technical errors?**
→ See [Troubleshooting](#troubleshooting) section

---

**Good luck with Gold trading! 🥇**

Remember: Paper trade first, verify everything works, then scale up slowly.
