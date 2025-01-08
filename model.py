from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey  # Import for database interactions (SQLAlchemy)
from sqlalchemy.orm import declarative_base  # Import for ORM (Object Relational Mapping)

# Define database models using SQLAlchemy
Base = declarative_base()  # Base class for SQLAlchemy models


class ChatMessage(Base):
    """
    Represents a single chat message in the database.
    """
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True)
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime)
    model_id = Column(String)


class Feedback(Base):
    """
    Represents user feedback on a chat message.
    """
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True)
    chat_message_id = Column(Integer, ForeignKey('chat_history.id'))
    is_positive = Column(Boolean)
    comment = Column(String)