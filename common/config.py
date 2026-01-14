##############################################
# SHARED CONFIGURATION
# All settings in one place
##############################################

import os
import sys

##############################################
# LOAD .env FILE (if exists)
##############################################

# Get the project root directory (parent of 'common' folder)
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CONFIG_DIR)

def _load_env():
    """Load environment variables from .env file."""
    # Look for .env in project root (absolute path)
    env_path = os.path.join(_PROJECT_ROOT, ".env")

    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        return True
    return False

# Auto-load .env on import
_load_env()

##############################################
# KITE CONNECT CREDENTIALS
##############################################

# Load from environment variables
API_KEY = os.environ.get("KITE_API_KEY", "")
ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN", "")
API_SECRET = os.environ.get("KITE_API_SECRET", "")

# Validate credentials
def validate_credentials():
    """Check if credentials are properly configured."""
    missing = []
    if not API_KEY or API_KEY == "your_api_key":
        missing.append("KITE_API_KEY")
    if not ACCESS_TOKEN or ACCESS_TOKEN == "your_access_token":
        missing.append("KITE_ACCESS_TOKEN")

    if missing:
        print("\n" + "=" * 50)
        print("ERROR: Missing Kite Connect Credentials")
        print("=" * 50)
        print(f"\nMissing: {', '.join(missing)}")
        print("\nTo fix this, run: python generate_token.py")
        print("This will generate a .env file with your credentials.")
        print("=" * 50 + "\n")
        return False
    return True

##############################################
# BROKER SETTINGS
##############################################

BROKER = "kite"  # Options: "kite", "angel", "icici" (future)

# Kite Connect constants
EXCHANGE_NSE = "NSE"
EXCHANGE_NFO = "NFO"
EXCHANGE_BSE = "BSE"
EXCHANGE_MCX = "MCX"  # Multi Commodity Exchange

TRANSACTION_BUY = "BUY"
TRANSACTION_SELL = "SELL"

ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_SL = "SL"
ORDER_TYPE_SLM = "SL-M"

PRODUCT_MIS = "MIS"      # Intraday
PRODUCT_CNC = "CNC"      # Delivery
PRODUCT_NRML = "NRML"    # F&O normal

VARIETY_REGULAR = "regular"
VARIETY_AMO = "amo"      # After market order

##############################################
# INSTRUMENT TOKENS
##############################################

NIFTY_50_TOKEN = 256265
BANKNIFTY_TOKEN = 260105

##############################################
# CAPITAL & POSITION SIZING (2 Lakhs Strategy)
##############################################

TOTAL_CAPITAL = 200000                # Rs. 2 Lakhs total capital
TRADING_CAPITAL = 150000              # Rs. 1.5 Lakhs for trading (75%)
RESERVE_CAPITAL = 50000               # Rs. 50K buffer (25%)

MAX_INVESTMENT_PER_TRADE = 75000      # Rs. 75K max per trade
MIN_INVESTMENT_PER_TRADE = 40000      # Rs. 40K min per trade

# NIFTY lot size (changed to 25 recently)
NIFTY_LOT_SIZE = 25

# BANKNIFTY lot size (changed to 15 recently)
BANKNIFTY_LOT_SIZE = 15
BANKNIFTY_STRIKE_STEP = 100           # Strike interval for BANKNIFTY
BANKNIFTY_MAX_TRADES_PER_DAY = 10     # Max trades for BANKNIFTY bot (capital erosion is primary limit)

##############################################
# RISK MANAGEMENT
##############################################

# Daily limits
NIFTY_MAX_TRADES_PER_DAY = 50         # Max 50 trades per day (high frequency trading)
MAX_LOSS_PER_DAY = 10000              # Rs. 10K max daily loss (5% of capital) - stop trading
MAX_CONSECUTIVE_LOSSES = 3            # Stop after 3 consecutive losses (capital erosion is primary limit)

# Cooldown after loss (prevents immediate re-entry)
LOSS_COOLDOWN_MINUTES = 30            # Wait 30 minutes after a loss before new trades
REASSESS_BIAS_AFTER_LOSS = True       # Re-check directional bias after a loss

# Weekly limits
MAX_WEEKLY_LOSS = 40000               # Rs. 40K max weekly loss

# Stop loss percentages (on premium)
INITIAL_SL_PERCENT = 10               # 10% initial stop loss (tightened - better risk management)
BREAKEVEN_TRIGGER_PERCENT = 5         # Move SL to entry at +5% profit (realistic for intraday)
TRAIL_PERCENT = 50                    # Trail at 50% of max profit (legacy - used by 'percent' method)

