##############################################
# GOLDBOT - GOLD FUTURES TRADING BOT
# Strategy: EMA + Supertrend + ADX Confluence
# Commodity: MCX Gold Mini (100 grams)
##############################################

import datetime
import pandas as pd

from common.config import (
    EXCHANGE_MCX, TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, PRODUCT_MIS,
    # Strategy parameters (reuse from index bot)
    TOTAL_CAPITAL, TRADING_CAPITAL,
    MAX_INVESTMENT_PER_TRADE, MIN_INVESTMENT_PER_TRADE,
    MAX_LOSS_PER_DAY, MAX_CONSECUTIVE_LOSSES,
    SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER,
    ADX_ENTRY_THRESHOLD
)
from common.logger import setup_logger, log_signal, log_system
from common.indicators import (
    atr, adx, ema,
    supertrend, is_supertrend_bullish, is_supertrend_bearish
)

##############################################
# GOLD-SPECIFIC CONSTANTS
##############################################

# Trading symbol (ASSUMPTION: verify this format with Zerodha)
# Gold mini contract (100 grams) - lower margin than standard Gold (1kg)
GOLD_SYMBOL = "GOLDM"  # Will append expiry month

# Contract specifications
GOLD_LOT_SIZE = 100  # 100 grams
GOLD_TICK_SIZE = 1   # Minimum price movement

# Trading hours (MCX commodity hours)
COMMODITY_OPEN_HOUR = 9
COMMODITY_OPEN_MINUTE = 0
COMMODITY_CLOSE_HOUR = 23  # 11 PM
COMMODITY_CLOSE_MINUTE = 30

# Strategy parameters (adapted for Gold futures)
GOLD_TIMEFRAME = "15minute"  # 15-min candles (smoother than 5-min)
GOLD_EMA_PERIOD = 20  # Replace VWAP with 20 EMA
GOLD_STOP_LOSS_POINTS = 250  # ₹250 SL per contract (~0.4% of ₹65,000)
GOLD_TRAILING_STOP_POINTS = 150  # ₹150 trailing stop
GOLD_MAX_TRADES_PER_DAY = 2  # Conservative for futures

# Risk limits (adjusted for futures margin)
GOLD_MAX_POSITION_VALUE = 40000  # Max ₹40k per trade (covers margin + buffer)

##############################################
# GOLDBOT CLASS
##############################################

