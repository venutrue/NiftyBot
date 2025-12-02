##############################################
# PAPER TRADING SIMULATOR
# Test strategies without risking real money
##############################################

import datetime
import json
import os
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

from common.logger import setup_logger, log_trade, log_position, log_system


@dataclass
class PaperTrade:
    """Paper trade record."""
    order_id: str
    timestamp: datetime.datetime
    symbol: str
    action: str
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    exit_time: Optional[datetime.datetime] = None
    status: str = "OPEN"  # OPEN, CLOSED, CANCELLED
    pnl: float = 0.0
    pnl_percent: float = 0.0
    reason: str = ""


class PaperTradingEngine:
    """
    Paper trading engine that simulates order execution.

    Tracks:
    - Virtual orders and fills
    - P&L tracking
    - Position management
    - Performance metrics
    """

    def __init__(self, initial_capital: float = 200000, data_dir: str = "data/paper_trading"):
        """
        Initialize paper trading engine.

        Args:
            initial_capital: Starting capital for paper trading
            data_dir: Directory for storing paper trading data
        """
        self.logger = setup_logger("PAPER_TRADE")
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Capital tracking
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital

        # Trade tracking
        self.open_trades: Dict[str, PaperTrade] = {}
        self.closed_trades: List[PaperTrade] = []
        self.order_counter = 1

        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0

        # Load previous session if exists
        self._load_session()

        log_system(f"Paper Trading Engine initialized | Capital: ₹{initial_capital:,}")

    def place_order(self, signal: dict, current_price: float) -> str:
        """
        Simulate order placement.

        Args:
            signal: Trading signal
            current_price: Current market price

        Returns:
            Order ID
        """
        order_id = f"PAPER_{self.order_counter:06d}"
        self.order_counter += 1

        # Simulate slippage (0.5%)
        slippage = 0.005
        fill_price = current_price * (1 + slippage) if signal['action'] == 'BUY' else current_price * (1 - slippage)

        # Create paper trade
        trade = PaperTrade(
            order_id=order_id,
            timestamp=datetime.datetime.now(),
            symbol=signal['symbol'],
            action=signal['action'],
            quantity=signal['quantity'],
            entry_price=fill_price,
            reason=signal.get('reason', '')
        )

        self.open_trades[signal['symbol']] = trade

        # Deduct capital
        position_value = fill_price * signal['quantity']
        self.current_capital -= position_value

        log_trade(
            action=signal['action'],
            symbol=signal['symbol'],
            qty=signal['quantity'],
            order_id=order_id,
            order_type="MARKET",
            source="PAPER_TRADE",
            reason=signal.get('reason', '')
        )

        self.logger.info(
            f"📄 Paper Order: {signal['action']} {signal['quantity']} x {signal['symbol']} "
            f"@ ₹{fill_price:.2f} | Order ID: {order_id}"
        )

        self._save_session()
        return order_id

    def exit_position(self, symbol: str, current_price: float, reason: str = "Manual exit") -> Optional[float]:
        """
        Simulate position exit.

        Args:
            symbol: Trading symbol
            current_price: Current market price
            reason: Exit reason

        Returns:
            P&L for the trade
        """
        if symbol not in self.open_trades:
            self.logger.warning(f"No open position for {symbol}")
            return None

        trade = self.open_trades[symbol]

        # Simulate slippage on exit
        slippage = 0.005
        exit_price = current_price * (1 - slippage)  # Slightly worse price on exit

        # Calculate P&L
        pnl = (exit_price - trade.entry_price) * trade.quantity
        pnl_percent = ((exit_price - trade.entry_price) / trade.entry_price) * 100

        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = datetime.datetime.now()
        trade.status = "CLOSED"
        trade.pnl = pnl
        trade.pnl_percent = pnl_percent
        trade.reason = reason

        # Update capital
        position_value = exit_price * trade.quantity
        self.current_capital += position_value

        # Update metrics
        self.total_trades += 1
        self.total_pnl += pnl

        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Update peak and drawdown
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        else:
            drawdown = (self.peak_capital - self.current_capital) / self.peak_capital * 100
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

        # Move to closed trades
        self.closed_trades.append(trade)
        del self.open_trades[symbol]

        log_position(
            "CLOSED",
            symbol,
            price=exit_price,
            qty=trade.quantity,
            reason=reason
        )

        self.logger.info(
            f"📄 Paper Exit: {symbol} @ ₹{exit_price:.2f} | "
            f"P&L: ₹{pnl:,.0f} ({pnl_percent:+.1f}%) | "
            f"Reason: {reason} | "
            f"Total P&L: ₹{self.total_pnl:,.0f}"
        )

        self._save_session()
        return pnl

    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get last traded price (simulated).

        In paper trading, this would need to be fetched from market data.
        For now, return None to indicate it needs real market data.

        Args:
            symbol: Trading symbol

        Returns:
            Last traded price or None
        """
        self.logger.debug(f"Paper trading: LTP for {symbol} requires real market data")
        return None

    def get_positions(self) -> List[dict]:
        """Get current open positions."""
        positions = []
        for symbol, trade in self.open_trades.items():
            positions.append({
                'symbol': symbol,
                'quantity': trade.quantity,
                'entry_price': trade.entry_price,
                'entry_time': trade.timestamp,
                'order_id': trade.order_id,
                'unrealized_pnl': 0  # Needs current price to calculate
            })
        return positions

    def get_performance_summary(self) -> dict:
        """Get performance metrics."""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_win = sum(t.pnl for t in self.closed_trades if t.pnl > 0) / max(self.winning_trades, 1)
        avg_loss = sum(t.pnl for t in self.closed_trades if t.pnl < 0) / max(self.losing_trades, 1)
        profit_factor = abs(avg_win * self.winning_trades / (avg_loss * self.losing_trades)) if self.losing_trades > 0 else float('inf')

        total_return = ((self.current_capital - self.initial_capital) / self.initial_capital) * 100

        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'total_pnl': self.total_pnl,
            'total_return_percent': total_return,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown,
            'open_positions': len(self.open_trades)
        }

    def print_summary(self):
        """Print performance summary."""
        summary = self.get_performance_summary()

        print("\n" + "=" * 70)
        print("PAPER TRADING PERFORMANCE SUMMARY")
        print("=" * 70)
        print(f"\n💰 CAPITAL:")
        print(f"  Initial: ₹{summary['initial_capital']:,.0f}")
        print(f"  Current: ₹{summary['current_capital']:,.0f}")
        print(f"  P&L: ₹{summary['total_pnl']:,.0f} ({summary['total_return_percent']:+.2f}%)")

        print(f"\n📊 TRADES:")
        print(f"  Total: {summary['total_trades']}")
        print(f"  Winners: {summary['winning_trades']} ({summary['win_rate']:.1f}%)")
        print(f"  Losers: {summary['losing_trades']}")
        print(f"  Open: {summary['open_positions']}")

        print(f"\n📈 PERFORMANCE:")
        print(f"  Avg Win: ₹{summary['avg_win']:,.0f}")
        print(f"  Avg Loss: ₹{summary['avg_loss']:,.0f}")
        print(f"  Profit Factor: {summary['profit_factor']:.2f}")
        print(f"  Max Drawdown: {summary['max_drawdown']:.2f}%")

        print("\n" + "=" * 70)

        # Recent trades
        if self.closed_trades:
            print("\nRECENT TRADES (Last 10):")
            print("-" * 70)
            for trade in self.closed_trades[-10:]:
                print(
                    f"{trade.timestamp.strftime('%Y-%m-%d %H:%M')} | "
                    f"{trade.symbol:20s} | "
                    f"₹{trade.pnl:8,.0f} ({trade.pnl_percent:+6.1f}%) | "
                    f"{trade.reason}"
                )
            print("=" * 70 + "\n")

    def _save_session(self):
        """Save paper trading session to disk."""
        session_file = os.path.join(self.data_dir, "paper_session.json")
        try:
            session_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'initial_capital': self.initial_capital,
                'current_capital': self.current_capital,
                'peak_capital': self.peak_capital,
                'total_pnl': self.total_pnl,
                'max_drawdown': self.max_drawdown,
                'order_counter': self.order_counter,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'open_trades': [asdict(t) for t in self.open_trades.values()],
                'closed_trades': [asdict(t) for t in self.closed_trades],
                'performance': self.get_performance_summary()
            }

            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Failed to save paper trading session: {e}")

    def _load_session(self):
        """Load previous paper trading session."""
        session_file = os.path.join(self.data_dir, "paper_session.json")
        if not os.path.exists(session_file):
            return

        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)

            # Check if session is from today
            session_date = datetime.datetime.fromisoformat(session_data['timestamp']).date()
            if session_date == datetime.date.today():
                self.current_capital = session_data['current_capital']
                self.peak_capital = session_data['peak_capital']
                self.total_pnl = session_data['total_pnl']
                self.max_drawdown = session_data['max_drawdown']
                self.order_counter = session_data['order_counter']
                self.total_trades = session_data['total_trades']
                self.winning_trades = session_data['winning_trades']
                self.losing_trades = session_data['losing_trades']

                # Restore open trades
                for trade_data in session_data.get('open_trades', []):
                    trade = PaperTrade(**trade_data)
                    self.open_trades[trade.symbol] = trade

                # Restore closed trades
                for trade_data in session_data.get('closed_trades', []):
                    self.closed_trades.append(PaperTrade(**trade_data))

                self.logger.info(f"Paper trading session restored from {session_date}")
            else:
                self.logger.info(f"Session from {session_date} is stale, starting fresh")

        except Exception as e:
            self.logger.error(f"Failed to load paper trading session: {e}")

    def reset_session(self):
        """Reset paper trading session (start fresh)."""
        self.current_capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.open_trades = {}
        self.closed_trades = []
        self.order_counter = 1
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0

        log_system("Paper trading session reset")
        self._save_session()
