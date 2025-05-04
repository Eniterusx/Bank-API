import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = 'postgresql://postgres:postgres@localhost:5433/test_bank_db'

def get_engine(database_url: str = None, echo: bool = True):
    if database_url is None:
        if DEFAULT_DATABASE_URL is None:
            raise ValueError("DATABASE_URL not found. Set it in your environment or pass it explicitly.")
        database_url = DEFAULT_DATABASE_URL

    print(f"[DB] Connecting to database at {database_url}")
    return create_engine(database_url, echo=echo)

def get_sessionmaker(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=True)
