import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=Role.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
