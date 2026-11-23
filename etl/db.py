"""Shared database connection for the ETL loaders."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_engine() -> Engine:
    url = URL.create(
        "mssql+pymssql",
        username="sa",
        password=os.environ["MSSQL_SA_PASSWORD"],
        host=os.getenv("MSSQL_HOST", "localhost"),
        port=int(os.getenv("MSSQL_PORT", "1433")),
        database=os.getenv("MSSQL_DATABASE", "RunNow"),
    )
    return create_engine(url)
