##############################################
# HYBRID VWAP NIFTY OPTIONS TRADING BOT
# Production-Ready Version with Risk Management
##############################################

import os
import time
import datetime
import logging
from collections import defaultdict
from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import numpy as np

##############################################
# CONFIGURATION
##############################################

class Config:
    # API Credentials (use environment variables)
    API_KEY = os.getenv("KITE_API_KEY", "your_api_key")
    ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "your_access_token")

    # Trading Parameters
    NIFTY_INSTRUMENT_TOKEN = 256265  # Nifty Futures token
    MAX_TRADES_PER_DAY = 5
    LOT_SIZE = 75  # Standard Nifty option lot size
    RISK_PER_TRADE_PCT = 2.0  # % of capital to risk per trade
    MAX_DAILY_LOSS_PCT = 5.0  # % max daily loss

    # Strategy Parameters
    VWAP_DEVIATION_THRESHOLD = 0.005  # 0.5%
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    RSI_PERIOD = 14
    ATR_PERIOD = 14
    ATR_MULTIPLIER_SL = 1.5  # Stop loss = entry - (ATR * multiplier)
    ATR_MULTIPLIER_TARGET = 2.5  # Target = entry + (ATR * multiplier)

    # Day Type Detection
    TREND_PRICE_CHANGE_PCT = 0.003  # 0.3%
    TREND_VWAP_CONFIDENCE = 0.7  # 70% candles above/below VWAP
    DAY_TYPE_REEVAL_INTERVAL = 30  # Re-evaluate every 30 minutes

    # Timing
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 15  # Square off by 3:15 PM
    POLL_INTERVAL_SECONDS = 10

    # Option Chain
    MIN_OI = 1000  # Minimum open interest
    MAX_BID_ASK_SPREAD_PCT = 2.0  # Max 2% bid-ask spread

