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

##############################################
# RISK MANAGEMENT
##############################################

# Daily limits
NIFTY_MAX_TRADES_PER_DAY = 2          # Quality over quantity
MAX_LOSS_PER_DAY = 20000              # Rs. 20K max daily loss - stop trading
MAX_CONSECUTIVE_LOSSES = 2            # Stop after 2 consecutive losses

# Weekly limits
MAX_WEEKLY_LOSS = 40000               # Rs. 40K max weekly loss

# Stop loss percentages (on premium)
INITIAL_SL_PERCENT = 20               # 20% initial stop loss
BREAKEVEN_TRIGGER_PERCENT = 20        # Move SL to entry at +20% profit
TRAIL_PERCENT = 50                    # Trail at 50% of max profit

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
# EXIT PARAMETERS
##############################################

# Trailing stop method: 'supertrend', 'percent', or 'ema'
TRAILING_STOP_METHOD = 'supertrend'

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
