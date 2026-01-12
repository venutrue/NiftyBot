##############################################
# PERFORMANCE METRICS TRACKER
# Tracks trading performance with outlier detection
# Provides realistic expectations vs actual results
##############################################

import datetime
import json
import os
import statistics
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple
from collections import deque

from common.config import (
    OUTLIER_WIN_THRESHOLD, OUTLIER_LOSS_THRESHOLD,
    PROFIT_TARGET_PERCENT
)
from common.logger import setup_logger


@dataclass
class TradeMetric:
    """Metrics for a single trade."""
    timestamp: datetime.datetime
    symbol: str
    pnl: float
    pnl_percent: float
    is_outlier: bool = False
    outlier_reason: str = ""

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'is_outlier': self.is_outlier,
            'outlier_reason': self.outlier_reason
        }


@dataclass
class DailyMetrics:
    """Aggregated metrics for a trading day."""
    date: str
    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    total_pnl: float = 0.0
    normalized_pnl: float = 0.0  # Excluding outliers
    outlier_count: int = 0
    outlier_pnl: float = 0.0  # P&L from outliers only
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0

    def to_dict(self):
        return asdict(self)


class PerformanceTracker:
    """
    Tracks trading performance with outlier detection and normalization.

    Key Features:
    1. Outlier Detection - Identifies unusually large wins/losses
    2. Normalized Returns - Shows performance excluding outliers
    3. Rolling Statistics - 7-day, 30-day moving averages
    4. Realistic Expectations - Compares actual vs expected returns
    5. Performance Alerts - Warns of unsustainable patterns
    """

    def __init__(self, data_dir: str = "data/metrics"):
        """
        Initialize performance tracker.

        Args:
            data_dir: Directory for storing metrics data
        """
        self.logger = setup_logger("METRICS")
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Current day tracking
        self.today = datetime.date.today().isoformat()
        self.trades_today: List[TradeMetric] = []

        # Historical data (last 90 days)
        self.daily_history: deque = deque(maxlen=90)

        # Outlier thresholds
        self.outlier_win_threshold = OUTLIER_WIN_THRESHOLD
        self.outlier_loss_threshold = OUTLIER_LOSS_THRESHOLD

        # Running totals
        self.all_time_pnl = 0.0
        self.all_time_trades = 0
        self.all_time_outliers = 0

        # Load historical data
        self._load_history()

    def record_trade(self, symbol: str, pnl: float, pnl_percent: float) -> TradeMetric:
        """
        Record a completed trade and check for outliers.

        Args:
            symbol: Trading symbol
            pnl: Profit/loss in rupees
            pnl_percent: Profit/loss percentage

        Returns:
            TradeMetric with outlier detection
        """
        # Check if this is an outlier
        is_outlier = False
        outlier_reason = ""

        if pnl_percent > self.outlier_win_threshold:
            is_outlier = True
            outlier_reason = f"Exceptional win: {pnl_percent:.1f}% > {self.outlier_win_threshold}% threshold"
            self.logger.warning(f"🎯 OUTLIER DETECTED: {symbol} +{pnl_percent:.1f}% (₹{pnl:,.0f})")

        elif pnl_percent < self.outlier_loss_threshold:
            is_outlier = True
            outlier_reason = f"Large loss: {pnl_percent:.1f}% < {self.outlier_loss_threshold}% threshold"
            self.logger.warning(f"⚠️ OUTLIER LOSS: {symbol} {pnl_percent:.1f}% (₹{pnl:,.0f})")

        trade = TradeMetric(
            timestamp=datetime.datetime.now(),
            symbol=symbol,
            pnl=pnl,
            pnl_percent=pnl_percent,
            is_outlier=is_outlier,
            outlier_reason=outlier_reason
        )

        self.trades_today.append(trade)
        self.all_time_pnl += pnl
        self.all_time_trades += 1
        if is_outlier:
            self.all_time_outliers += 1

        return trade

    def get_daily_metrics(self) -> DailyMetrics:
        """
        Calculate today's metrics with normalized returns.

        Returns:
            DailyMetrics including outlier-adjusted figures
        """
        if not self.trades_today:
            return DailyMetrics(date=self.today)

        trades = self.trades_today
        total_pnl = sum(t.pnl for t in trades)

        # Separate outliers
        normal_trades = [t for t in trades if not t.is_outlier]
        outlier_trades = [t for t in trades if t.is_outlier]

        normalized_pnl = sum(t.pnl for t in normal_trades)
        outlier_pnl = sum(t.pnl for t in outlier_trades)

        # Win/loss stats
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]

        win_rate = (len(winners) / len(trades) * 100) if trades else 0
        avg_win = statistics.mean([t.pnl for t in winners]) if winners else 0
        avg_loss = statistics.mean([t.pnl for t in losers]) if losers else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winners)
        gross_loss = abs(sum(t.pnl for t in losers))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Best/worst trades
        pnl_percents = [t.pnl_percent for t in trades]
        best_trade = max(pnl_percents) if pnl_percents else 0
        worst_trade = min(pnl_percents) if pnl_percents else 0

        return DailyMetrics(
            date=self.today,
            total_trades=len(trades),
            winners=len(winners),
            losers=len(losers),
            total_pnl=total_pnl,
            normalized_pnl=normalized_pnl,
            outlier_count=len(outlier_trades),
            outlier_pnl=outlier_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            best_trade=best_trade,
            worst_trade=worst_trade
        )

    def get_rolling_stats(self, days: int = 7) -> Dict:
        """
        Calculate rolling statistics over recent days.

        Args:
            days: Number of days to include

        Returns:
            Dictionary with rolling metrics
        """
        recent = list(self.daily_history)[-days:] if self.daily_history else []

        if not recent:
            return {
                'period_days': days,
                'trading_days': 0,
                'avg_daily_pnl': 0,
                'avg_normalized_pnl': 0,
                'total_pnl': 0,
                'avg_trades_per_day': 0,
                'avg_win_rate': 0,
                'outlier_contribution': 0
            }

        trading_days = len(recent)
        total_pnl = sum(d.get('total_pnl', 0) for d in recent)
        total_normalized = sum(d.get('normalized_pnl', 0) for d in recent)
        total_outlier = sum(d.get('outlier_pnl', 0) for d in recent)
        total_trades = sum(d.get('total_trades', 0) for d in recent)
        win_rates = [d.get('win_rate', 0) for d in recent if d.get('total_trades', 0) > 0]

        outlier_contribution = (total_outlier / total_pnl * 100) if total_pnl != 0 else 0

        return {
            'period_days': days,
            'trading_days': trading_days,
            'avg_daily_pnl': total_pnl / trading_days if trading_days > 0 else 0,
            'avg_normalized_pnl': total_normalized / trading_days if trading_days > 0 else 0,
            'total_pnl': total_pnl,
            'avg_trades_per_day': total_trades / trading_days if trading_days > 0 else 0,
            'avg_win_rate': statistics.mean(win_rates) if win_rates else 0,
            'outlier_contribution': outlier_contribution
        }

    def get_performance_alerts(self) -> List[str]:
        """
        Generate alerts for unsustainable patterns.

        Returns:
            List of warning messages
        """
        alerts = []
        metrics = self.get_daily_metrics()
        rolling_7 = self.get_rolling_stats(7)

        # Alert: High outlier contribution
        if metrics.outlier_pnl != 0 and metrics.total_pnl != 0:
            outlier_pct = abs(metrics.outlier_pnl / metrics.total_pnl * 100)
            if outlier_pct > 50:
                alerts.append(
                    f"⚠️ {outlier_pct:.0f}% of today's P&L came from outlier trades. "
                    f"Normalized P&L: ₹{metrics.normalized_pnl:,.0f} vs Actual: ₹{metrics.total_pnl:,.0f}"
                )

        # Alert: Unsustainable win rate
        if metrics.win_rate > 75 and metrics.total_trades >= 5:
            alerts.append(
                f"⚠️ Win rate of {metrics.win_rate:.0f}% is unsustainably high. "
                f"Expect mean reversion to 45-55%."
            )

        # Alert: Very high profit factor
        if metrics.profit_factor > 4 and metrics.total_trades >= 5:
            alerts.append(
                f"⚠️ Profit factor of {metrics.profit_factor:.1f} is exceptional. "
                f"Realistic target is 1.5-2.5."
            )

        # Alert: Single trade dominance
        if metrics.total_trades > 1 and metrics.best_trade > 0:
            best_contribution = 0
            if metrics.total_pnl > 0:
                # Find best trade's actual P&L
                best_trade = max(self.trades_today, key=lambda t: t.pnl)
                best_contribution = (best_trade.pnl / metrics.total_pnl * 100)
                if best_contribution > 60:
                    alerts.append(
                        f"⚠️ Single trade contributed {best_contribution:.0f}% of daily profits. "
                        f"Don't expect this daily."
                    )

        return alerts

    def print_daily_report(self):
        """Print comprehensive daily performance report."""
        metrics = self.get_daily_metrics()
        alerts = self.get_performance_alerts()
        rolling_7 = self.get_rolling_stats(7)

        print("\n" + "=" * 70)
        print("📊 PERFORMANCE METRICS REPORT")
        print("=" * 70)

        print(f"\n📅 DATE: {self.today}")
        print(f"\n💰 P&L BREAKDOWN:")
        print(f"   Actual P&L:     ₹{metrics.total_pnl:>10,.0f}")
        print(f"   Normalized P&L: ₹{metrics.normalized_pnl:>10,.0f}  (excluding {metrics.outlier_count} outliers)")
        print(f"   Outlier P&L:    ₹{metrics.outlier_pnl:>10,.0f}")

        print(f"\n📈 TRADE STATS:")
        print(f"   Total Trades:   {metrics.total_trades}")
        print(f"   Winners:        {metrics.winners} ({metrics.win_rate:.1f}%)")
        print(f"   Losers:         {metrics.losers}")
        print(f"   Avg Win:        ₹{metrics.avg_win:,.0f}")
        print(f"   Avg Loss:       ₹{metrics.avg_loss:,.0f}")
        print(f"   Profit Factor:  {metrics.profit_factor:.2f}")

        print(f"\n📊 7-DAY ROLLING AVERAGE:")
        print(f"   Trading Days:   {rolling_7['trading_days']}")
        print(f"   Avg Daily P&L:  ₹{rolling_7['avg_daily_pnl']:,.0f}")
        print(f"   Avg Normalized: ₹{rolling_7['avg_normalized_pnl']:,.0f}")
        print(f"   Outlier Impact: {rolling_7['outlier_contribution']:.1f}%")

        if alerts:
            print(f"\n🚨 PERFORMANCE ALERTS:")
            for alert in alerts:
                print(f"   {alert}")

        print("\n" + "=" * 70)

        # Realistic expectations
        print("\n📋 REALISTIC EXPECTATIONS (based on system design):")
        print("   Daily Return:   1-3% (not 19%)")
        print("   Win Rate:       45-55%")
        print("   Profit Factor:  1.5-2.5")
        print("   Outlier Freq:   1-2 per week")
        print("=" * 70 + "\n")

    def end_of_day(self):
        """Save daily metrics and reset for next day."""
        if self.trades_today:
            metrics = self.get_daily_metrics()
            self.daily_history.append(metrics.to_dict())
            self._save_history()

        # Print report
        self.print_daily_report()

        # Reset for next day
        self.trades_today = []
        self.today = datetime.date.today().isoformat()

    def _save_history(self):
        """Save historical metrics to file."""
        history_file = os.path.join(self.data_dir, "performance_history.json")
        try:
            data = {
                'last_updated': datetime.datetime.now().isoformat(),
                'all_time_pnl': self.all_time_pnl,
                'all_time_trades': self.all_time_trades,
                'all_time_outliers': self.all_time_outliers,
                'daily_history': list(self.daily_history)
            }
            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save metrics history: {e}")

    def _load_history(self):
        """Load historical metrics from file."""
        history_file = os.path.join(self.data_dir, "performance_history.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                self.all_time_pnl = data.get('all_time_pnl', 0)
                self.all_time_trades = data.get('all_time_trades', 0)
                self.all_time_outliers = data.get('all_time_outliers', 0)
                self.daily_history = deque(data.get('daily_history', []), maxlen=90)
                self.logger.info(f"Loaded {len(self.daily_history)} days of performance history")
            except Exception as e:
                self.logger.error(f"Failed to load metrics history: {e}")


# Singleton instance
_tracker: Optional[PerformanceTracker] = None


def get_tracker() -> PerformanceTracker:
    """Get or create the performance tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker
