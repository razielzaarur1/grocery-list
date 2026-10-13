from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="category", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    quantity = Column(String(50), default="")
    unit = Column(String(50), default="")
    note = Column(String(300), default="")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    is_checked = Column(Boolean, default=False)
    checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    global_add_order = Column(Integer, default=0, index=True)

    category = relationship("Category", back_populates="items")


class ClassifierCache(Base):
    __tablename__ = "classifier_cache"

    id = Column(Integer, primary_key=True, index=True)
    item_name_normalized = Column(String(200), unique=True, index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    confidence = Column(Float, default=1.0)  # 0.0 to 1.0 (1.0 = 100%)
    source = Column(String(50), default="ai")  # 'user', 'ai', 'algo'
    usage_count = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GeminiModel(Base):
    __tablename__ = "gemini_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(150), unique=True, nullable=False)
    display_name = Column(String(200), default="")
    is_active = Column(Boolean, default=True)
    rank = Column(Integer, default=100)
    last_tested_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")
