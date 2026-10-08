"""규칙 기반(Rule-based) 추천.

점수 = 0.4 × 톤 선호 + 0.4 × 색 계열 선호 + 0.2 × 무늬 선호 + 공간 조건 가산점
- 선호도: 사용자의 선택 이력에서 계산 (생성 1점, 저장 3점)
- 공간 조건: 원본 사진이 어두우면 밝은 톤 벽지에 가산점 (사진에서 실제로 측정 가능한 조건만 사용)
"""
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..colors import FAMILY_KO
from ..models import Material, MaterialHistory, Project

EVENT_WEIGHT = {"generated": 1, "saved": 3}
MIN_EVENTS = 3            # 이력이 이보다 적으면 취향 추천을 하지 않음 (콜드 스타트)
DARK_THRESHOLD = 0.4      # 사진 평균 밝기가 이보다 낮으면 '어두운 공간'
HISTORY_LIMIT = 500


def _normalize(counter: Counter) -> dict:
    total = sum(counter.values())
    return {k: round(v / total, 3) for k, v in counter.items()} if total else {}


def preference_summary(db: Session, user_id: str) -> dict:
    rows = db.execute(
        select(MaterialHistory.event, MaterialHistory.tone,
               MaterialHistory.color_family, MaterialHistory.pattern)
        .where(MaterialHistory.user_id == user_id)
        .order_by(MaterialHistory.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    tone, family, pattern = Counter(), Counter(), Counter()
    for event, t, f, p in rows:
        w = EVENT_WEIGHT.get(event, 1)
        if t: tone[t] += w
        if f: family[f] += w
        if p: pattern[p] += w
    return {
        "event_count": len(rows),
        "tone": _normalize(tone),
        "color_family": _normalize(family),
        "pattern": _normalize(pattern),
    }


def is_dark(project: Project | None) -> bool:
    return bool(project and project.brightness is not None and project.brightness < DARK_THRESHOLD)


def score_materials(db: Session, user: CurrentUser, materials: list[Material],
                    project: Project | None) -> dict[str, dict | None]:
    prefs = None if user.is_anonymous else preference_summary(db, user.uid)
    use_prefs = bool(prefs and prefs["event_count"] >= MIN_EVENTS)
    dark = is_dark(project)

    result: dict[str, dict | None] = {}
    for m in materials:
        score, reasons = 0.0, []
        if use_prefs:
            t = prefs["tone"].get(m.tone, 0)
            c = prefs["color_family"].get(m.color_family, 0)
            p = prefs["pattern"].get(m.pattern, 0)
            score += 0.4 * t + 0.4 * c + 0.2 * p
            if t >= 0.6:
                tone_ko = "밝은" if m.tone == "bright" else "어두운"
                reasons.append({"code": "PREFERRED_TONE", "message": f"자주 고르신 {tone_ko} 톤이에요"})
            if c >= 0.35:
                reasons.append({"code": "PREFERRED_COLOR",
                                "message": f"자주 고르신 {FAMILY_KO.get(m.color_family, m.color_family)} 계열이에요"})
        if dark and m.category == "wall" and m.tone == "bright":
            score += 0.2
            reasons.append({"code": "DARK_ROOM_BRIGHT", "message": "채광이 적은 공간이라 밝은 톤을 추천해요"})
        result[m.material_id] = {"score": round(score, 3), "reasons": reasons} if reasons else None
    return result


def space_tips(project: Project | None) -> list[dict]:
    tips = []
    if is_dark(project):
        tips.append({"code": "DARK_ROOM",
                     "message": "사진이 어두운 편이에요. 밝은 톤이나 반사율이 높은 마감재를 고려해보세요."})
    # 아래는 사진으로 측정하지 않는 '일반 팁'입니다 (공간 크기·천장 높이는 사진 한 장으로 판단 불가).
    tips.append({"code": "GENERAL_SMALL_SPACE",
                 "message": "작은 공간이라면 큰 무늬보다 단색이나 잔잔한 패턴이 덜 답답해 보여요."})
    tips.append({"code": "GENERAL_LOW_CEILING",
                 "message": "천장이 낮게 느껴진다면 세로 패턴 벽지가 공간을 높아 보이게 해요."})
    return tips
