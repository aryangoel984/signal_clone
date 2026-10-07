from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.deps import AppSettings, CurrentUser, DbSession
from app.schemas.user import MeResponse, UpdateMeRequest
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(user)


@router.patch("/me")
async def update_me(body: UpdateMeRequest, user: CurrentUser, db: DbSession) -> MeResponse:
    try:
        updated = await user_service.update_profile(db, user, body)
    except user_service.UsernameTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username is already taken") from None
    return MeResponse.model_validate(updated)


@router.put("/me/avatar")
async def upload_avatar(file: UploadFile, user: CurrentUser, db: DbSession, settings: AppSettings) -> MeResponse:
    try:
        updated = await user_service.set_avatar(db, user, file, settings.uploads_dir)
    except user_service.AvatarTooLargeError:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="Avatar must be 5 MB or smaller") from None
    except user_service.UnsupportedImageError:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Avatar must be a JPEG, PNG or WebP image"
        ) from None
    return MeResponse.model_validate(updated)


@router.delete("/me/avatar")
async def delete_avatar(user: CurrentUser, db: DbSession, settings: AppSettings) -> MeResponse:
    return MeResponse.model_validate(await user_service.remove_avatar(db, user, settings.uploads_dir))
