# 05 r3 — roblox-tech-reviewer

## 판정: FAIL

## 이슈 수: 치명 0 / 중대 1 / 경미 2

## 이전 이슈 추적

| 이전 이슈 ID | 해결 여부 | 근거 한 줄 |
|---|---|---|
| 05-r1-T-03 | 해결 | 10.1 #14, 10.2 ButtonX 행, 10.3 #7, 10.7, 11.4, 13장 PROMPT_KEYS · COMBO_MODIFIER_GRACE_MS에 KeyboardKeyCode = F · GamepadKeyCode = ButtonX 명시, L1/R1 누르는 동안 + 100ms `ProximityPromptService.Enabled = false`, InputHoldBegin/End 모바일 전용, MaxPromptsVisible = 1이 반영됐다. 공식 yaml에서 Enabled("프롬프트를 켜고 표시할지", 보안 None · 클라이언트 쓰기 가능), PromptShown/PromptHidden("client-side")을 다시 확인해 기술적으로 타당하다. 같은 프레임 동시 입력 문제는 새 경미 05-r3-T-02로 올림 |
| 05-r2-T-01 | 해결 | 무적 구간 [t0, t0 + 0.2초] · t0 = 수신 − min(RTT/2, 150ms), 피해 기록 150ms 환급, 사망 유예, 확정 피해에도 무적, 이동 스킬 공통 적용, RTT = `Player:GetNetworkPing()` 이동 평균이 10.5 · 10.6 ④ · 13장에 반영됐다. GetNetworkPing은 공식 yaml에서 서버 호출이 가능하고 왕복 지연을 초 단위로 반환함을 확인했다. 다만 '체력 0 고정 사망 유예'는 로블록스 Humanoid 동작과 충돌한다. r2에서 내가 낸 제안 자체에 있던 결함이므로 새 중대 05-r3-T-01로 올림 |
| 05-r2-T-02 | 해결 | 10.6 '판정 주체'와 ②에 startPos · endPos 페이로드와 (i)~(iii) 검증 순서가 들어갔다 |
| 05-r2-T-03 | 해결 | 문맥 버튼을 x = 0.80U로 옮기고 표 열을 0.91U(364 / 377 / 546)로 고쳤다. 검산 결과 U = 400에서 364, 조이스틱 경계 379, 여유 15로 일치한다. X 버튼과의 간격도 약 54로 겹침이 없다 |
| 05-r2-T-04 | 해결 | 14.1 #12에 포크 확정, TouchJump · DynamicThumbstick 수정, TouchControlsEnabled 미사용, 포크 유지 규칙 3개가 반영됐다 |
| 05-r2-T-05 | 해결 | 5.4와 13장 SUMMON_CAP에 '본인의 가장 오래된 소환수 소멸, 본인 소환수가 없으면 1체로 축소', SK-V09 분신을 상한에 포함하는 규칙이 반영됐다 |

## 이슈

### 05-r3-T-01
- 등급: 중대
- 위치: 10.6 '이동형 스킬 권한' ④ "체력을 0으로 만드는 피해는 바로 사망 처리하지 않고 체력 0 고정 '사망 유예' 150ms"(869줄), 13장 DMG_HISTORY_MS / DEATH_GRACE_MS(1123줄), 4장 J-H4 최후의 시련("체력이 1 아래로 내려가지 않음")
- 위반 조항: 3-C(사실과 추정을 구분하고 로블록스 기술 제약에는 출처를 단다. 엔진 동작을 확인하지 않고 '체력 0 고정'을 설계함), 1-목표(이 문장대로 구현하면 사망을 취소할 수 없다)
- 수정 제안: 공식 Humanoid 문서는 이렇게 적는다. "Health가 0에 닿으면 Humanoid는 자동으로 Dead 상태로 바뀐다." "죽은 Humanoid의 Health는 계속 0으로 설정된다." BreakJointsOnDeath의 기본값은 true다. 또 "SetStateEnabled는 서버와 클라이언트 사이에 복제되지 않는다." 플레이어 캐릭터는 클라이언트가 소유하므로, 서버가 Dead 상태를 끄는 방법도 믿을 수 없다. 따라서 체력을 `Humanoid.Health`로 관리하면 '체력 0 고정 → 사망 취소'가 불가능하다. 피해를 환급해도 캐릭터는 이미 Dead이고 관절이 끊겨 있다. 10.6 ④와 13장에 다음을 명시한다. (1) **논리 체력은 서버 값으로 둔다**: 캐릭터 Attribute `HP` · `HPMax`를 서버만 쓴다. 모든 피해 · 회복 · 환급 · 보호막은 이 값에만 적용한다. (2) **`Humanoid.Health`는 표시용 거울**로 쓴다. 서버가 `Humanoid.Health = max(1, HP)`로 맞추고, 사망 유예 중에도 1을 유지한다. HUD 체력 바는 Attribute `HP`를 읽어 0으로 그린다. (3) **사망 확정** = DEATH_GRACE_MS가 지날 때까지 유효한 무적 요청이 없으면, 서버가 `Humanoid.Health = 0`을 설정하고 자체 사망 처리(04 7.6 사망 페널티 · 08 팀 생명 예산 차감)를 실행한다. 팀 생명 예산 차감과 사망 로그는 **확정 시점에만** 한다는 문장도 넣는다. (4) 유예 중 '행동 불가'에서 **피격 시각 이전 t0를 가진 대시 · 무적 요청은 예외**로 처리한다고 적는다. 지금 문장은 '행동 불가'와 '그 안에 무적 요청이 오면 사망 취소'가 서로 부딪친다. (5) 환급할 수 없는 효과를 정한다. 넉백 · 끌어당김처럼 위치를 바꾸는 효과는 서버가 RemoteEvent로 클라이언트에 지시한다. 클라이언트는 자신의 로컬 무적 구간 안이면 그 지시를 무시하고, 서버는 그 구간을 ②(i)의 위치 허용 오차로 받아준다. J-H4 최후의 시련의 '체력 1 하한'도 같은 논리 체력에 거는 규칙으로 적는다.

