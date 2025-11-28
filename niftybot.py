##############################################
# HYBRID VWAP NIFTY OPTIONS TRADING BOT
##############################################

import datetime
import time
import logging
from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import numpy as np

##############################################
# LOGGING SETUP (for audit compliance)
##############################################

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('niftybot_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

##############################################
# 1. CONFIGURATION & CONSTANTS
##############################################

# Kite Connect credentials (replace with actual values or use environment variables)
API_KEY = "your_api_key"
ACCESS_TOKEN = "your_access_token"

# Kite Connect constants (as per official API documentation)
EXCHANGE_NFO = "NFO"
TRANSACTION_TYPE_BUY = "BUY"
TRANSACTION_TYPE_SELL = "SELL"
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
PRODUCT_MIS = "MIS"           # Intraday
PRODUCT_NRML = "NRML"         # Carry forward
VARIETY_REGULAR = "regular"   # Regular order

# Instrument tokens
NIFTY_50_TOKEN = 256265       # NIFTY 50 index token

# Trading parameters
LOT_SIZE = 75                 # NIFTY options lot size
MAX_TRADES_PER_DAY = 5

##############################################
# 2. AUTHENTICATION
##############################################

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)
logger.info("Kite Connect client initialized")

##############################################
# 3. INDICATORS
##############################################

