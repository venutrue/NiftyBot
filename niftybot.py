##############################################
# HYBRID VWAP NIFTY OPTIONS TRADING BOT
##############################################

import datetime
from kiteconnect import KiteConnect, KiteTicker
import pandas as pd
import numpy as np

##############################################
# 1. AUTHENTICATION
##############################################

kite = KiteConnect(api_key="your_api_key")
kite.set_access_token("your_access_token")   # after generating request token

##############################################
# 2. INDICATORS
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
# 3. DAY TYPE DETECTION
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
# 4. STRATEGY SIGNALS
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
# 5. STRIKE SELECTION
##############################################

def get_atm_strike(nifty_price):
    return round(nifty_price / 50) * 50

##############################################
# 6. ORDER PLACEMENT
##############################################

def place_order(symbol, qty=75, side="BUY"):
    try:
        order_id = kite.place_order(
            tradingsymbol=symbol,
            exchange="NFO",
            transaction_type=side,
            quantity=qty,
            order_type="MARKET",
            product="MIS"
        )
        print(f"Order placed: {order_id}")
        return order_id
    except Exception as e:
        print("Order failed:", e)
        return None

##############################################
# 7. MAIN BOT LOOP
##############################################

def run_bot():
    trade_count = 0
    day_type = None
    
    print("Bot started... Waiting for first 20 candles...")

    historical = pd.DataFrame()

    # Use WebSocket but for simplicity this loop simulates data updates
    while True:
        now = datetime.datetime.now()

        # Stop after market close
        if now.hour >= 15 and now.minute >= 25:
            print("Market closed. Stopping bot.")
            break

        # Fetch latest NIFTY futures data (1m)
        df = kite.historical_data(
            instrument_token=256265,     # Nifty Fut token
            from_date=now - datetime.timedelta(minutes=60),
            to_date=now,
            interval="minute"
        )
        df = pd.DataFrame(df)
        df = compute_vwap(df)
        df = atr(df)

        # Detect day mode after 20 candles
        if len(df) >= 20 and day_type is None:
            day_type = detect_day_type(df)
            print("Day type detected:", day_type)

        # Skip until day type known
        if day_type is None:
            continue

        # If max 5 trades reached
        if trade_count >= 5:
            print("Max trades reached for the day.")
            continue

        # ---- SIGNAL ENGINE ----
        if day_type == "TRENDING":
            signal = trend_signal(df)
        else:
            signal = mean_rev_signal(df)

        # ---- EXECUTE TRADE ----
        if signal:
            # determine ATM CE/PE symbol
            last_price = df["close"].iloc[-1]
            atm = get_atm_strike(last_price)

            if signal == "BUY_CE":
                symbol = f"NIFTY{atm}CE"
            else:
                symbol = f"NIFTY{atm}PE"

            print(f"Signal: {signal} → {symbol}")
            place_order(symbol)
            trade_count += 1

        # Loop delay
        time.sleep(10)

##############################################
# RUN
##############################################

if __name__ == "__main__":
    run_bot()