### 05-r3-T-02
- 등급: 경미
- 위치: 10.2 ButtonX 행(811줄), 10.3 #7 ②(838줄), 11.4 게임패드 ②(979줄)
- 위반 조항: 3-C(모든 스킬을 게임패드로도 플레이할 수 있어야 하고 입력 충돌 해결을 명시해야 함). 확인 필요
- 수정 제안: 두 가지는 공식 문서로 확인하지 못했다. ① L1과 X가 **같은 프레임**에 들어올 때, Lua의 L1 InputBegan 핸들러가 `ProximityPromptService.Enabled = false`를 실행하는 시점과 엔진이 GamepadKeyCode로 프롬프트를 발동하는 시점 중 어느 쪽이 먼저인지. ② ButtonX를 ContextActionService로 바인딩할 때 핸들러가 Sink를 반환하면 엔진 프롬프트 입력까지 막히는지. 그래서 아래 두 가지를 보험으로 적는다. (a) 즉시 발동하는 프롬프트(HoldDuration 0)를 두지 않고 **모든 프롬프트 HoldDuration ≥ 0.15초**로 한다(PROMPT_MIN_HOLD_SEC). 그러면 같은 프레임에 들어온 L1 + X는 홀드 시작에 그치고, 곧바로 Enabled = false가 되어 PromptHidden으로 홀드가 취소된다. (b) ButtonX의 CAS 핸들러는 수식 키가 눌려 있지 않으면 `Enum.ContextActionResult.Pass`를 반환한다. 그래야 단독 X가 프롬프트 쪽에 전달된다. 실제 동작은 11번 단계에서 실기 패드로 검증한다고 14.1에 추가한다.

### 05-r3-T-03
- 등급: 경미
- 위치: 3.6 '장소'(231줄, "허수아비 · 표적은 클라이언트별 로컬 개체") ↔ 3.6 '체험 스킬'("판정 · 계수는 실제와 같음") ↔ 10.6 '판정 주체'("피해 · 적중은 전부 서버")
- 위반 조항: 1-목표(문서 안 모순: 서버에는 로컬 허수아비가 없으므로 서버 판정을 할 수 없다)
- 수정 제안: 체험 모드의 판정 경로를 적는다. 체험 중 스킬 요청은 서버로 보내지 않는다. 클라이언트가 **서버와 같은 공유 ModuleScript**(피해 공식 5.4 · 스킬 표)로 로컬 허수아비에 대한 피해 숫자를 계산해 표시한다. 보상 · 경험치가 없으므로 위조해도 문제가 없다. 서버는 대여 무기 · 임시 Z 장착 · 체험 종료 복구(3.6 '종료 시')만 관리한다. 체험 중에는 서버 쪽 실제 스킬 요청을 거부한다(체험 플래그). 그래야 체험 마당 밖으로 나가 대여 무기 · 50% 비용으로 실제 몬스터를 치는 악용이 막힌다. 마당 경계를 벗어나면 서버가 체험을 즉시 종료한다.

## 확인한 외부 출처
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Player.yaml (create.roblox.com/docs/reference/engine/classes/Player 의 원본) — GetNetworkPing: "Returns the round-trip, isolated network latency in seconds." 서버에서 호출할 수 있다. 클라이언트에서는 LocalPlayer에만 동작한다. 지연은 역직렬화 · 처리 시간을 뺀 값이다. D-52 RTT 출처로 타당하다
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/ProximityPromptService.yaml (create.roblox.com/docs/reference/engine/classes/ProximityPromptService 원본) — Enabled: "Whether ProximityPrompts are enabled, and therefore shown, in-experience." 보안 None(읽기 · 쓰기). MaxPromptsVisible: 보이는 최대 프롬프트 수. PromptShown / PromptHidden: "Triggers client-side". D-52 프롬프트 차단 경로가 타당함을 확인했다(05-r1-T-03 해결 근거)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Humanoid.yaml (create.roblox.com/docs/reference/engine/classes/Humanoid 원본) — Health: "If the humanoid is dead, this property is continually set to 0." Health가 0에 닿으면 Dead 상태로 자동 전환된다. BreakJointsOnDeath 기본값 true. SetStateEnabled: "using SetStateEnabled() on the server does not replicate the change to the client, nor vice-versa"(05-r3-T-01 근거)
- https://create.roblox.com/docs/reference/engine/classes/Humanoid — 레퍼런스 페이지 요약본에는 Health 설명이 렌더링되지 않아 원본 yaml로 확인했다
