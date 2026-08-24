"""Simple Kanban — a plugin-owned ranked working queue."""

from __future__ import annotations

from pathlib import Path

_VIEW_ROOT = Path(__file__).parent / "view"


def _view_html() -> str:
    template = (_VIEW_ROOT / "board.html").read_text(encoding="utf-8")
    css = (_VIEW_ROOT / "board.css").read_text(encoding="utf-8")
    javascript = (_VIEW_ROOT / "board.js").read_text(encoding="utf-8")
    return template.replace("{{CSS}}", css).replace("{{JS}}", javascript)


def build_view_router():
    from fastapi import APIRouter
    from fastapi.responses import HTMLResponse

    router = APIRouter()

    @router.get("/view", response_class=HTMLResponse)
    async def view() -> str:
        # Read source per request so an isolated development install can refresh
        # without a frontend build. Installed plugin releases remain exact pins.
        return _view_html()

    return router


def register(registry) -> None:
    # Lazy package-relative imports keep the repository host-free under pytest,
    # while the host loads this file under its synthetic plugin package name.
    from .api import build_data_router
    from .events import bind_registry
    from .tools import TOOLS

    bind_registry(registry)
    for kanban_tool in TOOLS:
        registry.register_tool(kanban_tool)
    registry.register_skill_dir("skills")
    registry.register_router(build_view_router(), prefix="/plugins/simple_kanban")
    registry.register_router(build_data_router(), prefix="/api/plugins/simple_kanban")


__all__ = ["register"]
