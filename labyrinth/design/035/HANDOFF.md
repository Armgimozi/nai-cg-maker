# 0.3.5 인수인계 (새 세션용)

이 세션(사용량 한도로 멈출 수 있음)에서 하던 0.3.5 구현을 다른 세션이 이어받을 때 읽는 메모.

## 어디에 무엇이 있나 (모두 GitHub Armgimozi/nai-cg-maker)
- 배포된 판: 브랜치 `claude/bold-darwin-nwa5vk` = 0.3.4.2 (12232f1). 작업 브랜치도 이것.
- 설계 자료: `backup/design-035` 의 `labyrinth/design/035/` — review2.md(최종 검토 + 구현 계획 §5, 주인 결정 §6), combat_spec, pvp_spec, look_spec, gear_spec, unique_spec, unique_assign_all.json, tools/(시뮬레이터·생성기)
- 구현 브랜치(20분마다 백업): `backup/int-035`(핵심 묶음 P0→P0b→P0c→P1→P2→P3, 그다음 통합·P6), `backup/p4-trial`(특별 시련, 끝남), `backup/p5-pack`(리소스팩)
- 구현 워크플로 스크립트: `labyrinth/design/035/workflow-impl-035.js` (경로는 원래 세션 기준 — 새 세션에서는 worktree·설계 경로를 고쳐 쓰기)

## 주인 결정 (최종) — review2.md §6 답
- B3: 보스 전설 2개(먹물 서고 지팡이·종말시계 단두도끼) 고유 효과 강도 0.6 으로 약하게
- B2: 무기 8개 추가 → 245개
- D1: 판금 그대로, 가죽 4부위 '구르기' 재사용 5초
- C1: 공격 속도 합계 +75%, 민첩 몫 +45%, 간격 하한 0.25초
- 그 밖: 무기 종류 없음 · 게이지 없음 + 무기별 간격 · 공격력 = 한 방 피해 + '공격 속도 초당 N회' 줄 · 힘 물리/지능 마법/민첩 공속·치명·회피 · 요구치 AND 만, 2~3 능력치 분할 · 장비 층 표시 없음(레벨 구간 풀) · PvP 한 방 상한 없음, 기절은 짧게+감소 누적+면역, 유리대포 방지 · 스탯 무료 초기화 1회 · 칭호 12개(0.3.4.1) 유지 · 어깨·등 장식 없음
- 검수: 주간 한도 때문에 마지막 검토 단계는 뺌 (리드가 팩·selftest·배포 zip 으로 직접 확인)

## 이어받는 법
1. 세 백업 브랜치를 가져와 worktree 로 만든다 (int-035, p4-trial, p5-pack).
2. `git log` 로 int-035 에 어느 묶음(P0, P0b, P0c, P1, P2, P3)까지 커밋됐는지 본다. 커밋 메시지 머리에 묶음 이름이 있다.
3. 남은 묶음부터 workflow-impl-035.js 의 프롬프트(COMMON + 묶음 설명)를 그대로 써서 차례로 진행 → INTEGRATE(P4·P5 합치기·팩 연결) → P6(툴팁·도감·문서·0.3.5).
4. 마지막: 팩 재생성(generate.py --no-preview) · check_assets · gen_enhance --check · 빌드/테스트 · 테스트 서버 10층 selftest · release.sh(SKIP_PACK=1, world.zip 은 main 의 labyrinth/dist) · 빈 폴더 검증 · `claude/bold-darwin-nwa5vk` 로 합쳐 push · jar 는 항상 `Labyrinth.jar` 이름으로 전달.
