##############################################
# NIFTYBOT - NIFTY OPTIONS TRADING BOT
# Strategy: VWAP + Supertrend + ADX Confluence
# Capital: Rs. 2 Lakhs
##############################################

import datetime
import time
import pandas as pd

from common.config import (
    NIFTY_50_TOKEN, NIFTY_LOT_SIZE, NIFTY_MAX_TRADES_PER_DAY,
    EXCHANGE_NFO, TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, PRODUCT_MIS,
    MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
    # New strategy parameters
    TOTAL_CAPITAL, TRADING_CAPITAL,
    MAX_INVESTMENT_PER_TRADE, MIN_INVESTMENT_PER_TRADE,
    MAX_LOSS_PER_DAY, MAX_CONSECUTIVE_LOSSES,
    LOSS_COOLDOWN_MINUTES, REASSESS_BIAS_AFTER_LOSS,
    INITIAL_SL_PERCENT, BREAKEVEN_TRIGGER_PERCENT, TRAIL_PERCENT,
    TRAIL_FREQUENCY, TRAIL_INCREMENT, MAX_PROFIT_GIVEBACK,
    SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER,
    ADX_ENTRY_THRESHOLD, VWAP_BUFFER_PERCENT,
    GAP_DETECTION_ENABLED, MEDIUM_GAP_THRESHOLD, LARGE_GAP_THRESHOLD,
    MEDIUM_GAP_WAIT_MINUTES, LARGE_GAP_WAIT_MINUTES,
    TRAILING_STOP_METHOD, TRAILING_EMA_PERIOD,
    TRADING_START_HOUR, TRADING_START_MINUTE,
    LAST_ENTRY_HOUR, LAST_ENTRY_MINUTE,
    FORCE_EXIT_HOUR, FORCE_EXIT_MINUTE,
    # Hidden Stop Loss (Anti Stop-Hunting)
    HIDDEN_SL_ENABLED, HIDDEN_SL_METHOD, EMERGENCY_SL_PERCENT, SL_CANDLE_INTERVAL,
    # Two-Candle Confirmation & Candle-Low Based SL
    TWO_CANDLE_EXIT_ENABLED, CANDLE_LOW_SL_ENABLED, SL_BUFFER_PERCENT, TRAIL_ON_NEW_HIGH_ONLY, MAX_SL_PERCENT_FROM_ENTRY,
    # Market Regime Filter (Weekly + Daily -> VWAP Matrix)
    MARKET_REGIME_ENABLED, MIN_TRADE_QUALITY_SCORE, ENFORCE_DIRECTION_FILTER,
    # Trend-Aware Trailing Stop Loss
    TREND_AWARE_TRAILING_ENABLED, STRONG_TREND_ADX, WEAK_TREND_ADX,
    STRONG_TREND_BREAKEVEN_PERCENT, STRONG_TREND_TRAIL_FREQUENCY,
    STRONG_TREND_TRAIL_INCREMENT, STRONG_TREND_MAX_GIVEBACK, STRONG_TREND_EXIT_ON_ST_FLIP,
    WEAK_TREND_BREAKEVEN_PERCENT, WEAK_TREND_TRAIL_FREQUENCY,
    WEAK_TREND_TRAIL_INCREMENT, WEAK_TREND_MAX_GIVEBACK,
    # Expiry Day Protection
    SKIP_OPTION_BUYING_ON_EXPIRY, EXPIRY_DAY_CUTOFF_TIME,
    # Profit Target & Return Normalization
    PROFIT_TARGET_ENABLED, PROFIT_TARGET_PERCENT,
    PARTIAL_PROFIT_ENABLED, PARTIAL_PROFIT_PERCENT, PARTIAL_PROFIT_QTY_PERCENT,
    # Market Open Trading
    MARKET_OPEN_TRADING_ENABLED, MARKET_OPEN_WINDOW_END_MINUTE,
    PREV_DAY_VWAP_THRESHOLD, ENFORCE_PREV_DAY_VWAP_BIAS
)
from common.logger import setup_logger, log_signal, log_system
from common.technical_sl import calculate_entry_stop_loss
from common.indicators import (
    compute_vwap, atr, adx, ema,
    supertrend, is_supertrend_bullish, is_supertrend_bearish,
    get_atm_strike
)
from common.market_regime import MarketRegimeAnalyzer, VWAPStrategy
from executor.trade_journal import get_journal

##############################################
# NIFTYBOT CLASS
##############################################

