"""
Backtesting Framework

Professional-grade backtesting system for options trading strategies.
Implements prop firm-style risk management and performance metrics.

Features:
- Configurable strategy presets (conservative, balanced, aggressive, etc.)
- Professional risk management (prop firm style)
- 20+ performance metrics (Sharpe, expectancy, profit factor, etc.)
- Equity curve tracking
- Trade-by-trade analysis
"""

from backtest.backtest_engine import BacktestEngine, BacktestConfig, Trade
from backtest.performance_metrics import PerformanceMetrics
from backtest.strategy_config import StrategyConfig, StrategyLibrary

__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'Trade',
    'PerformanceMetrics',
    'StrategyConfig',
    'StrategyLibrary'
]
