##############################################
# SHARED CONFIGURATION
# All settings in one place
##############################################

import os
import sys

##############################################
# LOAD .env FILE (if exists)
##############################################

def _load_env():
    """Load environment variables from .env file."""
    # Look for .env in project root
    env_paths = [".env", "../.env"]
    for env_path in env_paths:
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
# TRADING PARAMETERS
##############################################

# NiftyBot settings
NIFTY_LOT_SIZE = 75
NIFTY_MAX_TRADES_PER_DAY = 5

# StockBot settings
STOCK_MAX_TRADES_PER_DAY = 5
STOCK_MAX_CAPITAL_PER_TRADE = 100000  # Rs. 1 Lakh

# Risk management
MAX_LOSS_PER_DAY = 10000              # Rs. 10,000 max loss
MAX_CAPITAL_DEPLOYED = 500000         # Rs. 5 Lakh total

##############################################
# STRATEGY PARAMETERS
##############################################

# NiftyBot - VWAP strategy
VWAP_DEVIATION_THRESHOLD = 0.005      # 0.5% deviation for mean reversion
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# StockBot - Momentum strategy
VOLUME_MULTIPLIER = 1.5               # Volume > 1.5x average
ADX_THRESHOLD = 28
BREAKOUT_LOOKBACK_DAYS = 5            # Price > 5-day high
VOLUME_LOOKBACK_DAYS = 10             # Compare to 10-day avg volume

# Exit parameters
ATR_MULTIPLIER_STOPLOSS = 2.5         # Stop loss = 2.5 x ATR
EMA_PERIOD = 20                       # Exit EMA period
PSAR_AF = 0.02                        # PSAR acceleration factor
PSAR_MAX_AF = 0.2                     # PSAR max acceleration

##############################################
# MARKET HOURS (IST)
##############################################

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# Scan times
NIFTY_SCAN_START_MINUTE = 20          # Start scanning 20 min after open
STOCK_SCAN_HOUR = 12                  # Scan stocks at 12:00 PM
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
