"""소유권 검사. 남의 리소스는 '없는 것'처럼 404를 돌려줍니다 (존재 여부도 숨김)."""
from fastapi import Depends
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_any_user
from .db import get_db
from .errors import AppError
from .models import Analysis, Project, Scenario


def get_owned_project(
    project_id: str,
    user: CurrentUser = Depends(get_any_user),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.uid:
        raise AppError(404, "PROJECT_NOT_FOUND", "프로젝트를 찾을 수 없습니다.")
    return project


def get_owned_scenario(
    scenario_id: str,
    user: CurrentUser = Depends(get_any_user),
    db: Session = Depends(get_db),
) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.owner_id != user.uid:
        raise AppError(404, "SCENARIO_NOT_FOUND", "시안을 찾을 수 없습니다.")
    return scenario


def get_project_analysis(db: Session, project: Project, analysis_id: str) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or analysis.project_id != project.project_id:
        raise AppError(404, "ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.")
    return analysis
