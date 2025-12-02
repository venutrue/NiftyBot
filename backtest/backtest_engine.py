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

    def __init__(self):
        # Capital management
        self.initial_capital = 500000  # ₹5 Lakh
        self.max_risk_per_trade = 0.01  # 1% of capital per trade
        self.max_daily_loss = 0.03  # 3% max loss per day
        self.max_capital_deployed = 0.30  # Max 30% in positions simultaneously

        # Position management
        self.max_positions = 3  # Maximum 3 positions at once
        self.stop_loss_percent = 0.20  # 20% stop loss
        self.target_percent = 0.40  # 40% target (2:1 risk:reward)
        self.trailing_stop_activation = 0.30  # Trail after 30% profit
        self.trailing_stop_distance = 0.10  # Trail 10% below max

        # Execution assumptions
        self.slippage_percent = 0.005  # 0.5% slippage
        self.commission_per_trade = 40  # ₹40 per trade (Zerodha approx)

        # Backtest parameters
        self.start_date = datetime.datetime.now() - datetime.timedelta(days=90)  # 3 months
        self.end_date = datetime.datetime.now()


class Trade:
    """Represents a single trade."""

    def __init__(self, entry_time, symbol, direction, entry_price, quantity, stop_loss, target):
        self.entry_time = entry_time
        self.symbol = symbol
        self.direction = direction  # 'BUY_CE' or 'BUY_PE'
        self.entry_price = entry_price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.target = target

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

        Uses Kelly Criterion-inspired position sizing:
        - Risk exactly config.max_risk_per_trade of capital
        - Respects max capital deployed limit
        - Returns number of lots to trade
        """
        # Max risk amount
        max_risk_amount = self.capital * self.config.max_risk_per_trade

        # Stop loss distance
        stop_loss_distance = premium * self.config.stop_loss_percent

        # Calculate quantity to risk exact amount
        quantity_for_risk = max_risk_amount / stop_loss_distance

        # Convert to lots
        lot_size = NIFTY_LOT_SIZE if 'NIFTY' in self.bot.name else BANKNIFTY_LOT_SIZE
        lots = int(quantity_for_risk / lot_size)

        # Ensure at least 1 lot
        lots = max(1, lots)

        # Check max capital deployed
        position_value = premium * lots * lot_size
        deployed_capital = sum(t.entry_cost for t in self.open_trades)

        if deployed_capital + position_value > self.capital * self.config.max_capital_deployed:
            # Reduce position size
            available = self.capital * self.config.max_capital_deployed - deployed_capital
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
        # TODO: Implement full simulation logic
        # This is a placeholder - full implementation coming next
        pass

    def _calculate_metrics(self):
        """Calculate performance metrics."""
        # TODO: Implement metrics calculation
        # This is a placeholder
        pass


if __name__ == "__main__":
    print("Backtesting engine loaded. Use run_backtest.py to execute.")
