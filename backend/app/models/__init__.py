"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.analysis import AnalysisResult
from app.models.application import Application, ApplicationEvent
from app.models.job import Job, JobPosting, JobSource
from app.models.llm import LlmUsage
from app.models.resume import Resume, ResumeVersion
from app.models.user import JobPreference, User

__all__ = [
    "AnalysisResult",
    "Application",
    "ApplicationEvent",
    "Job",
    "JobPosting",
    "JobPreference",
    "JobSource",
    "LlmUsage",
    "Resume",
    "ResumeVersion",
    "User",
]
