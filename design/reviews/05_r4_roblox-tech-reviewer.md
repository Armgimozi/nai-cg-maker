# 05 r4 — roblox-tech-reviewer

## 판정: FAIL

## 이슈 수: 치명 0 / 중대 1 / 경미 0

## 이전 이슈 추적

| 이전 이슈 ID | 해결 여부 | 근거 한 줄 |
|---|---|---|
| 05-r3-T-01 | 해결 | 10.6 ④ (가)~(라), 사망 유예, 사망 확정, 환급 불가 효과, 12.1 비저장 Attribute 행, 13장 HP_SOURCE · HP_MIRROR · DMG_HISTORY_MS / DEATH_GRACE_MS · KNOCKBACK_AUTHORITY, SK-H4-04, 출처 [17]에 r3 제안 (1)~(5)가 모두 반영됐다. 출처 [17]의 Humanoid 동작 설명도 공식 yaml과 일치한다. 다만 이번 분리로 '서버가 확정하지 않은 엔진 쪽 사망' 경로가 새로 생겼고 규칙이 비어 있다. 이 문제는 새 중대 05-r4-T-01로 올림 |
| 05-r3-T-02 | 미해결(BACKLOG 이관) | 경미라 BACKLOG에 넘어갔다. 재등록하지 않는다 |
| 05-r3-T-03 | 미해결(BACKLOG 이관) | 경미라 BACKLOG에 넘어갔다. 재등록하지 않는다 |

## 이슈

### 05-r4-T-01
- 등급: 중대
- 위치: 10.6 '이동형 스킬 권한' ④ '사망 확정'(870줄), 12.1 비저장 캐릭터 Attribute 행 "접속 · 리스폰 시 HP = HPMax"(1014줄), 13장 DMG_HISTORY_MS / DEATH_GRACE_MS(1127줄)
- 위반 조항: 1-목표(개발자가 추가 질문 없이 구현할 수 있어야 함), 3-B-10(레이드 팀 생명 예산 무결성), 3-C(서버 권한 · 치트 대책)
- 수정 제안: D-60 이후 사망 처리(04 7.6 사망 페널티 · 08 팀 생명 예산 차감 · 사망 로그)는 '논리 HP 0 → DEATH_GRACE_MS 경과' 경로에서만 실행된다. 하지만 Humanoid는 그 경로를 거치지 않고도 죽는다. 사례는 두 가지다. (a) 로블록스 기본 메뉴의 **캐릭터 리셋 버튼**. 공식 문서는 `StarterGui:SetCore("ResetButtonCallback", …)`로 이 버튼의 동작을 끄거나 BindableEvent로 바꿀 수 있다고 적는다. 기본값에서는 리셋하면 그냥 죽는다. (b) **`Workspace.FallenPartsDestroyHeight` 아래로 떨어지는 경우**. 엔진이 파트와 조상 Model을 nil로 보내므로 캐릭터가 사라진다. 지금 문서대로 구현하면 이 두 경우에 논리 HP > 0인 채로 캐릭터가 죽는다. 서버 사망 처리는 실행되지 않고, 리스폰 때 HP = HPMax가 된다. 그러면 레이드나 던전에서 체력이 바닥난 플레이어가 리셋 한 번으로 **팀 생명 예산 차감 없이 체력을 가득 채울 수 있다**. 사망 페널티(내구도 −10%)도 피하고, 04 7.6의 부활 위치 선택 UI도 거치지 않는다. 10.6 ④와 13장에 다음 3줄을 넣는다. (1) `StarterGui:SetCore("ResetButtonCallback", BindableEvent)`로 리셋 버튼을 서버 요청으로 바꾼다. 서버는 비전투 상태(5초)에서만 받아 주고, 받은 요청은 '사망 확정'과 같은 자체 사망 처리로 보낸다. 전투 중이거나 레이드 · 던전 인스턴스 안이면 거부하거나 사망으로 확정해 팀 생명 예산을 차감한다. 메인이 둘 중 하나를 고른다. (2) 서버는 `Humanoid.Died`와 `Player.CharacterRemoving`을 감시한다. 서버가 확정한 사망이 아닌데 캐릭터가 죽거나 사라지면 **엔진 사망**으로 보고, 논리 HP를 0으로 만든 뒤 같은 자체 사망 처리(사망 페널티 · 팀 생명 예산 차감 · 사망 로그 · 부활 위치 선택)를 실행한다. 사망 유예는 적용하지 않는다. (3) 낙사 높이는 맵 최저 지형보다 충분히 낮게 둔다. 맵 밖 추락은 엔진 사망 규칙 (2)로 처리한다(별도 낙하 피해를 두지 않는다면 그렇게 명시). 구현 세부(PlayerModule · CharacterAutoLoads 처리)는 11로 넘겨도 되지만, '엔진 사망도 서버 사망 처리와 동일하게 집계한다'는 규칙은 이 문서의 사망 정의에 있어야 한다.

## 확인한 외부 출처
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/StarterGui.yaml (create.roblox.com/docs/reference/engine/classes/StarterGui 원본): SetCore "ResetButtonCallback"은 "Determines the behavior, if any, of the reset button given a boolean or a BindableEvent to be fired when a player requests to reset." 불리언으로 기본 리셋 동작 유지 여부를 정하고, BindableEvent를 주면 플레이어가 리셋을 확인할 때 그 이벤트가 발생한다(05-r4-T-01 근거)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Workspace.yaml (create.roblox.com/docs/reference/engine/classes/Workspace 원본): FallenPartsDestroyHeight는 "the height at which the engine automatically removes falling BaseParts and their ancestor Models from Workspace by parenting them to nil"이다. 모델의 마지막 파트가 제거되면 모델도 제거된다(05-r4-T-01 근거)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Humanoid.yaml (r3에서 확인): Health가 0이 되면 Dead로 전환되고, BreakJointsOnDeath 기본값은 true이며, SetStateEnabled는 복제되지 않는다. 문서 출처 [17]과 일치함을 재확인했다(05-r3-T-01 해결 근거)
