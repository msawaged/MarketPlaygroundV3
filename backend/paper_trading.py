import os
# backend/paper_trading.py
import sqlite3
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import yfinance as yf
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class PositionType(Enum):
    LONG = "long"
    SHORT = "short"
    CALL = "call"
    PUT = "put"
    SPREAD = "spread"

@dataclass
class Order:
    order_id: str
    user_id: str
    ticker: str
    order_type: OrderType
    position_type: PositionType
    quantity: int
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    status: OrderStatus
    strategy_id: str
    belief: str
    created_at: datetime
    filled_at: Optional[datetime] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: int = 0
    commission: Decimal = Decimal('0.00')
    
SHARE_STEP = Decimal('0.0001')  # practice shares are fractional to 4 decimals


def _shares_txt(q) -> str:
    """2.5 shares, 1 share: for sale messages."""
    n = float(q)
    t = f"{n:,.4f}".rstrip("0").rstrip(".")
    return f"{t} share{'' if n == 1 else 's'}"


def _clock() -> dict:
    """Market open/closed from the shared v4 market clock (Alpaca, holiday-aware)."""
    try:
        from backend.v4 import market as _m
        return _m.clock()
    except Exception:
        return {"is_open": True}


def _when(iso) -> str:
    try:
        from backend.v4 import brokerage as _b
        return _b._when(iso)
    except Exception:
        return "next trading day, 9:30am ET"


def _open_after(ticker: str, after_iso: str):
    """(date, opening price) of the first session that opened after this order was placed, or None."""
    from backend.v4 import market as _m
    after = datetime.fromisoformat(str(after_iso).replace("Z", "+00:00"))
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    return _m.session_open_after(ticker, after)


