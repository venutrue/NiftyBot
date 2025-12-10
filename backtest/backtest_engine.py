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

    def connect(self):
        """Connect to Kite for historical data."""
        if not self.executor.connect():
            self.logger.error("Failed to connect to Kite")
            return False
        self.logger.info("Connected to Kite for historical data")
        return True

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
        self.logger.info(f"Stop Loss: {self.config.stop_loss_percent*100:.0f}%")
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
        Check if bot generates entry signal at current time.

        Simulates the full VWAP + Supertrend + ADX entry strategy:
        - Premium > VWAP (simulated option VWAP)
        - Supertrend bullish/bearish
        - ADX > threshold

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

        # Get current values
        current_adx = df_slice['ADX'].iloc[-1]
        current_price = df_slice['close'].iloc[-1]

        # Check indicators (already imported at module level)
        st_bullish = is_supertrend_bullish(df_slice)
        st_bearish = is_supertrend_bearish(df_slice)
        atm_strike = get_atm_strike(current_price)

        # Check ADX threshold (strategy parameter)
        adx_threshold = self.config.strategy.adx_threshold

        if pd.isna(current_adx) or current_adx < adx_threshold:
            return None

        # CRITICAL FIX: Check VWAP conditions on options
        # In backtest, we simulate option VWAP using a simplified model:
        # - Option premium follows spot movement with delta correlation
        # - VWAP accumulation happens when premium > historical average
        # - We check if current premium is above its intraday VWAP

        # Estimate option premium (1.5% of spot for ATM)
        estimated_premium = current_price * 0.015

        # Calculate simulated option VWAP from recent candles
        # Use last 30 candles to estimate intraday option VWAP
        if len(df_slice) >= 30:
            recent_slice = df_slice.tail(30)
            # Simulate option premium movement (correlated to spot)
            simulated_premiums = recent_slice['close'] * 0.015
            simulated_volumes = recent_slice['volume']

            # FIX: Check if volume data is valid (indices have zero/invalid volume)
            total_volume = simulated_volumes.sum()
            if total_volume == 0 or pd.isna(total_volume):
                # Volume data is invalid - use spot VWAP as proxy
                if 'vwap' in recent_slice.columns and not pd.isna(recent_slice['vwap'].iloc[-1]):
                    # Scale spot VWAP to option premium level (1.5% of spot)
                    spot_vwap = recent_slice['vwap'].iloc[-1]
                    option_vwap = spot_vwap * 0.015
                    self.logger.debug(
                        f"Using spot VWAP proxy (volume data invalid): spot_vwap={spot_vwap:.2f}, option_vwap={option_vwap:.2f}"
                    )
                else:
                    # No valid VWAP data available, skip signal
                    self.logger.debug(
                        f"NO SIGNAL | No valid VWAP data available (volume={total_volume})"
                    )
                    return None
            else:
                # Calculate VWAP for simulated option using volume
                option_vwap = (simulated_premiums * simulated_volumes).sum() / total_volume

            # Validate option_vwap is not NaN
            if pd.isna(option_vwap) or option_vwap <= 0:
                self.logger.debug(
                    f"NO SIGNAL | Invalid option VWAP calculated: {option_vwap}"
                )
                return None

            # Check VWAP condition: Premium must be > VWAP (smart money accumulation)
            vwap_buffer = self.config.strategy.vwap_buffer_percent
            vwap_threshold = option_vwap * (1 + vwap_buffer)

            if estimated_premium <= vwap_threshold:
                # VWAP condition not met - no signal
                self.logger.debug(
                    f"NO SIGNAL | Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"ADX: {current_adx:.1f} | ST: {'Bullish' if st_bullish else 'Bearish'} | "
                    f"Premium: {estimated_premium:.2f} <= VWAP: {option_vwap:.2f} (VWAP condition failed)"
                )
                return None
        else:
            # Not enough data for VWAP calculation, skip
            return None

        # All conditions met - generate signal
        if st_bullish:
            self.logger.info(
                f"✓ SIGNAL: BUY_CE | Spot: {current_price:.2f} | ATM: {atm_strike} | "
                f"ADX: {current_adx:.1f} | ST: Bullish | "
                f"Premium: {estimated_premium:.2f} > VWAP: {option_vwap:.2f} (+{((estimated_premium/option_vwap-1)*100):.1f}%)"
            )
            return 'BUY_CE'
        elif st_bearish:
            self.logger.info(
                f"✓ SIGNAL: BUY_PE | Spot: {current_price:.2f} | ATM: {atm_strike} | "
                f"ADX: {current_adx:.1f} | ST: Bearish | "
                f"Premium: {estimated_premium:.2f} > VWAP: {option_vwap:.2f} (+{((estimated_premium/option_vwap-1)*100):.1f}%)"
            )
            return 'BUY_PE'

        return None

    def _enter_trade(self, signal: str, entry_time, spot_price: float) -> Optional[Trade]:
        """Enter a new trade based on signal."""
        try:
            # Get ATM strike
            atm_strike = get_atm_strike(
                spot_price,
                NIFTY_LOT_SIZE if 'NIFTY' in self.bot.name else BANKNIFTY_LOT_SIZE
            )

            # Determine option type
            option_type = "CE" if signal == "BUY_CE" else "PE"

            # Get option symbol
            symbol = self.bot.get_option_symbol(atm_strike, option_type)

            # Estimate option premium (simplified: 1-2% of spot for ATM)
            # In production, use actual historical option data
            premium = spot_price * 0.015  # 1.5% of spot

            # Apply slippage on entry
            entry_price = premium * (1 + self.config.slippage_percent)

            # Calculate position size
            quantity = self.calculate_position_size(entry_price)

            # Calculate stop loss and target
            stop_loss = entry_price * (1 - self.config.stop_loss_percent)
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
