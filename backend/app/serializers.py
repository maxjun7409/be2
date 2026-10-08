"""DB 객체 → 앱에 보낼 JSON. 여기서 저장 경로(*_path)를 주소(*_url)로 바꿉니다."""
from datetime import datetime

from . import storage
from .models import Analysis, Material, Project, Scenario, User


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def ser_user(u: User) -> dict:
    return {
        "uid": u.uid,
        "email": u.email,
        "display_name": u.display_name,
        "provider": u.provider,
        "settings": u.settings or {},
        "created_at": iso(u.created_at),
        "last_login_at": iso(u.last_login_at),
    }


def ser_project(p: Project) -> dict:
    return {
        "project_id": p.project_id,
        "title": p.title,
        "original_image_url": storage.url(p.original_image_path),
        "width": p.width,
        "height": p.height,
        "brightness": round(p.brightness, 3) if p.brightness is not None else None,
        "current_analysis_id": p.current_analysis_id,
        "created_at": iso(p.created_at),
    }


def ser_analysis(a: Analysis) -> dict:
    return {
        "analysis_id": a.analysis_id,
        "project_id": a.project_id,
        "label_url": storage.url(a.label_path),
        "overlay_url": storage.url(a.overlay_path),
        "wall_count": a.wall_count,
        "regions": a.regions,
        "source": a.source,
        "parent_analysis_id": a.parent_analysis_id,
        "created_at": iso(a.created_at),
    }


def ser_material(m: Material, recommendation: dict | None = None) -> dict:
    return {
        "material_id": m.material_id,
        "category": m.category,
        "name": m.name,
        "source": m.source,
        "color_hex": m.color_hex,
        "color_family": m.color_family,
        "tone": m.tone,
        "pattern": m.pattern,
        "tags": m.tags or [],
        "texture_url": storage.url(m.texture_path),
        "thumbnail_url": storage.url(m.thumbnail_path),
        "recommendation": recommendation,
    }


def _ser_used(entry: dict) -> dict:
    out = {k: v for k, v in entry.items() if k != "thumbnail_path"}
    out["thumbnail_url"] = storage.url(entry.get("thumbnail_path"))
    return out


def ser_scenario(s: Scenario) -> dict:
    return {
        "scenario_id": s.scenario_id,
        "project_id": s.project_id,
        "analysis_id": s.analysis_id,
        "title": s.title,
        "saved": s.saved,
        "result_image_url": storage.url(s.result_image_path),
        "thumbnail_url": storage.url(s.thumbnail_path),
        "before_image_url": storage.url(s.project.original_image_path) if s.project else None,
        "materials_used": [_ser_used(e) for e in (s.materials_used or [])],
        "created_at": iso(s.created_at),
        "saved_at": iso(s.saved_at),
    }