##############################################
# HIDDEN STOP LOSS (Anti Stop-Hunting)
##############################################
# Instead of exiting on LTP touching SL, wait for CANDLE CLOSE below SL
# This prevents stop-hunting via intraday wicks

HIDDEN_SL_ENABLED = True              # Enable hidden SL with candle close confirmation
HIDDEN_SL_METHOD = 'technical'        # 'technical' (candle structure) or 'fixed' (percentage)
EMERGENCY_SL_PERCENT = 12             # Emergency exit if LTP drops 12%+ (reduced from 20% - tighter risk)
SL_CANDLE_INTERVAL = '5minute'        # Candle interval for SL confirmation (5minute recommended)

##############################################
# TWO-CANDLE CONFIRMATION & CANDLE-LOW BASED SL
##############################################
# Enhanced exit logic to reduce false signals:
# 1. Initial SL: Set below entry candle's low (not arbitrary percentage)
# 2. Trailing: Only trail when new high is made (not on every uptick)
# 3. Exit: Require 2 consecutive candle closes below SL (not just 1)

TWO_CANDLE_EXIT_ENABLED = True        # Require 2 consecutive candle closes below SL to exit
CANDLE_LOW_SL_ENABLED = False         # DISABLED: Was using candle low which could be 20%+ away
SL_BUFFER_PERCENT = 1.0               # Buffer below candle low for SL (1% below candle low)
TRAIL_ON_NEW_HIGH_ONLY = True         # Only trail SL when price makes a new high
MAX_SL_PERCENT_FROM_ENTRY = 10        # NEW: Cap SL at max 10% below entry price (prevents wide SL)

##############################################
# TREND-AWARE TRAILING STOP LOSS
##############################################
# Adapts trailing behavior based on trend strength (ADX)
# Strong trends: Let profits run with wider trailing
# Weak trends: Lock profits quickly with tight trailing

TREND_AWARE_TRAILING_ENABLED = True   # Enable/disable trend-aware trailing

# ADX thresholds for trend classification
STRONG_TREND_ADX = 25                 # ADX > 25 = strong trend (wide trailing)
WEAK_TREND_ADX = 18                   # ADX < 18 = weak/ranging (tight trailing)

# STRONG TREND parameters (ADX > 25) - Let profits run
STRONG_TREND_BREAKEVEN_PERCENT = 10   # Move SL to entry at +10% profit
STRONG_TREND_TRAIL_FREQUENCY = 5      # Trail every 5% gain
STRONG_TREND_TRAIL_INCREMENT = 3      # Lock 3% profit with each trail step
STRONG_TREND_MAX_GIVEBACK = 40        # Allow up to 40% giveback in trends
STRONG_TREND_EXIT_ON_ST_FLIP = True   # Also exit if Supertrend flips

# WEAK/RANGING parameters (ADX < 18) - Lock profits quickly
WEAK_TREND_BREAKEVEN_PERCENT = 8      # Move SL to entry at +8% profit
WEAK_TREND_TRAIL_FREQUENCY = 3        # Trail every 3% gain
WEAK_TREND_TRAIL_INCREMENT = 2        # Lock 2% profit with each trail step
WEAK_TREND_MAX_GIVEBACK = 40          # Never give back >40% of max profit

# Legacy parameters (used when TREND_AWARE_TRAILING_ENABLED = False)
TRAIL_FREQUENCY = 3                   # Trail stop loss every 3% gain
TRAIL_INCREMENT = 2                   # Lock 2% profit with each trail step
MAX_PROFIT_GIVEBACK = 30              # Never give back >30% of max profit seen

##############################################
# MARKET REGIME FILTER (Weekly + Daily -> VWAP Matrix)
##############################################
# Pre-trade filter that eliminates 50-60% of bad trades
# Mental model: Weekly sets battlefield, Daily sets rules, VWAP executes

MARKET_REGIME_ENABLED = True          # Enable/disable market regime filter
MIN_TRADE_QUALITY_SCORE = 50          # Minimum quality score to take a trade (0-100)
REGIME_ANALYSIS_LOG_LEVEL = "INFO"    # Log level for regime analysis

# Direction filter: Only take trades aligned with regime
ENFORCE_DIRECTION_FILTER = True       # If True, only trade in direction allowed by regime

# Skip trading on these patterns even if score is ok
SKIP_ON_INSIDE_DAY = True             # Skip when trending week + inside day
SKIP_ON_EVENT_DAY = True              # Skip on RBI, Budget, Monthly expiry days

