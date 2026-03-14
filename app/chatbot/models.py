"""SQLAlchemy models for chatbot tables."""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.chatbot.db import Base


class Resources(Base):
    __tablename__ = "resources"
    __table_args__ = {"extend_existing": True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    activation_status = Column(Integer)
    category = Column(String(50))


class FacilityResource(Base):
    __tablename__ = "facility_resources"
    __table_args__ = {"extend_existing": True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    activation_status = Column(Integer)
    category = Column(String(50))


class SafetyDevice(Base):
    __tablename__ = "safety_device"
    __table_args__ = {"extend_existing": True}

    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(200))
    location = Column(Integer)
    category = Column(String(255))
    isworking = Column(Integer)


class LabIncharge(Base):
    __tablename__ = "lab_incharge"
    __table_args__ = {"extend_existing": True}

    locationid = Column(Integer, primary_key=True, index=True)
    location = Column(String(255))
    memberid = Column(Integer)
    status = Column(String(50))


class Complaint(Base):
    __tablename__ = "complaint"

    complaint_id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer)
    machine_id = Column(Integer, nullable=True)
    location_name = Column(String(255))
    location_id = Column(Integer)
    complaint_description = Column(Text, nullable=False)
    type = Column(Integer, nullable=False)
    status = Column(String(50), default="Open")
    time_of_complaint = Column(DateTime(timezone=True), server_default=func.now())


class ConversationState(Base):
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String(40), unique=True, index=True, nullable=False)
    current_step = Column(String(100), nullable=False)
    collected_data = Column(Text, nullable=False)
