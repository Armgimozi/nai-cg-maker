# CLAUDE.md — 로블록스 오픈월드 판타지 RPG 기획 프로젝트

> 이 저장소의 기존 코드(NAI CG maker, Flask)는 이 기획 작업과 무관하다. 기획 작업은 `design/` 폴더와 `.claude/agents/`에서만 이루어진다. 코드·로블록스 스튜디오 작업은 하지 않는다(기획 단계).

## 세션 재개 절차 (컨텍스트 압축·세션 단절 시)
1. `design/PROGRESS.md`를 먼저 읽는다 → 현재 단계·문서·라운드·판정을 확인한다.
2. `design/00_BRIEF.md`(기준 문서)와 `design/DECISIONS.md`, `design/ASSUMPTIONS.md`를 읽는다.
3. 진행 중인 문서가 있으면 그 문서와 `design/reviews/<문서번호>_r<라운드>_*.md`의 최신 라운드를 읽고 이어서 한다.

## 핵심 파일 경로
| 파일 | 역할 |
|---|---|
| `design/00_BRIEF.md` | 사용자 프롬프트 전문. 모든 판단·검수의 기준. 조항 인용 형식: `3-B-5`, `3-C`, `4-정량` |
| `design/PROGRESS.md` | 단계·문서·라운드·판정 현황 (매 라운드 갱신) |
| `design/DECISIONS.md` | 치명·중대 이슈별 수용/반박 결정과 근거, 메인의 설계 판단(PvP·전쟁 등) |
| `design/ASSUMPTIONS.md` | 불확실한 사항의 가정 + 영향받는 문서 목록 |
| `design/BACKLOG.md` | 경미 이슈 이관 |
| `design/OPEN_ISSUES.md` | 라운드 상한 초과·반복 되돌림(사용자 결정 필요) 이슈 |
| `design/reviews/` | 검수 결과. 파일명 `<문서번호>_r<라운드>_<검수자>.md` (예: `04_r1_system-reviewer.md`) |
| `design/01_reference.md` ~ `design/12_mvp_roadmap.md` | 기획 문서 본문 |
| `design/99_summary.md` | 최종 요약 |
| `.claude/agents/*.md` | 검수 서브에이전트 4종 (system / lore / roblox-tech / player-market) |

## 작업 규칙 요약 (자세한 내용은 00_BRIEF.md 3-A)
- 역할: 메인(오케스트레이터)이 문서를 쓰고 고친다. 검수자는 문서를 고치지 않고 `design/reviews/`에만 쓴다.
- 검수자 호출: model `claude-opus-5-5` 고정. 문서 성격에 맞는 2~3명 병렬. 02번과 3단계 통합 검수는 4명 전원.
- 검수자는 다른 검수자의 리뷰를 읽지 않는다(자기 이전 라운드는 가능). 메인에게는 판정·이슈 수·리뷰 경로만 돌려준다.
- 리뷰 형식: 판정(PASS/FAIL) + 이슈별 등급(치명/중대/경미)·위치·위반 조항·수정 제안. 칭찬·요약 금지. 조항 근거 없는 취향 지적은 경미까지만.
- 메인은 치명·중대마다 수용/반박을 정해 DECISIONS.md에 기록한다. 무조건 수용하지 않는다.
- 통과: 배정 검수자 전원 PASS(치명 0, 중대 0). 경미는 BACKLOG.md로.
- 문서당 최대 5라운드, 통합 검수 최대 3라운드. 초과 시 OPEN_ISSUES.md 정리 후 다음으로.
- 같은 이슈가 수정↔되돌림 2회 이상 반복 → '사용자 결정 필요'로 OPEN_ISSUES.md.
- 사용자에게 질문하지 않는다. 가정은 ASSUMPTIONS.md에 기록.
- 이슈 ID 규칙: `<문서번호>-r<라운드>-<검수자약자>-<번호>` (약자: S=system, L=lore, T=roblox-tech, M=player-market). 예: `06-r2-S-03`

## 문서 작성 규칙
- 전부 한국어. 수치는 표. 반복 데이터(아이템·스킬·몬스터·지역·NPC·아크·히든피스)는 ID가 있는 표로 쓴다.
- ID 접두어: 대륙 C-, 국가 N-, 도시 T-, 사냥터/던전 H-, 종족 RC-, 세력 F-, 시작위치 SP-, 직업 J-, 스킬 SK-, 아이템 IT-, 도안 BP-, 재료 MT-, 아크 A-, 히든피스 HP-, 레이드 보스 RB-, 랭킹 RK-, 상품 SH-, 거점 ST-, 분쟁 구역 PZ-, 대형 연결 사건 E-, 몬스터 MO-, 퀘스트 Q-, NPC NP-. **가정은 AS-**(ASSUMPTIONS.md), 설계 결정은 D-. A-는 아크 전용
- 사실/추정 구분. 로블록스 기술 제약은 출처(create.roblox.com/docs URL)를 적는다.
- 레퍼런스 고유명사·설정 재사용 금지. 모든 이름은 오리지널.
- 브랜치: `ccr-6327a4a9-gw3zyq`. 커밋 메시지는 한국어 요약.
