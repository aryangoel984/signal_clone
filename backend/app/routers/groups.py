from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.deps import AppSettings, CurrentUser, DbSession, RealtimeDep
from app.schemas.conversation import ConversationDetail
from app.schemas.group import AddMembersRequest, ChangeRoleRequest, CreateGroupRequest, RenameGroupRequest
from app.services import group_service, media
from app.services.conversation_service import ConversationNotFoundError
from app.services.group_service import MAX_GROUP_MEMBERS

router = APIRouter(prefix="/groups", tags=["groups"])

_ERRORS: dict[type[Exception], tuple[int, str]] = {
    ConversationNotFoundError: (status.HTTP_404_NOT_FOUND, "Group not found"),
    group_service.MemberNotFoundError: (status.HTTP_404_NOT_FOUND, "Not a member of this group"),
    group_service.NotAdminError: (status.HTTP_403_FORBIDDEN, "Only admins can do that"),
    group_service.AlreadyMembersError: (status.HTTP_409_CONFLICT, "Already in the group"),
    group_service.LastAdminError: (status.HTTP_409_CONFLICT, "Make someone else an admin first"),
    group_service.GroupFullError: (status.HTTP_422_UNPROCESSABLE_CONTENT, f"Groups can have at most {MAX_GROUP_MEMBERS} members"),
    media.ImageTooLargeError: (status.HTTP_413_CONTENT_TOO_LARGE, "Photo must be 5 MB or smaller"),
    media.UnsupportedImageError: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Photo must be a JPEG, PNG or WebP image"),
}


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, group_service.InvalidMembersError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    code, detail = _ERRORS[type(error)]
    return HTTPException(code, detail=detail)


_HANDLED = (*_ERRORS, group_service.InvalidMembersError)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(body: CreateGroupRequest, user: CurrentUser, db: DbSession, realtime: RealtimeDep) -> ConversationDetail:
    try:
        return await group_service.create_group(db, realtime, user, body.name, body.member_ids)
    except _HANDLED as error:
        raise _http_error(error) from None


@router.patch("/{conversation_id}")
async def rename_group(
    conversation_id: int, body: RenameGroupRequest, user: CurrentUser, db: DbSession, realtime: RealtimeDep
) -> ConversationDetail:
    try:
        return await group_service.rename_group(db, realtime, user, conversation_id, body.name)
    except _HANDLED as error:
        raise _http_error(error) from None


@router.put("/{conversation_id}/avatar")
async def set_avatar(
    conversation_id: int, file: UploadFile, user: CurrentUser, db: DbSession, realtime: RealtimeDep, settings: AppSettings
) -> ConversationDetail:
    try:
        return await group_service.set_group_avatar(db, realtime, user, conversation_id, file, settings.uploads_dir)
    except _HANDLED as error:
        raise _http_error(error) from None


@router.delete("/{conversation_id}/avatar")
async def remove_avatar(
    conversation_id: int, user: CurrentUser, db: DbSession, realtime: RealtimeDep, settings: AppSettings
) -> ConversationDetail:
    try:
        return await group_service.set_group_avatar(db, realtime, user, conversation_id, None, settings.uploads_dir)
    except _HANDLED as error:
        raise _http_error(error) from None


@router.post("/{conversation_id}/members")
async def add_members(
    conversation_id: int, body: AddMembersRequest, user: CurrentUser, db: DbSession, realtime: RealtimeDep
) -> ConversationDetail:
    try:
        return await group_service.add_members(db, realtime, user, conversation_id, body.user_ids)
    except _HANDLED as error:
        raise _http_error(error) from None


@router.delete("/{conversation_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(conversation_id: int, user_id: int, user: CurrentUser, db: DbSession, realtime: RealtimeDep) -> None:
    """Admins remove others; anyone can remove themselves (leave the group)."""
    try:
        await group_service.remove_member(db, realtime, user, conversation_id, user_id)
    except _HANDLED as error:
        raise _http_error(error) from None


@router.patch("/{conversation_id}/members/{user_id}")
async def change_role(
    conversation_id: int, user_id: int, body: ChangeRoleRequest, user: CurrentUser, db: DbSession, realtime: RealtimeDep
) -> ConversationDetail:
    try:
        return await group_service.change_role(db, realtime, user, conversation_id, user_id, body.role)
    except _HANDLED as error:
        raise _http_error(error) from None