##############################################
# EXPIRY DAY PROTECTION
##############################################
# On expiry day, option buying is extremely risky due to rapid theta decay
# Options can lose 80-90% of value in minutes as time premium evaporates

SKIP_OPTION_BUYING_ON_EXPIRY = True   # Block option buying on expiry day (STRONGLY RECOMMENDED)
EXPIRY_DAY_CUTOFF_TIME = "12:00"      # If trading on expiry, stop after this time (HH:MM format)

##############################################
# ENTRY PARAMETERS (VWAP + Supertrend + ADX)
##############################################

# Supertrend settings
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 2

# ADX threshold for entry
ADX_ENTRY_THRESHOLD = 23              # Enter only when ADX > 23

# VWAP settings
VWAP_BUFFER_PERCENT = 0.1             # 0.1% buffer around VWAP

##############################################
# GAP PROTECTION (Avoid gap-fill traps)
##############################################

# Gap detection thresholds
GAP_DETECTION_ENABLED = True          # Enable/disable gap protection
MEDIUM_GAP_THRESHOLD = 0.4            # 0.4% gap = medium gap
LARGE_GAP_THRESHOLD = 0.8             # 0.8% gap = large gap

# Trading delays on gap days (in minutes from market open)
MEDIUM_GAP_WAIT_MINUTES = 30          # Wait 30 min on medium gap (start at 9:45 AM)
LARGE_GAP_WAIT_MINUTES = 60           # Wait 60 min on large gap (start at 10:15 AM)

##############################################
# EXIT PARAMETERS
##############################################

# Trailing stop method: 'dynamic', 'supertrend', 'percent', or 'ema'
# 'dynamic' = Progressive trailing with TRAIL_FREQUENCY and TRAIL_INCREMENT (recommended for intraday)
# 'supertrend' = Exit on supertrend flip (legacy)
# 'percent' = Trail at TRAIL_PERCENT of max profit (legacy)
TRAILING_STOP_METHOD = 'dynamic'

# EMA for trailing (if using EMA method)
TRAILING_EMA_PERIOD = 5

# Time-based exit
LAST_ENTRY_HOUR = 14                  # No new entries after 2:30 PM
LAST_ENTRY_MINUTE = 30
FORCE_EXIT_HOUR = 15                  # Force exit all positions at 3:15 PM
FORCE_EXIT_MINUTE = 15

##############################################
# LEGACY PARAMETERS (for StockBot compatibility)
##############################################

# StockBot settings
STOCK_MAX_TRADES_PER_DAY = 5
STOCK_MAX_CAPITAL_PER_TRADE = 100000  # Rs. 1 Lakh
MAX_CAPITAL_DEPLOYED = TOTAL_CAPITAL

# StockBot - Momentum strategy
VOLUME_MULTIPLIER = 1.5
ADX_THRESHOLD = 28
BREAKOUT_LOOKBACK_DAYS = 5
VOLUME_LOOKBACK_DAYS = 10

# Exit parameters (legacy)
ATR_MULTIPLIER_STOPLOSS = 2.5
EMA_PERIOD = 20
PSAR_AF = 0.02
PSAR_MAX_AF = 0.2
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
VWAP_DEVIATION_THRESHOLD = 0.005

##############################################
# MARKET HOURS (IST)
##############################################

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# Trading start time (skip first 15 min noise)
TRADING_START_HOUR = 9
TRADING_START_MINUTE = 30

# Scan times
NIFTY_SCAN_START_MINUTE = 30          # Start scanning at 9:30 AM
STOCK_SCAN_HOUR = 12
STOCK_SCAN_MINUTE = 0

##############################################
# FILE PATHS
##############################################

WATCHLIST_PATH = "data/watchlist.csv"
LOG_DIR = "logs"
AUDIT_LOG_DIR = "logs/audit"

##############################################
# LOGGING
##############################################

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)-10s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

##############################################
# NETWORK & RETRY CONFIGURATION
##############################################

# API retry settings for network/server errors
API_MAX_RETRIES = 5                    # Maximum retry attempts for API calls (increased from 3)
API_RETRY_DELAY = 1                    # Initial retry delay in seconds (doubles each retry)
API_TIMEOUT = 30                       # Request timeout in seconds

# Specific retry delays (exponential backoff): 1s, 2s, 4s, 8s, 16s
# Total max wait time: ~31 seconds for 5 retries
# This handles temporary Kite API issues during market hours