class GoldBot:
    """
    Gold Futures Trading Bot - MCX Gold Mini.

    Entry Strategy (ALL must be true):
    - Price > 20 EMA (trend confirmation)
    - Supertrend bullish (BUY) or bearish (SELL)
    - ADX > 23 (confirming trend strength)

    Exit Strategy:
    - Initial SL: ₹250 from entry
    - Trailing: ₹150 from highest price seen
    - Supertrend flip: exit immediately
    - Hard exit at 11:00 PM (before market close)

    Key Differences from Options Bot:
    - Futures (not options): no theta decay, simpler P&L
    - No VWAP: use 20 EMA instead
    - 15-min timeframe: smoother trends
    - Absolute stop loss: ₹250, not percentage
    - Single contract: no CE/PE selection needed
    """

    def __init__(self, executor):
        """Initialize GoldBot."""
        self.name = "GOLDBOT"
        self.executor = executor
        self.logger = setup_logger(self.name)

        # State tracking
        self.trade_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.active_positions = {}  # {symbol: {entry, sl, qty, ...}}

        # Position tracking
        self.max_price_seen = {}  # Track highest price for trailing

        # Instrument cache
        self._mcx_instruments = None
        self._instruments_loaded = False
        self._current_contract_symbol = None
        self._instrument_token = None  # Token for current contract

        self.logger.info(f"{self.name} initialized for MCX Gold Mini futures")

    def reset_daily_state(self):
        """Reset state at start of new trading day."""
        self.trade_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.active_positions = {}
        self.max_price_seen = {}
        # Refresh instruments daily (contract month might change)
        self._mcx_instruments = None
        self._instruments_loaded = False
        self._current_contract_symbol = None
        self._instrument_token = None
        self.logger.info("Daily state reset")

    def _load_mcx_instruments(self):
        """Load MCX instruments list (cached for the day)."""
        if self._instruments_loaded:
            return self._mcx_instruments

        try:
            self._mcx_instruments = self.executor.get_instruments(EXCHANGE_MCX)
            self._instruments_loaded = True
            self.logger.info(f"Loaded {len(self._mcx_instruments)} MCX instruments")
            return self._mcx_instruments
        except Exception as e:
            self.logger.error(f"Failed to load MCX instruments: {str(e)}")
            return None

    def _get_current_month_symbol(self):
        """
        Get current month Gold futures symbol by querying MCX instruments.

        NO ASSUMPTIONS: Queries actual instrument list from exchange,
        finds Gold Mini contract with nearest expiry.

        Returns current month contract symbol or None if not found.
        """
        if self._current_contract_symbol:
            return self._current_contract_symbol

        try:
            # Load MCX instruments
            instruments = self._load_mcx_instruments()
            if not instruments:
                self.logger.error("Cannot load MCX instruments")
                return None

            # Filter for Gold futures based on actual MCX format
            # Format: GOLDYYMMFUT (e.g., GOLD25DECFUT)
            gold_contracts = []
            for inst in instruments:
                symbol = inst.get('tradingsymbol', '')
                name = inst.get('name', '')

                # Match Gold futures: symbol starts with "GOLD" and ends with "FUT"
                # AND name is exactly "GOLD" (not GOLDGUINEA, etc.)
                if (symbol.startswith('GOLD') and
                    symbol.endswith('FUT') and
                    name == 'GOLD' and
                    inst.get('instrument_type') == 'FUT'):
                    gold_contracts.append(inst)

            if not gold_contracts:
                self.logger.error("No Gold futures found in MCX instruments")
                return None

            self.logger.info(f"Found {len(gold_contracts)} Gold futures contracts")

            # Find contract with nearest expiry date after today
            now = datetime.datetime.now().date()
            valid_contracts = []

            for contract in gold_contracts:
                expiry = contract.get('expiry')
                if expiry:
                    # expiry might be datetime or string
                    if isinstance(expiry, str):
                        expiry_date = datetime.datetime.strptime(expiry, '%Y-%m-%d').date()
                    else:
                        expiry_date = expiry.date() if hasattr(expiry, 'date') else expiry

                    # Only consider contracts expiring in the future
                    if expiry_date >= now:
                        valid_contracts.append({
                            'symbol': contract['tradingsymbol'],
                            'expiry': expiry_date,
                            'instrument_token': contract.get('instrument_token')
                        })

            if not valid_contracts:
                self.logger.error("No valid Gold Mini contracts with future expiry found")
                return None

            # Sort by expiry date and pick the nearest one (current month)
            valid_contracts.sort(key=lambda x: x['expiry'])
            current_contract = valid_contracts[0]

            symbol = current_contract['symbol']
            expiry = current_contract['expiry']

            self._current_contract_symbol = symbol
            self._instrument_token = current_contract['instrument_token']

            self.logger.info(
                f"Trading Gold contract: {symbol} "
                f"(Expiry: {expiry.strftime('%Y-%m-%d')}, Token: {self._instrument_token})"
            )

            return symbol

        except Exception as e:
            self.logger.error(f"Failed to determine Gold contract symbol: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def fetch_data(self):
        """
        Fetch 15-min historical data for Gold futures.

        Returns DataFrame with OHLCV data.
        """
        try:
            # Get current contract (this sets both symbol and token)
            symbol = self._get_current_month_symbol()
            if not symbol or not self._instrument_token:
                return None

            # Fetch 15-min data (100 candles = ~25 hours of data)
            from_date = datetime.datetime.now() - datetime.timedelta(days=2)
            to_date = datetime.datetime.now()

            # Use instrument token for data fetch (more reliable than symbol)
            df = self.executor.get_historical_data(
                instrument_token=self._instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=GOLD_TIMEFRAME
            )

            if df is None or len(df) < 50:
                self.logger.debug(f"Insufficient data for {symbol}")
                return None

            return df

        except Exception as e:
            self.logger.error(f"Failed to fetch Gold data: {str(e)}")
            return None

    def _can_enter_new_trade(self, now):
        """Check if we can enter a new trade."""
        # Max trades per day check
        if self.trade_count >= GOLD_MAX_TRADES_PER_DAY:
            return False

        # Max consecutive losses check
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.logger.warning(f"Max consecutive losses ({MAX_CONSECUTIVE_LOSSES}) hit")
            return False

        # Daily loss limit check
        if self.daily_pnl <= -MAX_LOSS_PER_DAY:
            self.logger.warning(f"Daily loss limit (Rs. {MAX_LOSS_PER_DAY:,}) hit")
            return False

        # Don't enter if already have open position
        if len(self.active_positions) > 0:
            return False

        # Trading hours check (9 AM - 10 PM for new entries)
        # Leave 1.5 hours before close for position management
        if now.hour < COMMODITY_OPEN_HOUR or now.hour >= 22:
            return False

        return True

    def scan(self):
        """
        Main scanning function. Called by run.py every interval.

        Returns list of signals (BUY/SELL).
        """
        signals = []
        now = datetime.datetime.now()

        # Check if within commodity trading hours
        if now.hour < COMMODITY_OPEN_HOUR or now.hour > COMMODITY_CLOSE_HOUR:
            return signals

        # Force exit at 11 PM (before 11:30 PM close)
        if now.hour >= 23:
            if len(self.active_positions) > 0:
                exit_signals = self._force_exit_all("End of trading day")
                signals.extend(exit_signals)
            return signals

        # Fetch data
        df = self.fetch_data()
        if df is None or len(df) < 50:
            self.logger.debug("Insufficient data")
            return signals

        # Check exits first (always check exits before entries)
        exit_signals = self._check_exits(df)
        signals.extend(exit_signals)

        # Check if we can take new entries
        if not self._can_enter_new_trade(now):
            return signals

        # Generate entry signal
        entry_signal = self._generate_entry_signal(df)
        if entry_signal:
            signals.append(entry_signal)

        return signals

    def _check_exits(self, df):
        """
        Check exit conditions for active positions.

        Exit triggers:
        1. Initial stop loss (₹250 from entry)
        2. Trailing stop loss (₹150 from highest price)
        3. Supertrend flip (bullish→bearish for longs, bearish→bullish for shorts)
        """
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            # Get current price
            current_price = self._get_ltp(symbol)
            if current_price is None:
                continue

            entry_price = position['entry_price']
            initial_sl = position['initial_sl']
            current_sl = position['current_sl']
            is_long = position['is_long']  # True for BUY, False for SELL

            # Update max/min price seen (for trailing)
            if symbol not in self.max_price_seen:
                self.max_price_seen[symbol] = entry_price

            if is_long:
                # For long positions, track highest price
                self.max_price_seen[symbol] = max(self.max_price_seen[symbol], current_price)
                max_price = self.max_price_seen[symbol]

                # Calculate trailing stop
                trail_sl = max_price - GOLD_TRAILING_STOP_POINTS
                if trail_sl > current_sl:
                    current_sl = trail_sl
                    position['current_sl'] = current_sl
                    self.logger.debug(f"{symbol}: Trailing SL to ₹{current_sl:.0f}")

                # Check stop loss
                exit_reason = None
                if current_price <= initial_sl:
                    exit_reason = f"Initial SL hit (₹{current_price:.0f} <= ₹{initial_sl:.0f})"
                elif current_price <= current_sl:
                    exit_reason = f"Trailing SL hit (₹{current_price:.0f} <= ₹{current_sl:.0f})"
                elif is_supertrend_bearish(df):
                    exit_reason = "Supertrend flipped bearish"

            else:
                # For short positions, track lowest price
                self.max_price_seen[symbol] = min(self.max_price_seen[symbol], current_price)
                min_price = self.max_price_seen[symbol]

                # Calculate trailing stop
                trail_sl = min_price + GOLD_TRAILING_STOP_POINTS
                if trail_sl < current_sl:
                    current_sl = trail_sl
                    position['current_sl'] = current_sl
                    self.logger.debug(f"{symbol}: Trailing SL to ₹{current_sl:.0f}")

                # Check stop loss
                exit_reason = None
                if current_price >= initial_sl:
                    exit_reason = f"Initial SL hit (₹{current_price:.0f} >= ₹{initial_sl:.0f})"
                elif current_price >= current_sl:
                    exit_reason = f"Trailing SL hit (₹{current_price:.0f} >= ₹{current_sl:.0f})"
                elif is_supertrend_bullish(df):
                    exit_reason = "Supertrend flipped bullish"

            # Generate exit signal if needed
            if exit_reason:
                pnl = (current_price - entry_price) * position['quantity'] if is_long else \
                      (entry_price - current_price) * position['quantity']

                self.logger.info(
                    f"EXIT: {symbol} | Reason: {exit_reason} | "
                    f"Entry: ₹{entry_price:.0f} | Exit: ₹{current_price:.0f} | "
                    f"P&L: ₹{pnl:,.0f}"
                )

                exit_signals.append({
                    'source': self.name,
                    'action': TRANSACTION_SELL if is_long else TRANSACTION_BUY,  # Reverse action to close
                    'symbol': symbol,
                    'exchange': EXCHANGE_MCX,
                    'quantity': position['quantity'],
                    'order_type': ORDER_TYPE_MARKET,
                    'product': PRODUCT_MIS,
                    'reason': exit_reason
                })

        return exit_signals

    def _generate_entry_signal(self, df):
        """
        Generate entry signal for Gold futures.

        Entry conditions (ALL must be true):
        1. Supertrend bullish (for BUY) or bearish (for SELL)
        2. ADX > 23 (trend strength)
        3. Price > 20 EMA (for BUY) or Price < 20 EMA (for SELL)

        Returns signal dict or None.
        """
        try:
            # Get current values
            current_price = df['close'].iloc[-1]

            # Compute indicators
            df = supertrend(df, period=SUPERTREND_PERIOD, multiplier=SUPERTREND_MULTIPLIER)
            df = adx(df)
            df = ema(df, period=GOLD_EMA_PERIOD, column='ema20')

            current_adx = df['adx'].iloc[-1]
            current_ema = df['ema20'].iloc[-1]

            st_bullish = is_supertrend_bullish(df)
            st_bearish = is_supertrend_bearish(df)

            # Check ADX threshold
            if current_adx < ADX_ENTRY_THRESHOLD:
                return None

            # Determine direction
            signal = None

            # BUY signal: Supertrend bullish + Price > EMA
            if st_bullish and current_price > current_ema:
                signal = 'BUY'
                action = TRANSACTION_BUY
                is_long = True
                initial_sl = current_price - GOLD_STOP_LOSS_POINTS

            # SELL signal: Supertrend bearish + Price < EMA
            elif st_bearish and current_price < current_ema:
                signal = 'SELL'
                action = TRANSACTION_SELL
                is_long = False
                initial_sl = current_price + GOLD_STOP_LOSS_POINTS

            else:
                return None

            # Calculate position size (conservative for futures)
            # Max 1 contract initially (₹6-8k margin for Gold mini)
            quantity = 1  # Start with 1 lot (100 grams)
            position_value = current_price * GOLD_LOT_SIZE  # Approx value

            if position_value > GOLD_MAX_POSITION_VALUE:
                self.logger.warning(f"Position value ₹{position_value:,} exceeds limit")
                return None

            # Log signal
            symbol = self._get_current_month_symbol()

            log_signal(
                source=self.name,
                signal_type=signal,
                symbol=symbol,
                price=current_price,
                reason=f"ST: {signal}, ADX: {current_adx:.1f}, EMA: {current_ema:.0f}"
            )

            self.logger.info(
                f"ENTRY SIGNAL: {signal} {symbol} @ ₹{current_price:.0f} | "
                f"SL: ₹{initial_sl:.0f} | ADX: {current_adx:.1f}"
            )

            return {
                'source': self.name,
                'action': action,
                'symbol': symbol,
                'exchange': EXCHANGE_MCX,
                'quantity': quantity,
                'order_type': ORDER_TYPE_MARKET,
                'product': PRODUCT_MIS,
                'reason': f"Gold {signal}: ST={signal}, ADX={current_adx:.1f}",
                'entry_price': current_price,
                'initial_sl': initial_sl
            }

        except Exception as e:
            self.logger.error(f"Error generating entry signal: {str(e)}")
            return None

    def _force_exit_all(self, reason):
        """Force exit all positions."""
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            self.logger.info(f"Force exit: {symbol} | Reason: {reason}")

            is_long = position['is_long']

            exit_signals.append({
                'source': self.name,
                'action': TRANSACTION_SELL if is_long else TRANSACTION_BUY,
                'symbol': symbol,
                'exchange': EXCHANGE_MCX,
                'quantity': position['quantity'],
                'order_type': ORDER_TYPE_MARKET,
                'product': PRODUCT_MIS,
                'reason': reason
            })

        return exit_signals

    def _get_ltp(self, symbol):
        """Get last traded price for symbol."""
        try:
            return self.executor.get_ltp(symbol, EXCHANGE_MCX)
        except Exception as e:
            self.logger.error(f"Failed to get LTP for {symbol}: {str(e)}")
            return None

    def on_order_complete(self, order_id, symbol, action, quantity, price, **kwargs):
        """
        Callback when order is completed.

        For futures:
        - BUY: Open long position
        - SELL: If closing long, remove from active_positions; if opening short, add to active_positions

        SUBTLETY: Futures can be shorted, unlike options. Need to track direction.
        """
        if action == TRANSACTION_BUY:
            # Opening long position
            initial_sl = kwargs.get('initial_sl', price - GOLD_STOP_LOSS_POINTS)

            self.trade_count += 1
            self.active_positions[symbol] = {
                'order_id': order_id,
                'entry_price': price,
                'initial_sl': initial_sl,
                'current_sl': initial_sl,
                'quantity': quantity,
                'is_long': True
            }

            self.logger.info(
                f"Position opened: LONG {symbol} @ ₹{price:.0f} | "
                f"Qty: {quantity} | SL: ₹{initial_sl:.0f}"
            )

        elif action == TRANSACTION_SELL:
            # Check if closing existing long or opening short
            if symbol in self.active_positions:
                # Closing long position
                entry = self.active_positions[symbol]['entry_price']
                pnl = (price - entry) * quantity

                # Update daily P&L
                self.daily_pnl += pnl

                # Update win/loss streak
                if pnl > 0:
                    self.consecutive_losses = 0
                else:
                    self.consecutive_losses += 1

                self.logger.info(
                    f"Position closed: LONG {symbol} | "
                    f"Entry: ₹{entry:.0f} | Exit: ₹{price:.0f} | "
                    f"P&L: ₹{pnl:,.0f} | Daily P&L: ₹{self.daily_pnl:,.0f}"
                )

                del self.active_positions[symbol]
                if symbol in self.max_price_seen:
                    del self.max_price_seen[symbol]

            else:
                # Opening short position
                initial_sl = kwargs.get('initial_sl', price + GOLD_STOP_LOSS_POINTS)

                self.trade_count += 1
                self.active_positions[symbol] = {
                    'order_id': order_id,
                    'entry_price': price,
                    'initial_sl': initial_sl,
                    'current_sl': initial_sl,
                    'quantity': quantity,
                    'is_long': False
                }

                self.logger.info(
                    f"Position opened: SHORT {symbol} @ ₹{price:.0f} | "
                    f"Qty: {quantity} | SL: ₹{initial_sl:.0f}"
                )
