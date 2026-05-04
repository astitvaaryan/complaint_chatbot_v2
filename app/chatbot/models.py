"""SQLAlchemy models for chatbot tables."""

import os
from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.chatbot.db import Base

load_dotenv()

# ─── Database name variables from .env ───────────────────────────────────────
# DB1 = slotbooking       (login, resources eqp-process, lab_incharge)
# DB2 = facility_management (resources facility)
# DB3 = safety            (safety_device)
# DB4 = iitbnf_troubleshooting (equipment_complaint, conversation_state, etc.)
_DB1 = os.getenv("DB1", "slotbooking")
_DB2 = os.getenv("DB2", "facility_management")
_DB3 = os.getenv("DB3", "safety")
_DB4 = os.getenv("DB4", "iitbnf_troubleshooting")


class EqpProcessResource(Base):
    __tablename__ = "resources"
    __table_args__ = {"schema": _DB1, "extend_existing": True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    activation_status = Column(Integer)
    isworking = Column(Integer, default=1)
    display = Column(Integer, nullable=True)


class FacilityResource(Base):
    __tablename__ = "resources"
    __table_args__ = {"schema": _DB2, "extend_existing": True}

    machid = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    location = Column(String(250))
    activation_status = Column(Integer)
    display = Column(Integer, nullable=True)


class SafetyDevice(Base):
    __tablename__ = "safety_device"
    __table_args__ = {"schema": _DB3, "extend_existing": True}

    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(200))
    location = Column(Integer)
    isworking = Column(Integer)


class LabIncharge(Base):
    __tablename__ = "lab_incharge"
    __table_args__ = {"schema": _DB1, "extend_existing": True}

    locationid = Column(Integer, primary_key=True, index=True)
    location = Column(String(255))
    # memberid = Column(Integer)
    # status = Column(String(50))


class Complaint(Base):
    __tablename__ = "equipment_complaint"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    complaint_id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, default=0, nullable=False)
    original_id = Column(Integer, default=0, nullable=False)
    member_id = Column(Integer, nullable=False)
    allocated_to = Column(Integer, nullable=True)
    type = Column(Integer, default=0, nullable=False)
    machine_id = Column(Integer, nullable=False)
    time_of_complaint = Column(DateTime, nullable=False)
    status = Column(Integer, nullable=False)  # 0=Pending, 1=In Process, 2=Closed, 3=On Hold
    status_timestamp = Column(DateTime, nullable=True)
    status_updated_by = Column(Integer, nullable=True)
    upload_file = Column(String(200), nullable=True)
    process_develop = Column(String(255), nullable=True)
    anti_contamination_develop = Column(String(255), nullable=True)
    complaint_description = Column(Text, nullable=True)
    scheduler = Column(Integer, nullable=True)


class ConversationState(Base):
    __tablename__ = "conversation_state"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String(40), unique=True, index=True, nullable=False)
    current_step = Column(String(100), nullable=False)
    collected_data = Column(Text, nullable=False)


class ComplaintKeyword(Base):
    """Keywords specifically for IT routing accuracy."""
    __tablename__ = "complaint_it_keywords"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(Integer, nullable=False)


class ComplaintBaseKeyword(Base):
    """Base category keywords for classification."""
    __tablename__ = "complaint_base_keywords"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(Integer, nullable=False)


class ChatbotErrorLog(Base):
    """Tracks backend exceptions and crashes for IT telemetry."""
    __tablename__ = "chatbot_error_logs"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String(40), index=True, nullable=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RoleMaster(Base):
    __tablename__ = "role_master"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    role_id = Column(Integer, primary_key=True, index=True)
    role = Column(String(100), nullable=False)
    description = Column(String(255))


class Role(Base):
    __tablename__ = "role"
    __table_args__ = {"schema": _DB4, "extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    memberid = Column(Integer, nullable=False)
    role = Column(Integer, nullable=False)  # role_id from role_master
    timestamp = Column(DateTime, server_default=func.now())
