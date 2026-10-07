"""Importing this package registers every model on Base.metadata (needed before create_all)."""

from app.models.attachment import Attachment
from app.models.base import Base
from app.models.block import Block
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.message_receipt import MessageReceipt
from app.models.reaction import Reaction
from app.models.user import User
from app.models.user_session import UserSession
from app.models.user_settings import UserSettings

__all__ = [
    "Attachment",
    "Base",
    "Block",
    "Contact",
    "Conversation",
    "ConversationMember",
    "Message",
    "MessageReceipt",
    "Reaction",
    "User",
    "UserSession",
    "UserSettings",
]
