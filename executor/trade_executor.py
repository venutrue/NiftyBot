##############################################
# TRADE EXECUTOR
# Broker-agnostic execution layer
# Currently supports: Kite Connect
# Future: Angel, ICICI, etc.
##############################################

import datetime
import time
from abc import ABC, abstractmethod
from kiteconnect import KiteConnect

from common.config import (
    API_KEY, ACCESS_TOKEN, BROKER,
    EXCHANGE_NSE, EXCHANGE_NFO,
    TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT, ORDER_TYPE_SL,
    PRODUCT_MIS, PRODUCT_CNC, PRODUCT_NRML,
    VARIETY_REGULAR,
    MAX_LOSS_PER_DAY, MAX_CAPITAL_DEPLOYED,
    API_MAX_RETRIES, API_RETRY_DELAY, API_TIMEOUT
)
from common.logger import (
    setup_logger, log_trade, log_error,
    log_position, log_system
)

##############################################
# ABSTRACT BROKER INTERFACE
##############################################

class BrokerInterface(ABC):
    """Abstract base class for broker implementations."""

    @abstractmethod
    def connect(self):
        """Establish connection to broker."""
        pass

    @abstractmethod
    def place_order(self, signal):
        """Place an order based on signal."""
        pass

    @abstractmethod
    def modify_order(self, order_id, **kwargs):
        """Modify an existing order."""
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        """Cancel an order."""
        pass

    @abstractmethod
    def get_positions(self):
        """Get current positions."""
        pass

    @abstractmethod
    def get_orders(self):
        """Get today's orders."""
        pass

    @abstractmethod
    def get_margins(self):
        """Get available margins."""
        pass

    @abstractmethod
    def get_ltp(self, symbol, exchange):
        """Get last traded price."""
        pass

##############################################
# KITE CONNECT IMPLEMENTATION
##############################################

