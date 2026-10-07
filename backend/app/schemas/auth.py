from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.schemas.common import PhoneNumber
from app.schemas.user import MeResponse

OtpCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


class OtpRequest(BaseModel):
    phone_number: PhoneNumber


class OtpRequestResponse(BaseModel):
    sent: Literal[True] = True


class OtpVerifyRequest(BaseModel):
    phone_number: PhoneNumber
    code: OtpCode


class AuthResponse(BaseModel):
    token: str
    user: MeResponse
    is_new_user: bool