class NiftyBot:
    """
    NIFTY Options Trading Bot - 2 Lakhs Capital Strategy.

    Entry Strategy (ALL must be true):
    - Option Premium > Option VWAP (smart money accumulation)
    - Supertrend bullish (for CE) or bearish (for PE) on spot
    - ADX > 23 (confirming trend strength) on spot

    Exit Strategy:
    - Phase 1: Fixed SL at 20% loss
    - Phase 2: Move SL to entry at +20% profit
    - Phase 3: Trail using Supertrend
    - Hard exit at 3:15 PM
    """

    def __init__(self, executor):
        """Initialize NiftyBot."""
        self.name = "NIFTYBOT"
        self.executor = executor
        self.logger = setup_logger(self.name)

        # Trade journal - Excel export for easy review
        # Determines mode from executor type
        mode = 'PAPER' if hasattr(executor, 'paper_engine') else 'LIVE'
        self.journal = get_journal(mode=mode)

        # State tracking
        self.trade_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.active_positions = {}

        # Position tracking
        self.max_premium_seen = {}  # Track highest premium for trailing

        # Gap detection tracking
        self.gap_detected = False
        self.gap_percentage = 0.0
        self.previous_close = None
        self.trading_delay_until = None  # Datetime when trading can start

        # Market-open trading (previous day VWAP reference)
        self.previous_day_vwap = None     # Yesterday's closing VWAP
        self.market_open_bias = None      # 'BULLISH' or 'BEARISH' based on prev day VWAP
        self.market_open_trade_taken = False  # Track if we took a market-open trade

        # Market regime analyzer (Weekly + Daily -> VWAP Matrix)
        self.regime_analyzer = MarketRegimeAnalyzer(executor) if MARKET_REGIME_ENABLED else None
        self.current_regime = None  # Cached regime for the day
        self._regime_analyzed = False  # Flag to run analysis once per day

        # Instrument cache (avoid repeated API calls)
        self._nfo_instruments = None
        self._instruments_loaded = False

        # Cooldown tracking (after losses)
        self.last_loss_time = None  # Time of last loss
        self.cooldown_until = None  # Don't trade until this time

    def reset_daily_state(self):
        """Reset state at start of new trading day."""
        self.trade_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.active_positions = {}
        self.max_premium_seen = {}

        # Reset gap detection
        self.gap_detected = False
        self.gap_percentage = 0.0
        self.previous_close = None
        self.trading_delay_until = None

        # Reset market-open trading state
        self.previous_day_vwap = None
        self.market_open_bias = None
        self.market_open_trade_taken = False

        # Reset market regime analysis (will be recalculated at market open)
        self.current_regime = None
        self._regime_analyzed = False

        # Reset expiry day flags (will be rechecked at first scan)
        self._expiry_day_checked = False
        self._is_expiry = False
        self._expiry_skip_logged = False
        self._expiry_cutoff_logged = False

        # Refresh instruments daily (expiry changes)
        self._nfo_instruments = None
        self._instruments_loaded = False

        # Reset cooldown
        self.last_loss_time = None
        self.cooldown_until = None

        self.logger.info("Daily state reset")

    def _load_nfo_instruments(self):
        """Load NFO instruments list (cached for the day)."""
        if self._instruments_loaded:
            return self._nfo_instruments

        try:
            self._nfo_instruments = self.executor.get_instruments(EXCHANGE_NFO)
            self._instruments_loaded = True
            self.logger.info(f"Loaded {len(self._nfo_instruments)} NFO instruments")
            return self._nfo_instruments
        except Exception as e:
            self.logger.error(f"Failed to load NFO instruments: {str(e)}")
            return None

    def _get_option_token(self, symbol):
        """Get instrument token for an option symbol."""
        instruments = self._load_nfo_instruments()
        if instruments is None:
            return None

        for inst in instruments:
            if inst['tradingsymbol'] == symbol:
                return inst['instrument_token']

        # Enhanced debugging: show similar symbols if exact match not found
        # This helps identify symbol format issues
        similar_symbols = []
        for inst in instruments:
            # Look for NIFTY options with similar characteristics
            if inst['name'] == 'NIFTY' and inst['instrument_type'] in ['CE', 'PE']:
                sym = inst['tradingsymbol']
                # Check if strike price matches
                if str(symbol.split('CE')[0].split('PE')[0][-5:]) in sym:
                    similar_symbols.append(sym)
                    if len(similar_symbols) >= 3:  # Show max 3 examples
                        break

        if similar_symbols:
            self.logger.warning(
                f"Symbol '{symbol}' not found. Similar symbols in instruments: {', '.join(similar_symbols[:3])}"
            )
        else:
            self.logger.warning(f"Symbol '{symbol}' not found in NFO instruments")

        return None

    def fetch_option_data(self, symbol):
        """
        Fetch option historical data and compute VWAP.

        Args:
            symbol: Option trading symbol (e.g., NIFTY25D1626200CE - Dec 16, 2025)

        Returns:
            DataFrame with option OHLCV and VWAP, or None if failed
        """
        token = self._get_option_token(symbol)
        if token is None:
            self.logger.debug(f"Could not find token for {symbol}")
            return None

        now = datetime.datetime.now()
        # Get data from market open for VWAP calculation
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)

        try:
            data = self.executor.get_historical_data(
                instrument_token=token,
                from_date=market_open,
                to_date=now,
                interval="minute"
            )

            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df = compute_vwap(df)

                # CRITICAL: Validate data freshness
                last_candle_time = df['date'].iloc[-1]
                # Remove timezone info to avoid tz-naive/tz-aware comparison error
                if hasattr(last_candle_time, 'tz_localize'):
                    last_candle_time = last_candle_time.tz_localize(None)
                elif hasattr(last_candle_time, 'replace') and last_candle_time.tzinfo is not None:
                    last_candle_time = last_candle_time.replace(tzinfo=None)

                data_age_seconds = (datetime.datetime.now() - last_candle_time).total_seconds()

                if data_age_seconds > 300:  # 5 minutes
                    self.logger.warning(
                        f"{symbol}: Historical data delayed by {data_age_seconds:.0f}s "
                        f"(last candle: {last_candle_time.strftime('%H:%M:%S')})"
                    )

                return df

        except Exception as e:
            self.logger.error(f"Failed to fetch option data for {symbol}: {str(e)}")

        return None

    def get_option_adx(self, symbol):
        """
        Calculate ADX for an option contract.

        Fetches option historical data (including previous day if needed)
        and calculates ADX. This is useful for index options where the
        underlying index has no trading volume - the option ADX reflects
        actual traded price action.

        Args:
            symbol: Option trading symbol (e.g., NIFTY25JAN24500CE)

        Returns:
            float: Current ADX value, or None if calculation failed
        """
        token = self._get_option_token(symbol)
        if token is None:
            return None

        now = datetime.datetime.now()
        market_open_today = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)

        # Calculate how many minutes since market open
        if now < market_open_today:
            minutes_since_open = 0
        else:
            minutes_since_open = int((now - market_open_today).total_seconds() / 60)

        # ADX needs ~30 candles minimum
        MIN_CANDLES_FOR_ADX = 35

        try:
            if minutes_since_open < MIN_CANDLES_FOR_ADX:
                # Fetch previous trading day data for ADX calculation
                yesterday = now - datetime.timedelta(days=1)
                while yesterday.weekday() >= 5:  # Skip weekends
                    yesterday = yesterday - datetime.timedelta(days=1)

                prev_day_start = yesterday.replace(hour=14, minute=30, second=0, microsecond=0)
                prev_day_end = yesterday.replace(hour=15, minute=30, second=0, microsecond=0)

                prev_data = self.executor.get_historical_data(
                    instrument_token=token,
                    from_date=prev_day_start,
                    to_date=prev_day_end,
                    interval="minute"
                )

                today_data = self.executor.get_historical_data(
                    instrument_token=token,
                    from_date=market_open_today,
                    to_date=now,
                    interval="minute"
                )

                if prev_data and today_data:
                    df_prev = pd.DataFrame(prev_data)
                    df_today = pd.DataFrame(today_data)
                    df_combined = pd.concat([df_prev, df_today], ignore_index=True)
                    df_combined = adx(df_combined)
                    option_adx = df_combined['ADX'].iloc[-1]
                    if pd.notna(option_adx):
                        return float(option_adx)
                elif today_data:
                    df = pd.DataFrame(today_data)
                    df = adx(df)
                    option_adx = df['ADX'].iloc[-1]
                    if pd.notna(option_adx):
                        return float(option_adx)
            else:
                # Normal case: enough candles from today
                from_date = now - datetime.timedelta(minutes=120)
                data = self.executor.get_historical_data(
                    instrument_token=token,
                    from_date=from_date,
                    to_date=now,
                    interval="minute"
                )

                if data:
                    df = pd.DataFrame(data)
                    df = adx(df)
                    option_adx = df['ADX'].iloc[-1]
                    if pd.notna(option_adx):
                        return float(option_adx)

        except Exception as e:
            self.logger.debug(f"Failed to calculate option ADX for {symbol}: {str(e)}")

        return None

    def get_weekly_expiry(self):
        """
        Get the nearest weekly expiry date from actual Kite instruments.

        This method queries real expiry dates from Kite instead of calculating
        them mathematically. This handles holidays and special cases automatically.

        Returns:
            datetime.date object for nearest expiry, or None if not found
        """
        instruments = self._load_nfo_instruments()
        if not instruments:
            self.logger.error("No instruments loaded, cannot determine expiry")
            return None

        today = datetime.date.today()

        # Extract all unique expiry dates for NIFTY options
        nifty_expiries = set()
        for inst in instruments:
            if inst['name'] == 'NIFTY' and inst['instrument_type'] in ['CE', 'PE']:
                expiry = inst.get('expiry')
                if expiry and expiry >= today:
                    nifty_expiries.add(expiry)

        if not nifty_expiries:
            self.logger.error(f"No NIFTY expiries found >= {today}")
            return None

        # Get the nearest expiry (min of all future expiries)
        nearest_expiry = min(nifty_expiries)

        self.logger.debug(f"Using NIFTY expiry: {nearest_expiry}")
        return nearest_expiry

    def get_option_symbol(self, strike, option_type):
        """
        Get NIFTY option symbol by looking up from actual instruments.

        This handles both weekly and monthly expiries correctly by querying
        the actual tradingsymbol from the instruments list instead of
        constructing it.

        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'

        Returns:
            Trading symbol string, or None if not found
        """
        expiry_date = self.get_weekly_expiry()
        if not expiry_date:
            self.logger.error("Could not determine expiry date")
            return None

        # Load instruments
        instruments = self._load_nfo_instruments()
        if not instruments:
            self.logger.error("No instruments loaded")
            return None

        # Find the option in instruments by matching expiry, strike, and type
        for inst in instruments:
            if (inst['name'] == 'NIFTY' and
                inst['instrument_type'] == option_type and
                inst['expiry'] == expiry_date and
                inst['strike'] == strike):

                symbol = inst['tradingsymbol']

                # Log expiry date for verification (only log once per session)
                if not hasattr(self, '_expiry_logged') or not self._expiry_logged:
                    # Determine if weekly or monthly based on symbol format
                    expiry_type = "weekly" if len(symbol.replace('NIFTY', '').split(option_type)[0]) <= 5 else "monthly"
                    self.logger.info(f"Trading expiry: {expiry_date.strftime('%Y-%m-%d')} ({expiry_date.strftime('%A')})")
                    self.logger.info(f"Option symbol format: {symbol.replace(str(int(strike)), 'XXXXX')} ({expiry_type})")
                    self._expiry_logged = True

                return symbol

        # Symbol not found
        self.logger.error(
            f"Could not find NIFTY option: expiry={expiry_date}, strike={strike}, type={option_type}"
        )
        return None

    def calculate_lots(self, premium):
        """
        Calculate number of lots based on capital constraints.

        Args:
            premium: Option premium price

        Returns:
            Number of lots to trade, or None if premium is invalid
        """
        # SAFETY: Validate premium is in reasonable range
        # ATM NIFTY options typically trade between Rs. 20 - Rs. 2000
        MIN_REASONABLE_PREMIUM = 20.0
        MAX_REASONABLE_PREMIUM = 2000.0

        if premium < MIN_REASONABLE_PREMIUM:
            self.logger.error(
                f"REJECTED: Premium too low (₹{premium:.2f} < ₹{MIN_REASONABLE_PREMIUM}) - "
                f"Option may be worthless or data error"
            )
            return None

        if premium > MAX_REASONABLE_PREMIUM:
            self.logger.error(
                f"REJECTED: Premium too high (₹{premium:.2f} > ₹{MAX_REASONABLE_PREMIUM}) - "
                f"Option may be deep ITM or data error"
            )
            return None

        lot_value = premium * NIFTY_LOT_SIZE

        # Calculate lots based on max investment
        max_lots = int(MAX_INVESTMENT_PER_TRADE / lot_value)
        min_lots = int(MIN_INVESTMENT_PER_TRADE / lot_value)

        # Ensure at least min_lots, but not more than max_lots
        lots = max(min_lots, 1)
        lots = min(lots, max_lots)

        # Cap at reasonable number (15 lots max)
        lots = min(lots, 15)

        # SAFETY: Validate calculated position size is reasonable
        total_investment = lots * lot_value
        if total_investment < MIN_INVESTMENT_PER_TRADE * 0.5:
            self.logger.warning(
                f"Position size very small: ₹{total_investment:,.0f} "
                f"(Premium: ₹{premium:.2f}, Lots: {lots})"
            )
        elif total_investment > MAX_INVESTMENT_PER_TRADE * 1.1:
            self.logger.error(
                f"REJECTED: Position size too large: ₹{total_investment:,.0f} > "
                f"₹{MAX_INVESTMENT_PER_TRADE:,.0f}"
            )
            return None

        self.logger.info(
            f"Position size: {lots} lots × ₹{premium:.2f} = ₹{total_investment:,.0f}"
        )

        return lots

    def detect_gap(self, df):
        """
        Detect gap at market open and determine trading delay.

        Gap Protection Strategy:
        - Medium Gap (0.4-0.8%): Wait 30 minutes (trade from 9:45 AM)
        - Large Gap (>0.8%): Wait 60 minutes (trade from 10:15 AM)

        This avoids gap-fill traps where premium crashes after initial excitement.

        Args:
            df: DataFrame with NIFTY spot data

        Returns:
            None (updates internal state)
        """
        if not GAP_DETECTION_ENABLED:
            return

        # Only detect gap once per day at market open
        if self.gap_detected:
            return

        now = datetime.datetime.now()
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)

        # Only check within first 5 minutes of market open
        if now > market_open + datetime.timedelta(minutes=5):
            # Too late to detect gap, assume no gap
            self.gap_detected = True
            return

        if df is None or len(df) < 2:
            return

        # Get today's open and yesterday's close
        first_candle = df.iloc[0]
        today_open = first_candle['open']

        # Store previous close and VWAP for future reference
        if self.previous_close is None:
            # Get previous trading day
            yesterday = now - datetime.timedelta(days=1)
            # Skip weekends
            while yesterday.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                yesterday = yesterday - datetime.timedelta(days=1)

            # Fetch full previous day's data for VWAP calculation (9:15 AM - 3:30 PM)
            prev_day_start = yesterday.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)
            prev_day_end = yesterday.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

            yesterday_data = self.executor.get_historical_data(
                instrument_token=NIFTY_50_TOKEN,
                from_date=prev_day_start,
                to_date=prev_day_end,
                interval="minute"
            )

            if yesterday_data and len(yesterday_data) > 0:
                self.previous_close = yesterday_data[-1]['close']

                # Calculate previous day's VWAP for market-open trading
                if MARKET_OPEN_TRADING_ENABLED:
                    df_yesterday = pd.DataFrame(yesterday_data)
                    df_yesterday = compute_vwap(df_yesterday)
                    self.previous_day_vwap = df_yesterday['vwap'].iloc[-1]
                    self.logger.info(
                        f"Previous Day VWAP: {self.previous_day_vwap:.2f} | "
                        f"Previous Close: {self.previous_close:.2f}"
                    )
            else:
                # Fallback: use first candle's open as previous close (assumes no gap)
                self.previous_close = today_open
                self.previous_day_vwap = None

        # Calculate gap percentage
        self.gap_percentage = ((today_open - self.previous_close) / self.previous_close) * 100
        self.gap_detected = True

        # Calculate market-open bias based on previous day VWAP
        if MARKET_OPEN_TRADING_ENABLED and self.previous_day_vwap is not None:
            vwap_deviation = ((today_open - self.previous_day_vwap) / self.previous_day_vwap) * 100

            if vwap_deviation >= PREV_DAY_VWAP_THRESHOLD:
                self.market_open_bias = 'BULLISH'
                self.logger.info(
                    f"📈 MARKET OPEN BIAS: BULLISH | Today Open {today_open:.2f} is "
                    f"+{vwap_deviation:.2f}% above Prev Day VWAP {self.previous_day_vwap:.2f} "
                    f"(threshold: {PREV_DAY_VWAP_THRESHOLD}%)"
                )
            elif vwap_deviation <= -PREV_DAY_VWAP_THRESHOLD:
                self.market_open_bias = 'BEARISH'
                self.logger.info(
                    f"📉 MARKET OPEN BIAS: BEARISH | Today Open {today_open:.2f} is "
                    f"{vwap_deviation:.2f}% below Prev Day VWAP {self.previous_day_vwap:.2f} "
                    f"(threshold: {PREV_DAY_VWAP_THRESHOLD}%)"
                )
            else:
                self.market_open_bias = None
                self.logger.info(
                    f"⚖️ MARKET OPEN BIAS: NEUTRAL | Today Open {today_open:.2f} is "
                    f"{vwap_deviation:+.2f}% from Prev Day VWAP {self.previous_day_vwap:.2f} "
                    f"(below threshold: {PREV_DAY_VWAP_THRESHOLD}%) - No market-open trade"
                )

        # Determine trading delay based on gap size
        if abs(self.gap_percentage) >= LARGE_GAP_THRESHOLD:
            # Large gap: wait 60 minutes
            self.trading_delay_until = market_open + datetime.timedelta(minutes=LARGE_GAP_WAIT_MINUTES)
            gap_type = "LARGE"
            wait_min = LARGE_GAP_WAIT_MINUTES

        elif abs(self.gap_percentage) >= MEDIUM_GAP_THRESHOLD:
            # Medium gap: wait 30 minutes
            self.trading_delay_until = market_open + datetime.timedelta(minutes=MEDIUM_GAP_WAIT_MINUTES)
            gap_type = "MEDIUM"
            wait_min = MEDIUM_GAP_WAIT_MINUTES

        else:
            # No significant gap: trade normally
            self.trading_delay_until = None
            gap_type = "NORMAL"
            wait_min = 0

        # Log gap detection
        gap_direction = "UP" if self.gap_percentage > 0 else "DOWN"
        if abs(self.gap_percentage) >= MEDIUM_GAP_THRESHOLD:
            self.logger.warning(
                f"🚨 GAP DETECTED: {gap_type} GAP {gap_direction} of {abs(self.gap_percentage):.2f}% | "
                f"Previous Close: {self.previous_close:.2f} | Today Open: {today_open:.2f} | "
                f"Trading delayed by {wait_min} minutes (start at {self.trading_delay_until.strftime('%H:%M')})"
            )
        else:
            self.logger.info(
                f"✓ Normal gap: {self.gap_percentage:+.2f}% | "
                f"Previous Close: {self.previous_close:.2f} | Today Open: {today_open:.2f}"
            )

    def fetch_data(self):
        """Fetch NIFTY minute data with all indicators.

        Handles early market hours by fetching previous day's data when needed
        to ensure ADX calculation has enough candles (requires ~30 candles minimum).
        """
        now = datetime.datetime.now()
        market_open_today = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)

        # Calculate how many minutes since market open
        if now < market_open_today:
            minutes_since_open = 0
        else:
            minutes_since_open = int((now - market_open_today).total_seconds() / 60)

        # ADX needs ~30 candles minimum (14 for TR/DM smoothing + 14 for DX smoothing)
        MIN_CANDLES_FOR_ADX = 35

        try:
            # If we don't have enough candles from today, fetch yesterday's data too
            if minutes_since_open < MIN_CANDLES_FOR_ADX:
                # Fetch previous trading day data (last 60 minutes of trading: 14:30-15:30)
                yesterday = now - datetime.timedelta(days=1)
                # Skip weekends
                while yesterday.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                    yesterday = yesterday - datetime.timedelta(days=1)

                prev_day_start = yesterday.replace(hour=14, minute=30, second=0, microsecond=0)
                prev_day_end = yesterday.replace(hour=15, minute=30, second=0, microsecond=0)

                prev_data = self.executor.get_historical_data(
                    instrument_token=NIFTY_50_TOKEN,
                    from_date=prev_day_start,
                    to_date=prev_day_end,
                    interval="minute"
                )

                # Fetch today's data from market open
                today_data = self.executor.get_historical_data(
                    instrument_token=NIFTY_50_TOKEN,
                    from_date=market_open_today,
                    to_date=now,
                    interval="minute"
                )

                if prev_data and today_data:
                    # Combine previous day and today's data for indicator calculation
                    df_prev = pd.DataFrame(prev_data)
                    df_today = pd.DataFrame(today_data)

                    # Mark the boundary so we know where today starts
                    prev_day_candle_count = len(df_prev)

                    # Combine dataframes
                    df_combined = pd.concat([df_prev, df_today], ignore_index=True)

                    # Calculate ADX on full combined data (needs history)
                    df_combined = atr(df_combined)
                    df_combined = adx(df_combined)
                    df_combined = supertrend(df_combined, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)

                    # Now slice to today's data only and calculate VWAP (session-based)
                    df = df_combined.iloc[prev_day_candle_count:].copy().reset_index(drop=True)

                    # Calculate VWAP on today's data only (it's session-based)
                    df = compute_vwap(df)

                    return df
                elif today_data:
                    # Fallback: only today's data available
                    df = pd.DataFrame(today_data)
                    df = compute_vwap(df)
                    df = atr(df)
                    df = adx(df)
                    df = supertrend(df, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)
                    return df
            else:
                # Normal case: enough candles from today
                from_date = now - datetime.timedelta(minutes=120)
                data = self.executor.get_historical_data(
                    instrument_token=NIFTY_50_TOKEN,
                    from_date=from_date,
                    to_date=now,
                    interval="minute"
                )

                if data:
                    df = pd.DataFrame(data)
                    df = compute_vwap(df)
                    df = atr(df)
                    df = adx(df)
                    df = supertrend(df, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)
                    return df

        except Exception as e:
            self.logger.error(f"Failed to fetch data: {str(e)}")

        return None

    def scan_option_chain(self, atm_strike, option_type, current_price):
        """
        Scan multiple strikes around ATM to detect smart money accumulation.

        Smart money spreads positions across strikes for:
        - Risk distribution
        - Stealth trading (avoid detection)
        - Building spreads and hedges
        - Managing liquidity impact

        Args:
            atm_strike: ATM strike price
            option_type: 'CE' or 'PE'
            current_price: Current spot price

        Returns:
            List of dicts with strike analysis, sorted by signal strength
        """
        # Check ATM and surrounding strikes (±2 strikes)
        # NIFTY strikes are in 50 increments
        strike_offsets = [-100, -50, 0, 50, 100]  # ATM-2, ATM-1, ATM, ATM+1, ATM+2

        strikes_data = []

        for offset in strike_offsets:
            strike = atm_strike + offset
            symbol = self.get_option_symbol(strike, option_type)

            # Skip if symbol generation failed
            if symbol is None:
                continue

            # Fetch option data with VWAP
            opt_data = self.fetch_option_data(symbol)
            if opt_data is None or len(opt_data) < 5:
                continue

            # Get both historical close and real-time LTP for comparison
            historical_close = opt_data['close'].iloc[-1]
            historical_timestamp = opt_data['date'].iloc[-1]
            # Remove timezone info to avoid tz-naive/tz-aware comparison error
            if hasattr(historical_timestamp, 'tz_localize'):
                historical_timestamp = historical_timestamp.tz_localize(None)
            elif hasattr(historical_timestamp, 'replace') and historical_timestamp.tzinfo is not None:
                historical_timestamp = historical_timestamp.replace(tzinfo=None)

            ltp = self.executor.get_ltp(symbol, EXCHANGE_NFO)

            # CRITICAL: Check how old the historical data is
            data_age_seconds = (datetime.datetime.now() - historical_timestamp).total_seconds()
            if data_age_seconds > 180:  # More than 3 minutes old
                self.logger.warning(
                    f"{symbol}: Historical data is {data_age_seconds:.0f}s old "
                    f"(last candle: {historical_timestamp.strftime('%H:%M:%S')})"
                )

            # Use LTP if available, otherwise fallback to historical close
            if ltp is not None and ltp > 0:
                premium = ltp
                self.logger.info(f"{symbol}: Using real-time LTP = ₹{ltp:.2f}")

                # Warn if LTP differs significantly from historical close (lowered from 10% to 5%)
                price_diff_pct = abs((ltp - historical_close) / historical_close * 100) if historical_close > 0 else 0
                if price_diff_pct > 5:
                    self.logger.warning(
                        f"{symbol}: LTP (₹{ltp:.2f}) differs {price_diff_pct:.1f}% "
                        f"from historical close (₹{historical_close:.2f})"
                    )
            else:
                # CRITICAL: Don't use stale data for trading decisions!
                if data_age_seconds > 180:
                    self.logger.error(
                        f"{symbol}: LTP unavailable and historical data too old "
                        f"({data_age_seconds:.0f}s). Skipping this strike."
                    )
                    continue  # Skip this strike

                premium = historical_close
                self.logger.warning(
                    f"{symbol}: LTP unavailable, using historical close = ₹{historical_close:.2f} "
                    f"(age: {data_age_seconds:.0f}s)"
                )

            vwap = opt_data['vwap'].iloc[-1]
            volume = opt_data['volume'].iloc[-1]
            avg_volume = opt_data['volume'].mean()

            # CRITICAL: Validate VWAP is not NaN (can happen with zero volume)
            if pd.isna(vwap) or vwap <= 0:
                self.logger.warning(
                    f"{symbol}: Invalid VWAP (NaN or zero), skipping strike. "
                    f"Volume: {volume}, Avg Volume: {avg_volume:.0f}"
                )
                continue  # Skip this strike

            # Calculate signal strength metrics
            vwap_diff = premium - vwap
            vwap_pct = ((premium - vwap) / vwap * 100) if vwap > 0 else 0
            volume_surge = (volume / avg_volume) if avg_volume > 0 else 1

            # Determine position type relative to spot
            if option_type == 'CE':
                if strike < current_price:
                    position = 'ITM'
                elif strike == atm_strike:
                    position = 'ATM'
                else:
                    position = 'OTM'
            else:  # PE
                if strike > current_price:
                    position = 'ITM'
                elif strike == atm_strike:
                    position = 'ATM'
                else:
                    position = 'OTM'

            strikes_data.append({
                'strike': strike,
                'symbol': symbol,
                'premium': premium,
                'vwap': vwap,
                'vwap_diff': vwap_diff,
                'vwap_pct': vwap_pct,
                'volume': volume,
                'avg_volume': avg_volume,
                'volume_surge': volume_surge,
                'position': position,
                'signal': vwap_diff > 0  # Smart money accumulation if premium > VWAP
            })

        # Sort by VWAP percentage difference (strongest accumulation first)
        strikes_data.sort(key=lambda x: x['vwap_pct'], reverse=True)

        return strikes_data

    def check_entry_conditions(self, df):
        """
        Check if all entry conditions are met for ATM option.

        Entry Logic:
        - Supertrend and ADX checked on SPOT data
        - VWAP checked on ATM option only (single position trading)
        - Scans full chain for visibility but only trades ATM

        Returns:
            'BUY_CE', 'BUY_PE', or None
        """
        if df is None or len(df) < 20:
            return None

        current_price = df['close'].iloc[-1]
        spot_adx = df['ADX'].iloc[-1]
        st_bullish = is_supertrend_bullish(df)
        st_bearish = is_supertrend_bearish(df)

        # Calculate ATM strike
        atm_strike = get_atm_strike(current_price)
        st_status = "Bullish" if st_bullish else "Bearish"

        # Scan option chain for CE if Supertrend is Bullish
        if st_bullish:
            ce_strikes = self.scan_option_chain(atm_strike, "CE", current_price)

            if not ce_strikes:
                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"SpotADX: {spot_adx:.1f} | ST: {st_status} | "
                    f"CE: No option data available"
                )
                return None

            # Find ATM strike in the results
            atm_data = None
            for strike_data in ce_strikes:
                if strike_data['strike'] == atm_strike:
                    atm_data = strike_data
                    break

            if not atm_data:
                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"SpotADX: {spot_adx:.1f} | ST: {st_status} | "
                    f"CE: ATM data not available"
                )
                return None

            # Calculate option ADX for hybrid approach: max(spot_adx, option_adx)
            option_adx = self.get_option_adx(atm_data['symbol'])
            if option_adx is None:
                option_adx = spot_adx  # Fallback to spot ADX if option ADX unavailable
            effective_adx = max(spot_adx, option_adx) if pd.notna(spot_adx) else option_adx

            # Check ADX strength - determine if we can trade or just monitor
            can_trade = effective_adx >= ADX_ENTRY_THRESHOLD
            mode_status = "" if can_trade else f" [MONITORING - ADX {effective_adx:.1f} < {ADX_ENTRY_THRESHOLD}]"

            # Count strikes with positive signals (for visibility)
            positive_signals = [s for s in ce_strikes if s['signal']]

            # Log chain analysis (informational - shows what's happening across strikes)
            self.logger.info(
                f"Spot: {current_price:.2f} | ATM: {atm_strike} | SpotADX: {spot_adx:.1f} | OptADX: {option_adx:.1f} | ST: {st_status}{mode_status}"
            )
            self.logger.info(
                f"CE Chain Analysis ({len(positive_signals)}/{len(ce_strikes)} strikes above VWAP):"
            )

            for strike_data in ce_strikes[:3]:  # Show top 3 strikes
                signal_icon = "✓" if strike_data['signal'] else "✗"
                atm_marker = " [ATM - TRADING]" if strike_data['strike'] == atm_strike else ""
                self.logger.info(
                    f"  {signal_icon} {strike_data['position']:3} {strike_data['strike']:5} | "
                    f"Premium: {strike_data['premium']:6.2f} | VWAP: {strike_data['vwap']:6.2f} | "
                    f"Diff: {strike_data['vwap_pct']:+5.1f}% | Vol: {strike_data['volume']:.0f}{atm_marker}"
                )

            # Entry condition: ATM Premium > VWAP AND ADX strong enough
            if atm_data['signal']:
                if can_trade:
                    self.logger.info(
                        f">>> CE SIGNAL: {atm_data['symbol']} (ATM) | "
                        f"Premium {atm_data['premium']:.2f} > VWAP {atm_data['vwap']:.2f} "
                        f"(+{atm_data['vwap_pct']:.1f}%) | "
                        f"Supertrend Bullish | ADX {effective_adx:.1f} (Spot:{spot_adx:.1f}/Opt:{option_adx:.1f})"
                    )
                    return 'BUY_CE'
                else:
                    self.logger.info(
                        f">>> CE SIGNAL DETECTED (MONITORING): {atm_data['symbol']} | "
                        f"Premium {atm_data['premium']:.2f} > VWAP {atm_data['vwap']:.2f} "
                        f"(+{atm_data['vwap_pct']:.1f}%) | ADX {effective_adx:.1f} < {ADX_ENTRY_THRESHOLD} - NOT TRADING"
                    )

        # Scan option chain for PE if Supertrend is Bearish
        elif st_bearish:
            pe_strikes = self.scan_option_chain(atm_strike, "PE", current_price)

            if not pe_strikes:
                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"SpotADX: {spot_adx:.1f} | ST: {st_status} | "
                    f"PE: No option data available"
                )
                return None

            # Find ATM strike in the results
            atm_data = None
            for strike_data in pe_strikes:
                if strike_data['strike'] == atm_strike:
                    atm_data = strike_data
                    break

            if not atm_data:
                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"SpotADX: {spot_adx:.1f} | ST: {st_status} | "
                    f"PE: ATM data not available"
                )
                return None

            # Calculate option ADX for hybrid approach: max(spot_adx, option_adx)
            option_adx = self.get_option_adx(atm_data['symbol'])
            if option_adx is None:
                option_adx = spot_adx  # Fallback to spot ADX if option ADX unavailable
            effective_adx = max(spot_adx, option_adx) if pd.notna(spot_adx) else option_adx

            # Check ADX strength - determine if we can trade or just monitor
            can_trade = effective_adx >= ADX_ENTRY_THRESHOLD
            mode_status = "" if can_trade else f" [MONITORING - ADX {effective_adx:.1f} < {ADX_ENTRY_THRESHOLD}]"

            # Count strikes with positive signals (for visibility)
            positive_signals = [s for s in pe_strikes if s['signal']]

            # Log chain analysis (informational - shows what's happening across strikes)
            self.logger.info(
                f"Spot: {current_price:.2f} | ATM: {atm_strike} | SpotADX: {spot_adx:.1f} | OptADX: {option_adx:.1f} | ST: {st_status}{mode_status}"
            )
            self.logger.info(
                f"PE Chain Analysis ({len(positive_signals)}/{len(pe_strikes)} strikes above VWAP):"
            )

            for strike_data in pe_strikes[:3]:  # Show top 3 strikes
                signal_icon = "✓" if strike_data['signal'] else "✗"
                atm_marker = " [ATM - TRADING]" if strike_data['strike'] == atm_strike else ""
                self.logger.info(
                    f"  {signal_icon} {strike_data['position']:3} {strike_data['strike']:5} | "
                    f"Premium: {strike_data['premium']:6.2f} | VWAP: {strike_data['vwap']:6.2f} | "
                    f"Diff: {strike_data['vwap_pct']:+5.1f}% | Vol: {strike_data['volume']:.0f}{atm_marker}"
                )

            # Entry condition: ATM Premium > VWAP AND ADX strong enough
            if atm_data['signal']:
                if can_trade:
                    self.logger.info(
                        f">>> PE SIGNAL: {atm_data['symbol']} (ATM) | "
                        f"Premium {atm_data['premium']:.2f} > VWAP {atm_data['vwap']:.2f} "
                        f"(+{atm_data['vwap_pct']:.1f}%) | "
                        f"Supertrend Bearish | ADX {effective_adx:.1f} (Spot:{spot_adx:.1f}/Opt:{option_adx:.1f})"
                    )
                    return 'BUY_PE'
                else:
                    self.logger.info(
                        f">>> PE SIGNAL DETECTED (MONITORING): {atm_data['symbol']} | "
                        f"Premium {atm_data['premium']:.2f} > VWAP {atm_data['vwap']:.2f} "
                        f"(+{atm_data['vwap_pct']:.1f}%) | ADX {effective_adx:.1f} < {ADX_ENTRY_THRESHOLD} - NOT TRADING"
                    )

        return None

    def get_option_premium(self, symbol):
        """Get current premium for an option."""
        try:
            return self.executor.get_ltp(symbol, EXCHANGE_NFO)
        except Exception as e:
            self.logger.error(f"Failed to get premium for {symbol}: {str(e)}")
            return None

    def get_option_candles(self, symbol, n_candles=3, interval='5minute'):
        """
        Get recent option premium candles for technical SL and candle close confirmation.

        Args:
            symbol: Option symbol (e.g., 'NIFTY25JAN9200CE')
            n_candles: Number of candles to fetch (default 3)
            interval: Candle interval (default '5minute')

        Returns:
            List of candle dicts with 'high', 'low', 'close', 'open' keys
            or None if failed
        """
        try:
            # Get instrument token for the option
            token = self.executor.get_instrument_token(symbol, EXCHANGE_NFO)
            if not token:
                self.logger.warning(f"Could not get token for {symbol}")
                return None

            # Calculate time range (fetch extra candles for safety)
            now = datetime.datetime.now()
            # For 5-minute candles, go back n_candles * 5 + 10 minutes
            minutes_back = (n_candles + 2) * 5 + 10
            from_time = now - datetime.timedelta(minutes=minutes_back)

            # Fetch historical data
            candles = self.executor.get_historical_data(
                instrument_token=token,
                from_date=from_time,
                to_date=now,
                interval=interval
            )

            if not candles or len(candles) < 2:
                self.logger.debug(f"Insufficient candles for {symbol}: got {len(candles) if candles else 0}")
                return None

            # Return last n_candles (excluding current incomplete candle)
            # Kite returns completed candles, so last one should be complete
            return candles[-n_candles:] if len(candles) >= n_candles else candles

        except Exception as e:
            self.logger.error(f"Failed to get option candles for {symbol}: {str(e)}")
            return None

    def scan(self):
        """Main scanning function. Called by run.py."""
        signals = []
        now = datetime.datetime.now()

        # Check if within trading hours
        if not self._is_trading_time(now):
            return signals

        # Force exit check (3:15 PM)
        if self._is_force_exit_time(now):
            return self._force_exit_all("End of day exit")

        # Check daily loss limit
        if self.daily_pnl <= -MAX_LOSS_PER_DAY:
            self.logger.warning(f"Daily loss limit reached: Rs. {self.daily_pnl}")
            return self._force_exit_all("Daily loss limit reached")

        # Check consecutive losses
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.logger.warning(f"Max consecutive losses ({MAX_CONSECUTIVE_LOSSES}) reached")
            return signals  # Don't take new trades, but keep existing positions

        # ============================================
        # CRITICAL: CHECK EXITS FIRST - BEFORE data fetch
        # ============================================
        # This ensures active positions are ALWAYS monitored, even if
        # spot data fetch fails. We check exits with df=None first for
        # emergency/basic SL, then again with df for advanced trailing.
        if len(self.active_positions) > 0:
            # First pass: Emergency exits (no df needed - pure LTP based)
            emergency_exits = self._check_exits(df=None)
            signals.extend(emergency_exits)

        # Fetch data for entries and advanced trailing
        self.logger.info("Fetching NIFTY spot data...")
        df = self.fetch_data()
        if df is None or len(df) < 20:
            self.logger.warning(f"Insufficient spot data (got {len(df) if df is not None else 0} candles) - entries skipped")
            return signals  # Return any emergency exits we found
        self.logger.info(f"Got {len(df)} candles, proceeding with analysis...")

        # Detect gap at market open (only runs once per day)
        self.detect_gap(df)

        # ============================================
        # MARKET REGIME ANALYSIS (Pre-Market Checklist)
        # Weekly sets battlefield, Daily sets rules, VWAP executes
        # ============================================
        if MARKET_REGIME_ENABLED and not self._regime_analyzed:
            self._analyze_market_regime()

        # Second pass: Advanced trailing exits (with df for Supertrend/ADX)
        if len(self.active_positions) > 0:
            exit_signals = self._check_exits(df)
            signals.extend(exit_signals)

        # Check if we can take new entries
        if not self._can_enter_new_trade(now):
            return signals

        # ============================================
        # EXPIRY DAY PROTECTION: Block option buying on expiry day
        # Options lose 80-90% of value rapidly due to theta decay
        # ============================================
        if SKIP_OPTION_BUYING_ON_EXPIRY and self._is_expiry_day():
            if not hasattr(self, '_expiry_skip_logged') or not self._expiry_skip_logged:
                self.logger.warning(
                    f"🚫 EXPIRY DAY PROTECTION: Option buying BLOCKED today. "
                    f"Rapid theta decay makes buying extremely risky. "
                    f"Consider option selling strategies instead."
                )
                self._expiry_skip_logged = True
            return signals

        # Additional check: Even if expiry buying is allowed, stop after cutoff time
        if self._is_expiry_day() and self._is_past_expiry_cutoff(now):
            if not hasattr(self, '_expiry_cutoff_logged') or not self._expiry_cutoff_logged:
                self.logger.warning(
                    f"⏰ EXPIRY CUTOFF: Past {EXPIRY_DAY_CUTOFF_TIME} on expiry day. "
                    f"No new entries allowed."
                )
                self._expiry_cutoff_logged = True
            return signals

        # ============================================
        # REGIME FILTER: Skip if market conditions don't align
        # This eliminates 50-60% of bad trades
        # ============================================
        if MARKET_REGIME_ENABLED and self.current_regime:
            if not self.current_regime.should_trade:
                # Log skip reason periodically (not every scan)
                if not hasattr(self, '_last_regime_skip_log') or \
                   (now - self._last_regime_skip_log).total_seconds() > 300:  # Every 5 min
                    self.logger.info(
                        f"REGIME FILTER: Skipping trades | "
                        f"Reason: {self.current_regime.skip_reason}"
                    )
                    self._last_regime_skip_log = now
                return signals

            # Check minimum quality score
            if self.current_regime.trade_quality_score < MIN_TRADE_QUALITY_SCORE:
                if not hasattr(self, '_last_quality_skip_log') or \
                   (now - self._last_quality_skip_log).total_seconds() > 300:
                    self.logger.info(
                        f"REGIME FILTER: Quality score too low | "
                        f"Score: {self.current_regime.trade_quality_score} < {MIN_TRADE_QUALITY_SCORE}"
                    )
                    self._last_quality_skip_log = now
                return signals

        # Check entry conditions
        signal_type = self.check_entry_conditions(df)

        if signal_type:
            # ============================================
            # MARKET-OPEN BIAS FILTER: During 9:15-9:30, only trade in bias direction
            # ============================================
            if self._is_market_open_window(now) and ENFORCE_PREV_DAY_VWAP_BIAS:
                if self.market_open_bias == 'BULLISH' and signal_type != 'BUY_CE':
                    self.logger.info(
                        f"MARKET-OPEN FILTER: Blocking {signal_type} | "
                        f"Bias is BULLISH (price above prev day VWAP) - only CE allowed"
                    )
                    return signals
                elif self.market_open_bias == 'BEARISH' and signal_type != 'BUY_PE':
                    self.logger.info(
                        f"MARKET-OPEN FILTER: Blocking {signal_type} | "
                        f"Bias is BEARISH (price below prev day VWAP) - only PE allowed"
                    )
                    return signals

            # ============================================
            # DIRECTION FILTER: Only trade in allowed direction
            # ============================================
            if MARKET_REGIME_ENABLED and ENFORCE_DIRECTION_FILTER and self.current_regime:
                # Get current ADX for counter-trend override check
                current_adx = df['ADX'].iloc[-1] if 'ADX' in df.columns and pd.notna(df['ADX'].iloc[-1]) else None
                should_trade, reason = self.regime_analyzer.should_trade_signal(
                    self.current_regime, signal_type, adx_value=current_adx
                )
                if not should_trade:
                    self.logger.info(
                        f"DIRECTION FILTER: Blocking {signal_type} | Reason: {reason}"
                    )
                    return signals

            signal = self._create_entry_signal(df, signal_type)
            if signal:
                # Add regime info to signal for logging
                if self.current_regime:
                    signal['regime_strategy'] = self.current_regime.vwap_strategy.value
                    signal['regime_quality'] = self.current_regime.trade_quality_score

                # Mark market-open trade if in window
                if self._is_market_open_window(now) and self.market_open_bias is not None:
                    signal['market_open_trade'] = True
                    signal['prev_day_vwap'] = self.previous_day_vwap
                    self.market_open_trade_taken = True
                    self.logger.info(
                        f"🌅 MARKET-OPEN TRADE: {signal_type} based on prev day VWAP bias ({self.market_open_bias})"
                    )

                signals.append(signal)

        return signals

    def _analyze_market_regime(self):
        """
        Perform market regime analysis (pre-market checklist).

        This should run once at market open and cache the result.
        Mental model:
          - Weekly sets the battlefield
          - Daily sets the rules
          - VWAP executes the trade
        """
        if self.regime_analyzer is None:
            return

        try:
            self.logger.info("-" * 60)
            self.logger.info("Running Pre-Market Checklist...")
            self.logger.info("-" * 60)

            self.current_regime = self.regime_analyzer.analyze(NIFTY_50_TOKEN)
            self._regime_analyzed = True

            # Log summary
            if self.current_regime.should_trade:
                self.logger.info(
                    f"REGIME DECISION: TRADE ALLOWED | "
                    f"Strategy: {self.current_regime.vwap_strategy.value} | "
                    f"Quality: {self.current_regime.trade_quality_score}/100"
                )
            else:
                self.logger.warning(
                    f"REGIME DECISION: NO TRADE TODAY | "
                    f"Reason: {self.current_regime.skip_reason}"
                )

        except Exception as e:
            self.logger.error(f"Market regime analysis failed: {str(e)}")
            # On failure, allow trading with caution
            self._regime_analyzed = True
            self.current_regime = None

    def _can_enter_new_trade(self, now):
        """Check if we can enter a new trade."""
        # Max trades check
        if self.trade_count >= NIFTY_MAX_TRADES_PER_DAY:
            self.logger.debug("Max trades reached")
            return False

        # No new entries after cutoff time
        cutoff = now.replace(hour=LAST_ENTRY_HOUR, minute=LAST_ENTRY_MINUTE, second=0)
        if now >= cutoff:
            self.logger.debug("Past entry cutoff time")
            return False

        # Already have a position
        if len(self.active_positions) > 0:
            return False

        # ============================================
        # COOLDOWN CHECK: Wait after a loss
        # ============================================
        if self.cooldown_until is not None:
            if now < self.cooldown_until:
                remaining = (self.cooldown_until - now).total_seconds() / 60
                # Log only periodically (every 5 minutes)
                if not hasattr(self, '_last_cooldown_log') or \
                   (now - self._last_cooldown_log).total_seconds() > 300:
                    self.logger.warning(
                        f"⏳ COOLDOWN ACTIVE: {remaining:.0f} minutes remaining | "
                        f"Last loss at {self.last_loss_time.strftime('%H:%M')} | "
                        f"Resume at {self.cooldown_until.strftime('%H:%M')}"
                    )
                    self._last_cooldown_log = now
                return False
            else:
                # Cooldown ended
                self.logger.info(
                    f"✓ COOLDOWN ENDED: Ready to trade again | "
                    f"Cooldown was {LOSS_COOLDOWN_MINUTES} minutes after loss"
                )
                self.cooldown_until = None

        return True

    def _create_entry_signal(self, df, signal_type):
        """Create entry signal with position sizing."""
        current_price = df['close'].iloc[-1]
        atm_strike = get_atm_strike(current_price)
        option_type = "CE" if signal_type == "BUY_CE" else "PE"
        symbol = self.get_option_symbol(atm_strike, option_type)

        # Get option premium with validation
        premium = self.get_option_premium(symbol)
        if premium is None:
            self.logger.error(f"Could not get premium for {symbol}")
            return None

        # CRITICAL: Re-fetch to confirm (prevent stale data)
        time.sleep(0.5)  # Small delay to ensure fresh data
        premium_confirm = self.get_option_premium(symbol)
        if premium_confirm and abs(premium_confirm - premium) / premium > 0.02:  # 2% difference
            self.logger.warning(
                f"{symbol}: Premium changed {premium:.2f} → {premium_confirm:.2f} "
                f"({((premium_confirm-premium)/premium*100):.1f}%) during signal generation"
            )
            premium = premium_confirm  # Use latest

        # Calculate lots based on capital (with premium validation)
        lots = self.calculate_lots(premium)
        if lots is None:
            self.logger.error(f"Position sizing rejected for {symbol} (premium: ₹{premium:.2f})")
            return None

        quantity = lots * NIFTY_LOT_SIZE

        # Calculate initial stop loss - ALWAYS based on ENTRY PRICE, not candle low
        # This prevents the 20%+ SL distance bug
        entry_candle_low = premium  # Default to premium if candle data unavailable

        # Calculate SL as percentage of entry price
        initial_sl = premium * (1 - INITIAL_SL_PERCENT / 100)
        max_allowed_sl = premium * (1 - MAX_SL_PERCENT_FROM_ENTRY / 100)

        if CANDLE_LOW_SL_ENABLED:
            # Fetch entry candle to get the low (for reference/trailing, not initial SL)
            entry_candles = self.get_option_candles(symbol, n_candles=2, interval=SL_CANDLE_INTERVAL)
            if entry_candles and len(entry_candles) >= 1:
                entry_candle_low = entry_candles[-1].get('low', premium)
                # Calculate what candle-low SL would be
                candle_based_sl = entry_candle_low * (1 - SL_BUFFER_PERCENT / 100)

                # CAP the SL: Use candle-low only if it's tighter than max allowed
                if candle_based_sl >= max_allowed_sl:
                    initial_sl = candle_based_sl
                    self.logger.info(
                        f"{symbol}: Using candle-low based SL | "
                        f"Candle Low: ₹{entry_candle_low:.2f} | SL: ₹{initial_sl:.2f} "
                        f"({((premium - initial_sl) / premium * 100):.1f}% from entry)"
                    )
                else:
                    # Candle low too far, use entry-price based SL
                    initial_sl = max_allowed_sl
                    self.logger.warning(
                        f"{symbol}: Candle-low SL too wide (₹{candle_based_sl:.2f} = "
                        f"{((premium - candle_based_sl) / premium * 100):.1f}% loss) | "
                        f"Using capped SL: ₹{initial_sl:.2f} ({MAX_SL_PERCENT_FROM_ENTRY}% from entry)"
                    )
        else:
            self.logger.info(
                f"{symbol}: Using entry-price based SL: ₹{initial_sl:.2f} ({INITIAL_SL_PERCENT}% from entry)"
            )

        # Calculate investment
        investment = premium * quantity

        log_signal(
            self.name,
            signal_type,
            symbol,
            spot=current_price,
            strike=atm_strike,
            premium=premium,
            lots=lots,
            investment=investment
        )

        self.logger.info(
            f"Entry Signal: {signal_type} | {symbol} | "
            f"Premium: Rs. {premium} | Lots: {lots} | "
            f"Investment: Rs. {investment:,.0f} | SL: Rs. {initial_sl:.2f}"
        )

        # Get entry ADX for trend-aware trailing
        entry_adx = df['adx'].iloc[-1] if 'adx' in df.columns else 25

        return {
            'source': self.name,
            'action': TRANSACTION_BUY,
            'symbol': symbol,
            'exchange': EXCHANGE_NFO,
            'quantity': quantity,
            'order_type': ORDER_TYPE_MARKET,
            'product': PRODUCT_MIS,
            'reason': f"{signal_type} - VWAP+ST+ADX confluence",
            'entry_price': premium,
            'entry_spot': current_price,
            'entry_candle_low': entry_candle_low,
            'initial_sl': initial_sl,
            'entry_adx': entry_adx
        }

    def _check_exits(self, df=None):
        """
        Check exit conditions for active positions.

        Args:
            df: NIFTY spot dataframe (optional). If None, only basic LTP/emergency
                exits are checked. This allows exit monitoring even when spot
                data fetch fails.

        Hidden Stop Loss Logic (Anti Stop-Hunting):
        - If HIDDEN_SL_ENABLED: Only exit when CANDLE CLOSES below SL (not on wick touch)
        - Emergency SL: If LTP drops EMERGENCY_SL_PERCENT (25%), exit immediately
        - Technical SL: Uses option candle structure instead of fixed percentage
        """
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            # Get current premium (LTP)
            current_premium = self.get_option_premium(symbol)
            if current_premium is None:
                continue

            entry_premium = position['entry_premium']
            initial_sl = position['initial_sl']
            current_sl = position['current_sl']
            is_call = symbol.endswith("CE")
            option_type = 'CE' if is_call else 'PE'

            # Update max premium seen (for trailing)
            if symbol not in self.max_premium_seen:
                self.max_premium_seen[symbol] = entry_premium
            self.max_premium_seen[symbol] = max(self.max_premium_seen[symbol], current_premium)
            max_premium = self.max_premium_seen[symbol]

            # Track last LTP for price movement logging
            last_ltp = position.get('last_ltp', entry_premium)
            last_ltp_time = position.get('last_ltp_time')
            now = datetime.datetime.now()
            position['last_ltp'] = current_premium
            position['last_ltp_time'] = now

            # Calculate profit/loss percentage
            profit_pct = ((current_premium - entry_premium) / entry_premium) * 100
            loss_pct = -profit_pct if profit_pct < 0 else 0

            # Determine exit reason
            exit_reason = None
            new_sl = current_sl

            # ============================================
            # PROFIT TARGET EXIT (Return Normalization)
            # ============================================
            # Exit at profit target to prevent chasing outlier returns
            # A 50% profit is excellent; don't wait for 100%+ which is rare
            if PROFIT_TARGET_ENABLED and profit_pct >= PROFIT_TARGET_PERCENT:
                exit_reason = f"🎯 PROFIT TARGET HIT: +{profit_pct:.1f}% >= {PROFIT_TARGET_PERCENT}% target"
                self.logger.info(
                    f"{symbol}: Profit target reached! "
                    f"Entry: ₹{entry_premium:.2f} → Current: ₹{current_premium:.2f} (+{profit_pct:.1f}%)"
                )

            # Fetch option candles once (used for hidden SL confirmation and trailing)
            option_candles = None
            candle_close = current_premium  # Default to LTP
            candle_high = current_premium
            candle_low = current_premium
            candle_time = None

            if HIDDEN_SL_ENABLED or TWO_CANDLE_EXIT_ENABLED or TRAIL_ON_NEW_HIGH_ONLY:
                option_candles = self.get_option_candles(symbol, n_candles=3, interval=SL_CANDLE_INTERVAL)
                if option_candles and len(option_candles) >= 1:
                    last_closed_candle = option_candles[-1]
                    candle_close = last_closed_candle.get('close', current_premium)
                    candle_high = last_closed_candle.get('high', current_premium)
                    candle_low = last_closed_candle.get('low', current_premium)
                    candle_time = last_closed_candle.get('date', None)

            # Check if this is a NEW candle (not already processed)
            last_processed_time = position.get('last_candle_time')
            is_new_candle = (candle_time is not None and candle_time != last_processed_time)

            # ============================================
            # TRAIL-ON-NEW-HIGH LOGIC
            # ============================================
            # Only trail when price makes a NEW HIGH, not on every uptick
            if TRAIL_ON_NEW_HIGH_ONLY and is_new_candle and option_candles:
                highest_high = position.get('highest_high', entry_premium)

                # Check if this candle made a new high
                if candle_high > highest_high:
                    # New high made! Update tracking and potentially trail SL
                    position['highest_high'] = candle_high

                    # Use the previous candle's low as the new trailing SL level
                    if len(option_candles) >= 2:
                        prev_candle = option_candles[-2]
                        prev_candle_low = prev_candle.get('low', candle_low)

                        # Apply buffer to previous candle low
                        new_trail_sl = prev_candle_low * (1 - SL_BUFFER_PERCENT / 100)

                        # Only move SL up, never down
                        if new_trail_sl > current_sl:
                            old_sl = current_sl
                            position['current_sl'] = new_trail_sl
                            position['highest_high_candle_low'] = prev_candle_low
                            current_sl = new_trail_sl  # Update local variable too

                            self.logger.info(
                                f"{symbol}: NEW HIGH ₹{candle_high:.2f} | "
                                f"Trailing SL: ₹{old_sl:.2f} → ₹{new_trail_sl:.2f} "
                                f"(prev candle low: ₹{prev_candle_low:.2f})"
                            )

            # Update last processed candle time
            if is_new_candle:
                position['last_candle_time'] = candle_time

            # ============================================
            # HIDDEN STOP LOSS WITH TWO-CANDLE CONFIRMATION
            # ============================================
            if HIDDEN_SL_ENABLED:
                # EMERGENCY SL: If LTP drops too much, exit immediately (no candle wait)
                # This protects against flash crashes and gap downs
                if loss_pct >= EMERGENCY_SL_PERCENT:
                    exit_reason = f"EMERGENCY SL hit (Loss: {loss_pct:.1f}% >= {EMERGENCY_SL_PERCENT}%)"
                    self.logger.warning(f"{symbol}: {exit_reason}")

                    # Enhanced logging for emergency SL diagnosis
                    expected_sl_price = entry_premium * (1 - EMERGENCY_SL_PERCENT / 100)
                    slippage_pct = loss_pct - EMERGENCY_SL_PERCENT
                    slippage_amount = entry_premium * slippage_pct / 100
                    price_change_since_last = ((current_premium - last_ltp) / last_ltp * 100) if last_ltp > 0 else 0
                    time_since_last_check = (now - last_ltp_time).total_seconds() if last_ltp_time else 0
                    entry_time = position.get('entry_time')
                    time_in_position = (now - entry_time).total_seconds() / 60 if entry_time else 0

                    self.logger.warning(
                        f"⚠️ EMERGENCY SL SLIPPAGE ANALYSIS | {symbol}:\n"
                        f"    Entry: ₹{entry_premium:.2f} | Current: ₹{current_premium:.2f}\n"
                        f"    Expected SL price (12%): ₹{expected_sl_price:.2f} | Actual exit: ₹{current_premium:.2f}\n"
                        f"    Slippage: {slippage_pct:.1f}% beyond {EMERGENCY_SL_PERCENT}% SL (₹{slippage_amount:.2f} extra loss)\n"
                        f"    Price change since last check: {price_change_since_last:.1f}% | Time: {time_since_last_check:.0f}s\n"
                        f"    Last LTP: ₹{last_ltp:.2f} | Time in position: {time_in_position:.1f} min"
                    )

                # HIDDEN SL: Check candle CLOSE, not LTP
                elif profit_pct < 0:  # Only check SL when in loss
                    if option_candles and len(option_candles) >= 2:
                        # Calculate technical SL if enabled
                        if HIDDEN_SL_METHOD == 'technical':
                            tech_sl, tech_sl_pct, sl_reason = calculate_entry_stop_loss(
                                entry_premium, option_candles, option_type
                            )
                            # Use the tighter of technical SL and initial SL
                            effective_sl = max(tech_sl, initial_sl)
                        else:
                            effective_sl = initial_sl

                        # Check if CANDLE CLOSED below SL (not just touched)
                        if candle_close <= effective_sl:
                            # ============================================
                            # TWO-CANDLE CONFIRMATION LOGIC
                            # ============================================
                            if TWO_CANDLE_EXIT_ENABLED and is_new_candle:
                                sl_warning_count = position.get('sl_warning_count', 0) + 1
                                position['sl_warning_count'] = sl_warning_count

                                if sl_warning_count >= 2:
                                    # Second consecutive candle closed below SL - EXIT
                                    exit_reason = (
                                        f"Hidden SL CONFIRMED (2 candles) - "
                                        f"(Close: ₹{candle_close:.2f} <= SL: ₹{effective_sl:.2f})"
                                    )
                                    self.logger.info(
                                        f"{symbol}: {exit_reason} | "
                                        f"2nd consecutive candle below SL - EXITING"
                                    )
                                else:
                                    # First candle closed below SL - WARNING, hold position
                                    # Track what old logic would have done for comparison
                                    old_logic_exit_price = current_premium
                                    old_logic_pnl = (old_logic_exit_price - entry_premium) * position['quantity']
                                    position['old_logic_would_exit_at'] = old_logic_exit_price
                                    position['old_logic_would_exit_pnl'] = old_logic_pnl

                                    self.logger.warning(
                                        f"{symbol}: SL WARNING (candle {sl_warning_count}/2) | "
                                        f"Close: ₹{candle_close:.2f} <= SL: ₹{effective_sl:.2f} | "
                                        f"Waiting for 2nd candle confirmation..."
                                    )
                                    self.logger.info(
                                        f"📊 COMPARISON: OLD LOGIC would EXIT now @ ₹{old_logic_exit_price:.2f} | "
                                        f"P&L: ₹{old_logic_pnl:,.0f} | NEW LOGIC: HOLDING..."
                                    )
                            elif not TWO_CANDLE_EXIT_ENABLED:
                                # Original single-candle exit
                                exit_reason = (
                                    f"Hidden SL triggered - Candle CLOSED below SL "
                                    f"(Close: ₹{candle_close:.2f} <= SL: ₹{effective_sl:.2f})"
                                )
                                self.logger.info(
                                    f"{symbol}: {exit_reason} | "
                                    f"LTP was ₹{current_premium:.2f}, waited for candle close"
                                )
                        else:
                            # Candle closed ABOVE SL - reset warning count
                            if position.get('sl_warning_count', 0) > 0:
                                # We held through the first candle warning and price recovered!
                                # Log the FALSE SIGNAL AVOIDED with P&L comparison
                                old_exit_price = position.get('old_logic_would_exit_at', 0)
                                old_exit_pnl = position.get('old_logic_would_exit_pnl', 0)
                                current_pnl = (current_premium - entry_premium) * position['quantity']
                                pnl_saved = current_pnl - old_exit_pnl

                                self.logger.info(
                                    f"{symbol}: SL warning RESET | "
                                    f"Candle closed at ₹{candle_close:.2f} (above SL ₹{effective_sl:.2f})"
                                )
                                if old_exit_price > 0:
                                    self.logger.info(
                                        f"📊 FALSE SIGNAL AVOIDED! | "
                                        f"OLD LOGIC would have exited @ ₹{old_exit_price:.2f} (P&L: ₹{old_exit_pnl:,.0f}) | "
                                        f"CURRENT: ₹{current_premium:.2f} (P&L: ₹{current_pnl:,.0f}) | "
                                        f"SAVED: ₹{pnl_saved:,.0f}"
                                    )
                                    # Clear the tracking once logged
                                    position.pop('old_logic_would_exit_at', None)
                                    position.pop('old_logic_would_exit_pnl', None)

                                position['sl_warning_count'] = 0

                            # Log that we're watching (helpful for debugging)
                            if current_premium <= effective_sl:
                                self.logger.debug(
                                    f"{symbol}: LTP ₹{current_premium:.2f} below SL ₹{effective_sl:.2f}, "
                                    f"but candle close ₹{candle_close:.2f} still above - HOLDING"
                                )
                    else:
                        # Fallback: If can't get candles, use traditional LTP check
                        if current_premium <= initial_sl:
                            exit_reason = f"Initial SL hit - fallback (Premium: {current_premium:.2f} <= SL: {initial_sl:.2f})"

            else:
                # Traditional SL check (LTP-based, no candle confirmation)
                if current_premium <= initial_sl:
                    exit_reason = f"Initial SL hit (Premium: {current_premium:.2f} <= SL: {initial_sl:.2f})"

            # Phase 2: Dynamic progressive trailing (when in profit)
            # Only run trailing logic if no exit triggered yet AND df is available
            # (df is needed for ADX/Supertrend checks)

            if exit_reason is None and df is not None and TRAILING_STOP_METHOD == 'dynamic':
                # ============================================
                # TREND-AWARE TRAILING STOP LOSS
                # ============================================
                # Adapts trailing behavior based on ADX (trend strength)
                # Strong trends: Let profits run with wider trailing
                # Weak trends: Lock profits quickly with tight trailing

                # Get current ADX from the dataframe
                current_adx = df['adx'].iloc[-1] if 'adx' in df.columns else 25

                # Use entry ADX if available - prevents switching to tight trailing
                # when we entered during a strong trend but ADX temporarily dips
                entry_adx = position.get('entry_adx', current_adx)
                effective_adx = max(entry_adx, current_adx)  # Use higher of entry or current

                # Determine trailing parameters based on trend strength
                if TREND_AWARE_TRAILING_ENABLED and effective_adx >= STRONG_TREND_ADX:
                    # STRONG TREND: Wide trailing to let profits run
                    breakeven_trigger = STRONG_TREND_BREAKEVEN_PERCENT
                    trail_frequency = STRONG_TREND_TRAIL_FREQUENCY
                    trail_increment = STRONG_TREND_TRAIL_INCREMENT
                    max_giveback = STRONG_TREND_MAX_GIVEBACK
                    trend_mode = "STRONG"
                    check_st_flip = STRONG_TREND_EXIT_ON_ST_FLIP
                elif TREND_AWARE_TRAILING_ENABLED and effective_adx <= WEAK_TREND_ADX:
                    # WEAK/RANGING: Tight trailing to lock profits
                    breakeven_trigger = WEAK_TREND_BREAKEVEN_PERCENT
                    trail_frequency = WEAK_TREND_TRAIL_FREQUENCY
                    trail_increment = WEAK_TREND_TRAIL_INCREMENT
                    max_giveback = WEAK_TREND_MAX_GIVEBACK
                    trend_mode = "WEAK"
                    check_st_flip = False
                else:
                    # MODERATE or trend-aware disabled: Use legacy parameters
                    breakeven_trigger = BREAKEVEN_TRIGGER_PERCENT
                    trail_frequency = TRAIL_FREQUENCY
                    trail_increment = TRAIL_INCREMENT
                    max_giveback = MAX_PROFIT_GIVEBACK
                    trend_mode = "MODERATE"
                    check_st_flip = False

                # Check if we've hit the breakeven trigger
                if profit_pct >= breakeven_trigger:
                    # Progressive trailing: Lock profits incrementally
                    # Calculate how many trail steps we should have taken
                    trail_steps = int((profit_pct - breakeven_trigger) / trail_frequency)

                    # Calculate target SL based on trail steps
                    locked_profit_pct = breakeven_trigger + (trail_steps * trail_increment)
                    target_sl = entry_premium * (1 + locked_profit_pct / 100)

                    # Move SL up progressively
                    if target_sl > current_sl:
                        old_sl = current_sl
                        new_sl = target_sl
                        position['current_sl'] = new_sl

                        locked_profit = ((new_sl - entry_premium) / entry_premium) * 100
                        self.logger.info(
                            f"{symbol}: Trailing SL from ₹{old_sl:.2f} → ₹{new_sl:.2f} "
                            f"(Locked {locked_profit:.1f}% profit, Current: {profit_pct:.1f}%) "
                            f"[{trend_mode} trend, EntryADX={entry_adx:.1f}, CurrentADX={current_adx:.1f}]"
                        )

                    # Max profit protection (dynamic based on trend)
                    max_profit_amount = max_premium - entry_premium
                    max_giveback_amount = max_profit_amount * (max_giveback / 100)
                    protection_sl = max_premium - max_giveback_amount

                    if protection_sl > new_sl:
                        old_sl = new_sl
                        new_sl = protection_sl
                        position['current_sl'] = new_sl
                        self.logger.info(
                            f"{symbol}: Max profit protection SL = ₹{new_sl:.2f} "
                            f"(Max seen: ₹{max_premium:.2f}, protecting {100-max_giveback}% of gains) "
                            f"[{trend_mode} trend, EntryADX={entry_adx:.1f}]"
                        )

                    # In strong trends, also check for Supertrend flip as exit signal
                    if check_st_flip:
                        if is_call and is_supertrend_bearish(df):
                            exit_reason = f"Supertrend flipped bearish in strong trend (ADX={current_adx:.1f})"
                        elif not is_call and is_supertrend_bullish(df):
                            exit_reason = f"Supertrend flipped bullish in strong trend (ADX={current_adx:.1f})"

            elif exit_reason is None and df is not None and TRAILING_STOP_METHOD == 'supertrend':
                # Legacy: Exit on Supertrend flip (requires df for Supertrend check)
                if profit_pct >= BREAKEVEN_TRIGGER_PERCENT:
                    if current_sl < entry_premium:
                        new_sl = entry_premium
                        position['current_sl'] = new_sl
                        self.logger.info(f"{symbol}: Moving SL to breakeven at ₹{new_sl:.2f}")

                    if is_call and is_supertrend_bearish(df):
                        exit_reason = "Supertrend flipped bearish"
                    elif not is_call and is_supertrend_bullish(df):
                        exit_reason = "Supertrend flipped bullish"

            elif exit_reason is None and df is not None and TRAILING_STOP_METHOD == 'percent':
                # Legacy: Trail at 50% of max profit
                if profit_pct >= BREAKEVEN_TRIGGER_PERCENT:
                    if current_sl < entry_premium:
                        new_sl = entry_premium
                        position['current_sl'] = new_sl
                        self.logger.info(f"{symbol}: Moving SL to breakeven at ₹{new_sl:.2f}")

                    trail_sl = entry_premium + (max_premium - entry_premium) * (TRAIL_PERCENT / 100)
                    if trail_sl > new_sl:
                        new_sl = trail_sl
                        position['current_sl'] = new_sl
                        self.logger.debug(f"{symbol}: Trailing SL to ₹{new_sl:.2f}")

                    if current_premium <= new_sl:
                        exit_reason = f"Trailing SL hit (Premium: {current_premium:.2f} <= SL: {new_sl:.2f})"

            # Check current SL (trailing SL)
            # Apply candle close confirmation if HIDDEN_SL_ENABLED
            if exit_reason is None and current_premium <= current_sl:
                if HIDDEN_SL_ENABLED and option_candles:
                    # Use candle close for trailing SL too
                    if candle_close <= current_sl:
                        # Apply two-candle confirmation for trailing SL too
                        if TWO_CANDLE_EXIT_ENABLED and is_new_candle:
                            sl_warning_count = position.get('sl_warning_count', 0) + 1
                            position['sl_warning_count'] = sl_warning_count

                            if sl_warning_count >= 2:
                                exit_reason = f"Trailing SL CONFIRMED (2 candles) - (Close: {candle_close:.2f} <= SL: {current_sl:.2f})"
                            else:
                                # Track what old logic would have done for comparison
                                old_logic_exit_price = current_premium
                                old_logic_pnl = (old_logic_exit_price - entry_premium) * position['quantity']
                                position['old_logic_would_exit_at'] = old_logic_exit_price
                                position['old_logic_would_exit_pnl'] = old_logic_pnl

                                self.logger.warning(
                                    f"{symbol}: Trailing SL WARNING ({sl_warning_count}/2) | "
                                    f"Close: ₹{candle_close:.2f} <= SL: ₹{current_sl:.2f} | "
                                    f"Waiting for 2nd candle..."
                                )
                                self.logger.info(
                                    f"📊 COMPARISON: OLD LOGIC would EXIT now @ ₹{old_logic_exit_price:.2f} | "
                                    f"P&L: ₹{old_logic_pnl:,.0f} | NEW LOGIC: HOLDING..."
                                )
                        elif not TWO_CANDLE_EXIT_ENABLED:
                            exit_reason = f"Trailing SL hit - Candle CLOSED (Close: {candle_close:.2f} <= SL: {current_sl:.2f})"
                    else:
                        # Candle closed above SL - reset warning count
                        if position.get('sl_warning_count', 0) > 0 and is_new_candle:
                            # We held through the first candle warning and price recovered!
                            old_exit_price = position.get('old_logic_would_exit_at', 0)
                            old_exit_pnl = position.get('old_logic_would_exit_pnl', 0)
                            current_pnl = (current_premium - entry_premium) * position['quantity']
                            pnl_saved = current_pnl - old_exit_pnl

                            self.logger.info(
                                f"{symbol}: Trailing SL warning RESET | "
                                f"Candle closed at ₹{candle_close:.2f} (above SL ₹{current_sl:.2f})"
                            )
                            if old_exit_price > 0:
                                self.logger.info(
                                    f"📊 FALSE SIGNAL AVOIDED! | "
                                    f"OLD LOGIC would have exited @ ₹{old_exit_price:.2f} (P&L: ₹{old_exit_pnl:,.0f}) | "
                                    f"CURRENT: ₹{current_premium:.2f} (P&L: ₹{current_pnl:,.0f}) | "
                                    f"SAVED: ₹{pnl_saved:,.0f}"
                                )
                                # Clear the tracking once logged
                                position.pop('old_logic_would_exit_at', None)
                                position.pop('old_logic_would_exit_pnl', None)

                            position['sl_warning_count'] = 0
                else:
                    exit_reason = f"Stop loss hit (Premium: {current_premium:.2f} <= SL: {current_sl:.2f})"

            # Generate exit signal if needed
            if exit_reason:
                pnl = (current_premium - entry_premium) * position['quantity']
                self.logger.info(
                    f"EXIT: {symbol} | Reason: {exit_reason} | "
                    f"Entry: {entry_premium:.2f} | Exit: {current_premium:.2f} | "
                    f"P&L: Rs. {pnl:,.2f}"
                )

                exit_signals.append({
                    'source': self.name,
                    'action': TRANSACTION_SELL,
                    'symbol': symbol,
                    'exchange': EXCHANGE_NFO,
                    'quantity': position['quantity'],
                    'order_type': ORDER_TYPE_MARKET,
                    'product': PRODUCT_MIS,
                    'reason': exit_reason
                })

        return exit_signals

    def _force_exit_all(self, reason):
        """Force exit all positions."""
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            self.logger.info(f"Force exit: {symbol} | Reason: {reason}")

            exit_signals.append({
                'source': self.name,
                'action': TRANSACTION_SELL,
                'symbol': symbol,
                'exchange': EXCHANGE_NFO,
                'quantity': position['quantity'],
                'order_type': ORDER_TYPE_MARKET,
                'product': PRODUCT_MIS,
                'reason': reason
            })

        return exit_signals

    def on_order_complete(self, order_id, symbol, action, quantity, price, **kwargs):
        """Callback when order is completed."""
        if action == TRANSACTION_BUY:
            entry_spot = kwargs.get('entry_spot', 0)
            initial_sl = kwargs.get('initial_sl', price * 0.8)
            entry_reason = kwargs.get('reason', 'Manual entry')
            entry_adx = kwargs.get('entry_adx', 25)  # Default to moderate ADX
            entry_candle_low = kwargs.get('entry_candle_low', price)  # Candle low at entry

            self.trade_count += 1
            self.active_positions[symbol] = {
                'order_id': order_id,
                'entry_premium': price,
                'entry_spot': entry_spot,
                'initial_sl': initial_sl,
                'current_sl': initial_sl,
                'quantity': quantity,
                'entry_time': datetime.datetime.now(),
                'entry_reason': entry_reason,
                'entry_adx': entry_adx,  # Store entry ADX for trend-aware trailing
                # New fields for two-candle confirmation and trail-on-new-high
                'sl_warning_count': 0,  # Consecutive candles closed below SL
                'highest_high': price,  # Highest premium seen (for trail-on-new-high)
                'highest_high_candle_low': entry_candle_low,  # Candle low when highest high was made
                'last_candle_time': None  # Track last processed candle to avoid double-counting
            }
            self.max_premium_seen[symbol] = price

            self.logger.info(
                f"Position opened: {symbol} @ Rs. {price} | "
                f"Qty: {quantity} | SL: Rs. {initial_sl:.2f} | "
                f"Trade #{self.trade_count}"
            )

            # Log to Excel journal
            direction = 'BUY_CE' if 'CE' in symbol else 'BUY_PE'
            self.journal.log_entry(
                bot_name=self.name,
                symbol=symbol,
                direction=direction,
                entry_price=price,
                quantity=quantity,
                entry_reason=entry_reason,
                stop_loss=initial_sl,
                spot_price=entry_spot
            )

        elif action == TRANSACTION_SELL:
            if symbol in self.active_positions:
                entry = self.active_positions[symbol]['entry_premium']
                pnl = (price - entry) * quantity
                exit_reason = kwargs.get('reason', 'Manual exit')

                # Update daily P&L
                self.daily_pnl += pnl

                # Track consecutive losses and activate cooldown
                if pnl < 0:
                    self.consecutive_losses += 1
                    # Activate cooldown after any loss
                    self.last_loss_time = datetime.datetime.now()
                    self.cooldown_until = self.last_loss_time + datetime.timedelta(minutes=LOSS_COOLDOWN_MINUTES)
                    self.logger.warning(
                        f"🛑 LOSS RECORDED: ₹{pnl:,.0f} | "
                        f"Activating {LOSS_COOLDOWN_MINUTES}-minute cooldown until {self.cooldown_until.strftime('%H:%M')}"
                    )

                    # Re-assess directional bias after loss
                    if REASSESS_BIAS_AFTER_LOSS and self.regime_analyzer and MARKET_REGIME_ENABLED:
                        self.logger.info("📊 Re-assessing market bias after loss...")
                        self._regime_analyzed = False  # Force re-analysis on next scan
                else:
                    self.consecutive_losses = 0
                    # Clear cooldown on a winning trade
                    if self.cooldown_until is not None:
                        self.logger.info("✓ Winning trade - cooldown cleared")
                        self.cooldown_until = None

                self.logger.info(
                    f"Position closed: {symbol} | "
                    f"Entry: {entry:.2f} | Exit: {price:.2f} | "
                    f"P&L: Rs. {pnl:,.2f} | Daily P&L: Rs. {self.daily_pnl:,.2f}"
                )

                # Log to Excel journal
                self.journal.log_exit(
                    symbol=symbol,
                    exit_price=price,
                    exit_reason=exit_reason,
                    pnl=pnl
                )

                del self.active_positions[symbol]
                if symbol in self.max_premium_seen:
                    del self.max_premium_seen[symbol]

    def _is_trading_time(self, now):
        """Check if within trading hours (accounts for gap delays and market-open trading)."""
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
        market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
        trading_start = now.replace(hour=TRADING_START_HOUR, minute=TRADING_START_MINUTE, second=0)

        # Check if we're in the market-open window (9:15-9:30) with valid bias
        if self._is_market_open_window(now):
            # Allow trading if we have a decisive market-open bias
            if self.market_open_bias is not None and not self.market_open_trade_taken:
                return True

        # Check if gap delay is active
        if self.trading_delay_until is not None:
            # Gap detected, use delayed start time
            if now < self.trading_delay_until:
                # Still in delay period
                return False
            else:
                # Delay period over, trade normally
                return now <= market_close
        else:
            # No gap delay, use normal trading hours
            return trading_start <= now <= market_close

    def _is_market_open_window(self, now):
        """Check if we're in the market-open trading window (9:15-9:30)."""
        if not MARKET_OPEN_TRADING_ENABLED:
            return False

        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
        market_open_window_end = now.replace(
            hour=MARKET_OPEN_HOUR,
            minute=MARKET_OPEN_WINDOW_END_MINUTE,
            second=0
        )

        return market_open <= now < market_open_window_end

    def _is_force_exit_time(self, now):
        """Check if it's time to force exit all positions."""
        force_exit = now.replace(hour=FORCE_EXIT_HOUR, minute=FORCE_EXIT_MINUTE, second=0)
        return now >= force_exit

    def _is_expiry_day(self):
        """
        Check if today is the expiry day for the instrument being traded.

        On expiry day, option buying is extremely risky due to rapid theta decay.
        Options can lose 80-90% of value in minutes as time premium evaporates.

        NIFTY weekly options expire on Thursday (weekday = 3).

        Returns:
            bool: True if today is expiry day
        """
        if not hasattr(self, '_expiry_day_checked') or not self._expiry_day_checked:
            expiry_date = self.get_weekly_expiry()
            if expiry_date:
                today = datetime.date.today()
                # Check if the nearest expiry matches today
                if expiry_date == today:
                    # Validate: NIFTY weekly expiry is on Thursday (weekday = 3)
                    # If today is not Thursday, this is likely stale data in instruments
                    if today.weekday() == 3:  # Thursday
                        self._is_expiry = True
                        self.logger.warning(
                            f"⚠️ TODAY IS EXPIRY DAY ({expiry_date.strftime('%Y-%m-%d')}) - "
                            f"Option buying is HIGH RISK due to rapid theta decay!"
                        )
                    else:
                        # Today is not Thursday but instruments show today's expiry
                        # This is likely stale data, not actual expiry day
                        self._is_expiry = False
                        self.logger.debug(
                            f"Found instruments with today's expiry ({today.strftime('%Y-%m-%d')}) but today is "
                            f"{today.strftime('%A')}, not Thursday. Treating as non-expiry day."
                        )
                else:
                    self._is_expiry = False
                self._expiry_day_checked = True
            else:
                self._is_expiry = False
                self._expiry_day_checked = True
        return getattr(self, '_is_expiry', False)

    def _is_past_expiry_cutoff(self, now):
        """Check if past the cutoff time for expiry day trading."""
        if EXPIRY_DAY_CUTOFF_TIME:
            try:
                cutoff_hour, cutoff_minute = map(int, EXPIRY_DAY_CUTOFF_TIME.split(':'))
                cutoff_time = now.replace(hour=cutoff_hour, minute=cutoff_minute, second=0)
                return now >= cutoff_time
            except:
                return False
        return False

    def get_status(self):
        """Get current bot status."""
        status = {
            'name': self.name,
            'trade_count': self.trade_count,
            'max_trades': NIFTY_MAX_TRADES_PER_DAY,
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len(self.active_positions),
            'positions': list(self.active_positions.keys())
        }

        # Add market regime info if available
        if MARKET_REGIME_ENABLED and self.current_regime:
            status['regime'] = {
                'weekly_trend': self.current_regime.weekly_trend.value,
                'daily_pattern': self.current_regime.daily_pattern.value,
                'vwap_strategy': self.current_regime.vwap_strategy.value,
                'quality_score': self.current_regime.trade_quality_score,
                'should_trade': self.current_regime.should_trade,
                'is_event_day': self.current_regime.is_event_day
            }
            if not self.current_regime.should_trade:
                status['regime']['skip_reason'] = self.current_regime.skip_reason

        return status
