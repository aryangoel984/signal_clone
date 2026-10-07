from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    CreateDirectRequest,
    UpdatePreferencesRequest,
)
from app.services import conversation_service
from app.services.conversation_service import (
    ConversationNotFoundError,
    SelfConversationError,
    UserNotFoundError,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.get("")
async def list_conversations(user: CurrentUser, db: DbSession, archived: bool = False) -> list[ConversationSummary]:
    return await conversation_service.list_conversations(db, user, archived=archived)


@router.post("/direct")
async def create_direct(
    body: CreateDirectRequest, user: CurrentUser, db: DbSession, response: Response
) -> ConversationDetail:
    try:
        conversation, created = await conversation_service.get_or_create_direct(db, user, body.user_id)
    except SelfConversationError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You can't start a chat with yourself") from None
    except UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found") from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return conversation


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: int, user: CurrentUser, db: DbSession) -> ConversationDetail:
    try:
        return await conversation_service.get_conversation(db, user, conversation_id)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None


@router.patch("/{conversation_id}/preferences")
async def update_preferences(
    conversation_id: int, body: UpdatePreferencesRequest, user: CurrentUser, db: DbSession
) -> ConversationDetail:
    try:
        return await conversation_service.update_preferences(db, user, conversation_id, body)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
