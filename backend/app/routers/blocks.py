from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.contact import UserPublic
from app.services import block_service

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.get("")
async def list_blocked(user: CurrentUser, db: DbSession) -> list[UserPublic]:
    return await block_service.list_blocked(db, user)


@router.put("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def block(user_id: int, user: CurrentUser, db: DbSession) -> None:
    try:
        await block_service.block(db, user, user_id)
    except block_service.SelfBlockError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You can't block yourself") from None
    except block_service.UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found") from None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock(user_id: int, user: CurrentUser, db: DbSession) -> None:
    await block_service.unblock(db, user, user_id)
