from enum import StrEnum


class SourceType(StrEnum):
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    X = "x"
    MANUAL = "manual"


class RiskLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CollectionRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class PrincipalType(StrEnum):
    DASHBOARD = "dashboard"
    INTERNAL_SERVICE = "internal_service"


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

class ReliabilityRating(StrEnum):
    A_1 = "A / 1"
    B_2 = "B / 2"
    C_2 = "C / 2"
    C_3 = "C / 3"
    D_4 = "D / 4"
    E_5 = "E / 5"
    F_6 = "F / 6"
