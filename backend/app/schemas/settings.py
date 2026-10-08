from pydantic import BaseModel, ConfigDict

from app.models.enums import Theme


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    theme: Theme
    read_receipts_enabled: bool
    typing_indicators_enabled: bool
    notifications_enabled: bool
    enter_key_sends: bool


class UpdateSettingsRequest(BaseModel):
    """PATCH semantics: only fields present in the body change."""

    model_config = ConfigDict(extra="forbid")

    theme: Theme | None = None
    read_receipts_enabled: bool | None = None
    typing_indicators_enabled: bool | None = None
    notifications_enabled: bool | None = None
    enter_key_sends: bool | None = None
