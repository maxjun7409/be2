"""요청(Request) 본문 형식. 응답 형식은 serializers.py에 있습니다."""
from pydantic import BaseModel, Field


class UserUpsert(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=30)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    settings: dict | None = None


class TitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class Stroke(BaseModel):
    region_id: int = Field(ge=0, le=255, description="칠할 영역 ID. 0이면 지우개")
    width: float = Field(gt=0, le=500, description="브러시 두께 (원본 이미지 픽셀 기준)")
    points: list[tuple[float, float]] = Field(min_length=1, max_length=5000,
                                              description="원본 이미지 픽셀 좌표 [[x, y], ...]")


class MaskEditRequest(BaseModel):
    strokes: list[Stroke] = Field(min_length=1, max_length=500)


class RegionOverride(BaseModel):
    region_id: int
    material_id: str


class GenerationRequest(BaseModel):
    analysis_id: str
    # {"wall": "wall_0003", "floor": "floor_0002", "molding": "molding_0001"}  (일부만 보내도 됨)
    materials: dict[str, str] = Field(default_factory=dict)
    # 포인트 벽지: 특정 벽만 다른 벽지로
    region_overrides: list[RegionOverride] = Field(default_factory=list)


class SaveRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)


class CompareRequest(BaseModel):
    scenario_ids: list[str] = Field(min_length=2, max_length=3)