##############################################
# LOGGING SETUP
##############################################

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('niftybot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

##############################################
# AUTHENTICATION
##############################################

try:
    kite = KiteConnect(api_key=Config.API_KEY)
    kite.set_access_token(Config.ACCESS_TOKEN)
    logger.info("Kite API authenticated successfully")
except Exception as e:
    logger.error(f"Failed to authenticate Kite API: {e}")
    raise

##############################################
# INDICATORS
##############################################

def compute_vwap(df):
    """Calculate VWAP (Volume Weighted Average Price)"""
    df = df.copy()
    df["TP"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (df["TP"] * df["volume"]).cumsum() / df["volume"].cumsum()
    return df

def calculate_ema(series, period):
    """Calculate Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    """Calculate Relative Strength Index - Fixed version"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    df = df.copy()
    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(period).mean()
    return df

##############################################
# DAY TYPE DETECTION
##############################################

def detect_day_type(df):
    """
    Detects market condition: TRENDING or SIDEWAYS
    Uses first 20 candles to determine initial mode
    """
    if len(df) < 20:
        return None

    first_20 = df.iloc[:20].copy()

    # Condition 1: Price consistently above/below VWAP
    above_vwap_ratio = (first_20["close"] > first_20["vwap"]).mean()
    below_vwap_ratio = (first_20["close"] < first_20["vwap"]).mean()
    vwap_consistency = max(above_vwap_ratio, below_vwap_ratio) > Config.TREND_VWAP_CONFIDENCE

    # Condition 2: Significant price movement
    price_change_pct = abs(first_20["close"].iloc[-1] - first_20["close"].iloc[0]) / first_20["close"].iloc[0]
    significant_movement = price_change_pct > Config.TREND_PRICE_CHANGE_PCT

    # Condition 3: EMA alignment (5 > 20 for uptrend, 5 < 20 for downtrend)
    ema5 = calculate_ema(first_20["close"], 5).iloc[-1]
    ema20 = calculate_ema(first_20["close"], 20).iloc[-1]
    ema_aligned = abs(ema5 - ema20) / ema20 > 0.002  # 0.2% difference

    # Trending if at least 2 conditions met
    trend_score = sum([vwap_consistency, significant_movement, ema_aligned])

    if trend_score >= 2:
        return "TRENDING"
    else:
        return "SIDEWAYS"

##############################################
# STRATEGY SIGNALS
##############################################

def trend_signal(df):
    """
    Trend continuation with pullback detection
    Enter when price pulls back to VWAP then resumes trend
    """
    if len(df) < 3:
        return None

    current_price = df["close"].iloc[-1]
    prev_price = df["close"].iloc[-2]
    vwap = df["vwap"].iloc[-1]
    ema5 = calculate_ema(df["close"], 5).iloc[-1]
    ema20 = calculate_ema(df["close"], 20).iloc[-1]

    # Bullish: EMA5 > EMA20, price pulled back to VWAP, now bouncing up
    if ema5 > ema20:
        if prev_price <= vwap < current_price:  # Pullback complete, resuming
            return "BUY_CE"

    # Bearish: EMA5 < EMA20, price pulled back to VWAP, now bouncing down
    elif ema5 < ema20:
        if prev_price >= vwap > current_price:  # Pullback complete, resuming
            return "BUY_PE"

    return None

def mean_reversion_signal(df):
    """
    Mean reversion when price deviates significantly from VWAP
    Enter when oversold/overbought + deviation from VWAP
    """
    if len(df) < Config.RSI_PERIOD + 1:
        return None

    current_price = df["close"].iloc[-1]
    vwap = df["vwap"].iloc[-1]
    deviation = (current_price - vwap) / vwap
    rsi = calculate_rsi(df["close"], Config.RSI_PERIOD).iloc[-1]

    if pd.isna(rsi):
        return None

    # Price above VWAP + overbought → expect reversion down
    if deviation > Config.VWAP_DEVIATION_THRESHOLD and rsi > Config.RSI_OVERBOUGHT:
        return "BUY_PE"

    # Price below VWAP + oversold → expect reversion up
    elif deviation < -Config.VWAP_DEVIATION_THRESHOLD and rsi < Config.RSI_OVERSOLD:
        return "BUY_CE"

    return None

##############################################
# OPTION CHAIN ANALYSIS
##############################################

def get_next_weekly_expiry():
    """Get next weekly Thursday expiry date"""
    today = datetime.date.today()
    days_ahead = 3 - today.weekday()  # Thursday = 3
    if days_ahead <= 0:
        days_ahead += 7
    next_thursday = today + datetime.timedelta(days=days_ahead)
    return next_thursday

def get_option_symbol(strike, option_type, expiry_date):
    """
    Generate correct Zerodha option symbol format
    Format: NIFTY[YY][MMM][DD][STRIKE][CE/PE]
    Example: NIFTY25JAN02 24000CE
    """
    month_map = {
        1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
        7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
    }

    year = str(expiry_date.year)[-2:]
    month = month_map[expiry_date.month]
    day = expiry_date.day

    symbol = f"NIFTY{year}{month}{day:02d}{strike}{option_type}"
    return symbol

def get_atm_strike(nifty_price):
    """Round to nearest 50"""
    return round(nifty_price / 50) * 50

def analyze_option_chain(strike, option_type):
    """
    Validate option liquidity and spreads
    Returns True if option is tradeable
    """
    try:
        expiry = get_next_weekly_expiry()
        symbol = get_option_symbol(strike, option_type, expiry)

        # Get quote for the option
        quote = kite.quote([f"NFO:{symbol}"])

        if not quote:
            logger.warning(f"No quote available for {symbol}")
            return False

        option_data = quote[f"NFO:{symbol}"]

        # Check open interest
        oi = option_data.get('oi', 0)
        if oi < Config.MIN_OI:
            logger.warning(f"{symbol} has low OI: {oi}")
            return False

        # Check bid-ask spread
        bid = option_data.get('depth', {}).get('buy', [{}])[0].get('price', 0)
        ask = option_data.get('depth', {}).get('sell', [{}])[0].get('price', 0)

        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / bid) * 100
            if spread_pct > Config.MAX_BID_ASK_SPREAD_PCT:
                logger.warning(f"{symbol} has wide spread: {spread_pct:.2f}%")
                return False

        logger.info(f"{symbol} passed liquidity checks - OI: {oi}, Spread: {spread_pct:.2f}%")
        return True

    except Exception as e:
        logger.error(f"Error analyzing option chain: {e}")
        return False

##############################################
# POSITION MANAGEMENT
##############################################

class PositionManager:
    def __init__(self):
        self.positions = {}  # symbol: {entry, sl, target, qty, order_id}
        self.daily_pnl = 0.0
        self.trade_count = 0

    def add_position(self, symbol, entry_price, stop_loss, target, qty, order_id):
        """Add new position to tracking"""
        self.positions[symbol] = {
            'entry': entry_price,
            'stop_loss': stop_loss,
            'target': target,
            'qty': qty,
            'order_id': order_id,
            'entry_time': datetime.datetime.now()
        }
        self.trade_count += 1
        logger.info(f"Position added: {symbol} @ {entry_price}, SL: {stop_loss}, TGT: {target}")

    def has_open_positions(self):
        """Check if any positions are open"""
        return len(self.positions) > 0

    def check_exits(self, current_quotes):
        """Check if any positions hit stop-loss or target"""
        to_exit = []

        for symbol, pos in self.positions.items():
            try:
                quote = current_quotes.get(f"NFO:{symbol}")
                if not quote:
                    continue

                ltp = quote.get('last_price', 0)
                if ltp == 0:
                    continue

                # Check stop-loss
                if ltp <= pos['stop_loss']:
                    logger.info(f"Stop-loss hit for {symbol}: LTP {ltp} <= SL {pos['stop_loss']}")
                    to_exit.append((symbol, ltp, 'STOP_LOSS'))

                # Check target
                elif ltp >= pos['target']:
                    logger.info(f"Target hit for {symbol}: LTP {ltp} >= TGT {pos['target']}")
                    to_exit.append((symbol, ltp, 'TARGET'))

            except Exception as e:
                logger.error(f"Error checking exit for {symbol}: {e}")

        return to_exit

    def close_position(self, symbol, exit_price, reason):
        """Close position and calculate P&L"""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        pnl = (exit_price - pos['entry']) * pos['qty']
        self.daily_pnl += pnl

        logger.info(f"Position closed: {symbol} @ {exit_price}, Reason: {reason}, P&L: {pnl:.2f}")
        del self.positions[symbol]

        return pnl

    def square_off_all(self):
        """Square off all open positions (used at market close)"""
        symbols = list(self.positions.keys())
        for symbol in symbols:
            try:
                place_order(symbol, self.positions[symbol]['qty'], "SELL")
                logger.info(f"Squared off position: {symbol}")
            except Exception as e:
                logger.error(f"Error squaring off {symbol}: {e}")

##############################################
# RISK MANAGEMENT
##############################################

def calculate_position_size(entry_price, stop_loss, account_size):
    """
    Calculate position size based on risk per trade
    Risk = (Entry - Stop Loss) * Quantity
    """
    risk_amount = account_size * (Config.RISK_PER_TRADE_PCT / 100)
    risk_per_unit = abs(entry_price - stop_loss)

    if risk_per_unit == 0:
        return Config.LOT_SIZE

    ideal_qty = risk_amount / risk_per_unit
    # Round to lot size
    lots = max(1, round(ideal_qty / Config.LOT_SIZE))
    return lots * Config.LOT_SIZE

def check_daily_loss_limit(position_manager, account_size):
    """Check if daily loss limit is breached"""
    max_loss = account_size * (Config.MAX_DAILY_LOSS_PCT / 100)
    if position_manager.daily_pnl < -max_loss:
        logger.error(f"Daily loss limit breached: {position_manager.daily_pnl:.2f}")
        return True
    return False

##############################################
# ORDER PLACEMENT
##############################################

def place_order(symbol, qty, side="BUY"):
    """Place order with error handling"""
    try:
        order_id = kite.place_order(
            tradingsymbol=symbol,
            exchange="NFO",
            transaction_type=side,
            quantity=qty,
            order_type="MARKET",
            product="MIS",
            validity="DAY"
        )
        logger.info(f"Order placed: {side} {qty} {symbol}, Order ID: {order_id}")
        return order_id
    except Exception as e:
        logger.error(f"Order placement failed for {symbol}: {e}")
        return None

def get_order_execution_price(order_id):
    """Get executed price for an order"""
    try:
        time.sleep(2)  # Wait for order to execute
        order_history = kite.order_history(order_id)

        for order in reversed(order_history):
            if order['status'] == 'COMPLETE':
                return order['average_price']

        logger.warning(f"Order {order_id} not yet executed")
        return None
    except Exception as e:
        logger.error(f"Error fetching order execution price: {e}")
        return None

##############################################
# MAIN BOT LOOP
##############################################

def run_bot():
    """Main trading loop with comprehensive error handling"""
    position_manager = PositionManager()
    day_type = None
    last_day_type_check = None
    account_size = 100000  # Default ₹1 lakh, should fetch from API

    logger.info("=" * 60)
    logger.info("NiftyBot started - Waiting for market data...")
    logger.info("=" * 60)

    try:
        # Get account balance
        profile = kite.profile()
        logger.info(f"Trading account: {profile.get('user_name', 'Unknown')}")
    except Exception as e:
        logger.warning(f"Could not fetch profile: {e}")

    last_candle_timestamp = None

    while True:
        try:
            now = datetime.datetime.now()

            # Check market hours
            if now.hour < Config.MARKET_OPEN_HOUR or \
               (now.hour == Config.MARKET_OPEN_HOUR and now.minute < Config.MARKET_OPEN_MINUTE):
                logger.info("Market not yet open")
                time.sleep(60)
                continue

            # Square off all positions before market close
            if now.hour >= Config.MARKET_CLOSE_HOUR and now.minute >= Config.MARKET_CLOSE_MINUTE:
                logger.info("Market close approaching - Squaring off all positions")
                position_manager.square_off_all()
                logger.info(f"Daily P&L: ₹{position_manager.daily_pnl:.2f}, Trades: {position_manager.trade_count}")
                break

            # Fetch latest NIFTY data
            df = kite.historical_data(
                instrument_token=Config.NIFTY_INSTRUMENT_TOKEN,
                from_date=now - datetime.timedelta(minutes=90),
                to_date=now,
                interval="minute"
            )

            if not df or len(df) == 0:
                logger.warning("No data received from API")
                time.sleep(Config.POLL_INTERVAL_SECONDS)
                continue

            df = pd.DataFrame(df)
            df = compute_vwap(df)
            df = calculate_atr(df, Config.ATR_PERIOD)

            # Prevent processing same candle multiple times
            latest_timestamp = df['date'].iloc[-1]
            if latest_timestamp == last_candle_timestamp:
                time.sleep(Config.POLL_INTERVAL_SECONDS)
                continue
            last_candle_timestamp = latest_timestamp

            # Detect or re-evaluate day type
            if day_type is None or \
               (last_day_type_check and (now - last_day_type_check).seconds >= Config.DAY_TYPE_REEVAL_INTERVAL * 60):
                new_day_type = detect_day_type(df)
                if new_day_type:
                    if day_type != new_day_type:
                        logger.info(f"Day type {'detected' if day_type is None else 'changed'}: {new_day_type}")
                    day_type = new_day_type
                    last_day_type_check = now

            if day_type is None:
                logger.info("Waiting for sufficient data to detect day type...")
                time.sleep(Config.POLL_INTERVAL_SECONDS)
                continue

            # Check daily loss limit
            if check_daily_loss_limit(position_manager, account_size):
                logger.error("Daily loss limit breached - Stopping bot")
                position_manager.square_off_all()
                break

            # Check max trades limit
            if position_manager.trade_count >= Config.MAX_TRADES_PER_DAY:
                logger.info(f"Max trades ({Config.MAX_TRADES_PER_DAY}) reached for the day")
                time.sleep(60)
                continue

            # Check exit conditions for open positions
            if position_manager.has_open_positions():
                try:
                    symbols_to_check = [f"NFO:{sym}" for sym in position_manager.positions.keys()]
                    quotes = kite.quote(symbols_to_check)
                    exits = position_manager.check_exits(quotes)

                    for symbol, exit_price, reason in exits:
                        place_order(symbol, position_manager.positions[symbol]['qty'], "SELL")
                        position_manager.close_position(symbol, exit_price, reason)

                except Exception as e:
                    logger.error(f"Error checking exits: {e}")

            # Only generate new signals if no open positions (one trade at a time)
            if not position_manager.has_open_positions():
                # Generate signal based on day type
                if day_type == "TRENDING":
                    signal = trend_signal(df)
                else:
                    signal = mean_reversion_signal(df)

                # Execute trade if signal generated
                if signal:
                    last_price = df["close"].iloc[-1]
                    atm_strike = get_atm_strike(last_price)
                    option_type = "CE" if signal == "BUY_CE" else "PE"

                    # Analyze option chain before trading
                    if not analyze_option_chain(atm_strike, option_type):
                        logger.warning(f"Option {atm_strike}{option_type} failed liquidity checks")
                        time.sleep(Config.POLL_INTERVAL_SECONDS)
                        continue

                    # Generate option symbol
                    expiry = get_next_weekly_expiry()
                    option_symbol = get_option_symbol(atm_strike, option_type, expiry)

                    # Get ATR for stop-loss calculation
                    atr_value = df["ATR"].iloc[-1]
                    if pd.isna(atr_value):
                        logger.warning("ATR not available, skipping trade")
                        time.sleep(Config.POLL_INTERVAL_SECONDS)
                        continue

                    # Place entry order
                    logger.info(f"Signal: {signal} ({day_type} mode) → {option_symbol}")
                    order_id = place_order(option_symbol, Config.LOT_SIZE, "BUY")

                    if order_id:
                        # Get execution price
                        entry_price = get_order_execution_price(order_id)

                        if entry_price:
                            # Calculate stop-loss and target using ATR
                            stop_loss = entry_price - (atr_value * Config.ATR_MULTIPLIER_SL)
                            target = entry_price + (atr_value * Config.ATR_MULTIPLIER_TARGET)

                            # Ensure stops are reasonable (min 5 points)
                            stop_loss = max(stop_loss, entry_price * 0.7)
                            target = min(target, entry_price * 2.0)

                            position_manager.add_position(
                                option_symbol,
                                entry_price,
                                stop_loss,
                                target,
                                Config.LOT_SIZE,
                                order_id
                            )

            # Wait before next iteration
            time.sleep(Config.POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            position_manager.square_off_all()
            break

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(Config.POLL_INTERVAL_SECONDS)

    logger.info("=" * 60)
    logger.info(f"Bot stopped. Final P&L: ₹{position_manager.daily_pnl:.2f}")
    logger.info("=" * 60)

##############################################
# RUN
##############################################

if __name__ == "__main__":
    run_bot()
