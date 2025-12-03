#!/usr/bin/env python3
##############################################
# RUN.PY - MAIN ENTRY POINT
# Start all trading bots with a single command
##############################################

import argparse
import datetime
import time
import signal
import sys

from common.config import (
    MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
    validate_credentials
)
from common.logger import (
    log_system, log_user_action, log_daily_summary,
    setup_logger
)
from executor.trade_executor import TradeExecutor
from executor.paper_executor import PaperTradeExecutor
from bots.niftybot import NiftyBot
from bots.bankniftybot import BankNiftyBot
from bots.stockbot import StockBot
from bots.goldbot import GoldBot

##############################################
# GLOBAL STATE
##############################################

running = True
logger = setup_logger("MAIN")

##############################################
# SIGNAL HANDLERS
##############################################

def handle_shutdown(signum, frame):
    """Handle graceful shutdown."""
    global running
    logger.info("Shutdown signal received...")
    log_user_action("SHUTDOWN", "Graceful shutdown initiated")
    running = False

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

##############################################
# BOT REGISTRY
##############################################

AVAILABLE_BOTS = {
    'nifty': NiftyBot,
    'banknifty': BankNiftyBot,
    'stock': StockBot,
    'gold': GoldBot,
}

##############################################
# MAIN FUNCTIONS
##############################################

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='NiftyBot Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                    # Run all bots
  python run.py --bot nifty        # Run only NiftyBot
  python run.py --bot stock        # Run only StockBot
  python run.py --bot gold         # Run only GoldBot (MCX)
  python run.py --bot nifty,stock  # Run specific bots
  python run.py --paper --bot gold # Paper trade Gold futures
  python run.py --dry-run          # Signals only, no trades
  python run.py --status           # Show system status
        """
    )

    parser.add_argument(
        '--bot',
        type=str,
        default='all',
        help='Bot(s) to run: all, nifty, banknifty, stock, gold, or comma-separated list'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate signals without executing trades'
    )

    parser.add_argument(
        '--paper',
        action='store_true',
        help='Paper trading mode (simulates trades with fake money)'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show system status and exit'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Scan interval in seconds (default: 300)'
    )

    return parser.parse_args()

def get_bots_to_run(bot_arg):
    """Get list of bot classes to instantiate."""
    if bot_arg == 'all':
        return list(AVAILABLE_BOTS.values())

    bot_names = [b.strip().lower() for b in bot_arg.split(',')]
    bots = []

    for name in bot_names:
        if name in AVAILABLE_BOTS:
            bots.append(AVAILABLE_BOTS[name])
        else:
            logger.warning(f"Unknown bot: {name}")

    return bots

def is_market_open(bots=None):
    """
    Check if market is currently open.

    For commodity bots (GoldBot): 9:00 AM - 11:30 PM (MCX hours)
    For equity bots (NiftyBot, etc.): 9:15 AM - 3:30 PM (NSE hours)
    """
    now = datetime.datetime.now()

    # Check if any commodity bots are in the list
    has_commodity_bot = False
    if bots:
        from bots.goldbot import GoldBot
        has_commodity_bot = any(isinstance(bot, GoldBot) for bot in bots)

    if has_commodity_bot:
        # MCX commodity hours: 9:00 AM - 11:30 PM
        market_open = now.replace(hour=9, minute=0, second=0)
        market_close = now.replace(hour=23, minute=30, second=0)
    else:
        # NSE equity hours
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
        market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)

    return market_open <= now <= market_close

def wait_for_market_open(bots=None):
    """
    Wait until market opens.

    Uses appropriate market hours based on bot types.
    """
    # Check if any commodity bots are in the list
    has_commodity_bot = False
    if bots:
        from bots.goldbot import GoldBot
        has_commodity_bot = any(isinstance(bot, GoldBot) for bot in bots)

    while not is_market_open(bots) and running:
        now = datetime.datetime.now()

        if has_commodity_bot:
            market_open = now.replace(hour=9, minute=0, second=0)
            market_type = "MCX"
        else:
            market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
            market_type = "NSE"

        if now < market_open:
            wait_seconds = (market_open - now).total_seconds()
            logger.info(f"{market_type} market opens in {wait_seconds/60:.0f} minutes. Waiting...")
        else:
            logger.info(f"{market_type} market closed for today.")
            return False

        # Sleep for a bit then check again
        time.sleep(60)

    return running

def show_status(executor, bots):
    """Display system status."""
    print("\n" + "=" * 50)
    print("NIFTYBOT TRADING SYSTEM - STATUS")
    print("=" * 50)

    # Connection status
    print(f"\nBroker Connected: {'Yes' if executor.broker.connected else 'No'}")

    # Margins
    margins = executor.get_margins()
    if margins:
        equity = margins.get('equity', {})
        available = equity.get('available', {}).get('live_balance', 0)
        print(f"Available Margin: Rs. {available:,.2f}")

    # Bot status
    print("\nBot Status:")
    print("-" * 40)
    for bot in bots:
        status = bot.get_status()
        print(f"  {status['name']}:")
        for key, value in status.items():
            if key != 'name':
                print(f"    {key}: {value}")

    # Positions
    positions = executor.get_positions()
    if positions:
        net = positions.get('net', [])
        if net:
            print(f"\nOpen Positions: {len(net)}")
            for pos in net[:5]:  # Show first 5
                print(f"  {pos['tradingsymbol']}: {pos['quantity']} @ Rs. {pos['average_price']:.2f}")

    print("\n" + "=" * 50)

def run_trading_loop(executor, bots, dry_run=False, interval=60):
    """Main trading loop."""
    global running

    logger.info("=" * 50)
    logger.info("TRADING SYSTEM STARTED")
    logger.info(f"Active Bots: {', '.join([b.name for b in bots])}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info(f"Scan Interval: {interval} seconds")
    logger.info("=" * 50)

    log_user_action("START", f"Bots: {', '.join([b.name for b in bots])}, Dry Run: {dry_run}")

    # Daily stats
    total_trades = 0
    total_winners = 0
    total_losers = 0
    total_pnl = 0

    while running:
        # Check market hours
        if not is_market_open(bots):
            logger.info("Market closed. Stopping bots.")
            break

        try:
            # Scan each bot for signals
            for bot in bots:
                signals = bot.scan()

                for signal in signals:
                    logger.info(f"Signal from {signal['source']}: {signal['action']} {signal['symbol']}")

                    if dry_run:
                        logger.info("[DRY RUN] Order not executed")
                    else:
                        order_id = executor.execute(signal)

                        if order_id:
                            total_trades += 1

                            # Get actual fill price from order history
                            fill_price = signal.get('entry_price', 0)
                            order_status = executor.get_order_history(order_id)
                            if order_status and order_status.get('average_price'):
                                fill_price = order_status['average_price']

                            # Notify bot of order completion
                            bot.on_order_complete(
                                order_id=order_id,
                                symbol=signal['symbol'],
                                action=signal['action'],
                                quantity=signal['quantity'],
                                price=fill_price,
                                entry_spot=signal.get('entry_spot'),
                                initial_sl=signal.get('initial_sl'),
                                stop_loss=signal.get('stop_loss')
                            )

        except Exception as e:
            logger.error(f"Error in trading loop: {str(e)}")

        # Sleep until next scan
        time.sleep(interval)

    # End of day summary
    log_daily_summary(total_trades, total_winners, total_losers, total_pnl)

    return {
        'trades': total_trades,
        'winners': total_winners,
        'losers': total_losers,
        'pnl': total_pnl
    }

##############################################
# MAIN ENTRY POINT
##############################################

def main():
    """Main entry point."""
    global running

    args = parse_arguments()

    # Validate credentials first
    if not validate_credentials():
        sys.exit(1)

    # Initialize executor (paper or live)
    if args.paper:
        logger.info("=" * 60)
        logger.info("📄 PAPER TRADING MODE - NO REAL MONEY AT RISK")
        logger.info("=" * 60)
        executor = PaperTradeExecutor(initial_capital=200000)
    else:
        if args.dry_run:
            logger.info("DRY RUN MODE - Signals only, no execution")
        else:
            logger.info("🔴 LIVE TRADING MODE - REAL MONEY AT RISK")
        executor = TradeExecutor()

    # Connect to broker
    logger.info("Connecting to broker...")
    if not executor.connect():
        logger.error("Failed to connect to broker. Exiting.")
        sys.exit(1)

    # Get bots to run
    bot_classes = get_bots_to_run(args.bot)
    if not bot_classes:
        logger.error("No valid bots specified. Exiting.")
        sys.exit(1)

    # Initialize bots
    bots = [BotClass(executor) for BotClass in bot_classes]
    logger.info(f"Initialized {len(bots)} bot(s)")

    # Status only mode
    if args.status:
        show_status(executor, bots)
        sys.exit(0)

    # Wait for market open
    if not is_market_open(bots):
        logger.info("Market not open yet...")
        if not wait_for_market_open(bots):
            logger.info("Exiting - market closed for today")
            sys.exit(0)

    # Reset daily state for all bots
    for bot in bots:
        bot.reset_daily_state()

    # Run trading loop
    try:
        summary = run_trading_loop(
            executor=executor,
            bots=bots,
            dry_run=args.dry_run,
            interval=args.interval
        )

        logger.info("Trading session complete")
        logger.info(f"Total Trades: {summary['trades']}")
        logger.info(f"Total P&L: Rs. {summary['pnl']:,.2f}")

        # Print paper trading summary if applicable
        if args.paper and hasattr(executor, 'print_summary'):
            print("\n")
            executor.print_summary()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        log_user_action("INTERRUPT", "User pressed Ctrl+C")

    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        log_user_action("CRASH", str(e))
        raise

    finally:
        log_user_action("STOP", "Trading session ended")

if __name__ == "__main__":
    main()
