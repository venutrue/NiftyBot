#!/usr/bin/env python3
"""
Paper Trade Executor - Wraps paper trading engine to work with existing bots
"""

import datetime
from typing import Dict, Optional

from executor.paper_trading import PaperTradingEngine
from executor.trade_executor import KiteExecutor
from common.logger import setup_logger, log_trade, log_system
from common.config import EXCHANGE_NSE, EXCHANGE_NFO


class PaperTradeExecutor:
    """
    Paper trading executor that mimics TradeExecutor interface.

    Uses real market data for prices, but simulates order execution.
    """

    def __init__(self, initial_capital: float = 200000):
        """
        Initialize paper trade executor.

        Args:
            initial_capital: Starting capital for paper trading
        """
        self.logger = setup_logger("PAPER_EXEC")
        self.paper_engine = PaperTradingEngine(initial_capital)

        # Use real Kite connection for market data (prices)
        self.kite_executor = KiteExecutor()

        # Daily tracking (mimics TradeExecutor)
        self.daily_pnl = 0
        self.daily_trades = 0
        self.positions = {}

        log_system(f"Paper Trade Executor initialized | Capital: ₹{initial_capital:,}")

    def connect(self):
        """Connect to broker (for market data only)."""
        connected = self.kite_executor.connect()
        if connected:
            log_system("Connected to Kite for market data (PAPER MODE)")
        return connected

    def execute(self, signal: dict) -> Optional[str]:
        """
        Execute a paper trade.

        Args:
            signal: Trading signal from bot

        Returns:
            Paper order ID if successful
        """
        try:
            # Get current market price
            symbol = signal['symbol']
            exchange = signal.get('exchange', EXCHANGE_NFO)

            current_price = self.get_ltp(symbol, exchange)
            if not current_price:
                self.logger.error(f"Could not get price for {symbol}")
                return None

            # Place paper order
            order_id = self.paper_engine.place_order(signal, current_price)

            if order_id:
                self.daily_trades += 1

                # Track position (mimics TradeExecutor)
                self.positions[symbol] = {
                    'order_id': order_id,
                    'entry_price': current_price,
                    'quantity': signal['quantity'],
                    'stop_loss': signal.get('stop_loss'),
                    'target': signal.get('target'),
                    'source': signal.get('source')
                }

                self.logger.info(
                    f"📄 Paper trade executed: {signal['action']} {signal['quantity']} x {symbol} "
                    f"@ ₹{current_price:.2f}"
                )

            return order_id

        except Exception as e:
            self.logger.error(f"Paper trade failed: {e}")
            return None

    def exit_position(self, symbol: str, reason: str = "Manual exit") -> Optional[str]:
        """
        Exit a paper position.

        Args:
            symbol: Trading symbol
            reason: Exit reason

        Returns:
            Order ID if successful
        """
        if symbol not in self.positions:
            self.logger.warning(f"No paper position for {symbol}")
            return None

        try:
            # Get current market price
            current_price = self.get_ltp(symbol, EXCHANGE_NFO)
            if not current_price:
                self.logger.error(f"Could not get price for {symbol}")
                return None

            # Exit in paper engine
            pnl = self.paper_engine.exit_position(symbol, current_price, reason)

            if pnl is not None:
                self.daily_pnl += pnl
                del self.positions[symbol]

                self.logger.info(
                    f"📄 Paper position closed: {symbol} | "
                    f"P&L: ₹{pnl:,.0f} | Total: ₹{self.daily_pnl:,.0f}"
                )

                return f"EXIT_{symbol}"

            return None

        except Exception as e:
            self.logger.error(f"Paper exit failed: {e}")
            return None

    def get_ltp(self, symbol: str, exchange: str = EXCHANGE_NSE) -> Optional[float]:
        """Get last traded price (real market data)."""
        return self.kite_executor.get_ltp(symbol, exchange)

    def get_historical_data(self, instrument_token, from_date, to_date, interval="minute"):
        """Get historical data (real market data)."""
        return self.kite_executor.get_historical_data(
            instrument_token, from_date, to_date, interval
        )

    def get_instruments(self, exchange=EXCHANGE_NSE):
        """Get instruments (real market data)."""
        return self.kite_executor.get_instruments(exchange)

    def get_instrument_token(self, symbol, exchange=EXCHANGE_NSE):
        """Get instrument token (real market data)."""
        return self.kite_executor.get_instrument_token(symbol, exchange)

    def get_positions(self):
        """Get paper positions."""
        return self.paper_engine.get_positions()

    def get_orders(self):
        """Get paper orders (empty list - not tracked)."""
        return []

    def get_margins(self):
        """Get paper margins."""
        return {
            'equity': {
                'available': {
                    'live_balance': self.paper_engine.current_capital
                }
            }
        }

    def get_order_history(self, order_id):
        """Get order history (simulated complete status)."""
        return {
            'status': 'COMPLETE',
            'average_price': 0  # Will be fetched from position
        }

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L."""
        self.daily_pnl += pnl

    def reset_daily_stats(self):
        """Reset daily statistics."""
        self.daily_pnl = 0
        self.daily_trades = 0
        self.positions = {}
        log_system("Paper trading daily stats reset")

    def get_daily_summary(self):
        """Get daily summary."""
        return {
            'date': datetime.date.today(),
            'trades': self.daily_trades,
            'pnl': self.daily_pnl,
            'open_positions': len(self.positions)
        }

    def get_performance_summary(self):
        """Get full performance summary."""
        return self.paper_engine.get_performance_summary()

    def print_summary(self):
        """Print performance summary."""
        self.paper_engine.print_summary()
