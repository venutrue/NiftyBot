"""
Backtesting Framework

Professional-grade backtesting system for options trading strategies.
Implements prop firm-style risk management and performance metrics.
"""

from backtest.backtest_engine import BacktestEngine, BacktestConfig, Trade
from backtest.performance_metrics import PerformanceMetrics

__all__ = ['BacktestEngine', 'BacktestConfig', 'Trade', 'PerformanceMetrics']
