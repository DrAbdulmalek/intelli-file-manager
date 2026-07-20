"""خادم API لـ IntelliFile Manager — FastAPI + WebSocket"""

from .server import app, create_app

__all__ = ["app", "create_app"]
