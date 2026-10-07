import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_SEPARATORS = re.compile(r"[\s\-().]")


def _strip_separators(value: object) -> object:
    return _SEPARATORS.sub("", value) if isinstance(value, str) else value


def _require_e164(value: str) -> str:
    if not E164_PATTERN.fullmatch(value):
        raise ValueError("Phone number must be in international format, e.g. +14155550123")
    return value


# "+1 (415) 555-0123" -> "+14155550123"; anything that isn't E.164 afterwards is a 422.
PhoneNumber = Annotated[str, BeforeValidator(_strip_separators), AfterValidator(_require_e164)]
