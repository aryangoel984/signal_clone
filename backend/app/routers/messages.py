from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.message import MessageOut, MessagePage, ReadRequest, SendMessageRequest
from app.services import message_service, receipt_service
from app.services.conversation_service import ConversationNotFoundError, load_membership

router = APIRouter(prefix="/conversations", tags=["messages"])

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: int,
    user: CurrentUser,
    db: DbSession,
    before: int | None = None,
    after: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    try:
        return await message_service.list_messages(db, user, conversation_id, before=before, after=after, limit=limit)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: int, body: SendMessageRequest, user: CurrentUser, db: DbSession, response: Response
) -> MessageOut:
    try:
        message, created = await message_service.send_message(db, user, conversation_id, body.client_id, body.body)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
    except message_service.NotActiveMemberError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You're no longer a member of this group") from None
    except message_service.ClientIdConflictError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="client_id was already used in another conversation") from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return message


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(conversation_id: int, body: ReadRequest, user: CurrentUser, db: DbSession) -> None:
    try:
        member, _ = await load_membership(db, user.id, conversation_id)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
    await receipt_service.mark_read(db, user, member, body.up_to_message_id)
