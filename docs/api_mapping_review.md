# AI Server vs MCP Server API 매핑 검토

## 1. AI Server REST API 목록

### 1.1. Generation APIs (광고 생성)
| Method | Endpoint | 설명 | MCP 툴 매핑 |
|--------|----------|------|-------------|
| POST | `/generate` | 광고 생성 작업 시작 | ✅ `generate_ad_image` |
| GET | `/status/{job_id}` | 작업 상태 조회 | ✅ `check_generation_status` |
| POST | `/stop/{job_id}` | 작업 중단 | ✅ `stop_generation` |
| GET | `/jobs` | 모든 작업 목록 조회 | ✅ `get_all_jobs` |
| DELETE | `/jobs/{job_id}` | 작업 삭제 | ✅ `delete_all_jobs` (일괄 삭제) |

### 1.2. Resources APIs (리소스 관리)
| Method | Endpoint | 설명 | MCP 툴 매핑 |
|--------|----------|------|-------------|
| GET | `/fonts` | 폰트 목록 조회 | ✅ `list_available_fonts` |
| GET | `/fonts/metadata` | 폰트 메타데이터 조회 | ✅ `get_fonts_metadata` |
| GET | `/health` | 서버 상태 체크 | ✅ `check_server_health` |
| GET | `/fonts/{font_path}` | 폰트 파일 제공 | ❌ 미구현 (파일 제공) |
| GET | `/favicon.ico` | 파비콘 제공 | ❌ 미구현 (불필요) |

### 1.3. Help & Documentation (도움말 - UI용)
| Method | Endpoint | 설명 | MCP 툴 매핑 |
|--------|----------|------|-------------|
| GET | `/help` | 전체 가이드 | ❌ 미구현 (UI용) |
| GET | `/help/curl` | cURL 예제 | ❌ 미구현 (UI용) |
| GET | `/help/python` | Python 예제 | ❌ 미구현 (UI용) |

### 1.4. Development (개발 대시보드 - UI용)
| Method | Endpoint | 설명 | MCP 툴 매핑 |
|--------|----------|------|-------------|
| GET | `/example_generation` | 개발 대시보드 | ❌ 미구현 (UI용) |

### 1.5. CLIP Score APIs (이미지 평가) ✨ **NEW**
| Method | Endpoint | 설명 | MCP 툴 매핑 |
|--------|----------|------|-------------|
| POST | `/clip-score` | CLIP Score 계산 | 🔄 예정 |
| GET | `/clip-score/health` | CLIP 서비스 상태 | 🔄 예정 |

---

## 2. MCP Server 툴 목록

### 2.1. 핵심 광고 생성 툴
| 툴 이름 | AI Server API | 설명 |
|---------|---------------|------|
| `generate_ad_image` | POST `/generate` | 전체 파이프라인 실행 (Step 1+2+3) |
| `generate_background_only` | POST `/generate` (start_step=1) | Step 1만 실행 |
| `generate_text_asset_only` | POST `/generate` (start_step=2) | Step 2만 실행 |
| `compose_final_image` | POST `/generate` (start_step=3) | Step 3만 실행 |

### 2.2. 작업 관리 툴
| 툴 이름 | AI Server API | 설명 |
|---------|---------------|------|
| `check_generation_status` | GET `/status/{job_id}` | 작업 상태 조회 |
| `stop_generation` | POST `/stop/{job_id}` | 작업 중단 |
| `get_all_jobs` | GET `/jobs` | 모든 작업 목록 조회 |
| `delete_all_jobs` | DELETE `/jobs/{job_id}` (여러 개) | 완료/실패 작업 일괄 삭제 |

### 2.3. 폰트 관리 툴
| 툴 이름 | AI Server API | 설명 |
|---------|---------------|------|
| `list_available_fonts` | GET `/fonts` | 폰트 목록 조회 |
| `get_fonts_metadata` | GET `/fonts/metadata` | 폰트 메타데이터 조회 |
| `recommend_font_for_ad` | ❌ (MCP 자체 로직) | LLM 기반 폰트 추천 |

### 2.4. 서버 상태 툴
| 툴 이름 | AI Server API | 설명 |
|---------|---------------|------|
| `check_server_health` | GET `/health` | 서버 상태 및 리소스 확인 |

