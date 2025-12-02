# Backtesting Guide

Complete guide to backtesting your trading strategies with professional risk management.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Understanding Strategy Presets](#understanding-strategy-presets)
3. [Customizing Strategies](#customizing-strategies)
4. [Interpreting Results](#interpreting-results)
5. [Parameter Tuning Guide](#parameter-tuning-guide)
6. [Best Practices](#best-practices)

---

## Quick Start

### List Available Strategies
```bash
python run_backtest.py --list-strategies
```

### Run Your First Backtest
```bash
# Backtest NIFTY with balanced strategy (90 days)
python run_backtest.py --bot NIFTYBOT --days 90

# Backtest BANKNIFTY with conservative strategy (30 days)
python run_backtest.py --bot BANKNIFTYBOT --strategy conservative --days 30

# Test all bots with aggressive strategy
python run_backtest.py --all --strategy aggressive --days 60
```

---

## Understanding Strategy Presets

### 1. **Balanced** (Default)
**Best for**: Beginners, learning the system

**Characteristics**:
- ADX Threshold: 23 (moderate trend strength required)
- Stop Loss: 20%
- Target: 40% (2:1 risk:reward)
- Risk per Trade: 1% of capital
- Max Positions: 3
- Trailing Stop: Enabled

**Use Case**: Good starting point. Works in most market conditions.

```bash
python run_backtest.py --bot NIFTYBOT --strategy balanced --days 90
```

---

### 2. **Conservative**
**Best for**: Risk-averse traders, preserving capital

**Characteristics**:
- ADX Threshold: 28 (strong trends only)
- Stop Loss: 15%
- Target: 30%
- Risk per Trade: 0.5% of capital
- Max Positions: 2
- Volume Confirmation: Required
- VWAP Confirmation: Required

**Use Case**: Lower drawdown, fewer but higher-quality trades. Ideal for prop firm evaluations.

```bash
python run_backtest.py --bot NIFTYBOT --strategy conservative --days 90
```

**Expected Metrics**:
- Win Rate: 45-55%
- Sharpe Ratio: > 1.5
- Max Drawdown: < 10%

---

### 3. **Aggressive**
**Best for**: Experienced traders, higher risk tolerance

**Characteristics**:
- ADX Threshold: 20 (weaker trends accepted)
- Stop Loss: 25%
- Target: 50%
- Risk per Trade: 1.5% of capital
- Max Positions: 5
- Fewer confirmations required

**Use Case**: More trades, higher potential returns, larger drawdowns. Good for trending markets.

```bash
python run_backtest.py --bot NIFTYBOT --strategy aggressive --days 90
```

**Expected Metrics**:
- Win Rate: 40-50%
- Sharpe Ratio: > 1.0
- Max Drawdown: 15-20%

---

### 4. **Scalper**
**Best for**: Quick trades, intraday focus

**Characteristics**:
- ADX Threshold: 18 (minimal trend required)
- Stop Loss: 10%
- Target: 15%
- Risk per Trade: 0.8% of capital
- Max Positions: 4
- Trailing Stop: Disabled (quick exits)

**Use Case**: Multiple small wins throughout the day. Requires constant monitoring in live trading.

```bash
python run_backtest.py --bot NIFTYBOT --strategy scalper --days 30
```

**Expected Metrics**:
- Win Rate: 55-65% (high win rate, small R:R)
- Many trades per day
- Lower profit per trade

---

### 5. **Trend Follower**
**Best for**: Capturing big moves, patient traders

**Characteristics**:
- ADX Threshold: 30 (very strong trends only)
- Stop Loss: 30%
- Target: 60%
- Risk per Trade: 1% of capital
- Max Positions: 2
- Aggressive Trailing Stops

**Use Case**: Hold winners longer, capture large trends. Works best in volatile, trending markets.

```bash
python run_backtest.py --bot NIFTYBOT --strategy trend_follower --days 90
```

**Expected Metrics**:
- Win Rate: 35-45% (lower win rate, big wins)
- Profit Factor: > 2.0
- Average win >> Average loss

---

## Customizing Strategies

### Override Preset Parameters

You can override any preset parameter from the command line:

```bash
# Conservative strategy with higher capital
python run_backtest.py --bot NIFTYBOT --strategy conservative --capital 1000000

# Aggressive strategy with tighter stop loss
python run_backtest.py --bot NIFTYBOT --strategy aggressive --stop-loss 0.18

# Balanced strategy with 2% risk per trade
python run_backtest.py --bot NIFTYBOT --strategy balanced --risk 0.02
```

### Create Custom Strategy in Code

For advanced customization, edit `backtest/strategy_config.py`:

```python
from backtest.strategy_config import StrategyConfig

# Create custom strategy
my_strategy = StrategyConfig()

# Tweak indicators
my_strategy.adx_threshold = 25
my_strategy.supertrend_period = 12
my_strategy.supertrend_multiplier = 2.5

# Tweak risk management
my_strategy.stop_loss_percent = 0.18
my_strategy.target_percent = 0.35
my_strategy.max_risk_per_trade = 0.012

# Tweak confirmations
my_strategy.require_volume_confirmation = True
my_strategy.volume_surge_threshold = 1.8

# Use in backtest
from backtest.backtest_engine import BacktestEngine, BacktestConfig
config = BacktestConfig(strategy_config=my_strategy)
engine = BacktestEngine(NiftyBot, config)
results = engine.run()
```

---

## Interpreting Results

After running a backtest, you'll see a detailed performance summary:

### Key Metrics to Focus On

#### 1. **Win Rate**
- **What**: Percentage of winning trades
- **Good**: > 45%
- **Excellent**: > 55%
- **Note**: Higher isn't always better if wins are small

#### 2. **Expectancy**
- **What**: Average expected profit per trade
- **Good**: > ₹500
- **Excellent**: > ₹1000
- **Critical**: This is the MOST important metric. Positive expectancy = profitable strategy.

#### 3. **Profit Factor**
- **What**: Gross profit / Gross loss
- **Good**: > 1.5
- **Excellent**: > 2.0
- **Minimum**: Must be > 1.0 (below 1 = losing money)

#### 4. **Sharpe Ratio**
- **What**: Risk-adjusted returns
- **Good**: > 1.0
- **Excellent**: > 2.0
- **World-class**: > 3.0

#### 5. **Max Drawdown**
- **What**: Largest peak-to-trough decline
- **Good**: < 15%
- **Excellent**: < 10%
- **Critical**: This is your worst-case scenario. Can you handle it emotionally?

#### 6. **Recovery Factor**
- **What**: Net profit / Max drawdown
- **Good**: > 2.0
- **Excellent**: > 3.0
- **Meaning**: How quickly you recover from losses

### Strategy Rating System

The backtest engine automatically rates your strategy:

- ⭐⭐⭐⭐⭐ **EXCELLENT** (Score ≥ 80): Ready for live trading
- ⭐⭐⭐⭐ **GOOD** (Score ≥ 60): Consider live with small capital
- ⭐⭐⭐ **ACCEPTABLE** (Score ≥ 40): Needs optimization
- ⭐⭐ **POOR** (Score ≥ 20): Significant improvements needed
- ⭐ **UNACCEPTABLE** (Score < 20): Do not trade live

---

## Parameter Tuning Guide

### Finding the Right Parameters for YOU

**Philosophy**: The market has patterns, but they change. Simple systems that adapt are better than complex ones.

### Step 1: Start with a Preset

Test all presets and see which performs best for your bot:

```bash
for strategy in conservative balanced aggressive scalper trend_follower; do
    echo "Testing $strategy..."
    python run_backtest.py --bot NIFTYBOT --strategy $strategy --days 90
done
```

### Step 2: Identify Best Preset

Look for:
- Highest Sharpe Ratio
- Acceptable drawdown (< 15%)
- Positive expectancy
- Good profit factor (> 1.5)

### Step 3: Optimize Around Best Preset

Once you find the best preset, tweak parameters:

#### Optimizing ADX Threshold

ADX controls trend strength requirement. Higher = fewer but stronger signals.

```bash
# Test different ADX thresholds
python run_backtest.py --bot NIFTYBOT --strategy custom --risk 0.01 --days 90
# Then manually edit strategy_config.py to test ADX values: 18, 20, 23, 25, 28, 30
```

**Too many losing trades?** → Increase ADX threshold (25 → 28)
**Too few trades?** → Decrease ADX threshold (23 → 20)

#### Optimizing Stop Loss

Stop loss controls your maximum loss per trade.

**High win rate but poor profit factor?** → Widen stop loss (20% → 25%)
**Low win rate with good profit factor?** → Tighten stop loss (20% → 15%)

#### Optimizing Risk per Trade

**Capital growing too slowly?** → Increase risk (1% → 1.5%)
**Drawdowns too large?** → Decrease risk (1% → 0.5%)

### Step 4: Test on Different Time Periods

A good strategy works across different market conditions:

```bash
# Test last 30 days (recent market)
python run_backtest.py --bot NIFTYBOT --strategy balanced --days 30

# Test last 90 days (medium term)
python run_backtest.py --bot NIFTYBOT --strategy balanced --days 90

# Test last 180 days (long term)
python run_backtest.py --bot NIFTYBOT --strategy balanced --days 180
```

**Consistent performance across all periods?** → Good strategy!
**Only works in one period?** → Overfit, likely to fail live.

---

## Best Practices

### 1. **Never Curve-Fit**

Don't optimize parameters until you get perfect backtest results. This creates overfitting.

**Instead**: Find parameters that work "well enough" across multiple time periods.

### 2. **The 3-Period Test**

Test your strategy on:
1. Last 30 days
2. Last 90 days
3. Last 180 days

If it's profitable in all three → Good signal.

### 3. **Walk-Forward Analysis**

Professional approach:
1. Optimize parameters on 60 days
2. Test on next 30 days
3. If it works, use those parameters
4. Repeat monthly

### 4. **Respect the Drawdown**

If backtest shows 15% max drawdown:
- Expect 20-25% drawdown in live trading
- Ask yourself: Can I handle a 25% loss without panicking?
- If no, reduce risk or don't trade live

### 5. **Start Small**

Even with great backtest results:
1. Paper trade for 2-4 weeks
2. Start live with 10% of planned capital
3. Gradually increase as confidence builds

### 6. **The 50-Trade Rule**

You need at least 50 trades in your backtest for statistical significance.

**< 20 trades**: Results are noise, meaningless
**20-50 trades**: Directional signal, but uncertain
**> 50 trades**: Statistically meaningful

### 7. **Compare to Buy & Hold**

Run this to see if your strategy beats simple buy-hold:

```python
# Simple benchmark: Would buying and holding NIFTY beat your strategy?
# If not, why trade at all?
```

---

## Advanced Topics

### Understanding Slippage

The backtest assumes 0.5% slippage. In reality:
- Market orders in liquid options: 0.3-0.7%
- Market orders in illiquid options: 1-2%
- Limit orders: 0-0.2% (but might not fill)

**During volatile hours (9:15-9:45, 3:15-3:30)**: Expect 2x normal slippage

### Commission Impact

At ₹40 per trade (entry + exit = ₹80 total):
- Trading 50 lots × ₹100 premium = ₹5000 position → 1.6% commission
- Trading 100 lots × ₹100 premium = ₹10000 position → 0.8% commission

**Smaller positions hurt more from commissions**. Consider this when setting position size.

### The Reality Gap

**Backtest Sharpe Ratio of 2.0 → Live trading Sharpe of 1.0-1.2**

Why the gap?
- Slippage is unpredictable
- You won't always be at computer to take signals
- Emotions affect execution
- Market changes over time
- Black swan events not in backtest data

**Rule of Thumb**: Divide backtest Sharpe by 1.5-2.0 for realistic live expectation.

---

## Troubleshooting

### "No trades in backtest"

**Cause**: Strategy is too restrictive or bot isn't generating signals

**Fix**:
1. Lower ADX threshold (30 → 23)
2. Remove volume confirmation requirement
3. Check if bot logic is working (look at logs)

### "Too many trades, all losing"

**Cause**: Strategy is too loose, taking bad signals

**Fix**:
1. Increase ADX threshold (20 → 25)
2. Add volume confirmation
3. Tighten stop loss
4. Reduce risk per trade

### "High win rate but losing money"

**Cause**: Small wins, big losses (poor risk:reward)

**Fix**:
1. Widen stop loss
2. Enable trailing stops
3. Increase target

### "Low win rate but making money"

**Cause**: Small losses, big wins (good risk:reward)

**Status**: This is actually GOOD! Don't change it. Trend-following strategies often have 30-40% win rate with excellent profit factor.

---

## Next Steps

1. ✅ Run `python run_backtest.py --list-strategies` to see all presets
2. ✅ Test each preset on 90 days of data
3. ✅ Pick the best one based on Sharpe ratio and drawdown
4. ✅ Test that preset on 30 and 180 days
5. ✅ If consistent, tweak parameters slightly
6. ✅ Paper trade for 2-4 weeks
7. ✅ Start live with 10% capital
8. ✅ Review and adjust monthly

**Remember**: The goal isn't perfection. The goal is a positive edge that you can execute consistently.

---

## Questions?

- Check logs in backtest output for detailed trade-by-trade analysis
- Review `backtest/strategy_config.py` for all available parameters
- Study `backtest/performance_metrics.py` to understand metrics calculations

**Happy Backtesting!** 🚀
