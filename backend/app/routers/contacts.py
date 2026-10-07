from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.contact import AddContactRequest, UpdateContactRequest, UserPublic
from app.services import contact_service

router = APIRouter(prefix="/contacts", tags=["contacts"])

_NOT_A_CONTACT = HTTPException(status.HTTP_404_NOT_FOUND, detail="Contact not found")


@router.get("")
async def list_contacts(user: CurrentUser, db: DbSession) -> list[UserPublic]:
    return await contact_service.list_contacts(db, user)


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_contact(body: AddContactRequest, user: CurrentUser, db: DbSession) -> UserPublic:
    try:
        return await contact_service.add_contact(db, user, body)
    except contact_service.UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No Signal user with that number or username") from None
    except contact_service.SelfContactError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You can't add yourself as a contact") from None
    except contact_service.ContactExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Already in your contacts") from None


@router.patch("/{user_id}")
async def update_contact(user_id: int, body: UpdateContactRequest, user: CurrentUser, db: DbSession) -> UserPublic:
    try:
        return await contact_service.update_nickname(db, user, user_id, body.nickname)
    except contact_service.ContactNotFoundError:
        raise _NOT_A_CONTACT from None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact(user_id: int, user: CurrentUser, db: DbSession) -> None:
    try:
        await contact_service.remove_contact(db, user, user_id)
    except contact_service.ContactNotFoundError:
        raise _NOT_A_CONTACT from None
