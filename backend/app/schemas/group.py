from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import MemberRole

GroupName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]  # Signal's limit


class CreateGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GroupName
    member_ids: list[int] = Field(min_length=1)


class RenameGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GroupName


class AddMembersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[int] = Field(min_length=1)


class ChangeRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MemberRole
