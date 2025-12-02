#!/usr/bin/env python3
"""
BACKTESTING RUNNER
Run backtests with professional risk management

Usage:
    python run_backtest.py --bot NIFTYBOT --days 90
    python run_backtest.py --bot BANKNIFTYBOT --days 30
    python run_backtest.py --all  # Test all bots

Examples with custom parameters:
    python run_backtest.py --bot NIFTYBOT --capital 1000000 --risk 0.02
"""

import argparse
import sys
from datetime import datetime, timedelta

from backtest.backtest_engine import BacktestEngine, BacktestConfig
from backtest.performance_metrics import PerformanceMetrics
from bots.niftybot import NiftyBot
from bots.bankniftybot import BankNiftyBot


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Backtest trading strategies with professional risk management'
    )

    parser.add_argument(
        '--bot',
        type=str,
        choices=['NIFTYBOT', 'BANKNIFTYBOT', 'ALL'],
        default='NIFTYBOT',
        help='Bot to backtest (default: NIFTYBOT)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Number of days to backtest (default: 90)'
    )

    parser.add_argument(
        '--capital',
        type=int,
        default=500000,
        help='Initial capital in rupees (default: 500000)'
    )

    parser.add_argument(
        '--risk',
        type=float,
        default=0.01,
        help='Risk per trade as decimal (default: 0.01 = 1%%)'
    )

    parser.add_argument(
        '--stop-loss',
        type=float,
        default=0.20,
        help='Stop loss percentage (default: 0.20 = 20%%)'
    )

    parser.add_argument(
        '--max-positions',
        type=int,
        default=3,
        help='Maximum simultaneous positions (default: 3)'
    )

    return parser.parse_args()


def run_backtest(bot_class, config: BacktestConfig):
    """Run backtest for a specific bot."""
    print(f"\n{'=' * 80}")
    print(f"BACKTESTING: {bot_class.__name__}")
    print(f"{'=' * 80}\n")

    # Create engine
    engine = BacktestEngine(bot_class, config)

    # Run backtest
    results = engine.run()

    if results is None:
        print("❌ Backtest failed")
        return None

    # Calculate and print metrics
    metrics = PerformanceMetrics(
        closed_trades=engine.closed_trades,
        equity_curve=engine.equity_curve,
        initial_capital=config.initial_capital
    )

    metrics.print_summary()

    return results


def main():
    """Main entry point."""
    args = parse_args()

    # Create configuration
    config = BacktestConfig()
    config.initial_capital = args.capital
    config.max_risk_per_trade = args.risk
    config.stop_loss_percent = args.stop_loss
    config.max_positions = args.max_positions
    config.start_date = datetime.now() - timedelta(days=args.days)
    config.end_date = datetime.now()

    print(f"\n{'=' * 80}")
    print("BACKTEST CONFIGURATION")
    print(f"{'=' * 80}")
    print(f"Period: {config.start_date.date()} to {config.end_date.date()} ({args.days} days)")
    print(f"Initial Capital: ₹{config.initial_capital:,.0f}")
    print(f"Risk per Trade: {config.max_risk_per_trade * 100:.1f}%")
    print(f"Stop Loss: {config.stop_loss_percent * 100:.0f}%")
    print(f"Max Positions: {config.max_positions}")
    print(f"{'=' * 80}\n")

    # Run backtests
    if args.bot == 'ALL':
        run_backtest(NiftyBot, config)
        run_backtest(BankNiftyBot, config)
    elif args.bot == 'NIFTYBOT':
        run_backtest(NiftyBot, config)
    elif args.bot == 'BANKNIFTYBOT':
        run_backtest(BankNiftyBot, config)

    print("\n✅ Backtest complete!")
    print("\nNEXT STEPS:")
    print("1. Review the metrics above")
    print("2. If Sharpe > 1.0 and Profit Factor > 1.5 → Good strategy")
    print("3. If metrics are poor → Optimize parameters or strategy")
    print("4. Paper trade for 2-4 weeks before going live")
    print("5. Start with 10% of capital when going live\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Backtest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
