"""Exception types for the filtered SKAI v2 client."""


class SkaiApiV2Error(Exception):
    """Raised when the filtered SKAI v2 API request fails."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
