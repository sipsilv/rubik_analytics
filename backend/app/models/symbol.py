from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Date, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class SymbolStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class Symbol(Base):
    __tablename__ = "symbols"
    __table_args__ = (
        UniqueConstraint('exchange', 'trading_symbol', name='uq_symbol_exchange_trading_symbol'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # CORE IDENTIFIERS (REQUIRED)
    exchange = Column(String, nullable=False, index=True)  # NSE, BSE
    trading_symbol = Column(String, nullable=False, index=True)  # RELIANCE-EQ, NIFTY23DECFUT
    
    # OPTIONAL FIELDS
    exchange_token = Column(String, nullable=True)
    name = Column(String, nullable=True)
    instrument_type = Column(String, nullable=True)  # EQ, FUT, OPT, INDEX
    segment = Column(String, nullable=True)
    series = Column(String, nullable=True)
    isin = Column(String, nullable=True)
    expiry_date = Column(Date, nullable=True)
    strike_price = Column(Float, nullable=True)
    lot_size = Column(Integer, nullable=True)
    
    # SYSTEM FIELDS
    status = Column(String, default="ACTIVE")
    source = Column(String, default="MANUAL")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

