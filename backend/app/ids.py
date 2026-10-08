"""ID 발급. 접두사로 종류를 구분합니다: p_(프로젝트) a_(분석) s_(시안) user_(사용자 마감재)."""
import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
