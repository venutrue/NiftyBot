##############################################
# LIVE TRADING CONFIGURATION
# Start here before going live
##############################################

"""
LIVE TRADING SAFETY CHECKLIST:
==============================

BEFORE YOU START:
☐ Test in paper trading mode for 2-4 weeks
☐ Verify win rate > 40%
☐ Verify Sharpe ratio > 1.0
☐ Verify max drawdown < 30%
☐ Have sufficient capital (min ₹50,000)
☐ Read and understand LIVE_TRADING_GUIDE.md
☐ Set up alerts (Telegram/Email)
☐ Review risk limits below

FIRST WEEK LIVE:
☐ Start with 10% of capital
☐ Max 1 trade per day
☐ Monitor every trade manually
☐ Keep stop losses tight

SCALING UP:
☐ Only scale if profitable for 2+ weeks
☐ Increase capital by 20% each week (max)
☐ Never risk more than 2% per trade
"""

from executor.risk_manager import RiskLimits

##############################################
# TRADING MODE
##############################################

# CRITICAL: Set this to False for paper trading!
# Set to True only when ready for live trading
LIVE_TRADING_ENABLED = False

# Paper trading mode (simulates orders)
PAPER_TRADING_ENABLED = True

# Confirmation required before each trade
REQUIRE_MANUAL_CONFIRMATION = True  # Set to True for first week

##############################################
# RISK LIMITS (START CONSERVATIVE!)
##############################################

LIVE_RISK_LIMITS = RiskLimits(
    # Daily limits (START SMALL!)
    max_loss_per_day=5000,          # ₹5K max daily loss (increase after proven success)
    max_profit_per_day=15000,       # ₹15K take profit and stop for day (optional)
    max_trades_per_day=3,           # Max 3 trades per day (quality over quantity)
    max_consecutive_losses=2,       # Stop after 2 losses in a row

    # Per-trade limits
    max_position_size=30000,        # ₹30K max per trade (start small!)
    min_position_size=10000,        # ₹10K minimum
    max_stop_loss_percent=20,       # Never risk more than 20%

    # Capital limits
    max_capital_deployed=50000,     # Max ₹50K deployed at once (25% of 2L capital)
    max_capital_per_bot=50000,      # ₹50K per bot

    # Position limits
    max_open_positions=2,           # Max 2 positions at a time
    max_positions_per_symbol=1,     # One position per symbol

    # Weekly limits
    max_loss_per_week=15000,        # ₹15K max weekly loss

    # Order limits
    max_order_value=50000,          # ₹50K max single order
    max_quantity_multiplier=3.0,    # Max 3x normal position size

    # Cool-off periods
    no_trading_after_loss_minutes=60  # 1 hour cool-off after stop loss
)

##############################################
# AGGRESSIVE LIMITS (AFTER 1 MONTH SUCCESS)
##############################################

# Use these only after:
# - 1 month profitable trading
# - Win rate > 50%
# - Sharpe > 1.5
# - Max drawdown < 15%

AGGRESSIVE_RISK_LIMITS = RiskLimits(
    max_loss_per_day=15000,
    max_profit_per_day=None,  # No daily profit cap
    max_trades_per_day=6,
    max_consecutive_losses=3,

    max_position_size=75000,
    min_position_size=20000,
    max_stop_loss_percent=20,

    max_capital_deployed=150000,  # 75% of 2L capital
    max_capital_per_bot=100000,

    max_open_positions=3,
    max_positions_per_symbol=1,

    max_loss_per_week=40000,

    max_order_value=100000,
    max_quantity_multiplier=5.0,

    no_trading_after_loss_minutes=30
)

##############################################
# BOT CONFIGURATION
##############################################

# Which bots to run
BOTS_ENABLED = {
    'NIFTYBOT': True,
    'BANKNIFTYBOT': False  # Start with one bot only
}

# Bot-specific limits
BOT_LIMITS = {
    'NIFTYBOT': {
        'max_trades_per_day': 2,
        'max_capital': 50000
    },
    'BANKNIFTYBOT': {
        'max_trades_per_day': 2,
        'max_capital': 50000
    }
}

##############################################
# ALERT CONFIGURATION
##############################################

# Telegram alerts (optional)
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = ""  # Get from @BotFather
TELEGRAM_CHAT_ID = ""    # Your chat ID

# Email alerts (optional)
EMAIL_ALERTS_ENABLED = False
EMAIL_TO = ""
EMAIL_FROM = ""
SMTP_SERVER = ""
SMTP_PORT = 587
SMTP_PASSWORD = ""

