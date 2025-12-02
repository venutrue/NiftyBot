##############################################
# RISK MANAGEMENT SYSTEM
# Multi-layered risk controls for live trading
# NEVER trade without these checks enabled
##############################################

import datetime
import os
import json
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from collections import deque

from common.config import (
    MAX_LOSS_PER_DAY, MAX_WEEKLY_LOSS, MAX_CONSECUTIVE_LOSSES,
    NIFTY_MAX_TRADES_PER_DAY, BANKNIFTY_MAX_TRADES_PER_DAY,
    MAX_CAPITAL_DEPLOYED, TRADING_CAPITAL, TOTAL_CAPITAL,
    MAX_INVESTMENT_PER_TRADE, INITIAL_SL_PERCENT
)
from common.logger import setup_logger, log_error, log_system


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    timestamp: datetime.datetime
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_percent: float
    reason: str


@dataclass
class RiskLimits:
    """Risk limits configuration."""
    # Daily limits
    max_loss_per_day: float = MAX_LOSS_PER_DAY
    max_profit_per_day: Optional[float] = None  # Stop when daily target hit
    max_trades_per_day: int = 10
    max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES

    # Per-trade limits
    max_position_size: float = MAX_INVESTMENT_PER_TRADE
    min_position_size: float = 10000  # Rs. 10K minimum
    max_stop_loss_percent: float = 25  # Never risk more than 25%

    # Capital limits
    max_capital_deployed: float = MAX_CAPITAL_DEPLOYED
    max_capital_per_bot: float = TRADING_CAPITAL

    # Position limits
    max_open_positions: int = 3
    max_positions_per_symbol: int = 1

    # Weekly limits
    max_loss_per_week: float = MAX_WEEKLY_LOSS

    # Order limits
    max_order_value: float = 100000  # Rs. 1L max single order
    max_quantity_multiplier: float = 5.0  # Max 5x normal position size

    # Time-based limits
    no_trading_after_loss_minutes: int = 30  # Cool-off after stop loss

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)


