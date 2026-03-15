"""
app/chatbot/models.py
─────────────────────────────────────────
SQLAlchemy models for chatbot tables.
Updated from teammate's latest (Feb 25, 2026):
  - Complaint: added location_name, location_id
  - ConversationState: user_phone extended to String(40)
  - LabIncharge: locationid is now PK, added status
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.chatbot.db import Base


class Resources(Base):
    """Facility/General resources."""
    __tablename__ = "resources"
    __table_args__ = {'extend_existing': True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    isworking = Column(Integer, default=1)
    category = Column(String(50))


class EqpProcessResource(Base):
    """Equipment and Process resources."""
    __tablename__ = "eqp-process_resources"
    __table_args__ = {'extend_existing': True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    isworking = Column(Integer, default=1)
    category = Column(String(150))


class SafetyDevice(Base):
    """Safety-related devices."""
    __tablename__ = "safety_device"
    __table_args__ = {'extend_existing': True}

    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(200)) # Note: named device_name in SQL
    location = Column(String(250))
    isworking = Column(Integer, default=1)
    category = Column(String(255))


class LabIncharge(Base):
    """Lab incharge per location."""
    __tablename__ = "lab_incharge"
    __table_args__ = {'extend_existing': True}

    locationid = Column(Integer, primary_key=True, index=True)
    location = Column(String(255))
    memberid = Column(Integer)
    status = Column(String(50))


class Complaint(Base):
    """Registered equipment complaints."""
    __tablename__ = "complaint"

    complaint_id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer)
    machine_id = Column(Integer, nullable=True)   # NULL for new/unknown equipment
    location_name = Column(String(255))
    location_id = Column(Integer)
    complaint_description = Column(Text, nullable=False)
    type = Column(Integer, nullable=False)   # 1=Equipment ... 10=Admin
    status = Column(String(50), default="Open")
    time_of_complaint = Column(DateTime(timezone=True), server_default=func.now())


class ConversationState(Base):
    """Tracks multi-step conversation per user (phone number)."""
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String(40), unique=True, index=True, nullable=False)
    current_step = Column(String(100), nullable=False)
    collected_data = Column(Text, nullable=False)


class ComplaintKeyword(Base):
    """Keywords extracted from CSV datasets to improve classification accuracy."""
    __tablename__ = "complaint_it_keywords"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(Integer, nullable=False) # 1=Equipment ... 10=Admin
