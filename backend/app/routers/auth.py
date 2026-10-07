from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

from app.core.deps import AppSettings, CurrentSession, DbSession
from app.schemas.auth import AuthResponse, OtpRequest, OtpRequestResponse, OtpVerifyRequest
from app.schemas.user import MeResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(body: OtpRequest) -> OtpRequestResponse:
    # Mocked: no SMS is sent and the code is always 123456. Same answer for known and
    # unknown numbers. (verify's is_new_user still reveals it; see README.)
    del body
    return OtpRequestResponse()


@router.post("/otp/verify")
async def verify_otp(body: OtpVerifyRequest, db: DbSession, settings: AppSettings) -> AuthResponse:
    try:
        result = await auth_service.verify_otp(
            db, body.phone_number, body.code, session_ttl=timedelta(days=settings.session_ttl_days)
        )
    except auth_service.InvalidOtpError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Incorrect verification code") from None
    return AuthResponse(
        token=result.token,
        user=MeResponse.model_validate(result.user),
        is_new_user=result.is_new_user,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current: CurrentSession, db: DbSession) -> None:
    user_session, _ = current
    await auth_service.logout(db, user_session)