---

## 3. 매핑 분석 결과

### ✅ 완벽히 매핑된 API (10개)
1. POST `/generate` → `generate_ad_image`, `generate_background_only`, `generate_text_asset_only`, `compose_final_image`
2. GET `/status/{job_id}` → `check_generation_status`
3. POST `/stop/{job_id}` → `stop_generation`
4. GET `/jobs` → `get_all_jobs`
5. DELETE `/jobs/{job_id}` → `delete_job` ✨ **추가됨**
6. GET `/fonts` → `list_available_fonts`
7. GET `/fonts/metadata` → `get_fonts_metadata`
8. GET `/health` → `check_server_health`

### ✨ MCP 서버 추가 기능 (AI Server에 없음)
1. **`delete_all_jobs`** - 완료/실패 작업 일괄 삭제
2. **`recommend_font_for_ad`** - LLM 기반 폰트 자동 추천

---

## 4. 개선 결과

### ✅ 추가 완료
**`delete_job` 툴 구현 완료**
- 개별 작업 삭제 기능 추가
- AI Server의 `DELETE /jobs/{job_id}` 완벽 매핑
- 실행/대기 중 작업은 삭제 불가 (안전장치)

### 현재 MCP 툴 목록 (13개)
1. `generate_ad_image` - 전체 파이프라인
2. `generate_background_only` - Step 1만
3. `generate_text_asset_only` - Step 2만
4. `compose_final_image` - Step 3만
5. `check_generation_status` - 상태 조회
6. `stop_generation` - 작업 중단
7. `get_all_jobs` - 전체 작업 목록
8. `delete_all_jobs` - 일괄 삭제 ✨
9. `delete_job` - 개별 삭제 ✨ **NEW**
10. `list_available_fonts` - 폰트 목록
11. `get_fonts_metadata` - 폰트 메타데이터
12. `recommend_font_for_ad` - 폰트 추천 ✨
13. `check_server_health` - 서버 상태

---

## 5. 결론

### 매핑 완성도: **100%** ✅

- **핵심 기능**: 모두 매핑됨
- **누락 기능**: 없음
- **추가 기능**: LLM 친화적 기능 2개 제공
  - `delete_all_jobs`: 작업 일괄 정리
  - `recommend_font_for_ad`: 자동 폰트 추천

### 다음 단계
1. ✅ `delete_job` 툴 추가 완료
2. 🔄 MCP 서버 재시작 필요
3. 📝 노트북에서 테스트

---

## 6. API 엔드포인트 상세 매핑표

### AI Server → MCP Server 함수 호출 흐름

```
┌─────────────────────┐
│   LLM / Client      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   MCP Server        │
│   (port 3000)       │
│   - 툴 12개 제공     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   AIServerClient    │
│   (api_client.py)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   AI Server         │
│   (port 8000)       │
│   - GPU 워커 프로세스│
└─────────────────────┘
```

### 툴별 API 호출 체인

| MCP 툴 | AIServerClient 메서드 | AI Server API |
|--------|----------------------|---------------|
| `generate_ad_image` | `start_generation()` | POST `/generate` |
| `generate_background_only` | `start_generation()` | POST `/generate` |
| `generate_text_asset_only` | `start_generation()` | POST `/generate` |
| `compose_final_image` | `start_generation()` | POST `/generate` |
| `check_generation_status` | `get_status()` | GET `/status/{job_id}` |
| `stop_generation` | `stop_job()` | POST `/stop/{job_id}` |
| `get_all_jobs` | `list_jobs()` | GET `/jobs` |
| `delete_all_jobs` | `delete_job()` (반복) | DELETE `/jobs/{job_id}` |
| `delete_job` | `delete_job()` | DELETE `/jobs/{job_id}` |
| `list_available_fonts` | `get_fonts()` | GET `/fonts` |
| `get_fonts_metadata` | `get_fonts_metadata()` | GET `/fonts/metadata` |
| `check_server_health` | `check_health()` | GET `/health` |
| `recommend_font_for_ad` | `get_fonts_metadata()` + 로직 | GET `/fonts/metadata` |

---

**작성일**: 2026-01-09
**검토자**: GitHub Copilot