# What to alert on
ALERT_ON = {
    'trade_entry': True,
    'trade_exit': True,
    'stop_loss': True,
    'target_hit': True,
    'daily_loss_limit': True,
    'circuit_breaker': True,
    'kill_switch': True,
    'error': True
}

##############################################
# MONITORING CONFIGURATION
##############################################

# Real-time monitoring
MONITOR_INTERVAL_SECONDS = 30  # Check positions every 30 seconds

# Position monitoring
CHECK_STOP_LOSS = True
CHECK_TARGET = True
CHECK_TRAILING_STOP = True

# Performance tracking
TRACK_SHARPE_RATIO = True
TRACK_DRAWDOWN = True
TRACK_WIN_RATE = True

# Log everything
VERBOSE_LOGGING = True
LOG_TO_FILE = True
LOG_TO_CONSOLE = True

##############################################
# MARKET HOURS OVERRIDE
##############################################

# Trading window (more restrictive than market hours)
LIVE_TRADING_START_HOUR = 9
LIVE_TRADING_START_MINUTE = 45  # Skip first 30 min volatility

LIVE_TRADING_END_HOUR = 15
LIVE_TRADING_END_MINUTE = 0     # Exit early before close

# No trading on these days (0=Monday, 4=Friday)
NO_TRADING_DAYS = []  # e.g., [4] for no Friday trading

##############################################
# SAFETY OVERRIDES
##############################################

# Maximum slippage tolerance
MAX_SLIPPAGE_PERCENT = 2.0  # Reject orders with >2% slippage

# Minimum option premium
MIN_OPTION_PREMIUM = 50  # Don't buy options < ₹50 (too volatile)

# Maximum option premium
MAX_OPTION_PREMIUM = 300  # Don't buy options > ₹300 (too expensive)

# Minimum volume requirement
MIN_OPTION_VOLUME = 100  # Minimum 100 lots traded (liquidity check)

# Maximum bid-ask spread
MAX_BID_ASK_SPREAD_PERCENT = 3.0  # Reject if spread > 3%

##############################################
# EMERGENCY CONTACTS
##############################################

EMERGENCY_CONTACTS = {
    'primary': '+91-XXXXXXXXXX',
    'backup': '+91-XXXXXXXXXX'
}

# Kill switch phone number (SMS)
KILL_SWITCH_PHONE = '+91-XXXXXXXXXX'

##############################################
# HELPER FUNCTIONS
##############################################

def get_current_limits():
    """Get currently active risk limits."""
    return LIVE_RISK_LIMITS

def is_trading_allowed():
    """Check if trading is allowed based on config."""
    import datetime

    # Check if live trading enabled
    if not LIVE_TRADING_ENABLED and not PAPER_TRADING_ENABLED:
        return False, "Trading disabled in config"

    # Check market hours
    now = datetime.datetime.now()
    current_time = now.time()

    start_time = datetime.time(LIVE_TRADING_START_HOUR, LIVE_TRADING_START_MINUTE)
    end_time = datetime.time(LIVE_TRADING_END_HOUR, LIVE_TRADING_END_MINUTE)

    if not (start_time <= current_time <= end_time):
        return False, f"Outside trading hours ({start_time}-{end_time})"

    # Check day of week
    if now.weekday() in NO_TRADING_DAYS:
        return False, f"No trading on {now.strftime('%A')}"

    return True, "Trading allowed"

def print_config_summary():
    """Print current configuration summary."""
    print("\n" + "=" * 60)
    print("LIVE TRADING CONFIGURATION")
    print("=" * 60)
    print(f"\nMode: {'🔴 LIVE' if LIVE_TRADING_ENABLED else '📄 PAPER'} TRADING")
    print(f"Confirmation Required: {'✅ Yes' if REQUIRE_MANUAL_CONFIRMATION else '❌ No'}")
    print(f"\nRisk Limits:")
    print(f"  Max Daily Loss: ₹{LIVE_RISK_LIMITS.max_loss_per_day:,}")
    print(f"  Max Trades/Day: {LIVE_RISK_LIMITS.max_trades_per_day}")
    print(f"  Max Position Size: ₹{LIVE_RISK_LIMITS.max_position_size:,}")
    print(f"  Max Capital Deployed: ₹{LIVE_RISK_LIMITS.max_capital_deployed:,}")
    print(f"\nBots Enabled:")
    for bot, enabled in BOTS_ENABLED.items():
        print(f"  {bot}: {'✅ Yes' if enabled else '❌ No'}")
    print(f"\nAlerts:")
    print(f"  Telegram: {'✅ Yes' if TELEGRAM_ENABLED else '❌ No'}")
    print(f"  Email: {'✅ Yes' if EMAIL_ALERTS_ENABLED else '❌ No'}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    print_config_summary()