class RiskManager:
    """
    Multi-layered risk management system.

    Layers of protection:
    1. Pre-trade validation (size, capital, exposure)
    2. Daily/weekly loss limits
    3. Consecutive loss protection
    4. Circuit breakers
    5. Position concentration limits
    6. Time-based restrictions
    7. Emergency kill switch
    """

    def __init__(self, limits: Optional[RiskLimits] = None, data_dir: str = "data/risk"):
        """
        Initialize risk manager.

        Args:
            limits: Risk limits configuration
            data_dir: Directory for storing risk data
        """
        self.logger = setup_logger("RISK_MGR")
        self.limits = limits or RiskLimits()
        self.data_dir = data_dir

        # Create data directory
        os.makedirs(data_dir, exist_ok=True)

        # State tracking
        self.trading_enabled = True
        self.kill_switch_active = False
        self.circuit_breaker_active = False
        self.cool_off_until: Optional[datetime.datetime] = None

        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_winners = 0
        self.daily_losers = 0
        self.consecutive_losses = 0
        self.open_positions: Dict[str, dict] = {}
        self.capital_deployed = 0.0

        # Weekly tracking
        self.weekly_pnl = 0.0
        self.weekly_trades = 0

        # Trade history (recent trades)
        self.trade_history: deque = deque(maxlen=100)

        # Bot-specific tracking
        self.bot_trades: Dict[str, int] = {}  # bot_name -> trade_count

        # Blocked symbols (after repeated losses)
        self.blocked_symbols: Dict[str, datetime.datetime] = {}  # symbol -> unblock_time

        # Load state if exists
        self._load_state()

        log_system(f"Risk Manager initialized | Limits: {self.limits.to_dict()}")

    def activate_kill_switch(self, reason: str):
        """
        EMERGENCY: Stop all trading immediately.

        This is the nuclear option - use when:
        - Catastrophic losses
        - System malfunction
        - Market crash
        - Manual override needed

        Args:
            reason: Why kill switch was activated
        """
        self.kill_switch_active = True
        self.trading_enabled = False
        self.circuit_breaker_active = True

        log_system(f"🚨 KILL SWITCH ACTIVATED: {reason}")
        self._save_state()

        # Log to separate emergency file
        self._log_emergency("KILL_SWITCH", reason)

    def deactivate_kill_switch(self, authorized_by: str):
        """
        Deactivate kill switch (requires manual authorization).

        Args:
            authorized_by: Who authorized reactivation
        """
        self.kill_switch_active = False
        self.circuit_breaker_active = False
        self.trading_enabled = True

        log_system(f"✅ Kill switch deactivated by: {authorized_by}")
        self._save_state()

        self._log_emergency("KILL_SWITCH_DEACTIVATED", f"By: {authorized_by}")

    def activate_circuit_breaker(self, reason: str, duration_minutes: int = 60):
        """
        Temporarily halt trading (circuit breaker).

        Auto-activates on:
        - Daily loss limit hit
        - Consecutive losses
        - Rapid drawdown

        Args:
            reason: Why circuit breaker triggered
            duration_minutes: How long to pause trading
        """
        self.circuit_breaker_active = True
        self.trading_enabled = False
        self.cool_off_until = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)

        log_system(f"⏸️  CIRCUIT BREAKER: {reason} | Cool-off: {duration_minutes} min")
        self._save_state()

    def check_circuit_breaker(self) -> Tuple[bool, str]:
        """
        Check if circuit breaker should be lifted.

        Returns:
            (should_lift, reason)
        """
        if not self.circuit_breaker_active:
            return (False, "Not active")

        if self.cool_off_until and datetime.datetime.now() >= self.cool_off_until:
            self.circuit_breaker_active = False
            self.trading_enabled = True
            self.cool_off_until = None
            log_system("✅ Circuit breaker lifted - trading resumed")
            self._save_state()
            return (True, "Cool-off period completed")

        return (False, f"Cool-off until {self.cool_off_until}")

    def validate_trade(self, signal: dict, current_capital: float) -> Tuple[bool, str]:
        """
        Comprehensive pre-trade validation.

        Args:
            signal: Trading signal to validate
            current_capital: Available capital

        Returns:
            (is_valid, reason)
        """
        # Check 1: Kill switch
        if self.kill_switch_active:
            return (False, "KILL SWITCH ACTIVE")

        # Check 2: Circuit breaker
        if self.circuit_breaker_active:
            self.check_circuit_breaker()  # Auto-check if should lift
            if self.circuit_breaker_active:
                return (False, f"CIRCUIT BREAKER | Cool-off until {self.cool_off_until}")

        # Check 3: Trading enabled
        if not self.trading_enabled:
            return (False, "Trading disabled")

        # Check 4: Daily loss limit
        if self.daily_pnl <= -self.limits.max_loss_per_day:
            self.activate_circuit_breaker(
                f"Daily loss limit hit: ₹{self.daily_pnl:,.0f}",
                duration_minutes=240  # Rest of day
            )
            return (False, f"DAILY LOSS LIMIT: ₹{self.daily_pnl:,.0f}")

        # Check 5: Daily profit target (if set)
        if self.limits.max_profit_per_day and self.daily_pnl >= self.limits.max_profit_per_day:
            return (False, f"Daily profit target hit: ₹{self.daily_pnl:,.0f} | Take the win!")

        # Check 6: Weekly loss limit
        if self.weekly_pnl <= -self.limits.max_loss_per_week:
            self.activate_kill_switch(f"Weekly loss limit hit: ₹{self.weekly_pnl:,.0f}")
            return (False, f"WEEKLY LOSS LIMIT: ₹{self.weekly_pnl:,.0f}")

        # Check 7: Daily trade limit
        if self.daily_trades >= self.limits.max_trades_per_day:
            return (False, f"Daily trade limit: {self.daily_trades}/{self.limits.max_trades_per_day}")

        # Check 8: Bot-specific trade limit
        bot_name = signal.get('source', 'UNKNOWN')
        bot_limit = NIFTY_MAX_TRADES_PER_DAY if 'NIFTY' in bot_name else BANKNIFTY_MAX_TRADES_PER_DAY
        bot_trades = self.bot_trades.get(bot_name, 0)
        if bot_trades >= bot_limit:
            return (False, f"{bot_name} daily limit: {bot_trades}/{bot_limit}")

        # Check 9: Consecutive losses
        if self.consecutive_losses >= self.limits.max_consecutive_losses:
            self.activate_circuit_breaker(
                f"Consecutive losses: {self.consecutive_losses}",
                duration_minutes=self.limits.no_trading_after_loss_minutes
            )
            return (False, f"CONSECUTIVE LOSSES: {self.consecutive_losses}")

        # Check 10: Position size limits
        position_value = signal.get('quantity', 0) * signal.get('price', 0)
        if position_value > self.limits.max_position_size:
            return (False, f"Position too large: ₹{position_value:,.0f} > ₹{self.limits.max_position_size:,.0f}")

        if position_value < self.limits.min_position_size:
            return (False, f"Position too small: ₹{position_value:,.0f} < ₹{self.limits.min_position_size:,.0f}")

        # Check 11: Capital deployment limit
        new_deployed = self.capital_deployed + position_value
        if new_deployed > self.limits.max_capital_deployed:
            return (False, f"Capital deployment: ₹{new_deployed:,.0f} > ₹{self.limits.max_capital_deployed:,.0f}")

        # Check 12: Open position limit
        if len(self.open_positions) >= self.limits.max_open_positions:
            return (False, f"Max open positions: {len(self.open_positions)}/{self.limits.max_open_positions}")

        # Check 13: Symbol-specific position limit
        symbol = signal.get('symbol', '')
        if symbol in self.open_positions:
            return (False, f"Already have position in {symbol}")

        # Check 14: Blocked symbol check
        if symbol in self.blocked_symbols:
            unblock_time = self.blocked_symbols[symbol]
            if datetime.datetime.now() < unblock_time:
                return (False, f"Symbol blocked until {unblock_time}")
            else:
                # Unblock
                del self.blocked_symbols[symbol]

        # Check 15: Stop loss validation
        stop_loss_percent = abs(signal.get('stop_loss_percent', INITIAL_SL_PERCENT))
        if stop_loss_percent > self.limits.max_stop_loss_percent:
            return (False, f"Stop loss too wide: {stop_loss_percent}% > {self.limits.max_stop_loss_percent}%")

        # Check 16: Available capital
        if position_value > current_capital:
            return (False, f"Insufficient capital: ₹{position_value:,.0f} > ₹{current_capital:,.0f}")

        # Check 17: Order value sanity check
        if position_value > self.limits.max_order_value:
            return (False, f"Order too large: ₹{position_value:,.0f} > ₹{self.limits.max_order_value:,.0f}")

        # All checks passed
        return (True, "Trade validated")

    def register_trade_entry(self, symbol: str, signal: dict):
        """
        Register a new trade entry.

        Args:
            symbol: Trading symbol
            signal: Trade signal
        """
        position_value = signal.get('quantity', 0) * signal.get('price', 0)

        self.open_positions[symbol] = {
            'entry_time': datetime.datetime.now(),
            'entry_price': signal.get('price', 0),
            'quantity': signal.get('quantity', 0),
            'value': position_value,
            'stop_loss': signal.get('stop_loss'),
            'target': signal.get('target'),
            'bot': signal.get('source', 'UNKNOWN')
        }

        self.capital_deployed += position_value
        self.daily_trades += 1

        # Increment bot counter
        bot_name = signal.get('source', 'UNKNOWN')
        self.bot_trades[bot_name] = self.bot_trades.get(bot_name, 0) + 1

        self.logger.info(f"Trade registered: {symbol} | ₹{position_value:,.0f} | Deployed: ₹{self.capital_deployed:,.0f}")
        self._save_state()

    def register_trade_exit(self, symbol: str, exit_price: float, reason: str) -> float:
        """
        Register trade exit and update P&L.

        Args:
            symbol: Trading symbol
            exit_price: Exit price
            reason: Exit reason

        Returns:
            P&L for this trade
        """
        if symbol not in self.open_positions:
            self.logger.warning(f"No open position for {symbol}")
            return 0.0

        position = self.open_positions[symbol]

        # Calculate P&L
        entry_price = position['entry_price']
        quantity = position['quantity']
        pnl = (exit_price - entry_price) * quantity
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100

        # Update tracking
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        self.capital_deployed -= position['value']

        # Win/loss tracking
        if pnl > 0:
            self.daily_winners += 1
            self.consecutive_losses = 0
        else:
            self.daily_losers += 1
            self.consecutive_losses += 1

            # Block symbol if repeated losses
            if reason == "STOP_LOSS" and self.consecutive_losses >= 2:
                # Block for 2 hours
                self.blocked_symbols[symbol] = datetime.datetime.now() + datetime.timedelta(hours=2)
                self.logger.warning(f"Symbol {symbol} blocked for 2 hours after consecutive losses")

        # Record trade
        trade_record = TradeRecord(
            timestamp=datetime.datetime.now(),
            symbol=symbol,
            direction="BUY",
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            reason=reason
        )
        self.trade_history.append(trade_record)

        # Remove position
        del self.open_positions[symbol]

        self.logger.info(
            f"Trade closed: {symbol} | P&L: ₹{pnl:,.0f} ({pnl_percent:+.1f}%) | "
            f"Daily P&L: ₹{self.daily_pnl:,.0f} | Reason: {reason}"
        )

        self._save_state()

        # Check if we need circuit breaker
        if self.daily_pnl <= -self.limits.max_loss_per_day:
            self.activate_circuit_breaker("Daily loss limit hit", duration_minutes=240)
        elif self.consecutive_losses >= self.limits.max_consecutive_losses:
            self.activate_circuit_breaker(
                f"Consecutive losses: {self.consecutive_losses}",
                duration_minutes=self.limits.no_trading_after_loss_minutes
            )

        return pnl

    def reset_daily_stats(self):
        """Reset daily statistics (call at start of trading day)."""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_winners = 0
        self.daily_losers = 0
        self.consecutive_losses = 0
        self.bot_trades = {}
        self.open_positions = {}
        self.capital_deployed = 0.0

        # Keep weekly stats
        # Keep blocked symbols
        # Keep circuit breaker if active

        log_system("Daily risk stats reset")
        self._save_state()

    def reset_weekly_stats(self):
        """Reset weekly statistics (call at start of week)."""
        self.weekly_pnl = 0.0
        self.weekly_trades = 0

        log_system("Weekly risk stats reset")
        self._save_state()

    def get_risk_summary(self) -> dict:
        """Get current risk status summary."""
        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'trading_enabled': self.trading_enabled,
            'kill_switch_active': self.kill_switch_active,
            'circuit_breaker_active': self.circuit_breaker_active,
            'cool_off_until': self.cool_off_until.isoformat() if self.cool_off_until else None,
            'daily': {
                'pnl': self.daily_pnl,
                'trades': self.daily_trades,
                'winners': self.daily_winners,
                'losers': self.daily_losers,
                'consecutive_losses': self.consecutive_losses,
                'open_positions': len(self.open_positions),
                'capital_deployed': self.capital_deployed
            },
            'weekly': {
                'pnl': self.weekly_pnl,
                'trades': self.weekly_trades
            },
            'limits': self.limits.to_dict(),
            'blocked_symbols': {
                symbol: unblock_time.isoformat()
                for symbol, unblock_time in self.blocked_symbols.items()
            }
        }

    def _save_state(self):
        """Save current state to disk."""
        state_file = os.path.join(self.data_dir, "risk_state.json")
        try:
            state = self.get_risk_summary()
            state['open_positions_detail'] = self.open_positions

            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            log_error("RISK_MGR", f"Failed to save state: {e}")

    def _load_state(self):
        """Load state from disk (if exists)."""
        state_file = os.path.join(self.data_dir, "risk_state.json")
        if not os.path.exists(state_file):
            return

        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            # Restore state (only if from today)
            if 'timestamp' in state:
                state_date = datetime.datetime.fromisoformat(state['timestamp']).date()
                if state_date == datetime.date.today():
                    self.trading_enabled = state.get('trading_enabled', True)
                    self.kill_switch_active = state.get('kill_switch_active', False)
                    self.circuit_breaker_active = state.get('circuit_breaker_active', False)

                    if state.get('cool_off_until'):
                        self.cool_off_until = datetime.datetime.fromisoformat(state['cool_off_until'])

                    if 'daily' in state:
                        self.daily_pnl = state['daily']['pnl']
                        self.daily_trades = state['daily']['trades']
                        self.daily_winners = state['daily']['winners']
                        self.daily_losers = state['daily']['losers']
                        self.consecutive_losses = state['daily']['consecutive_losses']
                        self.capital_deployed = state['daily']['capital_deployed']

                    if 'weekly' in state:
                        self.weekly_pnl = state['weekly']['pnl']
                        self.weekly_trades = state['weekly']['trades']

                    if 'open_positions_detail' in state:
                        self.open_positions = state['open_positions_detail']

                    self.logger.info(f"Risk state restored from {state_date}")
                else:
                    self.logger.info(f"State from {state_date} is stale, starting fresh")
        except Exception as e:
            log_error("RISK_MGR", f"Failed to load state: {e}")

    def _log_emergency(self, event_type: str, details: str):
        """Log emergency events to separate file."""
        emergency_file = os.path.join(self.data_dir, "emergency_log.txt")
        try:
            with open(emergency_file, 'a') as f:
                timestamp = datetime.datetime.now().isoformat()
                f.write(f"{timestamp} | {event_type} | {details}\n")
        except Exception as e:
            log_error("RISK_MGR", f"Failed to log emergency: {e}")
