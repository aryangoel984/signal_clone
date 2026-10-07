from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints


def _lowercase(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
About = Annotated[str, StringConstraints(strip_whitespace=True, max_length=140)]
Username = Annotated[str, BeforeValidator(_lowercase), StringConstraints(pattern=r"^[a-z0-9_.]{3,32}$")]


class MeResponse(BaseModel):
    """The signed-in user's own profile (includes the phone number)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: str
    username: str | None
    display_name: str | None
    about: str | None
    avatar_url: str | None
    avatar_color: str
    created_at: datetime


class UpdateMeRequest(BaseModel):
    """PATCH semantics: only fields present in the body are changed."""

    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    about: About | None = None
    username: Username | None = None
