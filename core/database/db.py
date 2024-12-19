from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from core.config import settings


engine = create_engine(settings.CONNECTION_STRING)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()
