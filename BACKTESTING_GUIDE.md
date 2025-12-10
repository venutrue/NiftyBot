# 📊 Backtesting Guide - NiftyBot Trading System

Your trading bot includes a **professional-grade backtesting framework** that lets you test your strategy on historical data before risking real money.

---

## 🚀 Quick Start

### 1. Basic Backtest (Last 90 Days)

```bash
python run_backtest.py --bot NIFTYBOT --days 90
```

This will:
- ✅ Test NiftyBot on last 90 days of data
- ✅ Use the "balanced" strategy preset
- ✅ Start with ₹5,00,000 capital
- ✅ Show detailed performance metrics

---

### 2. Test Different Strategy Presets

```bash
# Conservative (lower risk, higher quality signals)
python run_backtest.py --bot NIFTYBOT --strategy conservative

# Aggressive (higher risk, more trades)
python run_backtest.py --bot NIFTYBOT --strategy aggressive

# Scalper (quick in/out, tight stops)
python run_backtest.py --bot NIFTYBOT --strategy scalper

# Trend Follower (ride big moves with trailing stops)
python run_backtest.py --bot NIFTYBOT --strategy trend_follower
```

---

### 3. List All Available Strategies

```bash
python run_backtest.py --list-strategies
```

Shows all strategy presets with their parameters and comparison table.

---

## 📈 Understanding Strategy Presets

### **Conservative**
- **Risk per Trade:** 0.5%
- **Stop Loss:** 25%
- **ADX Threshold:** 28 (strong trends only)
- **Best For:** Capital preservation, steady growth
- **Expected:** Lower returns, fewer drawdowns

### **Balanced** (Default)
- **Risk per Trade:** 1%
- **Stop Loss:** 20%
- **ADX Threshold:** 23 (moderate trends)
- **Best For:** Most traders, good starting point
- **Expected:** Moderate returns, acceptable risk

### **Aggressive**
- **Risk per Trade:** 2%
- **Stop Loss:** 15%
- **ADX Threshold:** 20 (more signals)
- **Best For:** Experienced traders, higher risk appetite
- **Expected:** Higher returns, larger drawdowns

---

## 🎯 Examples

```bash
# Test with ₹10 Lakhs capital
python run_backtest.py --bot NIFTYBOT --capital 1000000

# Test with 2% risk per trade
python run_backtest.py --bot NIFTYBOT --risk 0.02

# Test last 6 months
python run_backtest.py --bot NIFTYBOT --days 180

# Test BankNifty
python run_backtest.py --bot BANKNIFTYBOT --days 90

# Test both bots
python run_backtest.py --bot ALL --strategy balanced
```

---

## 📊 Understanding Results

### **Key Metrics**

| Metric | Excellent | Good | Poor |
|--------|-----------|------|------|
| **Win Rate** | > 60% | 50-60% | < 50% |
| **Profit Factor** | > 2.0 | 1.5-2.0 | < 1.5 |
| **Sharpe Ratio** | > 1.5 | 1.0-1.5 | < 1.0 |
| **Max Drawdown** | < 10% | 10-20% | > 20% |
| **Return** | > 15%/yr | 10-15%/yr | < 10%/yr |

### **Red Flags** 🚩

- ❌ Win rate < 40% → Strategy isn't working
- ❌ Profit factor < 1.0 → Losing money!
- ❌ Max drawdown > 25% → Too risky
- ❌ Few trades (< 20) → Need more data

---

## 🎓 From Backtest to Live

### Step 1: Backtest (Historical Data)
```bash
python run_backtest.py --bot NIFTYBOT --days 180
```
**Goal:** Find settings that work consistently.

### Step 2: Paper Trade (Real-time, Fake Money)
```bash
python run.py --paper --bot NIFTYBOT
```
**Duration:** 2-4 weeks minimum

### Step 3: Live Trade (Start Small)
```bash
python run.py --bot NIFTYBOT
```
**Start:** 10% of intended capital

### Step 4: Scale Up
Once consistent for 1-2 months, scale to full capital.

---

## ⚠️ Important Notes

### **Backtest Limitations**

1. **Option Pricing Simplified**
   - Uses estimated option prices (not actual historical data)
   - Real prices affected by IV, theta, gamma

2. **Perfect Hindsight**
   - No slippage randomness
   - No order rejections
   - Always assumes fills at expected price

3. **Market Changes**
   - Past performance ≠ future results
   - Market conditions change

### **Best Practices**

✅ Test on at least 90 days of data
✅ Test across different market conditions
✅ Always paper trade before going live
✅ Start with small capital
✅ Monitor and adjust weekly

❌ Don't optimize until perfect (overfitting!)
❌ Don't skip paper trading
❌ Don't use 100% capital immediately

---

## 🐛 Troubleshooting

### "Failed to connect to Kite"
Check `.env` for valid API credentials.

### "No trades generated"
- Try longer period (--days 180)
- Try less strict strategy (--strategy aggressive)

---

**Remember:** Backtesting tests ideas, not guarantees. Always start with paper trading!

Good luck! 🚀
