from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class UserPrefs(Base):
    __tablename__ = "user_prefs"
    user_id = Column(Integer, primary_key=True)
    bitrate = Column(String, default="192k")
    format = Column(String, default="mp3")
    dynamic_quality = Column(Boolean, default=True)
    send_as_voice = Column(Boolean, default=False)

class ConversionStats(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    file_size = Column(Integer)
    duration = Column(Float)
    processing_time = Column(Float)
    success = Column(Boolean, default=True)
    error_message = Column(String)
    platform = Column(String) # 'web' or 'telegram'
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
