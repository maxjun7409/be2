# Matelier 백엔드 · AI 연결 · DB 전체 코드

앱(React Native) ↔ API 서버(FastAPI) ↔ AI 서버, 그리고 DB까지 한 번에 동작하는 최소 완성본입니다.

```
[앱]  ⇄  [API 서버 :8000]  ⇄  [AI 서버 :8001 (지금은 가짜)]
               ⇅
         [DB: SQLite → 나중에 Supabase]   [이미지: 서버 폴더 storage/]
```

## 폴더 구성

```
matelier/
├── backend/                     API 서버
│   ├── requirements.txt
│   ├── .env.example             설정 예시 (복사해서 .env로)
│   └── app/
│       ├── main.py              서버 시작점, 라우터 등록, 정리 작업
│       ├── config.py            .env 읽기
│       ├── db.py                DB 연결 (DATABASE_URL로 SQLite/PostgreSQL 전환)
│       ├── models.py            테이블 6개
│       ├── auth.py              Firebase 토큰 검증 (+ 개발용 X-Debug-Uid)
│       ├── permissions.py       "내 것만" 접근 검사
│       ├── storage.py           이미지 저장 (경로 저장, 응답 때 URL 변환)
│       ├── imaging.py           EXIF 회전, 썸네일, 오버레이, 브러시 반영
│       ├── colors.py            색 계열·톤 자동 계산
│       ├── ai_client.py         AI 서버 호출 (약속한 형식 검증)
│       ├── schemas.py           요청 형식
│       ├── serializers.py       응답 형식 (path → url)
│       ├── errors.py, handlers.py  공통 에러 형식
│       ├── routers/             users, projects, analyses, materials, generations, scenarios
│       └── services/            추천, 이력, 프리셋, 기본 마감재, 정리, 탈퇴
├── ai_mock/                     가짜 AI 서버
│   ├── main.py                  /segment, /refine, /compose
│   └── engine.py                가짜 분할 + "진짜" 명암 유지 합성
└── frontend/lib/
    ├── api.ts                   앱에서 쓰는 API 함수 전부 + 타입
    └── coords.ts                화면 터치 → 원본 이미지 픽셀 좌표 변환
```

---

## 1. 실행하기 (처음 한 번)

### 1-1. AI 서버 (터미널 1)

```bash
cd ai_mock
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 1-2. API 서버 (터미널 2)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
# .env에서 PUBLIC_BASE_URL을 내 PC의 와이파이 IP로 바꾸기 (ipconfig로 확인)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

처음 켜지면 `matelier.db` 파일과 기본 마감재 19개가 자동으로 만들어집니다.

### 1-3. 브라우저에서 테스트

`http://localhost:8000/docs` 를 열면 모든 API를 눌러서 테스트할 수 있습니다.

1. 각 API를 펼치면 Parameters에 `x-debug-uid` 칸이 있습니다. 여기에 `test-user` 입력 (DEV_AUTH=true일 때)
2. `POST /api/v1/projects` → 사진 파일 선택 → Execute → `project_id` 복사
3. `POST /api/v1/projects/{project_id}/analyses` → `analysis_id` 복사
4. `POST /api/v1/projects/{project_id}/generations`에 아래 본문:
   ```json
   { "analysis_id": "a_...", "materials": { "wall": "wall_0005", "floor": "floor_0003", "molding": "molding_0001" },
     "region_overrides": [ { "region_id": 2, "material_id": "wall_0008" } ] }
   ```
5. 응답의 `result_image_url`을 브라우저로 열면 합성 결과가 보입니다.

### 1-4. 폰에서 연결 확인

폰 브라우저로 `http://<PC IP>:8000/health` → `{"status":"ok"}`가 보이면 앱 연결 준비 완료.
안 되면: ① `--host 0.0.0.0` 빠졌는지 ② 같은 와이파이인지 ③ Windows 방화벽 8000 포트

---

## 2. 앱(프론트) 연결

### 2-1. 설정

`frontend/lib/api.ts`, `coords.ts`를 앱 프로젝트의 `lib/` 폴더에 복사합니다.

