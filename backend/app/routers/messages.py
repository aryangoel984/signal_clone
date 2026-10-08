from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.deps import CurrentUser, DbSession, RealtimeDep
from app.schemas.message import MessageDetails, MessageOut, MessagePage, ReactRequest, ReadRequest, SendMessageRequest
from app.services import message_service, reaction_service, receipt_service
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
    conversation_id: int,
    body: SendMessageRequest,
    user: CurrentUser,
    db: DbSession,
    realtime: RealtimeDep,
    response: Response,
) -> MessageOut:
    try:
        message, created = await message_service.send_message(
            db, realtime, user, conversation_id, body.client_id, body.body, body.reply_to_id
        )
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
    except message_service.NotActiveMemberError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You're no longer a member of this group") from None
    except message_service.RecipientBlockedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Unblock this person to send messages") from None
    except message_service.ClientIdConflictError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="client_id was already used in another conversation") from None
    except message_service.InvalidReplyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Can't reply to that message") from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return message


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    conversation_id: int, body: ReadRequest, user: CurrentUser, db: DbSession, realtime: RealtimeDep
) -> None:
    try:
        member, _ = await load_membership(db, user.id, conversation_id)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
    changed = await receipt_service.mark_read(db, user, member, body.up_to_message_id)
    await realtime.statuses_changed(changed)  # after the commit inside mark_read


message_router = APIRouter(prefix="/messages", tags=["messages"])

_MESSAGE_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")


@message_router.get("/{message_id}/receipts")
async def message_details(message_id: int, user: CurrentUser, db: DbSession) -> MessageDetails:
    try:
        return await message_service.get_details(db, user, message_id)
    except message_service.MessageNotFoundError:
        raise _MESSAGE_NOT_FOUND from None
    except message_service.NotSenderError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the sender can see message details") from None


@message_router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_for_everyone(message_id: int, user: CurrentUser, db: DbSession, realtime: RealtimeDep) -> None:
    try:
        await message_service.delete_for_everyone(db, realtime, user, message_id)
    except message_service.MessageNotFoundError:
        raise _MESSAGE_NOT_FOUND from None
    except message_service.NotSenderError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the sender can delete a message for everyone") from None
    except message_service.NotActiveMemberError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You're no longer a member of this group") from None
    except message_service.DeleteWindowExpiredError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Messages can only be deleted for everyone within 24 hours of sending"
        ) from None


@message_router.put("/{message_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
async def react(message_id: int, body: ReactRequest, user: CurrentUser, db: DbSession, realtime: RealtimeDep) -> None:
    await _set_reaction(db, realtime, user, message_id, body.emoji)


@message_router.delete("/{message_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reaction(message_id: int, user: CurrentUser, db: DbSession, realtime: RealtimeDep) -> None:
    await _set_reaction(db, realtime, user, message_id, None)


async def _set_reaction(db: DbSession, realtime: RealtimeDep, user: CurrentUser, message_id: int, emoji: str | None) -> None:
    try:
        await reaction_service.set_reaction(db, realtime, user, message_id, emoji)
    except message_service.MessageNotFoundError:
        raise _MESSAGE_NOT_FOUND from None
    except message_service.NotActiveMemberError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You're no longer a member of this group") from None
    except message_service.RecipientBlockedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Unblock this person to react") from None
