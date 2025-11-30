##############################################
# TRADE EXECUTOR
# Broker-agnostic execution layer
# Currently supports: Kite Connect
# Future: Angel, ICICI, etc.
##############################################

import datetime
from abc import ABC, abstractmethod
from kiteconnect import KiteConnect

from common.config import (
    API_KEY, ACCESS_TOKEN, BROKER,
    EXCHANGE_NSE, EXCHANGE_NFO,
    TRANSACTION_BUY, TRANSACTION_SELL,
    ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT, ORDER_TYPE_SL,
    PRODUCT_MIS, PRODUCT_CNC, PRODUCT_NRML,
    VARIETY_REGULAR,
    MAX_LOSS_PER_DAY, MAX_CAPITAL_DEPLOYED
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
        """Get last traded price."""
        if not self.connected:
            return None

        try:
            instrument = f"{exchange}:{symbol}"
            ltp_data = self.kite.ltp([instrument])
            return ltp_data[instrument]['last_price']
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get LTP: {str(e)}")
            return None

    def get_historical_data(self, instrument_token, from_date, to_date, interval="minute"):
        """Get historical data for backtesting/analysis."""
        if not self.connected:
            return None

        try:
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            return data
        except Exception as e:
            log_error("EXECUTOR", f"Failed to get historical data: {str(e)}")
            return None

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
                'source': signal.get('source')
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