앱 루트 `.env`:
```
EXPO_PUBLIC_API_URL=http://192.168.0.10:8000
```

`app/_layout.tsx`:
```tsx
import { configureApi } from "../lib/api";
import { auth } from "../firebaseConfig";   // 팀의 Firebase 설정 파일 경로

configureApi({ getToken: () => auth.currentUser?.getIdToken() ?? null });
// 로그인 없이 테스트할 때: configureApi({ debugUid: "test-user" });
```

로그인/회원가입 성공 직후 한 번: `await api.upsertMe();`

### 2-2. 화면별 연결 코드

**이미지 확인 화면 → 업로드 + AI 분석**
```tsx
const project = await api.uploadProject(imageUri);      // 편집이 끝난 사진 uri
const analysis = await api.analyze(project.project_id);
if (analysis.wall_count === 0) {
  // "벽을 찾지 못했어요" 안내 → 직접 수정 또는 다시 촬영
}
router.push({ pathname: "/analysis-result",
  params: { projectId: project.project_id, analysisId: analysis.analysis_id } });
```

**분석 결과 확인 화면 ("공간이 잘 분석되었나요?")**
```tsx
<View>
  <Image source={{ uri: project.original_image_url }} style={StyleSheet.absoluteFill} resizeMode="contain" />
  <Image source={{ uri: analysis.overlay_url }} style={StyleSheet.absoluteFill} resizeMode="contain" />
</View>
// 벽 1, 벽 2 이름표: wallRegions(analysis).map((r, i) => `벽 ${i + 1}`)
```

**area-edit.tsx (브러시·지우개)**
```tsx
import { containRect, toImagePoint, toImageWidth } from "../lib/coords";

const rect = containRect(viewSize, { width: project.width, height: project.height });
// 터치할 때마다
const p = toImagePoint(e.nativeEvent.locationX, e.nativeEvent.locationY, rect,
                       { width: project.width, height: project.height });
if (p) currentStroke.points.push(p);
// 완료 버튼
const edited = await api.submitEdits(projectId, analysisId, strokes);
// strokes: [{ region_id: 1(벽1) | 0(지우개), width: toImageWidth(24, rect, size), points: [...] }]
```

**material-select.tsx**
```tsx
const { items, tips } = await api.getMaterials("wall", projectId);   // 추천 순으로 정렬됨
// item.recommendation?.reasons[0]?.message → "자주 고르신 밝은 톤이에요"
const { items: presets } = await api.getPresets(projectId);          // 밝은/아늑한/모던/내추럴
const maxPoints = maxPointWallpapers(analysis.wall_count);           // 벽 1개 → 0, 2개 → 1, 3개 → 2

const scenario = await api.generate(projectId, {
  analysis_id: analysisId,
  materials: { wall: baseWall, floor, molding },
  region_overrides: points,          // [{ region_id: 2, material_id: "wall_0008" }]
});
```

**최종 시안 화면**
```tsx
// 저장 → 홈
await api.saveScenario(scenario.scenario_id);
router.replace("/main");                       // push가 아니라 replace (뒤로가기 재저장 방지)

// 새 시안 만들기: 저장 후 같은 projectId, analysisId로 마감재 선택 화면에 돌아가면 끝
await api.saveScenario(scenario.scenario_id);
router.replace({ pathname: "/material-select", params: { projectId, analysisId } });
```
게스트가 저장하면 `ApiError.code === "GUEST_NOT_ALLOWED"` → 회원가입 안내.

**saved-designs.tsx / compare-designs.tsx**
```tsx
const { items, next_offset } = await api.listScenarios();
await api.deleteScenario(id);
const cmp = await api.compareScenarios(selectedIds);    // 2~3개
// cmp.different_categories → 표에서 다른 항목 강조, cmp.same_project=false면 "다른 공간" 안내
```

**에러 처리 공통**
```tsx
try { ... } catch (e) {
  if (e instanceof ApiError) Alert.alert("알림", e.message);   // 서버 메시지가 한국어로 옴
}
```

