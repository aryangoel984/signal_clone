import os

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class MediaFiles(StaticFiles):
    """Serves user uploads. Adds `X-Content-Type-Options: nosniff` (StaticFiles doesn't),
    so a browser never second-guesses the declared type of an uploaded file."""

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