class KiteExecutor(BrokerInterface):
    """Kite Connect broker implementation."""

    def __init__(self, api_key=API_KEY, access_token=ACCESS_TOKEN):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = None
        self.logger = setup_logger("EXECUTOR")
        self.connected = False

        # API rate limiting (max 50 calls per day)
        self.max_api_calls_per_day = 50
        self.api_call_count = 0
        self.api_call_date = datetime.date.today()
        self.api_limit_reached = False

    def connect(self):
        """Connect to Kite Connect API."""
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            self.connected = True
            log_system("Kite Connect connected successfully")
            return True
        except Exception as e:
            log_error("EXECUTOR", f"Failed to connect to Kite: {str(e)}")
            self.connected = False
            return False

    def _check_api_rate_limit(self):
        """
        Check if API rate limit has been reached.

        Returns:
            bool: True if within limit, False if limit reached
        """
        today = datetime.date.today()

        # Reset counter if new day
        if today != self.api_call_date:
            self.api_call_count = 0
            self.api_call_date = today
            self.api_limit_reached = False
            self.logger.info(f"API rate limit reset for new day: {today}")

        # Check if limit reached
        if self.api_call_count >= self.max_api_calls_per_day:
            if not self.api_limit_reached:
                # Log warning only once per day
                log_error("EXECUTOR",
                    f"🚨 API RATE LIMIT REACHED: {self.api_call_count}/{self.max_api_calls_per_day} calls today. "
                    f"No more API calls until tomorrow to prevent issues."
                )
                self.api_limit_reached = True
            return False

        return True

    def _increment_api_call_count(self, call_name: str):
        """Increment API call counter and log if approaching limit."""
        self.api_call_count += 1

        # Log progress every 10 calls
        if self.api_call_count % 10 == 0:
            remaining = self.max_api_calls_per_day - self.api_call_count
            self.logger.info(
                f"API calls today: {self.api_call_count}/{self.max_api_calls_per_day} "
                f"({remaining} remaining)"
            )

        # Warn when approaching limit
        if self.api_call_count >= self.max_api_calls_per_day - 5:
            self.logger.warning(
                f"⚠️  Approaching API limit: {self.api_call_count}/{self.max_api_calls_per_day} "
                f"({self.max_api_calls_per_day - self.api_call_count} calls remaining)"
            )

    def _retry_api_call(self, func, func_name, *args, **kwargs):
        """
        Retry an API call with exponential backoff on network errors.
        Includes rate limiting check.

        Args:
            func: The API function to call
            func_name: Name of the function (for logging)
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Result of the API call, or None if all retries fail
        """
        # SAFETY: Check API rate limit before making call
        if not self._check_api_rate_limit():
            self.logger.error(
                f"{func_name}: BLOCKED - API rate limit reached "
                f"({self.api_call_count}/{self.max_api_calls_per_day} calls today)"
            )
            return None

        last_error = None
        delay = API_RETRY_DELAY

        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                self.logger.debug(f"{func_name}: Attempt {attempt}/{API_MAX_RETRIES}")
                result = func(*args, **kwargs)

                # Success - increment counter and log if we had retries
                if attempt == 1:
                    # Only count successful first attempts (not retries)
                    self._increment_api_call_count(func_name)

                if attempt > 1:
                    self.logger.info(f"{func_name}: Succeeded on attempt {attempt}")

                return result

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Check if it's a network error that should be retried
                is_network_error = any(err in error_str.lower() for err in [
                    'connection', 'reset', 'timeout', 'timed out',
                    'network', 'refused', 'unreachable', 'aborted'
                ])

                if is_network_error and attempt < API_MAX_RETRIES:
                    self.logger.warning(
                        f"{func_name}: Network error on attempt {attempt}/{API_MAX_RETRIES}: {error_str}"
                    )
                    self.logger.info(f"{func_name}: Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    # Non-network error or last attempt
                    if attempt == API_MAX_RETRIES:
                        log_error("EXECUTOR",
                            f"{func_name}: Failed after {API_MAX_RETRIES} attempts: {error_str}")
                    else:
                        log_error("EXECUTOR", f"{func_name}: {error_str}")
                    return None

        # All retries exhausted
        return None

    def place_order(self, signal):
        """
        Place an order based on signal.

        Args:
            signal: dict with keys:
                - source: Bot name (NIFTYBOT, STOCKBOT)
                - action: BUY or SELL
                - symbol: Trading symbol
                - exchange: NSE, NFO, BSE
                - quantity: Order quantity
                - order_type: MARKET, LIMIT, SL
                - product: MIS, CNC, NRML
                - price: Limit price (optional)
                - trigger_price: Stop loss trigger (optional)
                - stop_loss: Stop loss price (optional)
                - target: Target price (optional)
                - reason: Signal reason

        Returns:
            order_id if successful, None otherwise
        """
        if not self.connected:
            log_error("EXECUTOR", "Not connected to broker")
            return None

        try:
            self.logger.info(f"Placing order: {signal['action']} {signal['quantity']} x {signal['symbol']}")

            order_params = {
                'variety': VARIETY_REGULAR,
                'tradingsymbol': signal['symbol'],
                'exchange': signal.get('exchange', EXCHANGE_NSE),
                'transaction_type': signal['action'],
                'quantity': signal['quantity'],
                'order_type': signal.get('order_type', ORDER_TYPE_MARKET),
                'product': signal.get('product', PRODUCT_MIS)
            }

            # Add price for limit orders
            if signal.get('price'):
                order_params['price'] = signal['price']

            # Add trigger price for SL orders
            if signal.get('trigger_price'):
                order_params['trigger_price'] = signal['trigger_price']

            order_id = self.kite.place_order(**order_params)

            log_trade(
                action=signal['action'],
                symbol=signal['symbol'],
                qty=signal['quantity'],
                order_id=order_id,
                order_type=signal.get('order_type', ORDER_TYPE_MARKET),
                source=signal.get('source', 'UNKNOWN'),
                reason=signal.get('reason', '')
            )

            return order_id

        except Exception as e:
            log_error("EXECUTOR", f"Order failed: {str(e)}", e)
            return None

    def modify_order(self, order_id, variety=VARIETY_REGULAR, **kwargs):
        """Modify an existing order."""
        if not self.connected:
            return None

        try:
            self.kite.modify_order(variety=variety, order_id=order_id, **kwargs)
            self.logger.info(f"Order modified: {order_id}")
            return True
        except Exception as e:
            log_error("EXECUTOR", f"Modify failed: {str(e)}")
            return False

    def cancel_order(self, order_id, variety=VARIETY_REGULAR):
        """Cancel an order."""
        if not self.connected:
            return None

        try:
            self.kite.cancel_order(variety=variety, order_id=order_id)
            self.logger.info(f"Order cancelled: {order_id}")
            log_trade(action="CANCEL", symbol="", order_id=order_id)
            return True
        except Exception as e:
            log_error("EXECUTOR", f"Cancel failed: {str(e)}")
            return False

    def get_positions(self):
        """Get current positions."""
        if not self.connected:
            return None

        try:
            positions = self.kite.positions()
            return positions
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get positions: {str(e)}")
            return None

    def get_orders(self):
        """Get today's orders."""
        if not self.connected:
            return None

        try:
            orders = self.kite.orders()
            return orders
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get orders: {str(e)}")
            return None

    def get_margins(self):
        """Get available margins."""
        if not self.connected:
            return None

        try:
            margins = self.kite.margins()
            return margins
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get margins: {str(e)}")
            return None

    def get_ltp(self, symbol, exchange=EXCHANGE_NSE):
        """
        Get last traded price with retry logic and enhanced logging.

        Args:
            symbol: Trading symbol
            exchange: Exchange (NSE, NFO, etc.)

        Returns:
            Last traded price, or None if failed
        """
        if not self.connected:
            self.logger.warning("get_ltp: Not connected to broker")  # Changed from debug to warning
            return None

        instrument = f"{exchange}:{symbol}"

        # Use retry wrapper
        ltp_data = self._retry_api_call(
            self.kite.ltp,
            "get_ltp",
            [instrument]
        )

        if ltp_data and instrument in ltp_data:
            ltp = ltp_data[instrument]['last_price']
            self.logger.info(f"get_ltp: {instrument} = ₹{ltp:.2f}")  # Changed to INFO level
            return ltp
        else:
            self.logger.error(f"get_ltp: No data for {instrument}")  # Changed to ERROR level
            return None

    def get_historical_data(self, instrument_token, from_date, to_date, interval="minute"):
        """
        Get historical data for backtesting/analysis with retry logic.

        Args:
            instrument_token: Instrument token
            from_date: Start datetime
            to_date: End datetime
            interval: Candle interval (minute, day, etc.)

        Returns:
            List of OHLCV candles, or None if failed
        """
        if not self.connected:
            self.logger.debug("get_historical_data: Not connected to broker")
            return None

        self.logger.debug(
            f"get_historical_data: Token={instrument_token}, "
            f"From={from_date.strftime('%Y-%m-%d %H:%M')}, "
            f"To={to_date.strftime('%Y-%m-%d %H:%M')}, "
            f"Interval={interval}"
        )

        # Use retry wrapper
        data = self._retry_api_call(
            self.kite.historical_data,
            "get_historical_data",
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )

        if data:
            self.logger.debug(f"get_historical_data: Retrieved {len(data)} candles")
        else:
            self.logger.warning("get_historical_data: No data retrieved")

        return data

    def get_instruments(self, exchange=EXCHANGE_NSE):
        """
        Get list of instruments for an exchange with retry logic.

        Args:
            exchange: Exchange name (NSE, NFO, etc.)

        Returns:
            List of instrument dicts, or None if failed
        """
        if not self.connected:
            self.logger.debug("get_instruments: Not connected to broker")
            return None

        self.logger.debug(f"get_instruments: Fetching instruments for {exchange}")

        # Use retry wrapper
        instruments = self._retry_api_call(
            self.kite.instruments,
            "get_instruments",
            exchange
        )

        if instruments:
            self.logger.debug(f"get_instruments: Retrieved {len(instruments)} instruments")
        else:
            self.logger.warning(f"get_instruments: No instruments for {exchange}")

        return instruments

    def get_instrument_token(self, symbol, exchange=EXCHANGE_NSE):
        """Get instrument token for a symbol."""
        if not self.connected:
            return None

        try:
            instruments = self.kite.instruments(exchange)
            for inst in instruments:
                if inst['tradingsymbol'] == symbol:
                    return inst['instrument_token']
            return None
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get instrument token for {symbol}: {str(e)}")
            return None

    def get_order_history(self, order_id):
        """Get order history/status to retrieve fill price."""
        if not self.connected:
            return None

        try:
            order_history = self.kite.order_history(order_id)
            if order_history:
                # Return the latest status
                return order_history[-1]
            return None
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get order history: {str(e)}")
            return None

    def get_api_usage_stats(self):
        """
        Get current API usage statistics.

        Returns:
            dict with API call count, limit, and remaining calls
        """
        # Ensure counter is up to date for current day
        self._check_api_rate_limit()

        remaining = max(0, self.max_api_calls_per_day - self.api_call_count)
        usage_percent = (self.api_call_count / self.max_api_calls_per_day) * 100

        return {
            'date': self.api_call_date.isoformat(),
            'calls_made': self.api_call_count,
            'calls_limit': self.max_api_calls_per_day,
            'calls_remaining': remaining,
            'usage_percent': usage_percent,
            'limit_reached': self.api_limit_reached
        }

##############################################
# TRADE EXECUTOR (Main Class)
##############################################

class TradeExecutor:
    """
    Main executor class that manages broker interaction.
    Handles risk management and order routing.
    """

    def __init__(self, broker=BROKER):
        self.logger = setup_logger("EXECUTOR")
        self.broker = self._get_broker(broker)
        self.daily_pnl = 0
        self.daily_trades = 0
        self.positions = {}

    def _get_broker(self, broker_name):
        """Get broker implementation based on name."""
        brokers = {
            'kite': KiteExecutor,
            # Future: 'angel': AngelExecutor,
            # Future: 'icici': ICICIExecutor,
        }

        if broker_name not in brokers:
            raise ValueError(f"Unsupported broker: {broker_name}")

        return brokers[broker_name]()

    def connect(self):
        """Connect to broker."""
        return self.broker.connect()

    def execute(self, signal):
        """
        Execute a trading signal with risk checks.

        Args:
            signal: Trading signal from a bot

        Returns:
            order_id if successful, None otherwise
        """
        # Risk check: Max daily loss
        if self.daily_pnl < -MAX_LOSS_PER_DAY:
            self.logger.warning(f"Max daily loss reached: Rs. {self.daily_pnl}")
            log_system(f"RISK BLOCK | Max daily loss reached | P&L: {self.daily_pnl}")
            return None

        # Execute the order
        order_id = self.broker.place_order(signal)

        if order_id:
            self.daily_trades += 1
            self.positions[signal['symbol']] = {
                'order_id': order_id,
                'entry_price': signal.get('price', 0),
                'quantity': signal['quantity'],
                'stop_loss': signal.get('stop_loss'),
                'target': signal.get('target'),
                'source': signal.get('source'),
                'exchange': signal.get('exchange', EXCHANGE_NSE)
            }

        return order_id

    def exit_position(self, symbol, reason="Manual exit"):
        """Exit a position."""
        if symbol not in self.positions:
            self.logger.warning(f"No position found for {symbol}")
            return None

        position = self.positions[symbol]

        exit_signal = {
            'source': position.get('source', 'EXECUTOR'),
            'action': TRANSACTION_SELL,
            'symbol': symbol,
            'exchange': position.get('exchange', EXCHANGE_NSE),
            'quantity': position['quantity'],
            'order_type': ORDER_TYPE_MARKET,
            'product': PRODUCT_MIS,
            'reason': reason
        }

        order_id = self.broker.place_order(exit_signal)

        if order_id:
            del self.positions[symbol]
            log_position("CLOSED", symbol, reason=reason)

        return order_id

    def get_positions(self):
        """Get current positions from broker."""
        return self.broker.get_positions()

    def get_orders(self):
        """Get today's orders."""
        return self.broker.get_orders()

    def get_margins(self):
        """Get available margins."""
        return self.broker.get_margins()

    def get_ltp(self, symbol, exchange=EXCHANGE_NSE):
        """Get last traded price."""
        return self.broker.get_ltp(symbol, exchange)

    def get_historical_data(self, instrument_token, from_date, to_date, interval="minute"):
        """Get historical data."""
        return self.broker.get_historical_data(instrument_token, from_date, to_date, interval)

    def get_instruments(self, exchange=EXCHANGE_NSE):
        """Get list of instruments for an exchange."""
        return self.broker.get_instruments(exchange)

    def get_instrument_token(self, symbol, exchange=EXCHANGE_NSE):
        """Get instrument token for a symbol."""
        return self.broker.get_instrument_token(symbol, exchange)

    def get_order_history(self, order_id):
        """Get order history/status to retrieve fill price."""
        return self.broker.get_order_history(order_id)

    def update_daily_pnl(self, pnl):
        """Update daily P&L tracking."""
        self.daily_pnl += pnl
        self.logger.info(f"Daily P&L updated: Rs. {self.daily_pnl}")

    def reset_daily_stats(self):
        """Reset daily statistics (call at start of day)."""
        self.daily_pnl = 0
        self.daily_trades = 0
        self.positions = {}
        log_system("Daily stats reset")

    def get_daily_summary(self):
        """Get daily trading summary."""
        return {
            'date': datetime.date.today(),
            'trades': self.daily_trades,
            'pnl': self.daily_pnl,
            'open_positions': len(self.positions)
        }
