# NiftyBot - Production-Ready VWAP Options Trading Bot

## 🎯 Overview

NiftyBot is a hybrid VWAP-based trading bot for Nifty Options that automatically detects market conditions and applies the optimal strategy:

- **Trending Markets**: VWAP pullback continuation strategy
- **Sideways Markets**: Mean reversion based on VWAP deviation + RSI

## ✨ Key Features

### Core Strategy
- ✅ Automatic day type detection (Trending vs Sideways)
- ✅ Dynamic strategy switching based on market conditions
- ✅ VWAP + EMA + RSI + ATR indicators
- ✅ ATM Nifty options trading only
- ✅ Re-evaluates market conditions every 30 minutes

### Risk Management
- ✅ ATR-based stop-loss and targets (1.5x & 2.5x ATR)
- ✅ Position tracking with real-time P&L
- ✅ Daily loss limit (5% of capital)
- ✅ Maximum 5 trades per day
- ✅ One position at a time (no overlapping trades)
- ✅ Auto square-off before market close (3:15 PM)

### Production Features
- ✅ Comprehensive error handling
- ✅ Professional logging (file + console)
- ✅ Environment variable configuration
- ✅ Option chain analysis (OI + bid-ask spread validation)
- ✅ Correct Zerodha option symbol format
- ✅ Prevents duplicate signals on same candle
- ✅ Configurable parameters via Config class

## 🚀 What's New (Fixed Issues)

### Critical Bugs Fixed
1. ✅ Added missing `import time`
2. ✅ Fixed RSI calculation (pandas Series handling)
3. ✅ Corrected option symbol format: `NIFTY25JAN0224000CE` (with expiry date)
4. ✅ Implemented complete exit strategy with stop-loss and targets
5. ✅ Added position management to prevent multiple overlapping positions

### Security & Reliability
6. ✅ Moved credentials to environment variables
7. ✅ Added comprehensive error handling throughout
8. ✅ Fixed API polling to prevent rate limits
9. ✅ Added data validation checks

### Strategy Improvements
10. ✅ Trend signal now includes actual pullback detection (not just above/below VWAP)
11. ✅ Day type re-evaluation every 30 minutes (not fixed forever)
12. ✅ ATR now actively used for stop-loss calculation
13. ✅ Market close timing fixed to 3:15 PM with position squaring

### New Features
14. ✅ Option chain analysis (OI, bid-ask spread, liquidity checks)
15. ✅ Risk management with position sizing and daily limits
16. ✅ Prevents processing same candle multiple times
17. ✅ Professional logging framework
18. ✅ Centralized configuration management
19. ✅ Better variable naming and code structure

## 📋 Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd NiftyBot
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure credentials**
   ```bash
   cp .env.example .env
   # Edit .env and add your Kite API credentials
   ```

## ⚙️ Configuration

Edit the `Config` class in `niftybot.py` to adjust parameters:

```python
class Config:
    # Trading Parameters
    MAX_TRADES_PER_DAY = 5
    LOT_SIZE = 75
    RISK_PER_TRADE_PCT = 2.0
    MAX_DAILY_LOSS_PCT = 5.0

    # Strategy Parameters
    VWAP_DEVIATION_THRESHOLD = 0.005  # 0.5%
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    ATR_MULTIPLIER_SL = 1.5
    ATR_MULTIPLIER_TARGET = 2.5

    # Option Chain
    MIN_OI = 1000
    MAX_BID_ASK_SPREAD_PCT = 2.0
```

## 🏃 Usage

### Setup Zerodha Kite API

