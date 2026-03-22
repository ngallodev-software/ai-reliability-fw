from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase
import enum

class Base(DeclarativeBase):
    pass

class FailureCategory(str, enum.Enum):
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    HALLUCINATION_SIGNAL = "HALLUCINATION_SIGNAL"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    SAFETY_FLAG = "SAFETY_FLAG"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    HUMAN_ESCALATED = "HUMAN_ESCALATED"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    INPUT_VALIDATION_ERROR = "INPUT_VALIDATION_ERROR"
    OUTPUT_CONTENT_ERROR = "OUTPUT_CONTENT_ERROR"

class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    REPLAYING = "REPLAYING"

class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = {"schema": "reliability"}
    workflow_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    definition_json = Column(JSONB, nullable=False)

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = {"schema": "reliability"}
    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("reliability.workflows.workflow_id"))
    status = Column(Enum(RunStatus, schema="reliability"), default=RunStatus.RUNNING)
    created_at = Column(DateTime, default=datetime.utcnow)

class LLMCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = {"schema": "reliability"}
    call_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("reliability.workflow_runs.run_id"))
    phase_id = Column(UUID(as_uuid=True), nullable=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("reliability.prompts.prompt_id"))
    retry_attempt_num = Column(Integer, default=0)
    failure_category = Column(Enum(FailureCategory, schema="reliability"), nullable=True)
    latency_ms = Column(Integer)
    response_raw = Column(Text)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    token_cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = {"schema": "reliability"}
    prompt_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    content = Column(Text, nullable=False)
    prompt_hash = Column(String, unique=True, nullable=False)
    version_tag = Column(String, nullable=False)

class EscalationRecord(Base):
    __tablename__ = "escalation_records"
    __table_args__ = {"schema": "reliability"}
    escalation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("reliability.workflow_runs.run_id"))
    phase_id = Column(UUID(as_uuid=True), nullable=True)
    llm_call_id = Column(UUID(as_uuid=True), ForeignKey("reliability.llm_calls.call_id"))
    retry_attempt_num = Column(Integer, default=0, nullable=False)
    failure_category = Column(Enum(FailureCategory, schema="reliability"), nullable=False)
    trigger_reason = Column(String(500), nullable=False)
    escalated_at = Column(DateTime, default=datetime.utcnow)
