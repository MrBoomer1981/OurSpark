"""Проверка живости. Railway переключает трафик на новый деплой только после 200 отсюда."""

from fastapi import APIRouter, Request, Response
from loguru import logger

router = APIRouter()


@router.get("/health")
async def health(request: Request, response: Response) -> dict[str, bool]:
    try:
        await request.app.state.pool.fetchval("SELECT 1", timeout=5)
    except Exception:
        logger.exception("Health: база не отвечает")
        response.status_code = 503
        return {"ok": False}
    return {"ok": True}
