from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.schemas.common import PhoneNumber
from app.schemas.user import Username

Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class UserPublic(BaseModel):
    """Another user's profile as the viewer sees it."""

    id: int
    name: str  # nickname > display name > phone number
    display_name: str | None
    username: str | None
    about: str | None
    avatar_url: str | None
    avatar_color: str
    phone_number: str | None  # only shown for the viewer's contacts
    is_contact: bool
    nickname: str | None


class AddContactRequest(BaseModel):
    """Exactly one way of identifying the person."""

    model_config = ConfigDict(extra="forbid")

    phone_number: PhoneNumber | None = None
    username: Username | None = None
    user_id: int | None = None
    nickname: Nickname | None = None

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "AddContactRequest":
        given = [value for value in (self.phone_number, self.username, self.user_id) if value is not None]
        if len(given) != 1:
            raise ValueError("Provide exactly one of phone_number, username or user_id")
        return self


class UpdateContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: Nickname | None
