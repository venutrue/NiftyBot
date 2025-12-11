# Stop-Loss Comparison Guide

This guide shows you how to compare **Fixed Percentage SL** vs **Technical SL** using backtesting.

---

## What's the Difference?

### Fixed Percentage SL (Default)
- **Rule**: Exit if option premium drops by X% from entry
- **Example**: Entry ₹454, 10% SL = Exit at ₹408.60
- **Pros**: Simple, predictable risk per trade
- **Cons**: Ignores market structure, may be too tight or too wide

### Technical SL (NEW)
- **Rule**: Exit if option premium breaks key technical level (low/high of last 2 candles)
- **Example**: Entry ₹454, last 2 candles low = ₹440, SL = ₹440 (capped to 10-20%)
- **Pros**: Respects market structure, adapts to volatility
- **Cons**: Variable risk per trade, more complex

---

## How to Run Comparison Backtests

### Step 1: Test Fixed 10% SL
```bash
python run_backtest.py \
  --bot NIFTYBOT \
  --days 90 \
  --capital 500000 \
  --strategy custom \
  --stop-loss 0.10 \
  --sl-method fixed
```

**Expected Output:**
```
POSITION MANAGEMENT:
  Stop Loss: Fixed 10%
  Target: 40%
  ...
```

### Step 2: Test Fixed 15% SL (NEW DEFAULT)
```bash
python run_backtest.py \
  --bot NIFTYBOT \
  --days 90 \
  --capital 500000 \
  --strategy custom \
  --stop-loss 0.15 \
  --sl-method fixed
```

### Step 3: Test Fixed 20% SL
```bash
python run_backtest.py \
  --bot NIFTYBOT \
  --days 90 \
  --capital 500000 \
  --strategy custom \
  --stop-loss 0.20 \
  --sl-method fixed
```

### Step 4: Test Technical SL
```bash
python run_backtest.py \
  --bot NIFTYBOT \
  --days 90 \
  --capital 500000 \
  --strategy custom \
  --sl-method technical
```

**Expected Output:**
```
POSITION MANAGEMENT:
  Stop Loss: Technical (option candle structure, capped 10-20%)
  Target: 40%
  ...
```

---

## Compare Results

After running all 4 tests, compare these metrics:

| Metric | Fixed 10% | Fixed 15% | Fixed 20% | Technical |
|--------|-----------|-----------|-----------|-----------|
| **Total Trades** | ? | ? | ? | ? |
| **Win Rate** | ? | ? | ? | ? |
| **Profit Factor** | ? | ? | ? | ? |
| **Total P&L** | ? | ? | ? | ? |
| **Max Drawdown** | ? | ? | ? | ? |
| **Sharpe Ratio** | ? | ? | ? | ? |

### What to Look For:
1. **Best Profit Factor** (>1.5 is good)
2. **Best Total P&L** (highest profit)
3. **Best Sharpe Ratio** (>1.0 is good)
4. **Lowest Max Drawdown** (less risk)

### Decision Rules:
- If **Technical SL** beats all fixed SL by >20% in Total P&L → Use Technical SL
- If **15% SL** is best → Stick with simple 15% (already configured)
- If results are marginal (<10% difference) → Choose simplest (15% fixed)

---

## Quick Comparison Script

Run all 4 tests automatically:

```bash
# Create a comparison script
cat > compare_sl_strategies.sh <<'EOF'
#!/bin/bash

echo "Starting Stop-Loss Comparison Backtest..."
echo "This will run 4 backtests (takes 10-15 minutes)"
echo ""

# Test 1: Fixed 10%
echo "========================================="
echo "TEST 1: Fixed 10% SL"
echo "========================================="
python run_backtest.py --bot NIFTYBOT --days 90 --strategy custom --stop-loss 0.10 --sl-method fixed

# Test 2: Fixed 15%
echo ""
echo "========================================="
echo "TEST 2: Fixed 15% SL (NEW DEFAULT)"
echo "========================================="
python run_backtest.py --bot NIFTYBOT --days 90 --strategy custom --stop-loss 0.15 --sl-method fixed

# Test 3: Fixed 20%
echo ""
echo "========================================="
echo "TEST 3: Fixed 20% SL"
echo "========================================="
python run_backtest.py --bot NIFTYBOT --days 90 --strategy custom --stop-loss 0.20 --sl-method fixed

# Test 4: Technical SL
echo ""
echo "========================================="
echo "TEST 4: Technical SL (Option Candles)"
echo "========================================="
python run_backtest.py --bot NIFTYBOT --days 90 --strategy custom --sl-method technical

echo ""
echo "========================================="
echo "ALL TESTS COMPLETE!"
echo "========================================="
echo "Compare the metrics above to choose the best SL strategy."
EOF

# Make it executable
chmod +x compare_sl_strategies.sh

# Run it
./compare_sl_strategies.sh
```

---

## For BANKNIFTY

Replace `--bot NIFTYBOT` with `--bot BANKNIFTYBOT` in all commands:

```bash
python run_backtest.py --bot BANKNIFTYBOT --days 90 --sl-method technical
```

---

## Extended Testing (3-6 Months)

For more reliable results, test over longer periods:

```bash
# 3 months
python run_backtest.py --bot NIFTYBOT --days 90 --sl-method technical

# 6 months
python run_backtest.py --bot NIFTYBOT --days 180 --sl-method technical

# 1 year
python run_backtest.py --bot NIFTYBOT --days 365 --sl-method technical
```

**Recommendation**: Test at least 3 months before going live.

---

## Understanding Technical SL Output

When using `--sl-method technical`, you'll see logs like:

```
Technical SL: ₹408.60 (10.0%) - Technical SL too tight (3.1%), using 10% minimum
```

**What this means:**
- Technical level was ₹440 (3.1% below entry ₹454)
- But 3.1% is too tight for options → capped to 10% minimum
- Final SL: ₹408.60 (10% below entry)

**Safety Caps:**
- Minimum: 10% (prevents too-tight SLs)
- Maximum: 20% (prevents too-wide SLs)

---

## Next Steps After Comparison

1. **Winner Found?**
   - If Technical SL wins → Integrate into live bots (future work)
   - If Fixed SL wins → Keep current 15% default

2. **Paper Trade First**
   - Test winner in paper trading for 2-4 weeks
   - Verify real-world performance matches backtest

3. **Go Live**
   - Start with 50% capital (₹75K instead of ₹150K)
   - Scale up after 2 weeks of profitability

---

## Troubleshooting

### Error: "Insufficient candles for technical SL"
- **Cause**: Option just started trading, not enough history
- **Fix**: Backtest falls back to fixed SL automatically
- **Impact**: Minimal, only affects first 1-2 candles

### Error: "Could not fetch option data"
- **Cause**: Option symbol not found or expired
- **Fix**: Check if expiry is valid, use shorter backtest period
- **Impact**: Trade will be skipped

### Very Low Trade Count
- **Cause**: Strategy is too strict or period is too short
- **Fix**:
  - Increase `--days` to 180 or 365
  - Use less strict strategy: `--strategy aggressive`

---

## Summary

```bash
# Quick comparison (recommended first step)
python run_backtest.py --bot NIFTYBOT --days 90 --stop-loss 0.15 --sl-method fixed
python run_backtest.py --bot NIFTYBOT --days 90 --sl-method technical

# Compare results
# Choose the one with better Profit Factor and Total P&L
```

**Current Default**: Fixed 15% SL (already configured in `common/config.py`)

**Your Decision**: Test both, let the data decide! 📊
