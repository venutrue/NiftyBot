##############################################
# NIFTYBOT - NIFTY OPTIONS TRADING BOT
# Strategy: VWAP + Supertrend + ADX Confluence
# Capital: Rs. 2 Lakhs
##############################################

import datetime
import pandas as pd

from common.config import (
    NIFTY_50_TOKEN, NIFTY_LOT_SIZE, NIFTY_MAX_TRADES_PER_DAY,
    EXCHANGE_NFO, TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, PRODUCT_MIS,
    MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
    # New strategy parameters
    TOTAL_CAPITAL, TRADING_CAPITAL,
    MAX_INVESTMENT_PER_TRADE, MIN_INVESTMENT_PER_TRADE,
    MAX_LOSS_PER_DAY, MAX_CONSECUTIVE_LOSSES,
    INITIAL_SL_PERCENT, BREAKEVEN_TRIGGER_PERCENT, TRAIL_PERCENT,
    SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER,
    ADX_ENTRY_THRESHOLD, VWAP_BUFFER_PERCENT,
    TRAILING_STOP_METHOD, TRAILING_EMA_PERIOD,
    TRADING_START_HOUR, TRADING_START_MINUTE,
    LAST_ENTRY_HOUR, LAST_ENTRY_MINUTE,
    FORCE_EXIT_HOUR, FORCE_EXIT_MINUTE
)
from common.logger import setup_logger, log_signal, log_system
from common.indicators import (
    compute_vwap, atr, adx, ema,
    supertrend, is_supertrend_bullish, is_supertrend_bearish,
    get_atm_strike
)

##############################################
# NIFTYBOT CLASS
##############################################

