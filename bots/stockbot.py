##############################################
# STOCKBOT - STOCK MOMENTUM TRADING BOT
# Strategy: Volume + Breakout + ADX + PSAR
##############################################

import datetime
import pandas as pd
import os

from common.config import (
    EXCHANGE_NSE, TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, PRODUCT_CNC, PRODUCT_MIS,
    STOCK_MAX_TRADES_PER_DAY, STOCK_MAX_CAPITAL_PER_TRADE,
    VOLUME_MULTIPLIER, ADX_THRESHOLD, BREAKOUT_LOOKBACK_DAYS,
    VOLUME_LOOKBACK_DAYS, ATR_MULTIPLIER_STOPLOSS, EMA_PERIOD,
    MARKET_OPEN_HOUR, MARKET_CLOSE_HOUR,
    STOCK_SCAN_HOUR, STOCK_SCAN_MINUTE,
    WATCHLIST_PATH
)
from common.logger import setup_logger, log_signal, log_system
from common.indicators import (
    adx, psar, atr, ema, rsi,
    is_psar_bullish, is_psar_bearish,
    is_breakout, get_breakout_level,
    check_exit_conditions, calculate_stop_loss
)

##############################################
# STOCKBOT CLASS
##############################################

class StockBot:
    """
    Stock Momentum Trading Bot.

    Entry Strategy:
    - Volume: First 3 hours > 1.5x last 10-day average
    - Breakout: Price closed above 3-5 day high
    - ADX > 28 (strong trend)
    - PSAR bullish (dots below price)

    Exit Strategy:
    - 2 of 3 conditions met:
      1. PSAR flips bearish
      2. Price closes below 20 EMA
      3. ADX starts declining
    - Hard stop: 2.5 x ATR below entry
    """

    def __init__(self, executor):
        """
        Initialize StockBot.

        Args:
            executor: TradeExecutor instance for order execution
        """
        self.name = "STOCKBOT"
        self.executor = executor
        self.logger = setup_logger(self.name)

        # State tracking
        self.watchlist = []
        self.trade_count = 0
        self.active_positions = {}
        self.scanned_today = False

        # Load watchlist
        self._load_watchlist()

    def _load_watchlist(self):
        """Load watchlist from CSV file."""
        try:
            if os.path.exists(WATCHLIST_PATH):
                df = pd.read_csv(WATCHLIST_PATH)
                self.watchlist = df['symbol'].tolist()
                self.logger.info(f"Loaded {len(self.watchlist)} stocks from watchlist")
            else:
                self.logger.warning(f"Watchlist not found: {WATCHLIST_PATH}")
                self.watchlist = []
        except Exception as e:
            self.logger.error(f"Failed to load watchlist: {str(e)}")
            self.watchlist = []

    def reset_daily_state(self):
        """Reset state at start of new trading day."""
        self.trade_count = 0
        self.scanned_today = False
        self.active_positions = {}
        self.logger.info("Daily state reset")

    def fetch_stock_data(self, symbol, days=15):
        """
        Fetch historical data for a stock.

        Args:
            symbol: Stock symbol
            days: Number of days of history

        Returns:
            DataFrame with OHLCV data or None
        """
        now = datetime.datetime.now()
        from_date = now - datetime.timedelta(days=days)

        try:
            # Get instrument token (simplified - in production, use instrument master)
            ltp = self.executor.get_ltp(symbol, EXCHANGE_NSE)
            if ltp is None:
                return None

            # For now, we'll work with daily data
            # In production, you'd fetch minute data for intraday volume
            data = self.executor.broker.kite.historical_data(
                instrument_token=self._get_instrument_token(symbol),
                from_date=from_date,
                to_date=now,
                interval="day"
            )

            if data:
                df = pd.DataFrame(data)
                return df

        except Exception as e:
            self.logger.error(f"Failed to fetch data for {symbol}: {str(e)}")

        return None

    def _get_instrument_token(self, symbol):
        """
        Get instrument token for a symbol.
        Note: In production, maintain an instrument master file.
        """
        # This is a placeholder - in production, lookup from instruments file
        # You would load the instruments file once at startup
        try:
            instruments = self.executor.broker.kite.instruments(EXCHANGE_NSE)
            for inst in instruments:
                if inst['tradingsymbol'] == symbol:
                    return inst['instrument_token']
        except:
            pass
        return None

    def check_volume_spike(self, df):
        """
        Check if today's first 3-hour volume exceeds average.

        Args:
            df: DataFrame with volume data

        Returns:
            (bool, ratio) - Whether spike detected and the ratio
        """
        if len(df) < VOLUME_LOOKBACK_DAYS + 1:
            return False, 0

        # Get average daily volume (last 10 days)
        avg_volume = df['volume'].iloc[-(VOLUME_LOOKBACK_DAYS+1):-1].mean()

        # Get today's volume (in production, use minute data for first 3 hours)
        today_volume = df['volume'].iloc[-1]

        ratio = today_volume / avg_volume if avg_volume > 0 else 0

        return ratio >= VOLUME_MULTIPLIER, ratio

    def check_breakout(self, df):
        """
        Check if price broke above recent high.

        Args:
            df: DataFrame with price data

        Returns:
            (bool, breakout_level) - Whether breakout detected and the level
        """
        if len(df) < BREAKOUT_LOOKBACK_DAYS + 1:
            return False, 0

        # Get high of last N days (excluding today)
        recent_high = df['high'].iloc[-(BREAKOUT_LOOKBACK_DAYS+1):-1].max()

        # Today's close
        today_close = df['close'].iloc[-1]

        return today_close > recent_high, recent_high

    def check_adx_strength(self, df):
        """
        Check if ADX indicates strong trend.

        Args:
            df: DataFrame with price data

        Returns:
            (bool, adx_value) - Whether ADX > threshold and the value
        """
        df_with_adx = adx(df)
        adx_value = df_with_adx['ADX'].iloc[-1]

        return adx_value >= ADX_THRESHOLD, adx_value

    def check_psar_bullish(self, df):
        """
        Check if PSAR is bullish.

        Args:
            df: DataFrame with price data

        Returns:
            bool - Whether PSAR is bullish
        """
        df_with_psar = psar(df)
        return is_psar_bullish(df_with_psar)

    def analyze_stock(self, symbol):
        """
        Analyze a single stock for entry signal.

        Args:
            symbol: Stock symbol

        Returns:
            dict with analysis results or None
        """
        df = self.fetch_stock_data(symbol)
        if df is None or len(df) < 20:
            return None

        # Check all conditions
        volume_ok, volume_ratio = self.check_volume_spike(df)
        breakout_ok, breakout_level = self.check_breakout(df)
        adx_ok, adx_value = self.check_adx_strength(df)
        psar_ok = self.check_psar_bullish(df)

        # Calculate indicators for exit tracking
        df_with_atr = atr(df)
        atr_value = df_with_atr['ATR'].iloc[-1]
        current_price = df['close'].iloc[-1]
        stop_loss = calculate_stop_loss(current_price, atr_value)

        # RSI check (not overbought)
        rsi_value = rsi(df['close']).iloc[-1]
        rsi_ok = rsi_value < 75

        conditions_met = sum([volume_ok, breakout_ok, adx_ok, psar_ok])

        return {
            'symbol': symbol,
            'current_price': current_price,
            'volume_ok': volume_ok,
            'volume_ratio': volume_ratio,
            'breakout_ok': breakout_ok,
            'breakout_level': breakout_level,
            'adx_ok': adx_ok,
            'adx_value': adx_value,
            'psar_ok': psar_ok,
            'rsi_ok': rsi_ok,
            'rsi_value': rsi_value,
            'atr_value': atr_value,
            'stop_loss': stop_loss,
            'conditions_met': conditions_met,
            'signal': conditions_met >= 4  # All 4 main conditions
        }

    def scan(self):
        """
        Main scanning function. Called by run.py.

        Returns:
            List of signals to execute
        """
        signals = []
        now = datetime.datetime.now()

        # Check market hours
        if not self._is_market_open(now):
            return signals

        # Check if it's scan time (12:00 PM)
        if not self._is_scan_time(now):
            # Still check exits for active positions
            return self._check_all_exits()

        # Only scan once per day
        if self.scanned_today:
            return self._check_all_exits()

        # Check max trades
        if self.trade_count >= STOCK_MAX_TRADES_PER_DAY:
            self.logger.debug("Max trades reached")
            return self._check_all_exits()

        self.logger.info(f"Starting scan of {len(self.watchlist)} stocks...")
        log_system(f"STOCKBOT | Scanning {len(self.watchlist)} stocks")

        qualifying_stocks = []

        for symbol in self.watchlist:
            if self.trade_count >= STOCK_MAX_TRADES_PER_DAY:
                break

            analysis = self.analyze_stock(symbol)

            if analysis and analysis['signal']:
                qualifying_stocks.append(analysis)
                self.logger.info(
                    f"SIGNAL: {symbol} | "
                    f"Vol: {analysis['volume_ratio']:.1f}x | "
                    f"ADX: {analysis['adx_value']:.1f} | "
                    f"RSI: {analysis['rsi_value']:.1f}"
                )

        # Create signals for qualifying stocks
        for stock in qualifying_stocks:
            signal = self._create_entry_signal(stock)
            if signal:
                signals.append(signal)

        self.scanned_today = True
        self.logger.info(f"Scan complete. Found {len(qualifying_stocks)} signals.")

        # Also check exits
        exit_signals = self._check_all_exits()
        signals.extend(exit_signals)

        return signals

    def _create_entry_signal(self, analysis):
        """Create entry signal dict."""
        symbol = analysis['symbol']
        current_price = analysis['current_price']

        # Calculate quantity based on max capital
        quantity = int(STOCK_MAX_CAPITAL_PER_TRADE / current_price)
        if quantity < 1:
            self.logger.warning(f"Price too high for {symbol}: Rs. {current_price}")
            return None

        log_signal(
            self.name,
            "BUY",
            symbol,
            price=current_price,
            volume_ratio=f"{analysis['volume_ratio']:.1f}x",
            adx=f"{analysis['adx_value']:.1f}",
            stop_loss=analysis['stop_loss']
        )

        return {
            'source': self.name,
            'action': TRANSACTION_BUY,
            'symbol': symbol,
            'exchange': EXCHANGE_NSE,
            'quantity': quantity,
            'order_type': ORDER_TYPE_MARKET,
            'product': PRODUCT_CNC,  # Delivery for stocks
            'stop_loss': analysis['stop_loss'],
            'reason': f"Vol: {analysis['volume_ratio']:.1f}x | ADX: {analysis['adx_value']:.1f}",
            'entry_price': current_price
        }

    def _check_all_exits(self):
        """Check exit conditions for all active positions."""
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            df = self.fetch_stock_data(symbol)
            if df is None:
                continue

            # Add required indicators
            df = atr(df)
            df = psar(df)
            df['EMA'] = ema(df['close'], EMA_PERIOD)
            df = adx(df)

            exit_check = check_exit_conditions(df, position['entry_price'])

            if exit_check['should_exit']:
                self.logger.info(
                    f"Exit signal: {symbol} | "
                    f"Reasons: {', '.join(exit_check['reasons'])}"
                )

                exit_signals.append({
                    'source': self.name,
                    'action': TRANSACTION_SELL,
                    'symbol': symbol,
                    'exchange': EXCHANGE_NSE,
                    'quantity': position['quantity'],
                    'order_type': ORDER_TYPE_MARKET,
                    'product': PRODUCT_CNC,
                    'reason': ', '.join(exit_check['reasons'])
                })

        return exit_signals

    def on_order_complete(self, order_id, symbol, action, quantity, price):
        """
        Callback when order is completed.

        Args:
            order_id: Completed order ID
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Filled quantity
            price: Filled price
        """
        if action == TRANSACTION_BUY:
            self.trade_count += 1
            self.active_positions[symbol] = {
                'order_id': order_id,
                'entry_price': price,
                'quantity': quantity
            }
            self.logger.info(f"Position opened: {symbol} @ Rs. {price} | Trade #{self.trade_count}")

        elif action == TRANSACTION_SELL:
            if symbol in self.active_positions:
                entry = self.active_positions[symbol]['entry_price']
                pnl = (price - entry) * quantity
                self.logger.info(f"Position closed: {symbol} | P&L: Rs. {pnl:.2f}")
                del self.active_positions[symbol]

    def _is_market_open(self, now):
        """Check if market is open."""
        return MARKET_OPEN_HOUR <= now.hour < MARKET_CLOSE_HOUR

    def _is_scan_time(self, now):
        """Check if it's time for the daily scan."""
        return now.hour == STOCK_SCAN_HOUR and now.minute >= STOCK_SCAN_MINUTE

    def get_status(self):
        """Get current bot status."""
        return {
            'name': self.name,
            'watchlist_count': len(self.watchlist),
            'trade_count': self.trade_count,
            'max_trades': STOCK_MAX_TRADES_PER_DAY,
            'scanned_today': self.scanned_today,
            'active_positions': len(self.active_positions)
        }
