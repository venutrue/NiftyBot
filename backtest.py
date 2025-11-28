##############################################
# NIFTYBOT BACKTESTER
# Run: python backtest.py
##############################################

import datetime
from kiteconnect import KiteConnect
import pandas as pd
import numpy as np

##############################################
# CONFIGURATION
##############################################

API_KEY = "your_api_key"
ACCESS_TOKEN = "your_access_token"

# Backtest settings
BACKTEST_DAYS = 30          # How many days to backtest
LOT_SIZE = 75               # NIFTY lot size
MAX_TRADES_PER_DAY = 5      # Max trades per day
BROKERAGE_PER_TRADE = 40    # Approximate brokerage per order

# NIFTY 50 token
NIFTY_50_TOKEN = 256265

##############################################
# CONNECT TO KITE
##############################################

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

##############################################
# INDICATORS (same as niftybot.py)
##############################################

def compute_vwap(df):
    df = df.copy()
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

##############################################
# DAY TYPE DETECTION
##############################################

def detect_day_type(df):
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
# STRATEGY SIGNALS
##############################################

def trend_signal(df):
    if df["close"].iloc[-1] > df["vwap"].iloc[-1]:
        return "BUY_CE"
    elif df["close"].iloc[-1] < df["vwap"].iloc[-1]:
        return "BUY_PE"
    return None

def mean_rev_signal(df):
    deviation = (df["close"].iloc[-1] - df["vwap"].iloc[-1]) / df["vwap"].iloc[-1]
    rsi_val = rsi(df["close"]).iloc[-1]

    if deviation > 0.005 and rsi_val > 70:
        return "BUY_PE"
    elif deviation < -0.005 and rsi_val < 30:
        return "BUY_CE"
    return None

def get_atm_strike(nifty_price):
    return round(nifty_price / 50) * 50

##############################################
# FETCH HISTORICAL DATA
##############################################

def fetch_historical_data(days):
    """Fetch minute-by-minute data for backtesting."""
    print(f"Fetching {days} days of historical data...")

    to_date = datetime.datetime.now()
    from_date = to_date - datetime.timedelta(days=days)

    try:
        data = kite.historical_data(
            instrument_token=NIFTY_50_TOKEN,
            from_date=from_date,
            to_date=to_date,
            interval="minute"
        )
        df = pd.DataFrame(data)
        print(f"Fetched {len(df)} candles")
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

##############################################
# SIMULATE OPTION PRICE MOVEMENT
##############################################

def estimate_option_pnl(entry_price, exit_price, signal, lot_size):
    """
    Simplified P&L estimation for options.
    In reality, option prices depend on many factors (delta, theta, IV, etc.)
    This uses a simplified model based on NIFTY movement.
    """
    price_change = exit_price - entry_price

    # Approximate delta for ATM options is ~0.5
    delta = 0.5

    if signal == "BUY_CE":
        # Call option gains when NIFTY goes up
        option_pnl = price_change * delta * lot_size
    else:
        # Put option gains when NIFTY goes down
        option_pnl = -price_change * delta * lot_size

    return option_pnl

##############################################
# RUN BACKTEST
##############################################

def run_backtest():
    print("=" * 60)
    print("NIFTYBOT BACKTESTER")
    print("=" * 60)
    print()

    # Fetch data
    df = fetch_historical_data(BACKTEST_DAYS)
    if df is None or len(df) == 0:
        print("No data available for backtesting")
        return

    # Add date column for grouping
    df['date'] = pd.to_datetime(df['date']).dt.date

    # Results tracking
    all_trades = []
    total_pnl = 0
    winning_trades = 0
    losing_trades = 0

    # Group by date and process each day
    unique_dates = df['date'].unique()
    print(f"Processing {len(unique_dates)} trading days...")
    print()

    for date in unique_dates:
        day_df = df[df['date'] == date].copy().reset_index(drop=True)

        if len(day_df) < 60:  # Need at least 60 candles for a meaningful day
            continue

        # Compute indicators
        day_df = compute_vwap(day_df)

        # Detect day type after first 20 candles
        if len(day_df) < 20:
            continue

        day_type = detect_day_type(day_df.iloc[:20])

        trade_count = 0

        # Simulate trading throughout the day
        for i in range(30, len(day_df) - 30, 10):  # Check every 10 candles
            if trade_count >= MAX_TRADES_PER_DAY:
                break

            current_df = day_df.iloc[:i+1].copy()
            current_df = compute_vwap(current_df)

            # Get signal
            if day_type == "TRENDING":
                signal = trend_signal(current_df)
            else:
                signal = mean_rev_signal(current_df)

            if signal:
                entry_price = current_df["close"].iloc[-1]
                entry_time = current_df.index[-1]
                atm_strike = get_atm_strike(entry_price)

                # Exit after 30 candles (30 minutes) or at day end
                exit_idx = min(i + 30, len(day_df) - 1)
                exit_price = day_df["close"].iloc[exit_idx]

                # Calculate P&L
                pnl = estimate_option_pnl(entry_price, exit_price, signal, LOT_SIZE)
                pnl -= BROKERAGE_PER_TRADE * 2  # Entry + Exit brokerage

                total_pnl += pnl
                trade_count += 1

                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1

                all_trades.append({
                    'date': date,
                    'day_type': day_type,
                    'signal': signal,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'strike': atm_strike,
                    'pnl': pnl
                })

                # Skip ahead to avoid overlapping trades
                i += 30

    # Print Results
    print("=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print()

    total_trades = winning_trades + losing_trades

    if total_trades == 0:
        print("No trades were generated during the backtest period.")
        return

    win_rate = (winning_trades / total_trades) * 100

    print(f"Period:           Last {BACKTEST_DAYS} days")
    print(f"Total Trades:     {total_trades}")
    print(f"Winning Trades:   {winning_trades}")
    print(f"Losing Trades:    {losing_trades}")
    print(f"Win Rate:         {win_rate:.1f}%")
    print()
    print(f"Total P&L:        Rs. {total_pnl:,.2f}")
    print(f"Avg P&L/Trade:    Rs. {total_pnl/total_trades:,.2f}")
    print()

    # Show recent trades
    print("=" * 60)
    print("LAST 10 TRADES")
    print("=" * 60)
    print()
    print(f"{'Date':<12} {'Type':<10} {'Signal':<8} {'Entry':<10} {'Exit':<10} {'P&L':<12}")
    print("-" * 60)

    for trade in all_trades[-10:]:
        pnl_str = f"Rs. {trade['pnl']:,.0f}"
        pnl_color = "+" if trade['pnl'] > 0 else ""
        print(f"{str(trade['date']):<12} {trade['day_type']:<10} {trade['signal']:<8} "
              f"{trade['entry_price']:<10.2f} {trade['exit_price']:<10.2f} {pnl_color}{pnl_str:<12}")

    print()
    print("=" * 60)
    print("Note: This is a simplified backtest. Actual results may vary due to:")
    print("- Option premium variations (IV, theta decay)")
    print("- Slippage and execution delays")
    print("- Market gaps and circuit limits")
    print("=" * 60)

##############################################
# ENTRY POINT
##############################################

if __name__ == "__main__":
    try:
        run_backtest()
    except KeyboardInterrupt:
        print("\nBacktest cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
