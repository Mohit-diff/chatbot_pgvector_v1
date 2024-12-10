import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Uuid,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column

from datetime import datetime
from core.database.db import Base


class ChatbotModel(Base):
    __tablename__ = "chatbot"
    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    chunk_id = Column(Integer, nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    slack_user_id = Column(Text, nullable=True)


class Products(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    product_id = Column(Integer, primary_key=True, nullable=False)

    name = Column(String, primary_key=True)
    product_json = Column(String)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())


class Pages(Base):
    __tablename__ = "pages"
    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda _: str(uuid.uuid4())
    )
    page_id = Column(Integer, primary_key=True, nullable=False)

    page_name = Column(String, primary_key = True,index=True)
    page_json = Column(String)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    
class Orders(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key = True, default=lambda _: str(uuid.uuid4()))
    cust_ref = Column(String, primary_key=True, nullable=False)
    po_no = Column(String, primary_key=True)
    order_status = Column(String)
    order_json = Column(String)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    
class InventoryNew(Base):
    __tablename__ = "inv_new"
    id = Column(String, primary_key=True, default=lambda _: str(uuid.uuid4()))
    sku = Column(String, primary_key=True, index = True)
    categories = Column(String)
    inventory_json = Column(String)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now())
    