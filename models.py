"""DB 테이블 정의 (SQLite와 PostgreSQL 모두에서 동작).

users            회원 정보 (Firebase uid가 기본 키)
projects         원본 사진 1장 = 프로젝트 1개
analyses         프로젝트의 AI 분석 결과 (사용자가 수정할 때마다 새 버전)
scenarios        생성된 시안. saved=False면 초안, True면 저장된 시안
materials        마감재 (기본 제공 + 사용자 업로드)
material_history 추천용 선택 이력
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    uid: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(30))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    # 게스트(익명 로그인)도 프로젝트를 만들 수 있으므로 users 외래 키를 걸지 않습니다.
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(100))
    original_image_path: Mapped[str] = mapped_column(String(500))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    brightness: Mapped[float | None] = mapped_column(Float)   # 0~1, 추천의 "어두운 공간" 판단용
    current_analysis_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True)


class Analysis(Base):
    __tablename__ = "analyses"

    analysis_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)
    label_path: Mapped[str] = mapped_column(String(500))     # 픽셀값 = region_id 인 PNG
    overlay_path: Mapped[str] = mapped_column(String(500))   # 앱 표시용 색칠 PNG
    regions: Mapped[list] = mapped_column(JSON)              # [{region_id, class, area_ratio, bbox}]
    wall_count: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))          # auto | user_edited
    parent_analysis_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="analyses")


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_owner_saved_created", "owner_id", "saved", "created_at"),)

    scenario_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(128))
    analysis_id: Mapped[str] = mapped_column(String(40))
    result_image_path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[str] = mapped_column(String(500))
    materials_used: Mapped[list] = mapped_column(JSON)       # 생성 당시 마감재 정보 스냅샷
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[str | None] = mapped_column(String(100))
    saved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="scenarios")


class Material(Base):
    __tablename__ = "materials"

    material_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)   # wall | floor | molding
    name: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20), default="default")  # default | user
    owner_id: Mapped[str | None] = mapped_column(String(128), index=True)
    texture_path: Mapped[str | None] = mapped_column(String(500))   # 없으면 단색 마감재
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    color_hex: Mapped[str] = mapped_column(String(7))
    color_family: Mapped[str] = mapped_column(String(20))
    tone: Mapped[str] = mapped_column(String(10))                   # bright | dark
    pattern: Mapped[str] = mapped_column(String(30), default="solid")
    tags: Mapped[list] = mapped_column(JSON, default=list)          # ["모던", "내추럴"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MaterialHistory(Base):
    __tablename__ = "material_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    scenario_id: Mapped[str | None] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(20))          # generated | saved
    material_id: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(20))
    color_family: Mapped[str | None] = mapped_column(String(20))
    tone: Mapped[str | None] = mapped_column(String(10))
    pattern: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