1. Get API key from [Kite Connect](https://kite.trade/)
2. Generate access token (valid for 1 day)
3. Add to `.env` file:
   ```
   KITE_API_KEY=your_api_key
   KITE_ACCESS_TOKEN=your_access_token
   ```

### Run the Bot

```bash
python niftybot.py
```

### Monitor Logs

```bash
tail -f niftybot.log
```

## 📊 How It Works

### 1. Day Type Detection (First 20 Minutes)

The bot analyzes the first 20 candles to determine market condition:

**Trending Day** (needs 2/3 conditions):
- 70%+ candles above or below VWAP
- Price moved >0.3% from open
- EMA5 and EMA20 diverging

**Sideways Day**: All other conditions

### 2. Strategy Selection

**Trending Mode**:
- Waits for pullback to VWAP
- Enters when price resumes trend direction
- Example: Uptrend → wait for dip to VWAP → buy CE when bouncing up

**Sideways Mode**:
- Trades mean reversion
- Enters when price deviates >0.5% from VWAP + RSI extreme
- Example: Price above VWAP + RSI > 70 → buy PE (expect reversion)

### 3. Entry Process

1. Signal generated → check option chain liquidity
2. Validate OI > 1000 and bid-ask spread < 2%
3. Place market order for ATM option
4. Calculate ATR-based stop-loss (entry - 1.5×ATR)
5. Set target (entry + 2.5×ATR)

### 4. Exit Process

Monitors every 10 seconds:
- Stop-loss hit → exit immediately
- Target hit → exit immediately
- 3:15 PM → square off all positions

## 📈 Example Trade Flow

```
09:15 AM - Bot starts, collecting data
09:35 AM - Day type detected: TRENDING
10:42 AM - Pullback to VWAP detected
10:43 AM - Signal: BUY_CE → NIFTY25JAN0224000CE
10:43 AM - Order placed @ ₹150, SL: ₹127, Target: ₹187.5
10:58 AM - Target hit @ ₹190, P&L: +₹3,000
         - Position closed (1/5 trades)
```

## ⚠️ Important Notes

### Before Live Trading

1. **Test in Paper Trading First**: Use Kite's paper trading to validate
2. **Start Small**: Use minimum lot size initially
3. **Monitor Closely**: Watch first few days of live trading
4. **Check Logs Daily**: Review `niftybot.log` for any issues

### Known Limitations

- **Access Token Expires Daily**: You must generate new token each day
- **No WebSocket (Yet)**: Currently uses polling (upgradable to WebSocket)
- **Single Position**: Only holds one position at a time
- **Options Only**: Doesn't trade futures or equity

### Risk Disclaimer

⚠️ **Trading involves risk of loss. This bot is provided as-is with no guarantees.**
- Past performance doesn't indicate future results
- Always test thoroughly before live trading
- Never risk more than you can afford to lose
- Monitor the bot during market hours

## 🔧 Troubleshooting

### Common Issues

**Error: "Failed to authenticate Kite API"**
- Check API key and access token in `.env`
- Ensure access token is valid (regenerate daily)

**Error: "No data received from API"**
- Check internet connection
- Verify market is open
- Check Kite API status

**Error: "Option failed liquidity checks"**
- Increase `MIN_OI` threshold
- Check if using weekly expiry (more liquid than monthly)

**Bot not entering trades**
- Check if day type detected (needs 20 candles)
- Verify signals in logs
- Ensure within trading hours (9:15 AM - 3:15 PM)

## 📝 Logging

Logs are written to both console and `niftybot.log`:

```
2025-11-28 09:15:23 - INFO - NiftyBot started - Waiting for market data...
2025-11-28 09:35:12 - INFO - Day type detected: TRENDING
2025-11-28 10:43:05 - INFO - Signal: BUY_CE (TRENDING mode) → NIFTY25JAN0224000CE
2025-11-28 10:43:07 - INFO - Order placed: BUY 75 NIFTY25JAN0224000CE, Order ID: 123456
2025-11-28 10:43:09 - INFO - Position added: NIFTY25JAN0224000CE @ 150.0, SL: 127.5, TGT: 187.5
2025-11-28 10:58:34 - INFO - Target hit for NIFTY25JAN0224000CE: LTP 190.0 >= TGT 187.5
2025-11-28 10:58:36 - INFO - Position closed: NIFTY25JAN0224000CE @ 190.0, Reason: TARGET, P&L: 3000.00
```

## 🛠️ Future Enhancements

Potential improvements:
- [ ] WebSocket integration for real-time data
- [ ] Multiple position management
- [ ] Backtesting framework
- [ ] Telegram notifications
- [ ] Dynamic position sizing based on account balance
- [ ] Machine learning for day type detection
- [ ] Support for Bank Nifty

## 📄 License

MIT License - Use at your own risk

## 🤝 Contributing

Pull requests welcome! Please test thoroughly before submitting.

## 📞 Support

For issues or questions:
- Open a GitHub issue
- Check logs in `niftybot.log`
- Review Zerodha Kite API documentation

---

**Happy Trading! 📈**
