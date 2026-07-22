from fastapi import Depends, Header, HTTPException
from app.config import Settings, get_settings


async def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_key:
        return  # auth disabled in local dev
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