def compute_vwap(df):
    df["TP"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (df["TP"] * df["volume"]).cumsum() / df["volume"].cumsum()
    return df

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(period).mean()
    return df

##############################################
# 4. DAY TYPE DETECTION
##############################################

def detect_day_type(df):
    """
    Checks first 15–20 minutes of data.
    """
    first_20 = df.iloc[:20]

    cond1 = (first_20["close"] > first_20["vwap"]).mean() > 0.7 or \
            (first_20["close"] < first_20["vwap"]).mean() > 0.7

    cond2 = abs(first_20["close"].iloc[-1] - first_20["close"].iloc[0]) > \
            0.003 * first_20["close"].iloc[0]

    cond3 = (ema(first_20["close"], 5).iloc[-1] >
             ema(first_20["close"], 20).iloc[-1])

    if (cond1 + cond2 + cond3) >= 2:
        return "TRENDING"
    else:
        return "SIDEWAYS"

##############################################
# 5. STRATEGY SIGNALS
##############################################

def trend_signal(df):
    """
    Trend continuation using VWAP pullback.
    """
    if df["close"].iloc[-1] > df["vwap"].iloc[-1]:
        return "BUY_CE"
    elif df["close"].iloc[-1] < df["vwap"].iloc[-1]:
        return "BUY_PE"
    return None

def mean_rev_signal(df):
    """
    Mean reversion when price deviates from VWAP.
    """
    deviation = (df["close"].iloc[-1] - df["vwap"].iloc[-1]) / df["vwap"].iloc[-1]
    rsi_val = rsi(df["close"]).iloc[-1]

    if deviation > 0.005 and rsi_val > 70:
        return "BUY_PE"
    elif deviation < -0.005 and rsi_val < 30:
        return "BUY_CE"

    return None

##############################################
# 6. STRIKE & SYMBOL SELECTION
##############################################

def get_atm_strike(nifty_price):
    """Calculate ATM strike price (NIFTY strikes are in multiples of 50)."""
    return round(nifty_price / 50) * 50

def get_weekly_expiry():
    """
    Get the current week's Thursday expiry date.
    NIFTY weekly options expire on Thursday.
    Returns expiry in format required by Kite (e.g., '24NOV' for Nov 2024).
    """
    today = datetime.date.today()
    days_until_thursday = (3 - today.weekday()) % 7
    if days_until_thursday == 0 and datetime.datetime.now().hour >= 15:
        # If it's Thursday after market close, move to next week
        days_until_thursday = 7
    expiry_date = today + datetime.timedelta(days=days_until_thursday)
    # Format: YYMMMDD (e.g., 24NOV28 for 28th Nov 2024)
    return expiry_date.strftime("%y%b%d").upper()

def get_option_symbol(strike, option_type, expiry=None):
    """
    Build the trading symbol for NIFTY options as per NSE/Kite format.

    Args:
        strike: ATM strike price (e.g., 19500)
        option_type: 'CE' for Call, 'PE' for Put
        expiry: Expiry date string (optional, defaults to current weekly expiry)

    Returns:
        Trading symbol (e.g., 'NIFTY24NOV2819500CE')
    """
    if expiry is None:
        expiry = get_weekly_expiry()
    symbol = f"NIFTY{expiry}{strike}{option_type}"
    logger.debug(f"Generated option symbol: {symbol}")
    return symbol

##############################################
# 7. ORDER PLACEMENT
##############################################

def place_order(symbol, qty=LOT_SIZE, transaction_type=TRANSACTION_TYPE_BUY):
    """
    Place an order via Kite Connect API.

    Args:
        symbol: Trading symbol (e.g., 'NIFTY24NOV2819500CE')
        qty: Quantity (default: LOT_SIZE)
        transaction_type: BUY or SELL (default: BUY)

    Returns:
        order_id if successful, None otherwise
    """
    try:
        logger.info(f"Placing order: {transaction_type} {qty} x {symbol}")

        order_id = kite.place_order(
            variety=VARIETY_REGULAR,
            tradingsymbol=symbol,
            exchange=EXCHANGE_NFO,
            transaction_type=transaction_type,
            quantity=qty,
            order_type=ORDER_TYPE_MARKET,
            product=PRODUCT_MIS
        )

        logger.info(f"Order placed successfully | order_id={order_id} | symbol={symbol} | "
                    f"transaction_type={transaction_type} | qty={qty}")
        return order_id

    except Exception as e:
        logger.error(f"Order failed | symbol={symbol} | transaction_type={transaction_type} | "
                     f"qty={qty} | error={str(e)}")
        return None

##############################################
# 8. MAIN BOT LOOP
##############################################

def run_bot():
    """
    Main trading bot loop.
    Fetches market data, detects day type, generates signals, and executes trades.
    """
    trade_count = 0
    day_type = None

    logger.info("=" * 50)
    logger.info("BOT STARTED")
    logger.info(f"Date: {datetime.date.today()}")
    logger.info(f"Max trades per day: {MAX_TRADES_PER_DAY}")
    logger.info(f"Lot size: {LOT_SIZE}")
    logger.info("Waiting for first 20 candles to detect day type...")
    logger.info("=" * 50)

    # Use WebSocket but for simplicity this loop simulates data updates
    while True:
        now = datetime.datetime.now()

        # Stop after market close (3:25 PM)
        if now.hour >= 15 and now.minute >= 25:
            logger.info("Market closed. Stopping bot.")
            logger.info(f"Total trades executed today: {trade_count}")
            break

        try:
            # Fetch latest NIFTY futures data (1m)
            df = kite.historical_data(
                instrument_token=NIFTY_50_TOKEN,
                from_date=now - datetime.timedelta(minutes=60),
                to_date=now,
                interval="minute"
            )
            df = pd.DataFrame(df)
            df = compute_vwap(df)
            df = atr(df)

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {str(e)}")
            time.sleep(10)
            continue

        # Detect day mode after 20 candles
        if len(df) >= 20 and day_type is None:
            day_type = detect_day_type(df)
            logger.info(f"Day type detected: {day_type}")

        # Skip until day type known
        if day_type is None:
            time.sleep(10)
            continue

        # If max trades reached
        if trade_count >= MAX_TRADES_PER_DAY:
            logger.info("Max trades reached for the day. Monitoring only.")
            time.sleep(60)
            continue

        # ---- SIGNAL ENGINE ----
        if day_type == "TRENDING":
            signal = trend_signal(df)
        else:
            signal = mean_rev_signal(df)

        # ---- EXECUTE TRADE ----
        if signal:
            last_price = df["close"].iloc[-1]
            atm = get_atm_strike(last_price)

            # Determine option type from signal
            option_type = "CE" if signal == "BUY_CE" else "PE"

            # Build proper symbol with expiry date
            symbol = get_option_symbol(atm, option_type)

            logger.info(f"Signal generated: {signal} | NIFTY spot: {last_price:.2f} | "
                        f"ATM strike: {atm}")

            order_id = place_order(symbol)
            if order_id:
                trade_count += 1
                logger.info(f"Trade count: {trade_count}/{MAX_TRADES_PER_DAY}")

        # Loop delay
        time.sleep(10)

##############################################
# 9. ENTRY POINT
##############################################

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Bot crashed with unhandled exception: {str(e)}")
        raise
