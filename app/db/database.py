from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from .models import Base

# In production, use the Supabase (PostgreSQL) connection string
# Standard SQLAlchemy format: postgresql+asyncpg://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///temp_nebulyze.db")

# Ensure PostgreSQL connection strings use the async driver if not specified
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    pool_pre_ping=True, 
    pool_size=5,
    max_overflow=10,
    pool_recycle=300, # Recycle connections every 5 mins
    connect_args={
        "command_timeout": 60, # 60s timeout for commands
        "timeout": 60          # 60s timeout for connection
    }
)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        yield session
