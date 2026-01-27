"""
BACKTESTING ENGINE
Professional-grade backtesting framework for options trading strategies

Features:
- Historical data from Kite
- Realistic slippage and commissions
- Position sizing based on risk
- Performance metrics (Sharpe, drawdown, expectancy)
- Trade-by-trade logging
- Equity curve generation
"""

import datetime
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import (
    NIFTY_50_TOKEN, BANKNIFTY_TOKEN,
    NIFTY_LOT_SIZE, BANKNIFTY_LOT_SIZE,
    ADX_ENTRY_THRESHOLD
)
from common.indicators import (
    compute_vwap, atr, adx, supertrend,
    is_supertrend_bullish, is_supertrend_bearish,
    get_atm_strike
)
from common.logger import setup_logger
from common.technical_sl import calculate_entry_stop_loss
from executor.trade_executor import KiteExecutor


class BacktestConfig:
    """Backtesting configuration - mirrors prop firm risk management."""

    def __init__(self, strategy_config=None):
        # Import here to avoid circular dependency
        from backtest.strategy_config import StrategyConfig

        # Use provided strategy config or create default
        if strategy_config is None:
            strategy_config = StrategyConfig()

        self.strategy = strategy_config

        # Capital management
        self.initial_capital = strategy_config.initial_capital
        self.max_risk_per_trade = strategy_config.max_risk_per_trade
        self.max_daily_loss = strategy_config.max_daily_loss
        self.max_capital_deployed = strategy_config.max_capital_deployed

        # Position management
        self.max_positions = strategy_config.max_positions
        self.stop_loss_percent = strategy_config.stop_loss_percent
        self.target_percent = strategy_config.target_percent
        self.trailing_stop_activation = strategy_config.trailing_stop_activation
        self.trailing_stop_distance = strategy_config.trailing_stop_distance

        # Execution assumptions
        self.slippage_percent = strategy_config.slippage_percent
        self.commission_per_trade = strategy_config.commission_per_trade

        # Backtest parameters
        self.start_date = datetime.datetime.now() - datetime.timedelta(days=90)  # 3 months
        self.end_date = datetime.datetime.now()


class Trade:
    """Represents a single trade."""

    def __init__(self, entry_time, symbol, direction, entry_price, quantity, stop_loss, target, entry_spot=None):
        self.entry_time = entry_time
        self.symbol = symbol
        self.direction = direction  # 'BUY_CE' or 'BUY_PE'
        self.entry_price = entry_price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.target = target
        self.entry_spot = entry_spot  # Track original spot price for delta calculations

        # Tracking
        self.max_price_seen = entry_price
        self.trailing_stop = None
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = 0
        self.pnl_percent = 0

        # Costs
        self.entry_cost = entry_price * quantity
        self.commission = 0

    def update_trailing_stop(self, current_price, config: BacktestConfig):
        """Update trailing stop if price moves favorably."""
        if current_price > self.max_price_seen:
            self.max_price_seen = current_price

            # Activate trailing stop if profit threshold reached
            profit_pct = (current_price - self.entry_price) / self.entry_price
            if profit_pct >= config.trailing_stop_activation:
                self.trailing_stop = self.max_price_seen * (1 - config.trailing_stop_distance)

    def check_exit(self, current_price, current_time):
        """Check if trade should be exited."""
        # Stop loss hit
        if current_price <= self.stop_loss:
            self.exit_time = current_time
            self.exit_price = self.stop_loss
            self.exit_reason = 'STOP_LOSS'
            return True

        # Trailing stop hit
        if self.trailing_stop and current_price <= self.trailing_stop:
            self.exit_time = current_time
            self.exit_price = self.trailing_stop
            self.exit_reason = 'TRAILING_STOP'
            return True

        # Target hit
        if current_price >= self.target:
            self.exit_time = current_time
            self.exit_price = self.target
            self.exit_reason = 'TARGET'
            return True

        return False

    def close(self, exit_price, exit_time, reason, config: BacktestConfig):
        """Close the trade."""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason

        # Apply slippage (worse fills on exits)
        slippage = exit_price * config.slippage_percent
        self.exit_price = exit_price - slippage

        # Calculate P&L
        self.pnl = (self.exit_price - self.entry_price) * self.quantity
        self.pnl -= (config.commission_per_trade * 2)  # Entry + Exit
        self.commission = config.commission_per_trade * 2

        self.pnl_percent = (self.exit_price - self.entry_price) / self.entry_price * 100


