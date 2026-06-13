from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Single canonical utcnow source — imported here for model column defaults.
from app.utils.datetime import utcnow  # noqa: F401


class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: dict[str, Any],
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class TableNameMixin:
    @declared_attr.directive
    def __tablename__(cls) -> str:
        name = cls.__name__
        chars: list[str] = []
        for index, char in enumerate(name):
            if char.isupper() and index > 0:
                chars.append("_")
            chars.append(char.lower())
        return "".join(chars)
