##############################################
# TRADING MONITOR
# Real-time position and performance monitoring
##############################################

import datetime
import time
from typing import Dict, List, Optional
import threading

from common.logger import setup_logger, log_system, log_error
from executor.risk_manager import RiskManager


class TradingMonitor:
    """
    Real-time monitoring of positions and risk metrics.

    Features:
    - Position P&L tracking
    - Stop loss monitoring
    - Target monitoring
    - Trailing stop management
    - Risk limit warnings
    - Performance tracking
    """

    def __init__(self, risk_manager: RiskManager, executor, check_interval: int = 30):
        """
        Initialize trading monitor.

        Args:
            risk_manager: Risk manager instance
            executor: Trade executor instance
            check_interval: How often to check positions (seconds)
        """
        self.logger = setup_logger("MONITOR")
        self.risk_manager = risk_manager
        self.executor = executor
        self.check_interval = check_interval

        self.running = False
        self.monitor_thread = None

        # Alert thresholds
        self.alert_on_profit_percent = 30  # Alert when position up 30%
        self.alert_on_loss_percent = 10    # Alert when position down 10%

        log_system(f"Trading Monitor initialized | Check interval: {check_interval}s")

    def start(self):
        """Start monitoring in background thread."""
        if self.running:
            self.logger.warning("Monitor already running")
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        log_system("Trading Monitor started")

    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        log_system("Trading Monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._check_positions()
                self._check_risk_limits()
                self._check_circuit_breaker()
                time.sleep(self.check_interval)
            except Exception as e:
                log_error("MONITOR", f"Error in monitor loop: {e}")
                time.sleep(self.check_interval)

    def _check_positions(self):
        """Check all open positions."""
        try:
            # Get open positions from risk manager
            open_positions = self.risk_manager.open_positions

            if not open_positions:
                return

            for symbol, position in open_positions.items():
                # Get current price
                ltp = self.executor.get_ltp(symbol, exchange="NFO")
                if not ltp:
                    continue

                # Calculate current P&L
                entry_price = position['entry_price']
                quantity = position['quantity']
                current_pnl = (ltp - entry_price) * quantity
                current_pnl_percent = ((ltp - entry_price) / entry_price) * 100

                # Check stop loss
                if position['stop_loss'] and ltp <= position['stop_loss']:
                    self.logger.warning(
                        f"⚠️  STOP LOSS HIT: {symbol} @ ₹{ltp:.2f} | "
                        f"P&L: ₹{current_pnl:,.0f} ({current_pnl_percent:+.1f}%)"
                    )
                    self._trigger_exit(symbol, ltp, "STOP_LOSS")

                # Check target
                if position['target'] and ltp >= position['target']:
                    self.logger.info(
                        f"🎯 TARGET HIT: {symbol} @ ₹{ltp:.2f} | "
                        f"P&L: ₹{current_pnl:,.0f} ({current_pnl_percent:+.1f}%)"
                    )
                    self._trigger_exit(symbol, ltp, "TARGET")

                # Alert on significant moves
                if current_pnl_percent >= self.alert_on_profit_percent:
                    self.logger.info(
                        f"📈 BIG PROFIT: {symbol} @ ₹{ltp:.2f} | "
                        f"P&L: ₹{current_pnl:,.0f} ({current_pnl_percent:+.1f}%)"
                    )

                elif current_pnl_percent <= -self.alert_on_loss_percent:
                    self.logger.warning(
                        f"📉 LOSS ALERT: {symbol} @ ₹{ltp:.2f} | "
                        f"P&L: ₹{current_pnl:,.0f} ({current_pnl_percent:+.1f}%)"
                    )

        except Exception as e:
            log_error("MONITOR", f"Error checking positions: {e}")

    def _check_risk_limits(self):
        """Check if any risk limits are approaching."""
        try:
            # Daily P&L check
            daily_pnl = self.risk_manager.daily_pnl
            max_loss = self.risk_manager.limits.max_loss_per_day

            # Warn at 75% of daily loss limit
            if daily_pnl <= -(max_loss * 0.75):
                self.logger.warning(
                    f"⚠️  APPROACHING DAILY LOSS LIMIT: "
                    f"₹{daily_pnl:,.0f} / ₹{-max_loss:,.0f}"
                )

            # Check consecutive losses
            if self.risk_manager.consecutive_losses >= 2:
                self.logger.warning(
                    f"⚠️  CONSECUTIVE LOSSES: {self.risk_manager.consecutive_losses}"
                )

            # Check capital deployed
            deployed = self.risk_manager.capital_deployed
            max_deployed = self.risk_manager.limits.max_capital_deployed

            if deployed >= (max_deployed * 0.9):
                self.logger.warning(
                    f"⚠️  HIGH CAPITAL DEPLOYMENT: "
                    f"₹{deployed:,.0f} / ₹{max_deployed:,.0f}"
                )

        except Exception as e:
            log_error("MONITOR", f"Error checking risk limits: {e}")

    def _check_circuit_breaker(self):
        """Check if circuit breaker should be lifted."""
        if self.risk_manager.circuit_breaker_active:
            lifted, reason = self.risk_manager.check_circuit_breaker()
            if lifted:
                self.logger.info(f"✅ Circuit breaker lifted: {reason}")

    def _trigger_exit(self, symbol: str, exit_price: float, reason: str):
        """
        Trigger position exit.

        Args:
            symbol: Trading symbol
            exit_price: Exit price
            reason: Exit reason
        """
        try:
            # Exit via executor
            order_id = self.executor.exit_position(symbol, reason=reason)

            if order_id:
                # Register with risk manager
                pnl = self.risk_manager.register_trade_exit(symbol, exit_price, reason)
                self.logger.info(
                    f"Position closed: {symbol} | P&L: ₹{pnl:,.0f} | Reason: {reason}"
                )
            else:
                self.logger.error(f"Failed to exit position: {symbol}")

        except Exception as e:
            log_error("MONITOR", f"Error triggering exit for {symbol}: {e}")

    def get_status(self) -> dict:
        """Get current monitoring status."""
        return {
            'running': self.running,
            'check_interval': self.check_interval,
            'open_positions': len(self.risk_manager.open_positions),
            'daily_pnl': self.risk_manager.daily_pnl,
            'circuit_breaker_active': self.risk_manager.circuit_breaker_active,
            'kill_switch_active': self.risk_manager.kill_switch_active
        }

    def print_status(self):
        """Print current status to console."""
        status = self.get_status()
        summary = self.risk_manager.get_risk_summary()

        print("\n" + "=" * 70)
        print("TRADING MONITOR STATUS")
        print("=" * 70)
        print(f"\nMonitor: {'🟢 RUNNING' if status['running'] else '🔴 STOPPED'}")
        print(f"Trading: {'🟢 ENABLED' if not summary['kill_switch_active'] else '🔴 DISABLED'}")
        print(f"Circuit Breaker: {'🔴 ACTIVE' if summary['circuit_breaker_active'] else '🟢 OK'}")

        print(f"\n📊 TODAY'S PERFORMANCE:")
        print(f"  P&L: ₹{summary['daily']['pnl']:,.0f}")
        print(f"  Trades: {summary['daily']['trades']}")
        print(f"  Winners: {summary['daily']['winners']}")
        print(f"  Losers: {summary['daily']['losers']}")
        print(f"  Consecutive Losses: {summary['daily']['consecutive_losses']}")

        print(f"\n💼 POSITIONS:")
        print(f"  Open: {summary['daily']['open_positions']}")
        print(f"  Capital Deployed: ₹{summary['daily']['capital_deployed']:,.0f}")

        if self.risk_manager.open_positions:
            print(f"\n  Open Positions:")
            for symbol, pos in self.risk_manager.open_positions.items():
                print(
                    f"    {symbol:20s} | "
                    f"Qty: {pos['quantity']:3d} | "
                    f"Entry: ₹{pos['entry_price']:.2f}"
                )

        print("=" * 70 + "\n")


class AlertSystem:
    """
    Alert system for sending notifications.

    Supports:
    - Console alerts (always enabled)
    - Telegram alerts (optional)
    - Email alerts (optional)
    - SMS alerts (optional)
    """

    def __init__(self):
        """Initialize alert system."""
        self.logger = setup_logger("ALERTS")
        self.telegram_enabled = False
        self.email_enabled = False
        self.sms_enabled = False

        log_system("Alert System initialized")

    def send_alert(self, level: str, title: str, message: str):
        """
        Send alert through all enabled channels.

        Args:
            level: Alert level (INFO, WARNING, ERROR, CRITICAL)
            title: Alert title
            message: Alert message
        """
        # Console alert (always)
        self._console_alert(level, title, message)

        # Other channels if enabled
        if self.telegram_enabled:
            self._telegram_alert(level, title, message)

        if self.email_enabled:
            self._email_alert(level, title, message)

        if self.sms_enabled:
            self._sms_alert(level, title, message)

    def _console_alert(self, level: str, title: str, message: str):
        """Print alert to console."""
        icon = {
            'INFO': 'ℹ️ ',
            'WARNING': '⚠️ ',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }.get(level, 'ℹ️ ')

        print(f"\n{icon} {level}: {title}")
        print(f"   {message}\n")

    def _telegram_alert(self, level: str, title: str, message: str):
        """Send Telegram alert."""
        # TODO: Implement Telegram bot integration
        self.logger.debug(f"Telegram alert: {title}")

    def _email_alert(self, level: str, title: str, message: str):
        """Send email alert."""
        # TODO: Implement email sending
        self.logger.debug(f"Email alert: {title}")

    def _sms_alert(self, level: str, title: str, message: str):
        """Send SMS alert."""
        # TODO: Implement SMS integration
        self.logger.debug(f"SMS alert: {title}")