class BacktestEngine:
    """Main backtesting engine."""

    def __init__(self, bot_class, config: BacktestConfig = None):
        self.bot_class = bot_class
        self.config = config or BacktestConfig()
        self.executor = KiteExecutor()
        self.logger = setup_logger("BACKTEST")

        # State
        self.capital = self.config.initial_capital
        self.starting_capital = self.config.initial_capital
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve = []
        self.daily_pnl = {}

        # Instantiate bot
        self.bot = bot_class(self.executor)

        # Option data caching (avoid redundant API calls)
        self._option_data_cache = {}  # {symbol: DataFrame}
        self._instruments_cache = None
        self._current_expiry = None

    def connect(self):
        """Connect to Kite for historical data."""
        if not self.executor.connect():
            self.logger.error("Failed to connect to Kite")
            return False
        self.logger.info("Connected to Kite for historical data")
        return True

    def _load_nfo_instruments(self):
        """Load NFO instruments list (cached)."""
        if self._instruments_cache is not None:
            return self._instruments_cache

        try:
            from common.config import EXCHANGE_NFO
            self._instruments_cache = self.executor.get_instruments(EXCHANGE_NFO)
            self.logger.info(f"Loaded {len(self._instruments_cache)} NFO instruments")
            return self._instruments_cache
        except Exception as e:
            self.logger.error(f"Failed to load NFO instruments: {str(e)}")
            return None

    def _get_option_token(self, symbol):
        """
        Get instrument token for an option symbol.

        Returns:
            instrument_token or None if not found
        """
        instruments = self._load_nfo_instruments()
        if instruments is None:
            return None

        for inst in instruments:
            if inst['tradingsymbol'] == symbol:
                return inst['instrument_token']

        self.logger.warning(f"Symbol '{symbol}' not found in NFO instruments")
        return None

    def _get_weekly_expiry(self, reference_date):
        """
        Get the nearest weekly expiry date from actual Kite instruments.

        This method validates that expiry dates fall on the expected weekday
        (Tuesday for NIFTY weekly per NSE rules, or Monday for holiday adjustments).

        Args:
            reference_date: Date to find expiry for (datetime.date or datetime.datetime)

        Returns:
            datetime.date object for nearest expiry, or None if not found
        """
        instruments = self._load_nfo_instruments()
        if not instruments:
            self.logger.error("No instruments loaded, cannot determine expiry")
            return None

        # Convert to date if datetime
        if isinstance(reference_date, datetime.datetime):
            reference_date = reference_date.date()

        # Extract all unique expiry dates for NIFTY options >= reference date
        nifty_expiries = set()
        for inst in instruments:
            if inst['name'] == 'NIFTY' and inst['instrument_type'] in ['CE', 'PE']:
                expiry = inst.get('expiry')
                if expiry and expiry >= reference_date:
                    nifty_expiries.add(expiry)

        if not nifty_expiries:
            self.logger.error(f"No NIFTY expiries found >= {reference_date}")
            return None

        # NIFTY weekly expiry is on Tuesday (weekday = 1) per NSE rules
        # If holiday on Tuesday, expiry moves to Monday (weekday = 0)
        # Valid expiry days: Tuesday (1) or Monday (0, holiday adjustment)
        valid_expiry_days = {0, 1}  # Monday, Tuesday

        # Filter to only valid expiry days
        valid_expiries = [exp for exp in nifty_expiries if exp.weekday() in valid_expiry_days]

        if valid_expiries:
            nearest_expiry = min(valid_expiries)
            self.logger.debug(f"Using NIFTY expiry: {nearest_expiry} ({nearest_expiry.strftime('%A')}) for date {reference_date}")
            return nearest_expiry

        # No valid expiries found - fall back to calculating expected expiry
        self.logger.warning(
            f"No valid NIFTY expiry dates found (expected Tuesday/Monday). "
            f"Available expiries: {sorted(nifty_expiries)[:5]}. Calculating fallback."
        )

        # Calculate next Tuesday from reference date
        days_until_tuesday = (1 - reference_date.weekday()) % 7
        if days_until_tuesday == 0:
            days_until_tuesday = 7  # Use next week if reference is Tuesday
        expected_expiry = reference_date + datetime.timedelta(days=days_until_tuesday)

        self.logger.info(f"Using calculated NIFTY expiry: {expected_expiry} ({expected_expiry.strftime('%A')})")
        return expected_expiry

    def _get_option_symbol(self, strike, option_type, reference_date):
        """
        Get NIFTY option symbol by looking up from actual instruments.

        This handles both weekly and monthly expiries correctly by querying
        the actual tradingsymbol from the instruments list instead of
        constructing it.

        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'
            reference_date: Date to determine which expiry to use

        Returns:
            Option symbol string, or None if failed
        """
        # Check if expiry needs to be updated (daily or when crossing expiry)
        if isinstance(reference_date, datetime.datetime):
            reference_date = reference_date.date()

        # Get expiry for this reference date
        expiry_date = self._get_weekly_expiry(reference_date)
        if not expiry_date:
            self.logger.error("Could not determine expiry date")
            return None

        # Cache the expiry we're using
        if self._current_expiry != expiry_date:
            self._current_expiry = expiry_date
            self.logger.info(f"Trading expiry updated: {expiry_date.strftime('%Y-%m-%d')} ({expiry_date.strftime('%A')})")

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
                return inst['tradingsymbol']

        # Symbol not found - log warning but don't fail
        self.logger.warning(
            f"Could not find NIFTY option: expiry={expiry_date}, strike={strike}, type={option_type}"
        )
        return None

    def _fetch_option_historical_data(self, symbol, from_date, to_date):
        """
        Fetch real option historical data with VWAP.

        Args:
            symbol: Option trading symbol (e.g., NIFTY25D1626200CE)
            from_date: Start date/time
            to_date: End date/time

        Returns:
            DataFrame with option OHLCV and VWAP, or None if failed
        """
        # Check cache first (key by symbol + date range)
        cache_key = f"{symbol}_{from_date.strftime('%Y%m%d%H%M')}_{to_date.strftime('%Y%m%d%H%M')}"
        if cache_key in self._option_data_cache:
            self.logger.debug(f"Using cached data for {symbol}")
            return self._option_data_cache[cache_key]

        # Get token for this option
        token = self._get_option_token(symbol)
        if token is None:
            self.logger.debug(f"Could not find token for {symbol}")
            return None

        try:
            data = self.executor.get_historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="5minute"  # Match backtest interval
            )

            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df = compute_vwap(df)

                # Cache the data
                self._option_data_cache[cache_key] = df

                return df
            else:
                # No data available for this period (option might not have been trading yet)
                self.logger.debug(
                    f"{symbol}: No data for {from_date.date()} to {to_date.date()} "
                    f"(option may not have started trading yet)"
                )

        except Exception as e:
            # Silently skip if data not available - this is expected for new options
            error_msg = str(e).lower()
            if 'invalid from date' in error_msg or 'invalid date' in error_msg:
                self.logger.debug(
                    f"{symbol}: Data not available for {from_date.date()} "
                    f"(option may not have been listed yet)"
                )
            else:
                # Log other errors
                self.logger.error(f"Failed to fetch option data for {symbol}: {str(e)}")

        return None

    def calculate_position_size(self, premium: float) -> int:
        """
        Calculate position size based on risk management.

        Uses fixed fractional position sizing based on INITIAL capital:
        - Risk exactly config.max_risk_per_trade of STARTING capital (not growing capital)
        - Prevents exponential position size growth from compounding
        - Respects max capital deployed limit
        - Returns number of lots to trade
        """
        # Max risk amount (based on INITIAL capital to prevent exponential growth)
        max_risk_amount = self.starting_capital * self.config.max_risk_per_trade

        # Stop loss distance
        stop_loss_distance = premium * self.config.stop_loss_percent

        # Calculate quantity to risk exact amount
        quantity_for_risk = max_risk_amount / stop_loss_distance

        # Convert to lots
        lot_size = NIFTY_LOT_SIZE if 'NIFTY' in self.bot.name else BANKNIFTY_LOT_SIZE
        lots = int(quantity_for_risk / lot_size)

        # Ensure at least 1 lot
        lots = max(1, lots)

        # Check max capital deployed (use STARTING capital to prevent position size growth)
        position_value = premium * lots * lot_size
        deployed_capital = sum(t.entry_cost for t in self.open_trades)

        if deployed_capital + position_value > self.starting_capital * self.config.max_capital_deployed:
            # Reduce position size
            available = self.starting_capital * self.config.max_capital_deployed - deployed_capital
            lots = max(1, int(available / (premium * lot_size)))

        return lots * lot_size

    def run(self):
        """Run the backtest."""
        self.logger.info("=" * 80)
        self.logger.info("STARTING BACKTEST")
        self.logger.info("=" * 80)
        self.logger.info(f"Bot: {self.bot.name}")
        self.logger.info(f"Period: {self.config.start_date.date()} to {self.config.end_date.date()}")
        self.logger.info(f"Initial Capital: ₹{self.config.initial_capital:,.0f}")
        self.logger.info(f"Max Risk/Trade: {self.config.max_risk_per_trade*100:.1f}%")

        # Display SL method
        sl_method = self.config.strategy.stop_loss_method
        if sl_method == "technical":
            self.logger.info(f"Stop Loss: Technical (option candle structure, capped 10-20%)")
        else:
            self.logger.info(f"Stop Loss: Fixed {self.config.stop_loss_percent*100:.0f}%")

        self.logger.info("=" * 80)

        # Connect to Kite
        if not self.connect():
            return None

        # Fetch historical data
        self.logger.info("Fetching historical data...")
        spot_data = self._fetch_spot_data()

        if spot_data is None or len(spot_data) == 0:
            self.logger.error("Failed to fetch historical data")
            return None

        self.logger.info(f"Fetched {len(spot_data)} candles")

        # Run simulation
        self.logger.info("Running simulation...")
        self._simulate(spot_data)

        # Generate results
        results = self._calculate_metrics()

        return results

    def _fetch_spot_data(self):
        """Fetch spot data from Kite."""
        token = NIFTY_50_TOKEN if 'NIFTY' in self.bot.name else BANKNIFTY_TOKEN

        data = self.executor.get_historical_data(
            instrument_token=token,
            from_date=self.config.start_date,
            to_date=self.config.end_date,
            interval="5minute"
        )

        if not data:
            return None

        # Convert to DataFrame and add indicators
        df = pd.DataFrame(data)
        df = compute_vwap(df)
        df = atr(df)
        df = adx(df)
        df = supertrend(df)

        return df

    def _simulate(self, spot_data: pd.DataFrame):
        """Simulate trading on historical data."""
        self.logger.info("Starting simulation...")

        daily_loss_today = 0
        current_date = None

        for idx, row in spot_data.iterrows():
            current_time = row['date']
            current_price = row['close']

            # Reset daily loss tracking at start of new day
            if current_date != current_time.date():
                current_date = current_time.date()
                daily_loss_today = 0
                self.logger.debug(f"New trading day: {current_date}")

            # Update existing trades
            self._update_open_trades(row, current_time, current_price)

            # Check daily loss limit
            if daily_loss_today <= -self.config.max_daily_loss * self.starting_capital:
                self.logger.warning(f"Daily loss limit hit on {current_date}")
                continue

            # Check if we can enter new positions
            if len(self.open_trades) >= self.config.max_positions:
                continue

            # Check for entry signals from bot
            signal = self._check_bot_signal(spot_data.iloc[:idx+1], current_time)

            if signal:
                # Get option data and enter trade
                trade = self._enter_trade(signal, current_time, current_price)
                if trade:
                    self.open_trades.append(trade)
                    self.logger.info(
                        f"ENTRY: {trade.symbol} @ ₹{trade.entry_price:.2f} "
                        f"x {trade.quantity} | SL: ₹{trade.stop_loss:.2f} | "
                        f"Target: ₹{trade.target:.2f}"
                    )

            # Update equity curve
            open_pnl = sum((row['close'] - t.entry_price) * t.quantity for t in self.open_trades)
            current_equity = self.capital + open_pnl
            self.equity_curve.append(current_equity)

        # Close any remaining open trades at end
        self._close_all_trades(spot_data.iloc[-1], "END_OF_BACKTEST")

        self.logger.info(f"Simulation complete. Total trades: {len(self.closed_trades)}")

    def _update_open_trades(self, row, current_time, current_price):
        """Update all open trades and check for exits."""
        trades_to_close = []

        for trade in self.open_trades:
            # Simulate option premium movement (simplified: correlated to spot)
            # In reality, option prices depend on spot, IV, time decay, etc.
            # For now, we'll use a simple correlation factor
            option_price = self._estimate_option_price(trade, current_price, current_time)

            # Update trailing stop
            trade.update_trailing_stop(option_price, self.config)

            # Check exit conditions
            if trade.check_exit(option_price, current_time):
                trades_to_close.append(trade)

        # Close trades that hit exit conditions
        for trade in trades_to_close:
            self.open_trades.remove(trade)

            # Finalize the trade
            trade.close(trade.exit_price, trade.exit_time, trade.exit_reason, self.config)
            self.closed_trades.append(trade)

            # Update capital
            self.capital += trade.pnl

            self.logger.info(
                f"EXIT: {trade.symbol} @ ₹{trade.exit_price:.2f} | "
                f"Reason: {trade.exit_reason} | P&L: ₹{trade.pnl:,.0f} ({trade.pnl_percent:+.2f}%)"
            )

    def _estimate_option_price(self, trade: Trade, current_spot: float, current_time) -> float:
        """
        Estimate option price based on spot movement with realistic factors.

        Enhanced model includes:
        - Delta correlation (spot movement impact)
        - Theta decay (time value erosion)
        - IV fluctuations (volatility changes)
        - Random market noise

        This provides more realistic P&L distribution and prevents 100% win rate.
        """
        # Calculate time elapsed since entry (in hours)
        if hasattr(trade, 'entry_time') and trade.entry_time:
            # Handle both datetime and timestamp types
            entry_time = trade.entry_time
            if hasattr(entry_time, 'timestamp'):
                entry_time = entry_time
            if hasattr(current_time, 'timestamp'):
                time_diff = current_time - entry_time
            else:
                time_diff = datetime.timedelta(hours=1)
            time_elapsed_hours = time_diff.total_seconds() / 3600
        else:
            time_elapsed_hours = 1  # Default to 1 hour

        # 1. Delta component (spot movement impact)
        # Calculate spot movement from entry spot price
        if hasattr(trade, 'entry_spot') and trade.entry_spot:
            spot_move_percent = (current_spot - trade.entry_spot) / trade.entry_spot
        else:
            # Fallback: use premium as proxy (less accurate)
            spot_move_percent = (current_spot - trade.entry_price) / trade.entry_price

        # ATM delta starts at ~0.5, increases as option goes ITM
        base_delta = 0.50
        adjusted_delta = base_delta + (spot_move_percent * 0.2)  # Delta increases with favorable moves
        adjusted_delta = max(0.3, min(0.8, adjusted_delta))  # Cap between 0.3-0.8

        delta_impact = trade.entry_price * (1 + spot_move_percent * adjusted_delta)

        # 2. Theta decay (time value erosion)
        # Options lose ~1-3% per day of time value
        # Accelerates as we approach expiry (simplified linear decay)
        theta_decay_per_hour = 0.0015  # ~3.6% per day
        theta_impact = 1 - (theta_decay_per_hour * time_elapsed_hours)
        theta_impact = max(0.85, theta_impact)  # Don't decay more than 15% in a day

        # 3. IV fluctuations (volatility changes)
        # IV can increase (favorable) or decrease (unfavorable) by 10-30%
        # Use a simple random walk model with deterministic seed
        seed_value = int(time_elapsed_hours * 1000) + int(current_spot * 100) + int(trade.entry_price * 100)
        np.random.seed(seed_value)
        iv_change = np.random.normal(0, 0.10)  # Mean 0, std 10% IV change
        iv_impact = 1 + iv_change

        # 4. Market noise (bid-ask spread, liquidity, etc.)
        noise = np.random.normal(0, 0.02)  # ±2% random noise
        noise_impact = 1 + noise

        # Combine all factors
        estimated_price = delta_impact * theta_impact * iv_impact * noise_impact

        # Realistic floor: ATM options rarely go below 50 paise in a single day
        return max(0.50, estimated_price)

    def _check_bot_signal(self, df_slice: pd.DataFrame, current_time) -> Optional[str]:
        """
        Check if bot generates entry signal at current time using REAL option data.

        NEW ARCHITECTURE: Fetches actual option contracts with real volume for accurate VWAP.
        Entry strategy:
        - Premium > VWAP (REAL option VWAP from actual volume)
        - Supertrend bullish/bearish (on spot)
        - ADX > threshold (on spot)

        Returns: 'BUY_CE', 'BUY_PE', or None
        """
        # Skip if not enough data for indicators
        if len(df_slice) < 20:
            return None

        # Check if within trading hours (9:20 AM - 2:30 PM)
        if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 20):
            return None
        if current_time.hour > 14 or (current_time.hour == 14 and current_time.minute > 30):
            return None

        # Get current values from spot data
        current_adx = df_slice['ADX'].iloc[-1]
        current_price = df_slice['close'].iloc[-1]

        # Check indicators on spot (already imported at module level)
        st_bullish = is_supertrend_bullish(df_slice)
        st_bearish = is_supertrend_bearish(df_slice)
        atm_strike = get_atm_strike(current_price)

        # Check ADX threshold (strategy parameter)
        adx_threshold = self.config.strategy.adx_threshold

        if pd.isna(current_adx) or current_adx < adx_threshold:
            return None

        # NEW: Fetch REAL option data for ATM strike
        # Determine option type based on Supertrend
        if st_bullish:
            option_type = 'CE'
            signal_type = 'BUY_CE'
        elif st_bearish:
            option_type = 'PE'
            signal_type = 'BUY_PE'
        else:
            # No clear trend
            return None

        # Build option symbol for ATM strike
        option_symbol = self._get_option_symbol(atm_strike, option_type, current_time)
        if option_symbol is None:
            self.logger.debug(f"Could not build option symbol for ATM {atm_strike} {option_type}")
            return None

        # Fetch real option historical data
        # Get data from market open (or start of day) to current time for VWAP calculation
        market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        from_date = max(market_open, current_time - datetime.timedelta(hours=2))

        option_data = self._fetch_option_historical_data(option_symbol, from_date, current_time)

        if option_data is None or len(option_data) == 0:
            self.logger.debug(
                f"NO SIGNAL | Could not fetch option data for {option_symbol}"
            )
            return None

        # Get real option premium and VWAP
        real_premium = option_data['close'].iloc[-1]
        real_vwap = option_data['vwap'].iloc[-1]
        real_volume = option_data['volume'].iloc[-1]

        # Validate VWAP is not NaN (can happen with zero volume)
        if pd.isna(real_vwap) or real_vwap <= 0:
            self.logger.debug(
                f"NO SIGNAL | {option_symbol} has invalid VWAP (NaN or zero). Volume: {real_volume}"
            )
            return None

        # Check VWAP condition: Premium must be > VWAP (smart money accumulation)
        vwap_buffer = self.config.strategy.vwap_buffer_percent
        vwap_threshold = real_vwap * (1 + vwap_buffer)

        if real_premium <= vwap_threshold:
            # VWAP condition not met - no signal
            self.logger.debug(
                f"NO SIGNAL | {option_symbol} | Spot: {current_price:.2f} | ATM: {atm_strike} | "
                f"ADX: {current_adx:.1f} | ST: {'Bullish' if st_bullish else 'Bearish'} | "
                f"Premium: {real_premium:.2f} <= VWAP: {real_vwap:.2f} (+{vwap_buffer*100:.1f}% buffer) "
                f"(VWAP condition failed)"
            )
            return None

        # All conditions met - generate signal with REAL data
        vwap_diff_pct = ((real_premium - real_vwap) / real_vwap) * 100
        self.logger.info(
            f"✓ SIGNAL: {signal_type} | {option_symbol} | Spot: {current_price:.2f} | ATM: {atm_strike} | "
            f"ADX: {current_adx:.1f} | ST: {'Bullish' if st_bullish else 'Bearish'} | "
            f"Premium: {real_premium:.2f} > VWAP: {real_vwap:.2f} (+{vwap_diff_pct:.1f}%)"
        )

        return signal_type

    def _enter_trade(self, signal: str, entry_time, spot_price: float) -> Optional[Trade]:
        """Enter a new trade based on signal using REAL option premium."""
        try:
            # Get ATM strike
            atm_strike = get_atm_strike(
                spot_price,
                NIFTY_LOT_SIZE if 'NIFTY' in self.bot.name else BANKNIFTY_LOT_SIZE
            )

            # Determine option type
            option_type = "CE" if signal == "BUY_CE" else "PE"

            # Build option symbol using backtest's method (handles expiry correctly)
            symbol = self._get_option_symbol(atm_strike, option_type, entry_time)
            if symbol is None:
                self.logger.error(f"Could not build option symbol for ATM {atm_strike} {option_type}")
                return None

            # NEW: Fetch REAL option premium from historical data
            market_open = entry_time.replace(hour=9, minute=15, second=0, microsecond=0)
            from_date = max(market_open, entry_time - datetime.timedelta(hours=2))

            option_data = self._fetch_option_historical_data(symbol, from_date, entry_time)

            if option_data is None or len(option_data) == 0:
                self.logger.error(f"Could not fetch option data for {symbol} at {entry_time}")
                return None

            # Get REAL premium from option data
            premium = option_data['close'].iloc[-1]

            if pd.isna(premium) or premium <= 0:
                self.logger.error(f"Invalid premium for {symbol}: {premium}")
                return None

            # Apply slippage on entry
            entry_price = premium * (1 + self.config.slippage_percent)

            # Calculate position size
            quantity = self.calculate_position_size(entry_price)

            # Calculate stop loss based on configured method
            if self.config.strategy.stop_loss_method == "technical":
                # Technical SL: Use option premium candle structure
                # Get last 2 candles from option_data for technical SL calculation
                if len(option_data) >= 2:
                    option_candles = option_data.tail(2).to_dict('records')

                    # Convert to simple dict format expected by technical_sl function
                    candles_for_sl = [
                        {'high': c['high'], 'low': c['low'], 'close': c['close']}
                        for c in option_candles
                    ]

                    # Call technical SL calculator
                    stop_loss, sl_pct, reason = calculate_entry_stop_loss(
                        entry_premium=entry_price,
                        option_candles=candles_for_sl,
                        option_type=option_type
                    )

                    self.logger.debug(
                        f"Technical SL: ₹{stop_loss:.2f} ({sl_pct:.1%}) - {reason}"
                    )
                else:
                    # Fallback to fixed SL if not enough candles
                    stop_loss = entry_price * (1 - self.config.stop_loss_percent)
                    self.logger.warning(
                        f"Insufficient candles for technical SL, using fixed {self.config.stop_loss_percent:.1%}"
                    )
            else:
                # Fixed percentage SL (default)
                stop_loss = entry_price * (1 - self.config.stop_loss_percent)

            # Target remains percentage-based
            target = entry_price * (1 + self.config.target_percent)

            # Create trade
            trade = Trade(
                entry_time=entry_time,
                symbol=symbol,
                direction=signal,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                target=target,
                entry_spot=spot_price  # Store original spot price
            )

            self.logger.debug(
                f"Trade entry: {symbol} @ ₹{entry_price:.2f} (real premium: ₹{premium:.2f} + slippage)"
            )

            return trade

        except Exception as e:
            self.logger.error(f"Error entering trade: {e}")
            return None

    def _close_all_trades(self, last_row, reason: str):
        """Close all remaining open trades."""
        for trade in self.open_trades:
            exit_price = self._estimate_option_price(trade, last_row['close'], last_row['date'])
            trade.close(exit_price, last_row['date'], reason, self.config)
            self.closed_trades.append(trade)
            self.capital += trade.pnl

            self.logger.info(
                f"EXIT: {trade.symbol} @ ₹{exit_price:.2f} | "
                f"Reason: {reason} | P&L: ₹{trade.pnl:,.0f}"
            )

        self.open_trades = []

    def _calculate_metrics(self):
        """Calculate performance metrics."""
        if not self.closed_trades:
            self.logger.warning("No closed trades to analyze")
            return None

        # Metrics are calculated by PerformanceMetrics class
        # This is just a wrapper that returns the results
        return {
            'total_trades': len(self.closed_trades),
            'capital_start': self.starting_capital,
            'capital_end': self.capital,
            'total_pnl': self.capital - self.starting_capital,
            'return_percent': ((self.capital - self.starting_capital) / self.starting_capital) * 100
        }


if __name__ == "__main__":
    print("Backtesting engine loaded. Use run_backtest.py to execute.")
