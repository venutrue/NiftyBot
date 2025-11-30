##############################################
# SHARED TECHNICAL INDICATORS
# Used by all bots for signal generation
##############################################

import pandas as pd
import numpy as np
from common.config import (
    PSAR_AF, PSAR_MAX_AF, EMA_PERIOD,
    ATR_MULTIPLIER_STOPLOSS
)

##############################################
# VOLUME INDICATORS
##############################################

def compute_vwap(df):
    """
    Calculate Volume Weighted Average Price.

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns

    Returns:
        DataFrame with 'vwap' column added
    """
    df = df.copy()
    df["TP"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (df["TP"] * df["volume"]).cumsum() / df["volume"].cumsum()
    return df

def volume_ratio(df, period=10):
    """
    Calculate volume ratio compared to average.

    Args:
        df: DataFrame with 'volume' column
        period: Lookback period for average

    Returns:
        Current volume / Average volume
    """
    avg_volume = df["volume"].rolling(period).mean().iloc[-1]
    current_volume = df["volume"].iloc[-1]
    return current_volume / avg_volume if avg_volume > 0 else 0

##############################################
# TREND INDICATORS
##############################################

def ema(series, period):
    """
    Calculate Exponential Moving Average.

    Args:
        series: Price series
        period: EMA period

    Returns:
        EMA series
    """
    return series.ewm(span=period, adjust=False).mean()

def sma(series, period):
    """
    Calculate Simple Moving Average.

    Args:
        series: Price series
        period: SMA period

    Returns:
        SMA series
    """
    return series.rolling(window=period).mean()

def adx(df, period=14):
    """
    Calculate Average Directional Index (ADX).

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ADX period (default 14)

    Returns:
        DataFrame with 'ADX', '+DI', '-DI' columns added
    """
    df = df.copy()

    # True Range
    df['TR'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )

    # Directional Movement
    df['+DM'] = np.where(
        (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
        np.maximum(df['high'] - df['high'].shift(1), 0),
        0
    )
    df['-DM'] = np.where(
        (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
        np.maximum(df['low'].shift(1) - df['low'], 0),
        0
    )

    # Smoothed values
    df['TR_smooth'] = df['TR'].rolling(window=period).sum()
    df['+DM_smooth'] = df['+DM'].rolling(window=period).sum()
    df['-DM_smooth'] = df['-DM'].rolling(window=period).sum()

    # Directional Indicators
    df['+DI'] = 100 * (df['+DM_smooth'] / df['TR_smooth'])
    df['-DI'] = 100 * (df['-DM_smooth'] / df['TR_smooth'])

    # ADX
    df['DX'] = 100 * abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
    df['ADX'] = df['DX'].rolling(window=period).mean()

    return df

##############################################
# MOMENTUM INDICATORS
##############################################

def rsi(series, period=14):
    """
    Calculate Relative Strength Index.

    Args:
        series: Price series
        period: RSI period (default 14)

    Returns:
        RSI series
    """
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi_values = 100 - (100 / (1 + rs))

    return pd.Series(rsi_values, index=series.index)

##############################################
# VOLATILITY INDICATORS
##############################################

def atr(df, period=14):
    """
    Calculate Average True Range.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)

    Returns:
        DataFrame with 'ATR' column added
    """
    df = df.copy()
    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(window=period).mean()
    return df

def calculate_stop_loss(entry_price, atr_value, multiplier=ATR_MULTIPLIER_STOPLOSS):
    """
    Calculate stop loss based on ATR.

    Args:
        entry_price: Entry price
        atr_value: Current ATR value
        multiplier: ATR multiplier (default from config)

    Returns:
        Stop loss price
    """
    return entry_price - (atr_value * multiplier)

##############################################
# PARABOLIC SAR
##############################################

def psar(df, af_start=PSAR_AF, af_max=PSAR_MAX_AF):
    """
    Calculate Parabolic SAR.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        af_start: Initial acceleration factor
        af_max: Maximum acceleration factor

    Returns:
        DataFrame with 'PSAR', 'PSAR_trend' columns added
        PSAR_trend: 1 = bullish (dots below), -1 = bearish (dots above)
    """
    df = df.copy()
    length = len(df)

    psar = np.zeros(length)
    psar_trend = np.zeros(length)
    af = af_start
    ep = 0  # Extreme point

    # Initialize
    psar[0] = df['close'].iloc[0]
    trend = 1  # 1 = bullish, -1 = bearish

    for i in range(1, length):
        if trend == 1:  # Bullish
            psar[i] = psar[i-1] + af * (ep - psar[i-1])
            psar[i] = min(psar[i], df['low'].iloc[i-1], df['low'].iloc[i-2] if i > 1 else df['low'].iloc[i-1])

            if df['low'].iloc[i] < psar[i]:
                trend = -1
                psar[i] = ep
                ep = df['low'].iloc[i]
                af = af_start
            else:
                if df['high'].iloc[i] > ep:
                    ep = df['high'].iloc[i]
                    af = min(af + af_start, af_max)
        else:  # Bearish
            psar[i] = psar[i-1] + af * (ep - psar[i-1])
            psar[i] = max(psar[i], df['high'].iloc[i-1], df['high'].iloc[i-2] if i > 1 else df['high'].iloc[i-1])

            if df['high'].iloc[i] > psar[i]:
                trend = 1
                psar[i] = ep
                ep = df['high'].iloc[i]
                af = af_start
            else:
                if df['low'].iloc[i] < ep:
                    ep = df['low'].iloc[i]
                    af = min(af + af_start, af_max)

        psar_trend[i] = trend

    df['PSAR'] = psar
    df['PSAR_trend'] = psar_trend

    return df

def is_psar_bullish(df):
    """Check if PSAR is bullish (dots below price)."""
    return df['PSAR_trend'].iloc[-1] == 1

def is_psar_bearish(df):
    """Check if PSAR is bearish (dots above price)."""
    return df['PSAR_trend'].iloc[-1] == -1

##############################################
# BREAKOUT DETECTION
##############################################

def is_breakout(df, lookback_days=5):
    """
    Check if price broke above recent high.

    Args:
        df: DataFrame with 'high', 'close' columns
        lookback_days: Days to look back for high

    Returns:
        True if current close > previous N days high
    """
    if len(df) < lookback_days + 1:
        return False

    recent_high = df['high'].iloc[-(lookback_days+1):-1].max()
    current_close = df['close'].iloc[-1]

    return current_close > recent_high

def get_breakout_level(df, lookback_days=5):
    """Get the breakout level (previous N days high)."""
    if len(df) < lookback_days + 1:
        return None
    return df['high'].iloc[-(lookback_days+1):-1].max()

##############################################
# EXIT SIGNALS
##############################################

def check_exit_conditions(df, entry_price):
    """
    Check exit conditions (2 of 3 rule).

    Args:
        df: DataFrame with all indicators calculated
        entry_price: Entry price for stop loss calculation

    Returns:
        dict with exit signal and reasons
    """
    conditions_met = 0
    reasons = []

    # Condition 1: PSAR bearish
    if 'PSAR_trend' in df.columns and is_psar_bearish(df):
        conditions_met += 1
        reasons.append("PSAR flip")

    # Condition 2: Price below EMA
    if 'close' in df.columns:
        ema_value = ema(df['close'], EMA_PERIOD).iloc[-1]
        if df['close'].iloc[-1] < ema_value:
            conditions_met += 1
            reasons.append(f"Below EMA({EMA_PERIOD})")

    # Condition 3: ADX declining
    if 'ADX' in df.columns and len(df) > 1:
        if df['ADX'].iloc[-1] < df['ADX'].iloc[-2]:
            conditions_met += 1
            reasons.append("ADX declining")

    # Check stop loss
    stop_loss_hit = False
    if 'ATR' in df.columns:
        stop_loss = calculate_stop_loss(entry_price, df['ATR'].iloc[-1])
        if df['close'].iloc[-1] < stop_loss:
            stop_loss_hit = True
            reasons.append("Stop loss hit")

    return {
        'should_exit': conditions_met >= 2 or stop_loss_hit,
        'conditions_met': conditions_met,
        'reasons': reasons,
        'stop_loss_hit': stop_loss_hit
    }

##############################################
# DAY TYPE DETECTION (for NIFTY)
##############################################

def detect_day_type(df):
    """
    Detect if it's a trending or sideways day.

    Args:
        df: DataFrame with at least 20 candles and VWAP

    Returns:
        'TRENDING' or 'SIDEWAYS'
    """
    if len(df) < 20:
        return None

    first_20 = df.iloc[:20]

    # Condition 1: Consistent position relative to VWAP
    cond1 = (first_20["close"] > first_20["vwap"]).mean() > 0.7 or \
            (first_20["close"] < first_20["vwap"]).mean() > 0.7

    # Condition 2: Significant price movement
    cond2 = abs(first_20["close"].iloc[-1] - first_20["close"].iloc[0]) > \
            0.003 * first_20["close"].iloc[0]

    # Condition 3: EMA crossover direction
    cond3 = (ema(first_20["close"], 5).iloc[-1] >
             ema(first_20["close"], 20).iloc[-1])

    if (cond1 + cond2 + cond3) >= 2:
        return "TRENDING"
    else:
        return "SIDEWAYS"

##############################################
# ATM STRIKE CALCULATION
##############################################

def get_atm_strike(price, step=50):
    """
    Calculate ATM strike price.

    Args:
        price: Current price
        step: Strike step (50 for NIFTY, 100 for BANKNIFTY)

    Returns:
        ATM strike price
    """
    return round(price / step) * step