---

## 3. API 목록 (`/api/v1`)

| 메서드 | 경로 | 설명 | 게스트 |
|---|---|---|---|
| POST | /users/me | 로그인 직후 회원 정보 생성·갱신 | ✕ |
| GET / PATCH / DELETE | /users/me | 내 정보 / 수정 / 탈퇴 | ✕ |
| GET | /users/me/preferences | 내 취향 분석 결과 | ✕ |
| POST | /projects | 사진 업로드 (프로젝트 생성) | ○ |
| GET / PATCH / DELETE | /projects/{id} | 상세 / 이름 / 삭제 | ○ |
| POST | /projects/{id}/analyses | AI 공간 분석 | ○ |
| POST | /projects/{id}/analyses/{aid}/edits | 브러시 수정 반영 | ○ |
| GET | /materials?category=&project_id= | 마감재 + 추천 + 팁 | ○ |
| GET | /materials/presets | 스타일 추천 조합 | ○ |
| POST | /materials/uploads | 내 벽지 사진 업로드 | ○ |
| POST | /projects/{id}/generations | 최종 시안 생성 (초안) | ○ |
| POST | /scenarios/{sid}/save | 시안 저장 | ✕ |
| GET | /scenarios | 저장된 시안 목록 | ✕ |
| GET / PATCH / DELETE | /scenarios/{sid} | 정보 보기 / 이름 / 삭제 | ✕ |
| POST | /scenarios/compare | 2~3개 비교 | ✕ |

에러는 항상 `{"error": {"code": "...", "message": "...", "details": ...}}`.

---

## 4. 인증 켜기 (Firebase)

1. Firebase 콘솔 → 프로젝트 설정 → 서비스 계정 → **새 비공개 키 생성** → `backend/firebase-service-account.json`으로 저장
2. 게스트 모드는 앱에서 **Firebase 익명 로그인**(`signInAnonymously`)을 쓰면 서버가 자동으로 게스트로 인식합니다 (Firebase 콘솔 > Authentication > 익명 사용 설정).
3. 키 파일은 **절대 GitHub에 올리지 마세요** (.gitignore에 포함됨).

## 5. DB를 Supabase로 옮기기

1. Supabase 프로젝트 생성 → Connect → **Session pooler** 연결 문자열 복사
2. `.env`의 `DATABASE_URL`을 `postgresql+psycopg://...` 형식으로 교체
3. 서버 재시작 → 테이블과 기본 마감재가 자동 생성됩니다. 코드 수정은 필요 없습니다.

무료 플랜은 일주일 동안 사용이 없으면 일시 정지되니, 발표 전날 꼭 접속해서 확인하세요.

## 6. 진짜 AI로 교체하기

`ai_mock/engine.py`의 `fake_segment()`만 진짜 모델 추론으로 바꾸면 됩니다. 지켜야 할 약속:
- 결과 마스크: 원본과 **같은 크기**의 흑백 PNG, 픽셀값 = region_id (0 = 영역 없음)
- 영역 이름: `wall`, `floor`, `ceiling`, `molding`, `window`
- 벽 번호: **왼쪽부터** 1, 2, 3 (포인트 벽지·3D 미리보기와 일치시키기 위해)

`compose()`는 이미 원본의 명암을 유지하는 실제 합성이라 그대로 써도 됩니다.

## 7. 지금 버전의 한계 (배포 전 체크리스트)

- `DEV_AUTH=false`로 바꾸기
- `/files/...` 이미지는 주소만 알면 누구나 볼 수 있음 → 실제 서비스에서는 Supabase/Firebase Storage의 서명 URL로 교체 (`storage.py`만 수정)
- 테이블 구조를 바꿀 일이 많아지면 Alembic(마이그레이션 도구) 도입
- 가짜 AI는 모든 사진을 같은 비율(천장/벽 2개/몰딩/바닥)로 나눕니다
- 영역 수정은 기존 영역(벽 1, 벽 2 …)으로만 칠할 수 있음. 새 벽을 추가하는 기능은 아직 없음
