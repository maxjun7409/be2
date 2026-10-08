"""추천용 선택 이력 기록. 게스트는 기록하지 않습니다."""
from sqlalchemy.orm import Session

from ..models import MaterialHistory, Scenario


def record(db: Session, user_id: str, scenario: Scenario, event: str) -> None:
    for entry in scenario.materials_used or []:
        db.add(MaterialHistory(
            user_id=user_id,
            scenario_id=scenario.scenario_id,
            event=event,
            material_id=entry["material_id"],
            category=entry["category"],
            color_family=entry.get("color_family"),
            tone=entry.get("tone"),
            pattern=entry.get("pattern"),
        ))
