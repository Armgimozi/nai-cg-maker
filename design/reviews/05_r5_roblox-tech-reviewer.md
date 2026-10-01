# 05 r5 — roblox-tech-reviewer

## 판정: PASS

## 이슈 수: 치명 0 / 중대 0 / 경미 1

## 이전 이슈 추적

| 이전 이슈 ID | 해결 여부 | 근거 한 줄 |
|---|---|---|
| 05-r4-T-01 | 해결 | r4 제안 (1)~(3)이 모두 반영됐다. (1)은 10.6 ④ '엔진 사망 (1)'과 13장 RESET_POLICY에 있다. 리셋 버튼을 서버 요청으로 바꿨고, 비전투 5초 이상이면서 인스턴스 밖이면 '귀환', 전투 중이거나 인스턴스 안이면 사망 확정으로 처리한다. 메인이 둘 중 하나를 고르라는 요청에는 상황별로 나눠 답했다. (2)는 '엔진 사망 (2)'와 ENGINE_DEATH_HANDLING에 있다. Died와 CharacterRemoving을 감시해 서버가 확정하지 않은 사망을 같은 자체 사망 처리로 보내고, 사망 유예는 적용하지 않는다. (3)은 '낙사 높이 (3)'에 있다. 낙사 높이를 최저 지형 Y − 100 studs 이하로 두고, 낙하 피해는 두지 않는다고 명시했다. 12.1 행의 '리스폰 시 HP = HPMax는 서버 사망 처리를 거친 리스폰에만 적용'과 출처 [18]·[19]도 갖췄다. 리셋 콜백을 건너뛰는 변조 클라이언트도 (2)에서 사망으로 잡히므로 우회 경로가 남지 않는다 |
| 05-r3-T-02 | 미해결(BACKLOG 이관) | 경미라 BACKLOG에 넘어갔다. 재등록하지 않는다 |
| 05-r3-T-03 | 미해결(BACKLOG 이관) | 경미라 BACKLOG에 넘어갔다. 재등록하지 않는다 |

## 이슈

### 05-r5-T-01
- 등급: 경미
- 위치: 10.6 ④ '엔진 사망 (2)'의 제외 목록('접속 종료'), 12.1 비저장 캐릭터 Attribute 행 "접속 시 HP = HPMax"(1015줄), 13장 ENGINE_DEATH_HANDLING(1131줄)
- 위반 조항: 3-B-10(레이드 팀 생명 예산 무결성). 08·11에서 해결할 수 있으므로 경미로 둔다
- 수정 제안: 접속 종료로 캐릭터가 사라지는 경우는 엔진 사망에서 빠진다. 접속하면 HP = HPMax가 된다. 이 두 규칙이 겹치면 구멍이 생긴다. 전투 중이거나 사망 유예 중(HP = 0)인 플레이어가 접속을 끊고 다시 들어오면 사망 처리를 건너뛰고 체력이 가득 찬다. 레이드처럼 재입장이 허용되는 곳에서는 팀 생명 예산 차감도 피한다. 08(레이드 재입장 규칙)이나 11(세션 처리)에 아래 둘 중 하나를 넣는다. (a) 전투 중이거나 인스턴스 안에서 접속이 끊기면 사망 확정과 같은 처리를 한다(유예 중이면 무조건 사망 확정). (b) 접속이 끊길 때 논리 HP를 세션 데이터(MemoryStore, TTL은 재입장 허용 시간)에 남겨 두고, 재접속하면 그 값으로 복원한다. 이 문서에서는 ENGINE_DEATH_HANDLING 비고에 "접속 종료 중 전투 · 유예 상태 처리는 08 · 11"이라는 참조 한 줄만 있으면 된다.

## 확인한 외부 출처
- https://create.roblox.com/docs/reference/engine/classes/Player#CharacterRemoving : 페이지에는 'Detecting Player Spawns and Despawns' 코드 예제에 이벤트가 쓰인다는 것만 나온다. 접속 종료 때 이벤트가 발생하는지는 적혀 있지 않다. 문서가 '접속 종료'를 엔진 사망에서 명시적으로 빼고 있으므로, 이 이벤트가 접속 종료 때 발생하든 안 하든 규칙은 성립한다
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/StarterGui.yaml (r4에서 확인): SetCore "ResetButtonCallback"에 BindableEvent를 주면 플레이어가 리셋을 확인할 때 그 이벤트가 발생한다. 문서 출처 [18]과 일치한다
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Workspace.yaml (r4에서 확인): FallenPartsDestroyHeight 아래로 떨어진 파트와 조상 Model은 nil로 보내진다. 문서 출처 [19]와 일치한다