class PaperTradingEngine:
    def __init__(self, db_path: str = None):
        # MP_DATA_DIR points at a persistent disk on Render so practice portfolios survive deploys.
        if db_path is None:
            data_dir = os.getenv("MP_DATA_DIR", "backend")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "paper_trading.db")
        self.db_path = db_path
        # Commission-free, like today's US brokerages for stocks and ETFs (practice should feel like the real thing)
        self.commission_rate = Decimal('0.00')
        self.min_commission = Decimal('0.00')
        self.starting_balance = Decimal('100000.00')  # $100k starting
        self.max_position_size = Decimal('0.20')  # 20% max per position
        self.margin_requirement = Decimal('0.25')  # 25% margin for shorts
        self._lock = threading.Lock()
        
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database with proper schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    cash_balance DECIMAL(15,2) NOT NULL DEFAULT 100000.00,
                    equity_value DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    margin_used DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    buying_power DECIMAL(15,2) NOT NULL DEFAULT 100000.00,
                    total_pnl DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    day_pnl DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price DECIMAL(10,4),
                    stop_price DECIMAL(10,4),
                    status TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    belief TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    filled_at TIMESTAMP,
                    filled_price DECIMAL(10,4),
                    filled_quantity REAL DEFAULT 0,
                    commission DECIMAL(8,2) DEFAULT 0.00,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    avg_price DECIMAL(10,4) NOT NULL,
                    current_price DECIMAL(10,4) NOT NULL,
                    market_value DECIMAL(15,2) NOT NULL,
                    unrealized_pnl DECIMAL(15,2) NOT NULL,
                    realized_pnl DECIMAL(15,2) DEFAULT 0.00,
                    day_pnl DECIMAL(15,2) DEFAULT 0.00,
                    strategy_id TEXT NOT NULL,
                    belief TEXT NOT NULL,
                    opened_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,  -- BUY, SELL, DIVIDEND, FEE
                    quantity REAL NOT NULL,
                    price DECIMAL(10,4) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    commission DECIMAL(8,2) NOT NULL,
                    net_amount DECIMAL(15,2) NOT NULL,
                    executed_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (order_id) REFERENCES orders (order_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    ticker TEXT NOT NULL,
                    price DECIMAL(10,4) NOT NULL,
                    bid DECIMAL(10,4),
                    ask DECIMAL(10,4),
                    volume INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    PRIMARY KEY (ticker, timestamp)
                )
            """)
            
            # One row per sale, with what it cost, so a sold position leaves a record (Closed trades on Portfolio).
            conn.execute("""
                CREATE TABLE IF NOT EXISTS closed_trades (
                    trade_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    proceeds REAL NOT NULL,
                    belief TEXT,
                    opened_at TEXT,
                    closed_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_closed_trades_user ON closed_trades(user_id, closed_at)")

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market_data_ticker ON market_data(ticker)")
            
    @contextmanager
    def _get_db_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
            
    def _get_real_market_price(self, ticker: str) -> Decimal:
        """Latest price from the same feed the idea cards use (Alpaca via backend.v4.market), then Yahoo, then
        the last price we cached. Never a made-up number: if nothing is available the trade is refused."""
        try:
            from backend.v4 import market as _m
            p = float(_m.latest_price(ticker))
            if p > 0:
                return Decimal(str(round(p, 4)))
        except Exception as e:
            logger.warning(f"Primary price feed failed for {ticker}: {e}")
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period="1d", interval="1m")
            if not data.empty:
                latest_price = data['Close'].iloc[-1]
                return Decimal(str(round(latest_price, 4)))
        except Exception as e:
            logger.warning(f"Failed to fetch price for {ticker}: {e}")
        cached = self._get_cached_price(ticker)
        if cached is None:
            raise ValueError(f"Couldn't get a live price for {ticker} right now. Please try again in a minute.")
        return cached

    def _get_cached_price(self, ticker: str) -> Optional[Decimal]:
        """Get last cached price from database"""
        with self._get_db_connection() as conn:
            result = conn.execute("""
                SELECT price FROM market_data 
                WHERE ticker = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (ticker,)).fetchone()
            
            if result:
                return Decimal(str(result['price']))
            
            return None  # no invented fallback prices: a practice fill must be a real price
    
    def _calculate_commission(self, quantity: int, price: Decimal) -> Decimal:
        """Calculate commission based on trade value"""
        trade_value = Decimal(str(quantity)) * Decimal(str(price))
        commission = trade_value * self.commission_rate
        return max(commission, self.min_commission)
    
    def _initialize_user(self, user_id: str) -> None:
        """Initialize new user account"""
        with self._get_db_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, cash_balance, buying_power)
                VALUES (?, ?, ?)
            """, (user_id, self.starting_balance, self.starting_balance))
    
    def execute_paper_trade(self, user_id: str, strategy_data: dict, belief: str):
        """Execute a paper trade with full validation and risk management"""
        with self._lock:
            try:
                self._initialize_user(user_id)
                
                # Extract strategy details
                ticker = strategy_data.get('ticker', '').upper()
                strategy_type = strategy_data.get('type', '')
                trade_legs = strategy_data.get('trade_legs', [])
                
                if not ticker or not trade_legs:
                    return {"status": "error", "message": "Invalid strategy data"}
                
                # Get current market price
                current_price = self._get_real_market_price(ticker)
                
                # Process each trade leg
                orders = []
                total_cost = Decimal('0.00')
                
                # Extract investment amount from strategy data
                target_investment = strategy_data.get('investment_amount', 1000)  # Default $1000 if not specified

                for leg in trade_legs:
                    action = leg.get('action', '').lower()
                    
                    # Calculate optimal position size based on investment amount
                    if 'buy' in action:
                        # For stocks: quantity = investment_amount / price (rounded down)
                        if strategy_data.get('asset_class') == 'options':
                            # For options: account for premium costs
                            estimated_premium = current_price * 0.05  # Rough premium estimate
                            quantity = max(1, int(target_investment / (estimated_premium * 100)))  # Options are per 100 shares
                        else:
                            # For stocks: fractional shares, like real brokers, so $1,000 buys $1,000 of the stock
                            # (whole shares meant $1,000 of a $5,000 stock bought $5,000, and $1,000 of a $185 one bought $925).
                            quantity = (Decimal(str(target_investment)) / current_price).quantize(SHARE_STEP, rounding=ROUND_DOWN)
                            if quantity <= 0:
                                return {"status": "error", "message": f"That amount is too small to buy any {ticker}. Try at least $1."}
                    else:
                        quantity = Decimal(str(leg.get('quantity', 1)))  # Keep original for sell orders
                    
                    # Determine position type
                    if 'buy' in action:
                        position_type = PositionType.LONG
                        cost = quantity * current_price
                    elif 'sell' in action:
                        position_type = PositionType.SHORT
                        cost = quantity * current_price * self.margin_requirement
                    else:
                        continue
                    
                    commission = self._calculate_commission(quantity, current_price)
                    total_cost += cost + commission
                    
                    # Create order
                    order = Order(
                        order_id=str(uuid.uuid4()),
                        user_id=user_id,
                        ticker=ticker,
                        order_type=OrderType.MARKET,
                        position_type=position_type,
                        quantity=quantity,
                        price=current_price,
                        stop_price=None,
                        status=OrderStatus.PENDING,
                        strategy_id=str(uuid.uuid4()),
                        belief=belief,
                        created_at=datetime.now(),
                        commission=commission
                    )
                    orders.append(order)
                
                # Validate buying power
                user_data = self._get_user_data(user_id)
                if total_cost > user_data['buying_power']:
                    return {
                        "status": "error", 
                        "message": f"Insufficient buying power. Required: ${total_cost}, Available: ${user_data['buying_power']}"
                    }
                
                # Market closed: queue the orders like a real broker would. Buying power is held now;
                # the fill happens at the next session's opening price (see _fill_queued).
                clk = _clock()
                if not clk.get("is_open"):
                    now_utc = datetime.now(timezone.utc)
                    with self._get_db_connection() as conn:
                        for order in orders:
                            conn.execute("""
                                INSERT INTO orders
                                (order_id, user_id, ticker, order_type, position_type, quantity,
                                 price, status, strategy_id, belief, created_at, commission)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (order.order_id, order.user_id, order.ticker, order.order_type.value,
                                  order.position_type.value, order.quantity, float(order.price),
                                  OrderStatus.PENDING.value, order.strategy_id, order.belief,
                                  now_utc.isoformat(), float(order.commission)))
                        conn.execute("UPDATE users SET buying_power = buying_power - ? WHERE user_id = ?",
                                     (float(total_cost), user_id))
                    return {
                        "status": "queued",
                        "message": f"The market is closed, so your {ticker} order is queued. It fills at the opening price "
                                   f"({_when(clk.get('next_open'))}). The price can be different from now.",
                        "next_open": clk.get("next_open"),
                        "orders": [asdict(o) for o in orders],
                        "total_cost": float(total_cost),
                        "current_price": float(current_price),
                    }

                # Execute orders
                executed_orders = []
                with self._get_db_connection() as conn:
                    for order in orders:
                        # Fill order immediately (paper trading)
                        order.status = OrderStatus.FILLED
                        order.filled_at = datetime.now()
                        order.filled_price = current_price
                        order.filled_quantity = order.quantity
                        
                        # Insert order record
                        conn.execute("""
                            INSERT INTO orders 
                            (order_id, user_id, ticker, order_type, position_type, quantity, 
                             price, status, strategy_id, belief, created_at, filled_at, 
                             filled_price, filled_quantity, commission)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            order.order_id, order.user_id, order.ticker, 
                            order.order_type.value, order.position_type.value,
                            order.quantity, order.price, order.status.value,
                            order.strategy_id, order.belief, order.created_at,
                            order.filled_at, order.filled_price, order.filled_quantity,
                            order.commission
                        ))
                        
                        # Create/update position
                        self._update_position(conn, order, current_price)
                        
                        # Record transaction
                        transaction_type = "BUY" if order.position_type == PositionType.LONG else "SELL_SHORT"
                        net_amount = (order.filled_quantity * order.filled_price) + order.commission
                        
                        conn.execute("""
                            INSERT INTO transactions 
                            (transaction_id, user_id, order_id, ticker, transaction_type,
                             quantity, price, amount, commission, net_amount, executed_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            str(uuid.uuid4()), order.user_id, order.order_id,
                            order.ticker, transaction_type, order.filled_quantity,
                            order.filled_price, order.filled_quantity * order.filled_price,
                            order.commission, net_amount, order.filled_at
                        ))
                        
                        executed_orders.append(order)
                    
                    # Update user cash balance
                    cash_impact = -total_cost if orders[0].position_type == PositionType.LONG else Decimal('0.00')
                    conn.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance + ?,
                            buying_power = buying_power - ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (cash_impact, total_cost, user_id))
                
                # Update market data cache
                self._cache_market_data(ticker, current_price)
                
                return {
                    "status": "success",
                    "message": f"Successfully executed {strategy_type} strategy on {ticker}",
                    "orders": [asdict(order) for order in executed_orders],
                    "total_cost": float(total_cost),
                    "current_price": float(current_price)
                }
                
            except Exception as e:
                logger.error(f"Trade execution failed: {e}")
                return {"status": "error", "message": f"Trade execution failed: {str(e)}"}
    
    def _update_position(self, conn, order: Order, current_price: Decimal):
        """Update or create position from order"""
        # Check if position exists
        existing = conn.execute("""
            SELECT * FROM positions 
            WHERE user_id = ? AND ticker = ? AND position_type = ?
        """, (order.user_id, order.ticker, order.position_type.value)).fetchone()
        
        if existing:
            # Update existing position (average price). sqlite hands back floats; keep the math in Decimal.
            fq = Decimal(str(order.filled_quantity))
            fp = Decimal(str(order.filled_price))
            cp = Decimal(str(current_price))
            old_q = Decimal(str(existing['quantity']))
            old_avg = Decimal(str(existing['avg_price']))
            total_quantity = old_q + fq
            new_avg_price = ((old_q * old_avg) + (fq * fp)) / total_quantity
            market_value = total_quantity * cp
            unrealized_pnl = market_value - (total_quantity * new_avg_price)

            conn.execute("""
                UPDATE positions 
                SET quantity = ?, avg_price = ?, current_price = ?,
                    market_value = ?, unrealized_pnl = ?, updated_at = CURRENT_TIMESTAMP
                WHERE position_id = ?
            """, (total_quantity, float(new_avg_price), float(cp),
                  float(market_value), float(unrealized_pnl), existing['position_id']))
        else:
            # Create new position
            market_value = order.filled_quantity * current_price
            unrealized_pnl = market_value - (order.filled_quantity * order.filled_price)
            
            conn.execute("""
                INSERT INTO positions 
                (position_id, user_id, ticker, position_type, quantity, avg_price,
                 current_price, market_value, unrealized_pnl, strategy_id, belief, opened_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), order.user_id, order.ticker, order.position_type.value,
                order.filled_quantity, order.filled_price, current_price,
                market_value, unrealized_pnl, order.strategy_id, order.belief, order.filled_at
            ))
    
    def _cache_market_data(self, ticker: str, price: Decimal):
        """Cache market data for later use. Best effort: a cache hiccup must never turn a trade that
        already went through into an error (two trades in the same second used to do exactly that)."""
        try:
            with self._get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO market_data (ticker, price, timestamp)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (ticker, float(price)))
        except Exception as e:
            logger.warning(f"price cache skipped for {ticker}: {e}")
    
    def _get_user_data(self, user_id: str) -> Dict:
        """Get user account data"""
        with self._get_db_connection() as conn:
            result = conn.execute("""
                SELECT * FROM users WHERE user_id = ?
            """, (user_id,)).fetchone()
            
            if result:
                return dict(result)
            return {}
    
    def _pending(self, conn, user_id: str):
        return conn.execute("SELECT * FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY created_at",
                            (user_id,)).fetchall()

    def _fill_queued(self, user_id: str) -> int:
        """Fill orders placed while the market was closed, at the opening price of the next session."""
        filled = 0
        with self._lock, self._get_db_connection() as conn:
            for o in self._pending(conn, user_id):
                try:
                    hit = _open_after(o['ticker'], o['created_at'])
                except Exception as e:
                    logger.warning(f"queued fill check failed for {o['ticker']}: {e}")
                    continue
                if not hit:
                    continue
                day, open_px = hit
                from backend.v4 import market as _m
                when = _m._session_open_dt(day).isoformat()  # 9:30 New York with that day's offset (-05:00 in winter)
                px = Decimal(str(round(open_px, 4)))
                if o['order_type'] == 'close':
                    pos = conn.execute("SELECT * FROM positions WHERE position_id = ? AND user_id = ?",
                                       (o['strategy_id'], user_id)).fetchone()
                    if pos:
                        self._close_at(conn, pos, px, executed_at=when, qty=o['quantity'])
                    conn.execute("UPDATE orders SET status = ?, filled_at = ?, filled_price = ?, filled_quantity = ? WHERE order_id = ?",
                                 ('filled' if pos else 'cancelled', when, float(px), o['quantity'] if pos else 0, o['order_id']))
                    filled += 1
                    continue
                qty = Decimal(str(o['quantity']))
                est_px = Decimal(str(o['price']))
                est_comm = Decimal(str(o['commission'] or 0))
                is_long = o['position_type'] == PositionType.LONG.value
                mult = Decimal('1') if is_long else Decimal(str(self.margin_requirement))
                held = qty * est_px * mult + est_comm
                comm = Decimal(str(self._calculate_commission(qty, px)))
                actual = qty * px * mult + comm
                # If it opened higher than the estimate, buy only what the account can afford
                # (the money held for this order + spare buying power), like a real broker would.
                u = conn.execute("SELECT buying_power FROM users WHERE user_id = ?", (user_id,)).fetchone()
                available = held + Decimal(str(u['buying_power'] if u else 0))
                while qty > 0 and actual > available:
                    qty -= max(1, qty // 20)
                    comm = Decimal(str(self._calculate_commission(qty, px))) if qty > 0 else Decimal('0')
                    actual = qty * px * mult + comm
                if qty <= 0:
                    conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (o['order_id'],))
                    conn.execute("UPDATE users SET buying_power = buying_power + ? WHERE user_id = ?", (float(held), user_id))
                    continue
                order = Order(order_id=o['order_id'], user_id=user_id, ticker=o['ticker'], order_type=OrderType.MARKET,
                              position_type=PositionType(o['position_type']), quantity=qty, price=est_px, stop_price=None,
                              status=OrderStatus.FILLED, strategy_id=o['strategy_id'], belief=o['belief'],
                              created_at=o['created_at'], filled_at=when, filled_price=px, filled_quantity=qty, commission=comm)
                conn.execute("UPDATE orders SET status = 'filled', filled_at = ?, filled_price = ?, filled_quantity = ?, commission = ? WHERE order_id = ?",
                             (when, float(px), qty, float(comm), o['order_id']))
                self._update_position(conn, order, px)
                conn.execute("""
                    INSERT INTO transactions (transaction_id, user_id, order_id, ticker, transaction_type,
                                              quantity, price, amount, commission, net_amount, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), user_id, o['order_id'], o['ticker'], "BUY" if is_long else "SELL_SHORT",
                      qty, float(px), float(qty * px), float(comm), float(qty * px + comm), when))
                # swap the hold for the real cost
                conn.execute("UPDATE users SET cash_balance = cash_balance - ?, buying_power = buying_power + ? - ? WHERE user_id = ?",
                             (float(actual) if is_long else 0.0, float(held), float(actual), user_id))
                filled += 1
        return filled

    def cancel_queued(self, user_id: str, order_id: str) -> dict:
        """Cancel an order that hasn't filled yet; a held buy gives its buying power back."""
        with self._lock, self._get_db_connection() as conn:
            o = conn.execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ? AND status = 'pending'",
                             (order_id, user_id)).fetchone()
            if not o:
                return {"status": "error", "message": "That order already filled or was cancelled."}
            if o['order_type'] != 'close':
                mult = Decimal('1') if o['position_type'] == PositionType.LONG.value else Decimal(str(self.margin_requirement))
                held = Decimal(str(o['quantity'])) * Decimal(str(o['price'])) * mult + Decimal(str(o['commission'] or 0))
                conn.execute("UPDATE users SET buying_power = buying_power + ? WHERE user_id = ?", (float(held), user_id))
            conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
        return {"status": "cancelled", "message": f"Cancelled the queued {o['ticker']} order."}

    def get_portfolio(self, user_id: str, force_refresh: bool = True):
        """Get comprehensive portfolio with real-time data"""
        self._initialize_user(user_id)
        try:
            self._fill_queued(user_id)
        except Exception as e:
            logger.warning(f"queued fills skipped: {e}")
        
        with self._get_db_connection() as conn:
            # Get user account data
            user_data = conn.execute("""
                SELECT * FROM users WHERE user_id = ?
            """, (user_id,)).fetchone()
            
            # Get all positions with current prices
            positions = conn.execute("""
                SELECT * FROM positions WHERE user_id = ?
            """, (user_id,)).fetchall()
            
            # Update positions with live prices
            portfolio_positions = []
            total_equity = Decimal('0.00')
            total_unrealized_pnl = Decimal('0.00')
            
            for pos in positions:
                try:
                    current_price = self._get_real_market_price(pos['ticker'])
                except ValueError:  # feed down: keep the last mark rather than break the whole portfolio
                    current_price = Decimal(str(pos['current_price'] or pos['avg_price']))
                market_value = Decimal(str(pos['quantity'])) * current_price
                unrealized_pnl = market_value - (Decimal(str(pos['quantity'])) * Decimal(str(pos['avg_price'])))

                
                # Update position in database
                conn.execute("""
                    UPDATE positions 
                    SET current_price = ?, market_value = ?, unrealized_pnl = ?
                    WHERE position_id = ?
                """, (current_price, market_value, unrealized_pnl, pos['position_id']))
                
                position_data = {
                    'position_id': pos['position_id'],
                    'ticker': pos['ticker'],
                    'position_type': pos['position_type'],
                    'quantity': pos['quantity'],
                    'avg_price': float(pos['avg_price']),
                    'current_price': float(current_price),
                    'market_value': float(market_value),
                    'unrealized_pnl': float(unrealized_pnl),
                    'unrealized_pnl_pct': float((unrealized_pnl / (Decimal(str(pos['quantity'])) * Decimal(str(pos['avg_price'])))) * 100),
                    'strategy_id': pos['strategy_id'],
                    'belief': pos['belief'],
                    'opened_at': pos['opened_at']
                }
                portfolio_positions.append(position_data)
                
                total_equity += market_value
                total_unrealized_pnl += unrealized_pnl
            
            # Calculate portfolio metrics
            total_value = Decimal(str(user_data['cash_balance'])) + total_equity
            total_return = total_value - self.starting_balance
            total_return_pct = (total_return / self.starting_balance) * 100
            
            clk = _clock()
            queued = [{
                "order_id": o['order_id'], "ticker": o['ticker'],
                "side": "sell" if o['order_type'] == 'close' else ("buy" if o['position_type'] == 'long' else "short"),
                "quantity": o['quantity'], "est_price": float(o['price']), "placed_at": o['created_at'],
            } for o in self._pending(conn, user_id)]
            return {
                "user_id": user_id,
                "market": {"is_open": bool(clk.get("is_open")), "next_open": clk.get("next_open"),
                           "next_open_text": _when(clk.get("next_open"))},
                "queued_orders": queued,
                "account": {
                    "cash_balance": float(user_data['cash_balance']),
                    "equity_value": float(total_equity),
                    "total_value": float(total_value),
                    "buying_power": float(user_data['buying_power']),
                    "day_pnl": float(user_data['day_pnl']),
                    "total_pnl": float(total_return),
                    "total_return_pct": float(total_return_pct)
                },
                "positions": portfolio_positions,
                "summary": {
                    "total_positions": len(portfolio_positions),
                    "unrealized_pnl": float(total_unrealized_pnl),
                    "starting_balance": float(self.starting_balance),
                    "performance_grade": self._calculate_performance_grade(total_return_pct)
                }
            }
    
    def _calculate_performance_grade(self, return_pct: Decimal) -> str:
        """Calculate performance grade A-F"""
        if return_pct >= 20:
            return "A+"
        elif return_pct >= 15:
            return "A"
        elif return_pct >= 10:
            return "B+"
        elif return_pct >= 5:
            return "B"
        elif return_pct >= 0:
            return "C"
        elif return_pct >= -5:
            return "D"
        else:
            return "F"

    def get_leaderboard(self):
        """Get performance leaderboard"""
        with self._get_db_connection() as conn:
            users = conn.execute("""
                SELECT user_id, cash_balance,
                       (SELECT COALESCE(SUM(market_value), 0) FROM positions WHERE user_id = users.user_id) as equity_value
                FROM users
            """).fetchall()

            leaderboard = []
            for user in users:
                total_value = user['cash_balance'] + user['equity_value']
                total_return = total_value - float(self.starting_balance)
                total_return_pct = (total_return / float(self.starting_balance)) * 100 if self.starting_balance else 0.0
                leaderboard.append({
                    "user_id": user['user_id'],
                    "total_value": float(total_value),
                    "total_return": float(total_return),
                    "total_return_pct": float(total_return_pct),
                    "performance_grade": self._calculate_performance_grade(total_return_pct),
                })
            
            # Sort by return percentage
            leaderboard.sort(key=lambda x: x["total_return_pct"], reverse=True)
            
            return {"leaderboard": leaderboard[:25]}  # Top 25
    
    def _sell_qty(self, position, qty=None, fraction=None, amount_usd=None, price=None):
        """How many shares a sale covers: all of them, a share count, a fraction (0.25 = a quarter) or a dollar amount
        at `price`. Returns (Decimal shares, None) or (None, error). A sale leaving under $1 or one share step sells it all."""
        held = Decimal(str(position['quantity']))
        px = Decimal(str(price if price is not None else (position['current_price'] or position['avg_price'])))
        try:
            if fraction is not None:
                f = Decimal(str(fraction))
                if not (0 < f <= 1):
                    return None, "Pick a share of the position between 1% and 100%."
                want = held if f == 1 else (held * f).quantize(SHARE_STEP, rounding=ROUND_DOWN)
            elif amount_usd is not None:
                a = Decimal(str(amount_usd))
                if a <= 0:
                    return None, "Type an amount above $0."
                want = (a / px).quantize(SHARE_STEP, rounding=ROUND_DOWN) if px > 0 else held
            elif qty not in (None, ""):
                want = Decimal(str(qty))
                if want <= 0:
                    return None, "Pick at least some shares to sell."
            else:
                want = held
        except Exception:
            return None, "That amount isn't a number."
        if want <= 0:
            return None, f"That amount is too small to sell any {position['ticker']}."
        if want >= held or (held - want) * px < 1 or held - want < SHARE_STEP:
            want = held
        return want, None

    def close_position(self, user_id: str, position_id: str, qty: Optional[int] = None,
                       fraction: Optional[float] = None, amount_usd: Optional[float] = None):
        """Sell a position, all of it or part (shares, a fraction, or dollars), and realize P&L."""
        with self._lock:
            try:
                with self._get_db_connection() as conn:
                    # Get position
                    position = conn.execute("""
                        SELECT * FROM positions WHERE position_id = ? AND user_id = ?
                    """, (position_id, user_id)).fetchone()
                    
                    if not position:
                        return {"status": "error", "message": "Position not found"}

                    clk = _clock()
                    if not clk.get("is_open"):
                        est = position['current_price'] or position['avg_price']
                        want, err = self._sell_qty(position, qty, fraction, amount_usd, est)
                        if err:
                            return {"status": "error", "message": err}
                        dup = conn.execute("SELECT order_id FROM orders WHERE user_id = ? AND status = 'pending' AND order_type = 'close' AND strategy_id = ?",
                                           (user_id, position_id)).fetchone()
                        if dup:  # one queued sale per position (tapping twice doesn't queue two)
                            return {"status": "queued", "already": True,
                                    "message": f"A sale of {position['ticker']} is already queued for the opening price "
                                               f"({_when(clk.get('next_open'))}). Cancel it first to change it.",
                                    "next_open": clk.get("next_open")}
                        conn.execute("""
                            INSERT INTO orders (order_id, user_id, ticker, order_type, position_type, quantity,
                                                price, status, strategy_id, belief, created_at, commission)
                            VALUES (?, ?, ?, 'close', ?, ?, ?, 'pending', ?, ?, ?, 0)
                        """, (str(uuid.uuid4()), user_id, position['ticker'], position['position_type'],
                              float(want), float(est), position_id, position['belief'], datetime.now(timezone.utc).isoformat()))
                        part = "" if want >= Decimal(str(position['quantity'])) else f"{_shares_txt(want)} of "
                        return {"status": "queued",
                                "message": f"The market is closed, so selling {part}{position['ticker']} is queued for the opening price "
                                           f"({_when(clk.get('next_open'))}).",
                                "next_open": clk.get("next_open"), "quantity": float(want)}
                    px = self._get_real_market_price(position['ticker'])
                    want, err = self._sell_qty(position, qty, fraction, amount_usd, px)
                    if err:
                        return {"status": "error", "message": err}
                    return self._close_at(conn, position, px, qty=want)
            except Exception as e:
                logger.error(f"Failed to close position: {e}")
                return {"status": "error", "message": f"Failed to close position: {str(e)}"}

    def _close_at(self, conn, position, current_price, executed_at=None, qty=None):
        """Realize a position, or `qty` shares of it, at a given price (now, or a queued sale at the open)."""
        
        # Calculate realized P&L (sqlite returns floats; keep money math in Decimal)
        current_price = Decimal(str(current_price))
        avg = Decimal(str(position['avg_price']))
        held = Decimal(str(position['quantity']))
        qty_d = held if qty is None else min(held, Decimal(str(qty)))
        partial = qty_d < held
        if position['position_type'] == 'long':
            realized_pnl = (current_price - avg) * qty_d
            proceeds = qty_d * current_price
        else:  # short
            realized_pnl = (avg - current_price) * qty_d
            proceeds = qty_d * current_price
        
        commission = Decimal(str(self._calculate_commission(qty_d, current_price)))
        net_proceeds = proceeds - commission
        
        # Create closing order
        order_id = str(uuid.uuid4())
        transaction_type = "SELL" if position['position_type'] == 'long' else "BUY_TO_COVER"
        
        executed_at = executed_at or datetime.now(timezone.utc).isoformat()
        # Record transaction
        user_id = position['user_id']
        conn.execute("""
            INSERT INTO transactions 
            (transaction_id, user_id, order_id, ticker, transaction_type,
             quantity, price, amount, commission, net_amount, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), user_id, order_id, position['ticker'],
            transaction_type, float(qty_d), float(current_price),
            float(proceeds), float(commission), float(net_proceeds),
            executed_at
        ))
        
        conn.execute("""
            INSERT INTO closed_trades (trade_id, user_id, order_id, ticker, position_type, quantity, avg_price,
                                       exit_price, realized_pnl, proceeds, belief, opened_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), user_id, order_id, position['ticker'], position['position_type'],
              float(qty_d), float(avg), float(current_price), float(realized_pnl), float(net_proceeds),
              position['belief'], str(position['opened_at'] or ''),
              executed_at))

        # Update user balance
        conn.execute("""
            UPDATE users 
            SET cash_balance = cash_balance + ?,
                buying_power = buying_power + ?,
                total_pnl = total_pnl + ?
            WHERE user_id = ?
        """, (float(net_proceeds), float(net_proceeds), float(realized_pnl), user_id))
        
        # Remove the position, or keep what's left of it (same cost per share)
        if partial:
            left = held - qty_d
            conn.execute("UPDATE positions SET quantity = ?, market_value = ?, unrealized_pnl = ? WHERE position_id = ?",
                         (float(left), float(left * current_price),
                          float((current_price - avg) * left if position['position_type'] == 'long' else (avg - current_price) * left),
                          position['position_id']))
        else:
            conn.execute("""
                DELETE FROM positions WHERE position_id = ?
            """, (position['position_id'],))
        
        return {
            "status": "success",
            "message": (f"Sold {_shares_txt(qty_d)} of {position['ticker']}; {_shares_txt(held - qty_d)} left" if partial
                        else "Position closed successfully"),
            "quantity": float(qty_d), "remaining": float(held - qty_d) if partial else 0.0,
            "realized_pnl": float(realized_pnl),
            "proceeds": float(net_proceeds),
            "commission": float(commission)
        }

    def closed_trades(self, user_id: str, limit: int = 50) -> list:
        """Sold share positions, newest first: what they cost, what they sold for, the gain.
        Sales from before this record existed come from the transactions table with no cost known."""
        out = []
        with self._get_db_connection() as conn:
            for r in conn.execute("SELECT * FROM closed_trades WHERE user_id = ? ORDER BY closed_at DESC LIMIT ?",
                                  (user_id, limit)).fetchall():
                cost = r['avg_price'] * r['quantity']
                out.append({
                    "kind": "shares", "id": r['trade_id'], "ticker": r['ticker'], "position_type": r['position_type'],
                    "quantity": r['quantity'], "avg_price": round(r['avg_price'], 4), "exit_price": round(r['exit_price'], 4),
                    "cost": round(cost, 2), "proceeds": round(r['proceeds'], 2), "pnl": round(r['realized_pnl'], 2),
                    "pnl_pct": round(r['realized_pnl'] / cost * 100, 2) if cost > 0 else None,
                    "belief": r['belief'], "opened_at": r['opened_at'] or None, "closed_at": r['closed_at'],
                })
            legacy = conn.execute("""
                SELECT * FROM transactions WHERE user_id = ? AND transaction_type IN ('SELL', 'BUY_TO_COVER')
                AND order_id NOT IN (SELECT order_id FROM closed_trades WHERE user_id = ?)
                ORDER BY executed_at DESC LIMIT ?""", (user_id, user_id, limit)).fetchall()
            for t in legacy:
                out.append({
                    "kind": "shares", "id": t['transaction_id'], "ticker": t['ticker'],
                    "position_type": "long" if t['transaction_type'] == 'SELL' else "short",
                    "quantity": t['quantity'], "avg_price": None, "exit_price": round(float(t['price']), 4),
                    "cost": None, "proceeds": round(float(t['net_amount']), 2), "pnl": None, "pnl_pct": None,
                    "belief": None, "opened_at": None, "closed_at": str(t['executed_at']),
                })
        return out

    def evaluate_strategy_performance(self, evaluation_days: int = 7):
        """
        Auto-evaluate paper trading positions to generate ML training data.
        Replaces manual feedback buttons with objective market performance.
        """
        # Calculate cutoff date for mature positions
        cutoff_date = datetime.now() - timedelta(days=evaluation_days)
        
        training_labels = []
        
        with self._get_db_connection() as conn:
            # Get positions old enough to evaluate
            positions = conn.execute("""
                SELECT * FROM positions 
                WHERE opened_at < ?
            """, (cutoff_date,)).fetchall()
            
            for pos in positions:
                # Get current market price
                try:
                    current_price = self._get_real_market_price(pos['ticker'])
                except ValueError:
                    continue
                
                # Calculate P&L percentage
                entry_price = Decimal(str(pos['avg_price']))
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                
                # Auto-generate training label based on performance
                if pnl_pct >= 5.0:
                    label = "good"
                elif pnl_pct <= -5.0:
                    label = "bad"
                else:
                    label = "neutral"
                
                # Store training data
                training_labels.append({
                    'belief': pos['belief'],
                    'strategy': pos['strategy_id'],
                    'feedback': label,
                    'pnl_pct': float(pnl_pct),
                    'auto_generated': True
                })
        
        return training_labels

    def process_automatic_feedback(self, evaluation_days: int = 7):
        """
        Process paper trading performance and send to ML training pipeline.
        Integrates with existing feedback_handler system.
        """
        from backend.feedback_handler import save_feedback_entry
        
        # Get performance evaluations
        training_data = self.evaluate_strategy_performance(evaluation_days)
        
        processed_count = 0
        for result in training_data:
            # Send to existing feedback system with metadata
            save_feedback_entry(
                belief=result['belief'],
                strategy=result['strategy'], 
                result=result['feedback'],
                user_id="auto_evaluation",
                pnl_percent=result['pnl_pct'],
                source="paper_trading_performance",
                auto_generated=True,
                confidence=abs(result['pnl_pct']) / 10.0,  # Scale confidence
                notes=f"Auto-evaluated after {evaluation_days} days"
            )
            processed_count += 1
        
        return {"processed": processed_count, "message": f"Added {processed_count} automatic feedback entries"}    

# Create the singleton instance
paper_engine = PaperTradingEngine()