class NiftyBot:
    """
    NIFTY Options Trading Bot - 2 Lakhs Capital Strategy.

    Entry Strategy (ALL must be true):
    - Option Premium > Option VWAP (smart money accumulation)
    - Supertrend bullish (for CE) or bearish (for PE) on spot
    - ADX > 23 (confirming trend strength) on spot

    Exit Strategy:
    - Phase 1: Fixed SL at 20% loss
    - Phase 2: Move SL to entry at +20% profit
    - Phase 3: Trail using Supertrend
    - Hard exit at 3:15 PM
    """

    def __init__(self, executor):
        """Initialize NiftyBot."""
        self.name = "NIFTYBOT"
        self.executor = executor
        self.logger = setup_logger(self.name)

        # State tracking
        self.trade_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.active_positions = {}

        # Position tracking
        self.max_premium_seen = {}  # Track highest premium for trailing

        # Instrument cache (avoid repeated API calls)
        self._nfo_instruments = None
        self._instruments_loaded = False

    def reset_daily_state(self):
        """Reset state at start of new trading day."""
        self.trade_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.active_positions = {}
        self.max_premium_seen = {}
        # Refresh instruments daily (expiry changes)
        self._nfo_instruments = None
        self._instruments_loaded = False
        self.logger.info("Daily state reset")

    def _load_nfo_instruments(self):
        """Load NFO instruments list (cached for the day)."""
        if self._instruments_loaded:
            return self._nfo_instruments

        try:
            self._nfo_instruments = self.executor.get_instruments(EXCHANGE_NFO)
            self._instruments_loaded = True
            self.logger.info(f"Loaded {len(self._nfo_instruments)} NFO instruments")
            return self._nfo_instruments
        except Exception as e:
            self.logger.error(f"Failed to load NFO instruments: {str(e)}")
            return None

    def _get_option_token(self, symbol):
        """Get instrument token for an option symbol."""
        instruments = self._load_nfo_instruments()
        if instruments is None:
            return None

        for inst in instruments:
            if inst['tradingsymbol'] == symbol:
                return inst['instrument_token']

        # Enhanced debugging: show similar symbols if exact match not found
        # This helps identify symbol format issues
        similar_symbols = []
        for inst in instruments:
            # Look for NIFTY options with similar characteristics
            if inst['name'] == 'NIFTY' and inst['instrument_type'] in ['CE', 'PE']:
                sym = inst['tradingsymbol']
                # Check if strike price matches
                if str(symbol.split('CE')[0].split('PE')[0][-5:]) in sym:
                    similar_symbols.append(sym)
                    if len(similar_symbols) >= 3:  # Show max 3 examples
                        break

        if similar_symbols:
            self.logger.warning(
                f"Symbol '{symbol}' not found. Similar symbols in instruments: {', '.join(similar_symbols[:3])}"
            )
        else:
            self.logger.warning(f"Symbol '{symbol}' not found in NFO instruments")

        return None

    def fetch_option_data(self, symbol):
        """
        Fetch option historical data and compute VWAP.

        Args:
            symbol: Option trading symbol (e.g., NIFTY24DEC26200CE)

        Returns:
            DataFrame with option OHLCV and VWAP, or None if failed
        """
        token = self._get_option_token(symbol)
        if token is None:
            self.logger.debug(f"Could not find token for {symbol}")
            return None

        now = datetime.datetime.now()
        # Get data from market open for VWAP calculation
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)

        try:
            data = self.executor.get_historical_data(
                instrument_token=token,
                from_date=market_open,
                to_date=now,
                interval="minute"
            )

            if data and len(data) > 0:
                df = pd.DataFrame(data)
                df = compute_vwap(df)
                return df

        except Exception as e:
            self.logger.error(f"Failed to fetch option data for {symbol}: {str(e)}")

        return None

    def get_weekly_expiry(self):
        """Get current week's Thursday expiry."""
        today = datetime.date.today()
        days_until_thursday = (3 - today.weekday()) % 7

        if days_until_thursday == 0 and datetime.datetime.now().hour >= 15:
            days_until_thursday = 7

        expiry_date = today + datetime.timedelta(days=days_until_thursday)
        return expiry_date.strftime("%y%b%d").upper()

    def get_option_symbol(self, strike, option_type):
        """Build NIFTY option symbol."""
        expiry = self.get_weekly_expiry()
        return f"NIFTY{expiry}{strike}{option_type}"

    def calculate_lots(self, premium):
        """
        Calculate number of lots based on capital constraints.

        Args:
            premium: Option premium price

        Returns:
            Number of lots to trade
        """
        lot_value = premium * NIFTY_LOT_SIZE

        # Calculate lots based on max investment
        max_lots = int(MAX_INVESTMENT_PER_TRADE / lot_value)
        min_lots = int(MIN_INVESTMENT_PER_TRADE / lot_value)

        # Ensure at least min_lots, but not more than max_lots
        lots = max(min_lots, 1)
        lots = min(lots, max_lots)

        # Cap at reasonable number (15 lots max)
        lots = min(lots, 15)

        return lots

    def fetch_data(self):
        """Fetch NIFTY minute data with all indicators."""
        now = datetime.datetime.now()
        from_date = now - datetime.timedelta(minutes=120)

        try:
            data = self.executor.get_historical_data(
                instrument_token=NIFTY_50_TOKEN,
                from_date=from_date,
                to_date=now,
                interval="minute"
            )

            if data:
                df = pd.DataFrame(data)
                # Calculate all required indicators
                df = compute_vwap(df)
                df = atr(df)
                df = adx(df)
                df = supertrend(df, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)
                return df

        except Exception as e:
            self.logger.error(f"Failed to fetch data: {str(e)}")

        return None

    def check_entry_conditions(self, df):
        """
        Check if all entry conditions are met.

        Entry Logic:
        - Supertrend and ADX checked on SPOT data
        - VWAP checked on OPTION data (specific strike)

        Returns:
            'BUY_CE', 'BUY_PE', or None
        """
        if df is None or len(df) < 20:
            return None

        current_price = df['close'].iloc[-1]
        current_adx = df['ADX'].iloc[-1]
        st_bullish = is_supertrend_bullish(df)
        st_bearish = is_supertrend_bearish(df)

        # Calculate ATM strike
        atm_strike = get_atm_strike(current_price)
        st_status = "Bullish" if st_bullish else "Bearish"

        # Check ADX strength first (no point fetching option data if no trend)
        if current_adx < ADX_ENTRY_THRESHOLD:
            self.logger.info(
                f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                f"ADX: {current_adx:.1f} | ST: {st_status} | "
                f"No trend (ADX < {ADX_ENTRY_THRESHOLD})"
            )
            return None

        # Build option symbols
        ce_symbol = self.get_option_symbol(atm_strike, "CE")
        pe_symbol = self.get_option_symbol(atm_strike, "PE")

        # Check CE conditions if Supertrend is Bullish
        if st_bullish:
            ce_data = self.fetch_option_data(ce_symbol)
            if ce_data is not None and len(ce_data) > 5:
                ce_premium = ce_data['close'].iloc[-1]
                ce_vwap = ce_data['vwap'].iloc[-1]
                vwap_status = "Above" if ce_premium > ce_vwap else "Below"

                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"ADX: {current_adx:.1f} | ST: {st_status} | "
                    f"CE: {ce_premium:.2f} vs VWAP: {ce_vwap:.2f} ({vwap_status})"
                )

                # BUY CE: Premium > VWAP (smart money buying)
                if ce_premium > ce_vwap:
                    self.logger.info(
                        f">>> CE SIGNAL: {ce_symbol} | Premium {ce_premium:.2f} > VWAP {ce_vwap:.2f} | "
                        f"Supertrend Bullish | ADX {current_adx:.1f}"
                    )
                    return 'BUY_CE'
            else:
                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"ADX: {current_adx:.1f} | ST: {st_status} | "
                    f"CE VWAP: No data for {ce_symbol}"
                )

        # Check PE conditions if Supertrend is Bearish
        elif st_bearish:
            pe_data = self.fetch_option_data(pe_symbol)
            if pe_data is not None and len(pe_data) > 5:
                pe_premium = pe_data['close'].iloc[-1]
                pe_vwap = pe_data['vwap'].iloc[-1]
                vwap_status = "Above" if pe_premium > pe_vwap else "Below"

                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"ADX: {current_adx:.1f} | ST: {st_status} | "
                    f"PE: {pe_premium:.2f} vs VWAP: {pe_vwap:.2f} ({vwap_status})"
                )

                # BUY PE: Premium > VWAP (smart money buying)
                if pe_premium > pe_vwap:
                    self.logger.info(
                        f">>> PE SIGNAL: {pe_symbol} | Premium {pe_premium:.2f} > VWAP {pe_vwap:.2f} | "
                        f"Supertrend Bearish | ADX {current_adx:.1f}"
                    )
                    return 'BUY_PE'
            else:
                self.logger.info(
                    f"Spot: {current_price:.2f} | ATM: {atm_strike} | "
                    f"ADX: {current_adx:.1f} | ST: {st_status} | "
                    f"PE VWAP: No data for {pe_symbol}"
                )

        return None

    def get_option_premium(self, symbol):
        """Get current premium for an option."""
        try:
            return self.executor.get_ltp(symbol, EXCHANGE_NFO)
        except Exception as e:
            self.logger.error(f"Failed to get premium for {symbol}: {str(e)}")
            return None

    def scan(self):
        """Main scanning function. Called by run.py."""
        signals = []
        now = datetime.datetime.now()

        # Check if within trading hours
        if not self._is_trading_time(now):
            return signals

        # Force exit check (3:15 PM)
        if self._is_force_exit_time(now):
            return self._force_exit_all("End of day exit")

        # Check daily loss limit
        if self.daily_pnl <= -MAX_LOSS_PER_DAY:
            self.logger.warning(f"Daily loss limit reached: Rs. {self.daily_pnl}")
            return self._force_exit_all("Daily loss limit reached")

        # Check consecutive losses
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.logger.warning(f"Max consecutive losses ({MAX_CONSECUTIVE_LOSSES}) reached")
            return signals  # Don't take new trades, but keep existing positions

        # Fetch data
        df = self.fetch_data()
        if df is None or len(df) < 20:
            self.logger.debug("Insufficient data")
            return signals

        # Check exits first (always check exits)
        exit_signals = self._check_exits(df)
        signals.extend(exit_signals)

        # Check if we can take new entries
        if not self._can_enter_new_trade(now):
            return signals

        # Check entry conditions
        signal_type = self.check_entry_conditions(df)

        if signal_type:
            signal = self._create_entry_signal(df, signal_type)
            if signal:
                signals.append(signal)

        return signals

    def _can_enter_new_trade(self, now):
        """Check if we can enter a new trade."""
        # Max trades check
        if self.trade_count >= NIFTY_MAX_TRADES_PER_DAY:
            self.logger.debug("Max trades reached")
            return False

        # No new entries after cutoff time
        cutoff = now.replace(hour=LAST_ENTRY_HOUR, minute=LAST_ENTRY_MINUTE, second=0)
        if now >= cutoff:
            self.logger.debug("Past entry cutoff time")
            return False

        # Already have a position
        if len(self.active_positions) > 0:
            return False

        return True

    def _create_entry_signal(self, df, signal_type):
        """Create entry signal with position sizing."""
        current_price = df['close'].iloc[-1]
        atm_strike = get_atm_strike(current_price)
        option_type = "CE" if signal_type == "BUY_CE" else "PE"
        symbol = self.get_option_symbol(atm_strike, option_type)

        # Get option premium
        premium = self.get_option_premium(symbol)
        if premium is None:
            self.logger.error(f"Could not get premium for {symbol}")
            return None

        # Calculate lots based on capital
        lots = self.calculate_lots(premium)
        quantity = lots * NIFTY_LOT_SIZE

        # Calculate initial stop loss (20% of premium)
        initial_sl = premium * (1 - INITIAL_SL_PERCENT / 100)

        # Calculate investment
        investment = premium * quantity

        log_signal(
            self.name,
            signal_type,
            symbol,
            spot=current_price,
            strike=atm_strike,
            premium=premium,
            lots=lots,
            investment=investment
        )

        self.logger.info(
            f"Entry Signal: {signal_type} | {symbol} | "
            f"Premium: Rs. {premium} | Lots: {lots} | "
            f"Investment: Rs. {investment:,.0f} | SL: Rs. {initial_sl:.2f}"
        )

        return {
            'source': self.name,
            'action': TRANSACTION_BUY,
            'symbol': symbol,
            'exchange': EXCHANGE_NFO,
            'quantity': quantity,
            'order_type': ORDER_TYPE_MARKET,
            'product': PRODUCT_MIS,
            'reason': f"{signal_type} - VWAP+ST+ADX confluence",
            'entry_price': premium,
            'entry_spot': current_price,
            'initial_sl': initial_sl
        }

    def _check_exits(self, df):
        """Check exit conditions for active positions."""
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            # Get current premium
            current_premium = self.get_option_premium(symbol)
            if current_premium is None:
                continue

            entry_premium = position['entry_premium']
            initial_sl = position['initial_sl']
            current_sl = position['current_sl']
            is_call = symbol.endswith("CE")

            # Update max premium seen (for trailing)
            if symbol not in self.max_premium_seen:
                self.max_premium_seen[symbol] = entry_premium
            self.max_premium_seen[symbol] = max(self.max_premium_seen[symbol], current_premium)
            max_premium = self.max_premium_seen[symbol]

            # Calculate profit percentage
            profit_pct = ((current_premium - entry_premium) / entry_premium) * 100

            # Determine exit reason
            exit_reason = None
            new_sl = current_sl

            # Phase 1: Check initial stop loss
            if current_premium <= initial_sl:
                exit_reason = f"Initial SL hit (Premium: {current_premium:.2f} <= SL: {initial_sl:.2f})"

            # Phase 2: Move to breakeven at +20%
            elif profit_pct >= BREAKEVEN_TRIGGER_PERCENT and current_sl < entry_premium:
                new_sl = entry_premium
                self.logger.info(f"{symbol}: Moving SL to breakeven at Rs. {new_sl:.2f}")
                position['current_sl'] = new_sl

            # Phase 3: Trail stop loss
            if profit_pct >= BREAKEVEN_TRIGGER_PERCENT:
                if TRAILING_STOP_METHOD == 'supertrend':
                    # Exit on Supertrend flip
                    if is_call and is_supertrend_bearish(df):
                        exit_reason = "Supertrend flipped bearish"
                    elif not is_call and is_supertrend_bullish(df):
                        exit_reason = "Supertrend flipped bullish"
                elif TRAILING_STOP_METHOD == 'percent':
                    # Trail at 50% of max profit
                    trail_sl = entry_premium + (max_premium - entry_premium) * (TRAIL_PERCENT / 100)
                    if trail_sl > new_sl:
                        new_sl = trail_sl
                        position['current_sl'] = new_sl
                        self.logger.debug(f"{symbol}: Trailing SL to Rs. {new_sl:.2f}")

                    if current_premium <= new_sl:
                        exit_reason = f"Trailing SL hit (Premium: {current_premium:.2f} <= SL: {new_sl:.2f})"

            # Check current SL
            if current_premium <= current_sl and exit_reason is None:
                exit_reason = f"Stop loss hit (Premium: {current_premium:.2f} <= SL: {current_sl:.2f})"

            # Generate exit signal if needed
            if exit_reason:
                pnl = (current_premium - entry_premium) * position['quantity']
                self.logger.info(
                    f"EXIT: {symbol} | Reason: {exit_reason} | "
                    f"Entry: {entry_premium:.2f} | Exit: {current_premium:.2f} | "
                    f"P&L: Rs. {pnl:,.2f}"
                )

                exit_signals.append({
                    'source': self.name,
                    'action': TRANSACTION_SELL,
                    'symbol': symbol,
                    'exchange': EXCHANGE_NFO,
                    'quantity': position['quantity'],
                    'order_type': ORDER_TYPE_MARKET,
                    'product': PRODUCT_MIS,
                    'reason': exit_reason
                })

        return exit_signals

    def _force_exit_all(self, reason):
        """Force exit all positions."""
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            self.logger.info(f"Force exit: {symbol} | Reason: {reason}")

            exit_signals.append({
                'source': self.name,
                'action': TRANSACTION_SELL,
                'symbol': symbol,
                'exchange': EXCHANGE_NFO,
                'quantity': position['quantity'],
                'order_type': ORDER_TYPE_MARKET,
                'product': PRODUCT_MIS,
                'reason': reason
            })

        return exit_signals

    def on_order_complete(self, order_id, symbol, action, quantity, price, **kwargs):
        """Callback when order is completed."""
        if action == TRANSACTION_BUY:
            entry_spot = kwargs.get('entry_spot', 0)
            initial_sl = kwargs.get('initial_sl', price * 0.8)

            self.trade_count += 1
            self.active_positions[symbol] = {
                'order_id': order_id,
                'entry_premium': price,
                'entry_spot': entry_spot,
                'initial_sl': initial_sl,
                'current_sl': initial_sl,
                'quantity': quantity,
                'entry_time': datetime.datetime.now()
            }
            self.max_premium_seen[symbol] = price

            self.logger.info(
                f"Position opened: {symbol} @ Rs. {price} | "
                f"Qty: {quantity} | SL: Rs. {initial_sl:.2f} | "
                f"Trade #{self.trade_count}"
            )

        elif action == TRANSACTION_SELL:
            if symbol in self.active_positions:
                entry = self.active_positions[symbol]['entry_premium']
                pnl = (price - entry) * quantity

                # Update daily P&L
                self.daily_pnl += pnl

                # Track consecutive losses
                if pnl < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0

                self.logger.info(
                    f"Position closed: {symbol} | "
                    f"Entry: {entry:.2f} | Exit: {price:.2f} | "
                    f"P&L: Rs. {pnl:,.2f} | Daily P&L: Rs. {self.daily_pnl:,.2f}"
                )

                del self.active_positions[symbol]
                if symbol in self.max_premium_seen:
                    del self.max_premium_seen[symbol]

    def _is_trading_time(self, now):
        """Check if within trading hours."""
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
        market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
        trading_start = now.replace(hour=TRADING_START_HOUR, minute=TRADING_START_MINUTE, second=0)

        return trading_start <= now <= market_close

    def _is_force_exit_time(self, now):
        """Check if it's time to force exit all positions."""
        force_exit = now.replace(hour=FORCE_EXIT_HOUR, minute=FORCE_EXIT_MINUTE, second=0)
        return now >= force_exit

    def get_status(self):
        """Get current bot status."""
        return {
            'name': self.name,
            'trade_count': self.trade_count,
            'max_trades': NIFTY_MAX_TRADES_PER_DAY,
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len(self.active_positions),
            'positions': list(self.active_positions.keys())
        }
