"""
PERFORMANCE METRICS
Professional trading metrics used by prop firms

Metrics Calculated:
- Win Rate
- Average Win/Loss
- Expectancy
- Profit Factor
- Sharpe Ratio
- Max Drawdown
- Recovery Factor
- Average Hold Time
"""

import numpy as np
import pandas as pd
from typing import List
from datetime import datetime, timedelta


class PerformanceMetrics:
    """Calculate professional trading performance metrics."""

    def __init__(self, closed_trades: List, equity_curve: List, initial_capital: float):
        self.trades = closed_trades
        self.equity_curve = equity_curve
        self.initial_capital = initial_capital

    def calculate_all(self) -> dict:
        """Calculate all performance metrics."""
        if not self.trades:
            return self._empty_metrics()

        metrics = {
            # Basic metrics
            'total_trades': len(self.trades),
            'winning_trades': sum(1 for t in self.trades if t.pnl > 0),
            'losing_trades': sum(1 for t in self.trades if t.pnl < 0),

            # Win rate
            'win_rate': self._calculate_win_rate(),

            # P&L metrics
            'total_pnl': sum(t.pnl for t in self.trades),
            'total_pnl_percent': self._calculate_total_return(),
            'avg_win': self._calculate_avg_win(),
            'avg_loss': self._calculate_avg_loss(),
            'largest_win': max((t.pnl for t in self.trades), default=0),
            'largest_loss': min((t.pnl for t in self.trades), default=0),

            # Key metrics
            'expectancy': self._calculate_expectancy(),
            'profit_factor': self._calculate_profit_factor(),
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'max_drawdown': self._calculate_max_drawdown(),
            'max_drawdown_percent': self._calculate_max_drawdown_percent(),
            'recovery_factor': self._calculate_recovery_factor(),

            # Streak analysis
            'max_win_streak': self._calculate_max_streak(wins=True),
            'max_loss_streak': self._calculate_max_streak(wins=False),
            'current_streak': self._calculate_current_streak(),

            # Time metrics
            'avg_hold_time_hours': self._calculate_avg_hold_time(),
            'avg_trades_per_day': self._calculate_trades_per_day(),

            # Risk metrics
            'risk_adjusted_return': self._calculate_risk_adjusted_return(),

            # Final capital
            'final_capital': self.initial_capital + sum(t.pnl for t in self.trades),
        }

        return metrics

    def _empty_metrics(self):
        """Return empty metrics when no trades."""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'total_pnl_percent': 0,
            'expectancy': 0,
            'profit_factor': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'final_capital': self.initial_capital
        }

    def _calculate_win_rate(self) -> float:
        """Calculate win rate percentage."""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl > 0)
        return (wins / len(self.trades)) * 100

    def _calculate_total_return(self) -> float:
        """Calculate total return percentage."""
        total_pnl = sum(t.pnl for t in self.trades)
        return (total_pnl / self.initial_capital) * 100

    def _calculate_avg_win(self) -> float:
        """Calculate average winning trade."""
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        return np.mean(wins) if wins else 0

    def _calculate_avg_loss(self) -> float:
        """Calculate average losing trade (absolute value)."""
        losses = [abs(t.pnl) for t in self.trades if t.pnl < 0]
        return np.mean(losses) if losses else 0

    def _calculate_expectancy(self) -> float:
        """
        Calculate expectancy - average amount expected per trade.

        Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)

        Positive = profitable strategy
        Negative = losing strategy
        """
        if not self.trades:
            return 0

        win_rate = self._calculate_win_rate() / 100
        avg_win = self._calculate_avg_win()
        avg_loss = self._calculate_avg_loss()

        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        return expectancy

    def _calculate_profit_factor(self) -> float:
        """
        Calculate profit factor - gross profit / gross loss.

        > 2.0 = Excellent
        > 1.5 = Good
        > 1.0 = Profitable
        < 1.0 = Losing
        """
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0

        return gross_profit / gross_loss

    def _calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio - risk-adjusted returns.

        > 3.0 = Excellent
        > 2.0 = Very Good
        > 1.0 = Good
        < 1.0 = Sub-optimal

        Assumes risk-free rate = 0 for simplicity
        """
        if len(self.trades) < 2:
            return 0

        returns = [t.pnl / self.initial_capital for t in self.trades]
        avg_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0

        # Annualized (assuming 252 trading days)
        sharpe = (avg_return / std_return) * np.sqrt(252)
        return sharpe

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown in absolute terms."""
        if not self.equity_curve:
            return 0

        peak = self.equity_curve[0]
        max_dd = 0

        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_max_drawdown_percent(self) -> float:
        """Calculate maximum drawdown as percentage."""
        if not self.equity_curve:
            return 0

        peak = self.equity_curve[0]
        max_dd_pct = 0

        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            if peak > 0:
                dd_pct = ((peak - equity) / peak) * 100
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

        return max_dd_pct

    def _calculate_recovery_factor(self) -> float:
        """
        Calculate recovery factor - net profit / max drawdown.

        Measures how well the strategy recovers from drawdowns.
        Higher is better.
        """
        max_dd = self._calculate_max_drawdown()
        if max_dd == 0:
            return float('inf')

        net_profit = sum(t.pnl for t in self.trades)
        return net_profit / max_dd

    def _calculate_max_streak(self, wins: bool) -> int:
        """Calculate maximum winning or losing streak."""
        if not self.trades:
            return 0

        max_streak = 0
        current_streak = 0

        for trade in self.trades:
            is_win = trade.pnl > 0
            if is_win == wins:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def _calculate_current_streak(self) -> int:
        """Calculate current win/loss streak."""
        if not self.trades:
            return 0

        streak = 0
        last_win = self.trades[-1].pnl > 0

        for trade in reversed(self.trades):
            is_win = trade.pnl > 0
            if is_win == last_win:
                streak += 1
            else:
                break

        return streak if last_win else -streak

    def _calculate_avg_hold_time(self) -> float:
        """Calculate average hold time in hours."""
        if not self.trades:
            return 0

        hold_times = []
        for trade in self.trades:
            if trade.exit_time and trade.entry_time:
                delta = trade.exit_time - trade.entry_time
                hold_times.append(delta.total_seconds() / 3600)  # Convert to hours

        return np.mean(hold_times) if hold_times else 0

    def _calculate_trades_per_day(self) -> float:
        """Calculate average number of trades per day."""
        if not self.trades:
            return 0

        first_trade = self.trades[0].entry_time
        last_trade = self.trades[-1].entry_time
        days = (last_trade - first_trade).days + 1

        return len(self.trades) / max(days, 1)

    def _calculate_risk_adjusted_return(self) -> float:
        """Calculate risk-adjusted return (return / max drawdown)."""
        total_return = self._calculate_total_return()
        max_dd = self._calculate_max_drawdown_percent()

        if max_dd == 0:
            return float('inf') if total_return > 0 else 0

        return total_return / max_dd

    def print_summary(self):
        """Print formatted performance summary."""
        metrics = self.calculate_all()

        print("\n" + "=" * 80)
        print("BACKTEST PERFORMANCE SUMMARY")
        print("=" * 80)

        print(f"\n{'TRADING STATISTICS':-^80}")
        print(f"Total Trades:        {metrics['total_trades']:>10}")
        print(f"Winning Trades:      {metrics['winning_trades']:>10} ({metrics['win_rate']:>6.2f}%)")
        print(f"Losing Trades:       {metrics['losing_trades']:>10}")

        print(f"\n{'PROFIT & LOSS':-^80}")
        print(f"Total P&L:           ₹{metrics['total_pnl']:>10,.0f} ({metrics['total_pnl_percent']:>+6.2f}%)")
        print(f"Average Win:         ₹{metrics['avg_win']:>10,.0f}")
        print(f"Average Loss:        ₹{metrics['avg_loss']:>10,.0f}")
        print(f"Largest Win:         ₹{metrics['largest_win']:>10,.0f}")
        print(f"Largest Loss:        ₹{metrics['largest_loss']:>10,.0f}")

        print(f"\n{'KEY METRICS':-^80}")
        print(f"Expectancy:          ₹{metrics['expectancy']:>10,.2f} per trade")
        print(f"Profit Factor:       {metrics['profit_factor']:>10.2f}")
        print(f"Sharpe Ratio:        {metrics['sharpe_ratio']:>10.2f}")

        print(f"\n{'RISK METRICS':-^80}")
        print(f"Max Drawdown:        ₹{metrics['max_drawdown']:>10,.0f} ({metrics['max_drawdown_percent']:>6.2f}%)")
        print(f"Recovery Factor:     {metrics['recovery_factor']:>10.2f}")

        print(f"\n{'CAPITAL':-^80}")
        print(f"Starting Capital:    ₹{self.initial_capital:>10,.0f}")
        print(f"Final Capital:       ₹{metrics['final_capital']:>10,.0f}")
        print(f"Return:              {metrics['total_pnl_percent']:>10.2f}%")

        print("\n" + "=" * 80)

        # Rating
        rating = self._get_strategy_rating(metrics)
        print(f"\nSTRATEGY RATING: {rating}")
        print("=" * 80 + "\n")

    def _get_strategy_rating(self, metrics: dict) -> str:
        """Rate the strategy based on metrics."""
        score = 0

        # Win rate (20 points)
        if metrics['win_rate'] >= 50:
            score += 20
        elif metrics['win_rate'] >= 40:
            score += 10

        # Profit factor (25 points)
        if metrics['profit_factor'] >= 2.0:
            score += 25
        elif metrics['profit_factor'] >= 1.5:
            score += 15
        elif metrics['profit_factor'] >= 1.0:
            score += 5

        # Sharpe ratio (25 points)
        if metrics['sharpe_ratio'] >= 2.0:
            score += 25
        elif metrics['sharpe_ratio'] >= 1.0:
            score += 15
        elif metrics['sharpe_ratio'] >= 0.5:
            score += 5

        # Expectancy (20 points)
        if metrics['expectancy'] > 1000:
            score += 20
        elif metrics['expectancy'] > 500:
            score += 10
        elif metrics['expectancy'] > 0:
            score += 5

        # Max drawdown (10 points)
        if metrics['max_drawdown_percent'] < 10:
            score += 10
        elif metrics['max_drawdown_percent'] < 20:
            score += 5

        # Rating
        if score >= 80:
            return "⭐⭐⭐⭐⭐ EXCELLENT - Ready for live trading"
        elif score >= 60:
            return "⭐⭐⭐⭐ GOOD - Consider live with small capital"
        elif score >= 40:
            return "⭐⭐⭐ ACCEPTABLE - Needs optimization"
        elif score >= 20:
            return "⭐⭐ POOR - Significant improvements needed"
        else:
            return "⭐ UNACCEPTABLE - Do not trade live"
