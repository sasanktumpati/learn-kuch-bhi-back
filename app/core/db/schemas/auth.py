from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable

from app.core.db.base import Base


class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)


__all__ = ["User"]
