"""스타일 추천 조합 (프론트의 '밝은 공간 / 아늑한 공간 / 모던 스타일')."""
PRESETS = [
    {
        "preset_id": "bright",
        "name": "밝은 공간",
        "description": "화이트 벽과 밝은 우드 바닥으로 넓고 환해 보이는 조합",
        "materials": {"wall": "wall_0001", "floor": "floor_0001", "molding": "molding_0001"},
    },
    {
        "preset_id": "cozy",
        "name": "아늑한 공간",
        "description": "베이지 벽과 짙은 우드 바닥으로 따뜻한 분위기",
        "materials": {"wall": "wall_0004", "floor": "floor_0003", "molding": "molding_0004"},
    },
    {
        "preset_id": "modern",
        "name": "모던 스타일",
        "description": "그레이 톤으로 정돈된 도시적인 분위기",
        "materials": {"wall": "wall_0003", "floor": "floor_0004", "molding": "molding_0003"},
    },
    {
        "preset_id": "natural",
        "name": "내추럴",
        "description": "세이지 그린과 오크 바닥으로 편안한 자연 느낌",
        "materials": {"wall": "wall_0005", "floor": "floor_0002", "molding": "molding_0002"},
    },
]
