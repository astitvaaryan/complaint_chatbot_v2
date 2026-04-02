"""SQLAlchemy models for chatbot tables."""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.chatbot.db import Base


# class Resources(Base):
#     __tablename__ = "resources"
#     __table_args__ = {"extend_existing": True}

#     machid = Column(Integer, primary_key=True, index=True)
#     name = Column(String(150))
#     location = Column(String(250))
#     activation_status = Column(Integer)
#     isworking = Column(Integer, default=1)
#     category = Column(String(50))


class EqpProcessResource(Base):
    __tablename__ = "resources"
    __table_args__ = {"schema": "slotbooking", "extend_existing": True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    activation_status = Column(Integer)
    isworking = Column(Integer, default=1)
    category = Column(String(50))
    display = Column(Integer, nullable=True)


class FacilityResource(Base):
    __tablename__ = "resources"
    __table_args__ = {"schema": "facility_management", "extend_existing": True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    activation_status = Column(Integer)
    category = Column(String(50))
    display = Column(Integer, nullable=True)


class SafetyDevice(Base):
    __tablename__ = "resources"
    __table_args__ = {"schema": "safety_device", "extend_existing": True}

    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(200))
    location = Column(Integer)
    category = Column(String(255))
    isworking = Column(Integer)


class LabIncharge(Base):
    __tablename__ = "lab_incharge"
    __table_args__ = {"schema": "slotbooking", "extend_existing": True}

    locationid = Column(Integer, primary_key=True, index=True)
    location = Column(String(255))
    memberid = Column(Integer)
    status = Column(String(50))


class Complaint(Base):
    __tablename__ = "equipment_complaint"
    __table_args__ = {"schema": "iitbnf_troubleshoot", "extend_existing": True}

    complaint_id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer)
    machine_id = Column(Integer, nullable=True)
    complaint_description = Column(Text, nullable=False)
    time_of_complaint = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Integer, default=0)  # 0=Pending, 1=In Process, 2=Closed, 3=On Hold
    type = Column(Integer, nullable=False)


class ConversationState(Base):
    __tablename__ = "conversation_state"
    __table_args__ = {"schema": "iitbnf_troubleshoot", "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String(40), unique=True, index=True, nullable=False)
    current_step = Column(String(100), nullable=False)
    collected_data = Column(Text, nullable=False)


class ComplaintKeyword(Base):
    """Keywords specifically for IT routing accuracy."""
    __tablename__ = "complaint_it_keywords"
    __table_args__ = {"schema": "iitbnf_troubleshoot", "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(Integer, nullable=False)


class ChatbotErrorLog(Base):
    """Tracks backend exceptions and crashes for IT telemetry."""
    __tablename__ = "chatbot_error_logs"
    __table_args__ = {"schema": "iitbnf_troubleshoot", "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String(40), index=True, nullable=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
