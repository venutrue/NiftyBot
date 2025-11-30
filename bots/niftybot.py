##############################################
# NIFTYBOT - NIFTY OPTIONS TRADING BOT
# Strategy: VWAP + Day Type Detection
##############################################

import datetime
import pandas as pd

from common.config import (
    NIFTY_50_TOKEN, NIFTY_LOT_SIZE, NIFTY_MAX_TRADES_PER_DAY,
    EXCHANGE_NFO, TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, PRODUCT_MIS,
    VWAP_DEVIATION_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE
)
from common.logger import setup_logger, log_signal, log_system
from common.indicators import (
    compute_vwap, atr, rsi, ema, psar,
    detect_day_type, get_atm_strike,
    check_exit_conditions
)

##############################################
# NIFTYBOT CLASS
##############################################

class NiftyBot:
    """
    NIFTY Options Trading Bot.

    Strategy:
    - Detects day type (TRENDING vs SIDEWAYS)
    - TRENDING: Trade with VWAP direction
    - SIDEWAYS: Mean reversion at VWAP extremes
    """

    def __init__(self, executor):
        """
        Initialize NiftyBot.

        Args:
            executor: TradeExecutor instance for order execution
        """
        self.name = "NIFTYBOT"
        self.executor = executor
        self.logger = setup_logger(self.name)

        # State tracking
        self.day_type = None
        self.trade_count = 0
        self.active_positions = {}

    def reset_daily_state(self):
        """Reset state at start of new trading day."""
        self.day_type = None
        self.trade_count = 0
        self.active_positions = {}
        self.logger.info("Daily state reset")

    def get_weekly_expiry(self):
        """
        Get current week's Thursday expiry.

        Returns:
            Expiry string (e.g., '25NOV28')
        """
        today = datetime.date.today()
        days_until_thursday = (3 - today.weekday()) % 7

        if days_until_thursday == 0 and datetime.datetime.now().hour >= 15:
            days_until_thursday = 7

        expiry_date = today + datetime.timedelta(days=days_until_thursday)
        return expiry_date.strftime("%y%b%d").upper()

    def get_option_symbol(self, strike, option_type):
        """
        Build NIFTY option symbol.

        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'

        Returns:
            Trading symbol (e.g., 'NIFTY25NOV2824300CE')
        """
        expiry = self.get_weekly_expiry()
        return f"NIFTY{expiry}{strike}{option_type}"

    def fetch_data(self):
        """
        Fetch NIFTY minute data.

        Returns:
            DataFrame with OHLCV data or None
        """
        now = datetime.datetime.now()
        from_date = now - datetime.timedelta(minutes=60)

        try:
            data = self.executor.get_historical_data(
                instrument_token=NIFTY_50_TOKEN,
                from_date=from_date,
                to_date=now,
                interval="minute"
            )

            if data:
                df = pd.DataFrame(data)
                df = compute_vwap(df)
                df = atr(df)
                df = psar(df)
                return df

        except Exception as e:
            self.logger.error(f"Failed to fetch data: {str(e)}")

        return None

    def generate_trend_signal(self, df):
        """
        Generate signal for trending day.

        Args:
            df: DataFrame with indicators

        Returns:
            'BUY_CE', 'BUY_PE', or None
        """
        current_close = df["close"].iloc[-1]
        current_vwap = df["vwap"].iloc[-1]

        if current_close > current_vwap:
            return "BUY_CE"
        elif current_close < current_vwap:
            return "BUY_PE"

        return None

    def generate_mean_rev_signal(self, df):
        """
        Generate signal for sideways day (mean reversion).

        Args:
            df: DataFrame with indicators

        Returns:
            'BUY_CE', 'BUY_PE', or None
        """
        current_close = df["close"].iloc[-1]
        current_vwap = df["vwap"].iloc[-1]

        deviation = (current_close - current_vwap) / current_vwap
        rsi_value = rsi(df["close"]).iloc[-1]

        # Overbought - expect reversal down
        if deviation > VWAP_DEVIATION_THRESHOLD and rsi_value > RSI_OVERBOUGHT:
            return "BUY_PE"

        # Oversold - expect reversal up
        elif deviation < -VWAP_DEVIATION_THRESHOLD and rsi_value < RSI_OVERSOLD:
            return "BUY_CE"

        return None

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

        # Check max trades
        if self.trade_count >= NIFTY_MAX_TRADES_PER_DAY:
            self.logger.debug("Max trades reached")
            return signals

        # Fetch data
        df = self.fetch_data()
        if df is None or len(df) < 20:
            return signals

        # Detect day type (once per day)
        if self.day_type is None:
            self.day_type = detect_day_type(df)
            if self.day_type:
                self.logger.info(f"Day type detected: {self.day_type}")
                log_system(f"NIFTYBOT | Day type: {self.day_type}")

        if self.day_type is None:
            return signals

        # Check for exit signals on active positions
        exit_signals = self._check_exits(df)
        signals.extend(exit_signals)

        # Generate entry signals
        if self.day_type == "TRENDING":
            signal_type = self.generate_trend_signal(df)
        else:
            signal_type = self.generate_mean_rev_signal(df)

        if signal_type:
            signal = self._create_entry_signal(df, signal_type)
            if signal:
                signals.append(signal)

        return signals

    def _create_entry_signal(self, df, signal_type):
        """Create entry signal dict."""
        current_price = df["close"].iloc[-1]
        atm_strike = get_atm_strike(current_price)
        option_type = "CE" if signal_type == "BUY_CE" else "PE"
        symbol = self.get_option_symbol(atm_strike, option_type)

        # Calculate stop loss
        atr_value = df["ATR"].iloc[-1]
        stop_loss = current_price - (2.5 * atr_value) if option_type == "CE" else current_price + (2.5 * atr_value)

        log_signal(
            self.name,
            signal_type,
            symbol,
            spot=current_price,
            strike=atm_strike,
            day_type=self.day_type
        )

        return {
            'source': self.name,
            'action': TRANSACTION_BUY,
            'symbol': symbol,
            'exchange': EXCHANGE_NFO,
            'quantity': NIFTY_LOT_SIZE,
            'order_type': ORDER_TYPE_MARKET,
            'product': PRODUCT_MIS,
            'stop_loss': stop_loss,
            'reason': f"{self.day_type} day - {signal_type}",
            'entry_price': current_price
        }

    def _check_exits(self, df):
        """Check exit conditions for active positions."""
        exit_signals = []

        for symbol, position in list(self.active_positions.items()):
            exit_check = check_exit_conditions(df, position['entry_price'])

            if exit_check['should_exit']:
                self.logger.info(f"Exit signal: {symbol} | Reasons: {', '.join(exit_check['reasons'])}")

                exit_signals.append({
                    'source': self.name,
                    'action': TRANSACTION_SELL,
                    'symbol': symbol,
                    'exchange': EXCHANGE_NFO,
                    'quantity': position['quantity'],
                    'order_type': ORDER_TYPE_MARKET,
                    'product': PRODUCT_MIS,
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
            self.logger.info(f"Position opened: {symbol} | Trade #{self.trade_count}")

        elif action == TRANSACTION_SELL:
            if symbol in self.active_positions:
                entry = self.active_positions[symbol]['entry_price']
                pnl = (price - entry) * quantity
                self.logger.info(f"Position closed: {symbol} | P&L: Rs. {pnl:.2f}")
                del self.active_positions[symbol]

    def _is_market_open(self, now):
        """Check if market is open."""
        market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
        market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
        return market_open <= now <= market_close

    def get_status(self):
        """Get current bot status."""
        return {
            'name': self.name,
            'day_type': self.day_type,
            'trade_count': self.trade_count,
            'max_trades': NIFTY_MAX_TRADES_PER_DAY,
            'active_positions': len(self.active_positions)
        }
