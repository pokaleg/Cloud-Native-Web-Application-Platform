from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables — imports must happen here so
    SQLAlchemy knows about all models before create_all runs."""
    from app.models.user import User, HealthCheck   # noqa: F401 — HealthCheck lives here too
    from app.models.course import Course             # noqa: F401
    from app.models.syllabus import Syllabus         # noqa: F401
    Base.metadata.create_all(engine)
