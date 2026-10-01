# 05 r2 — roblox-tech-reviewer

## 판정: FAIL

## 이슈 수: 치명 0 / 중대 2 / 경미 4

## 이전 이슈 추적

| 이전 이슈 ID | 해결 여부 | 근거 한 줄 |
|---|---|---|
| 05-r1-T-01 | 해결 | D-44로 10.6에 '이동형 스킬 권한' 행 추가(클라이언트 즉시 이동, 서버 거리·Raycast 검증과 롤백, WalkSpeed 서버 변경, 위치 기록 40개). 되감기 상한을 150ms로 둔 것은 설계 판단으로 수용. 무적 구간 식과 소급 적용 방식은 새 이슈 05-r2-T-01로 올림 |
| 05-r1-T-02 | 해결 | 10.2 ButtonR3 행에 '기본 바인딩 충돌 → 해제', 10.3 2-b에 PlayerModule 포크와 대안(BindActionAtPriority + Sink), 10.4에 '금지 ② 해제한 기본 키'(I·O·R3) 반영 |
| 05-r1-T-03 | 미해결 | `Style = Custom`은 기본 UI만 없앤다. 엔진의 키 발동(KeyboardKeyCode 기본 E, GamepadKeyCode 기본 ButtonX)은 그대로 남는다(공식 API 문서). 문서에는 엔진 발동을 끄는 방법이 없어서, PC E(무기 스킬 2)와 패드 L1+X(무기 스킬 Q)가 상호작용과 함께 발동하는 충돌이 그대로다. r1 제안 (b)가 불완전했던 점까지 포함해 아래에 같은 ID로 다시 올림 |
| 05-r1-T-04 | 해결 | 10.3 #2 코드가 `false`로 바뀌었고 RightShift 추가 |
| 05-r1-T-05 | 해결 | U = clamp(H, 400, 600)과 모든 버튼 하한(64/52/48) 반영, 11.1 검산표 신설 |
| 05-r1-T-06 | 해결 | 11.2 안전 영역을 ScreenInsets 하나로 지정(CoreUISafeInsets / DeviceSafeInsets), 출처 [15] 추가 |
| 05-r1-T-07 | 해결 | 10.6 매크로 행이 서버 수신 시각 기준, 쿨 종료 후 ±1틱 분포, 길게 누르기와 탭 연타 구분, 검토 큐 적재로 바뀜 |
| 05-r1-T-08 | 해결 | 5.4에 SUMMON_CAP_PER_PLAYER 4 / SERVER 40, Anchored 모델 + 간이 AI, 타인 이펙트 생략 명시 |
| 05-r1-T-09 | 해결 | 10.2 ButtonSelect 행에 SelectedObject 처리, 14.3 #3 '공식 문서 미기재', 14.1 #6 Backpack '확인 못함' 명시 |
| 05-r1-T-10 | 해결 | SK-J6-06 · SK-H2-04가 사전 지정 + 버튼 1회 발동, 길게 누르면 선택 링(이동 유지) |
| 05-r1-T-11 | 해결 | 12.1에 계정 단위 표를 분리하고 inputBindings 크기 추정 2.6KB 추가 |

## 이슈

### 05-r1-T-03
- 등급: 중대
- 위치: 10.2 ButtonX 행(787줄), 10.3 #7(814줄), 11.4 게임패드 행(955줄), 10.7 '쓰러진 파티원'(862줄), 14.3 #12
- 위반 조항: 3-C(PC 키가 기준이지만 모든 스킬을 게임패드로도 플레이할 수 있어야 하고 입력 충돌 해결을 명시해야 함), 1-목표(개발자가 추가 질문 없이 구현 착수)
- 수정 제안: ProximityPrompt API 문서에는 "Style이 Custom이면 기본 UI를 제공하지 않는다"는 설명만 있다. 키 입력으로 발동하는 기능은 Style과 관계없이 남는다. 또 KeyboardKeyCode 기본값은 **E**, GamepadKeyCode 기본값은 **ButtonX**다. 그래서 지금 문서대로 Style = Custom만 지정하면 PC에서 NPC 옆에서 E(무기 스킬 2)를 누를 때, 패드에서 L1+X를 누를 때 프롬프트가 함께 발동한다. 자체 핸들러의 InputHoldBegin 경로는 '추가' 경로일 뿐이고 엔진 경로를 막지 못한다. 10.3 #7과 11.4를 아래처럼 고칠 것을 제안한다. (1) 모든 프롬프트에 `KeyboardKeyCode = F`(10.4 재배치 값), `GamepadKeyCode = ButtonX`를 명시해서 만든다. 재배치하면 클라이언트가 PromptShown 시점에 해당 프롬프트의 KeyCode를 새 값으로 덮어쓴다. (2) 클라이언트는 ButtonL1 · ButtonR1을 누르는 동안과 뗀 뒤 COMBO_MODIFIER_GRACE_MS(100ms) 동안 `ProximityPromptService.Enabled = false`로 둔다(엔진 발동 자체를 끄는 공식 속성). 그사이 자체 프롬프트 UI는 PromptHidden에 따라 잠시 숨겨진다. (3) InputHoldBegin/End는 모바일의 자체 프롬프트 버튼을 탭할 때만 쓴다(공식 문서가 밝힌 용도). (4) '가장 가까운 1개'는 `ProximityPromptService.MaxPromptsVisible = 1`로 보장한다. 되살림의 문맥 발동과 일으키기도 같은 규칙을 따른다고 적는다. 10.2 충돌 열 문구도 "Style = Custom + 수식 키 중 ProximityPromptService 비활성"으로 고친다.

### 05-r2-T-01
- 등급: 중대
- 위치: 10.6 '이동형 스킬 권한' ④(845줄), 10.5 '판정 동등'(838줄), 13장 IFRAME_REWIND_MS_CAP(1087줄), 6.1 SK-J3-04 전이 · 7.3 SK-W2-03 후퇴 사격(0.3초 무적), SK-J5-06 암습 연격(회피 100%)
- 위반 조항: 3-C(모바일 입력 지연 공정. 10.5가 '대시 무적 0.2초 플랫폼 공통'을 약속함), 1-목표
- 수정 제안: (a) 구간 식이 모순이다. 무적 구간이 [수신 − r, 수신 + 0.2초]이면 길이가 0.2 + r이 되어, RTT 300ms 유저는 무적이 0.35초가 된다. 지연이 클수록 무적이 길어져서 10.5의 '0.2초 공통'과 맞지 않는다. 식을 **[t0, t0 + 0.2초], t0 = 수신 시각 − r, r = min(RTT/2, 150ms)** 로 고친다. (b) 서버는 무적 시작을 과거로 되돌리는데, 그 사이 이미 적용한 피해를 어떻게 처리할지 정의가 없다. 그래서 '되감기'를 구현할 수 없다. 제안은 다음과 같다. 서버가 플레이어별로 최근 150ms 동안 받은 피해 기록(서버 시각 · 피해량 · 부여된 상태이상)을 보관하고, 대시 요청을 받으면 t0 이후에 들어온 피해를 환급한다(체력 복구 · 그 피해로 걸린 상태이상 제거). 치명 피해는 바로 사망 처리하지 않는다. 체력 0으로 고정한 '사망 유예'를 IFRAME_REWIND_MS_CAP(150ms) 동안 둔다. 그 안에 t0 ≤ 피격 시각인 대시 요청이 오면 사망을 취소하고, 오지 않으면 사망을 확정한다. 보스 '확정 피해'(5.6)도 환급 대상인지 명시한다(권장: 무적 판정은 확정 피해에도 적용, 감소 · 보호막 무시만 유지). (c) 같은 규칙을 전이(0.3초) · 후퇴 사격(0.3초) · 암습 연격(회피 100%)에도 적용한다고 적는다. (d) RTT 출처를 `Player:GetNetworkPing()`(서버에서 호출, 왕복 지연을 초 단위로 반환)의 이동 평균으로 정한다.

### 05-r2-T-02
- 등급: 경미
- 위치: 10.6 '판정 주체'(844줄) ↔ '이동형 스킬 권한' ②(845줄)
- 위반 조항: 1-목표(문서 안 모순)
- 수정 제안: '판정 주체'는 "클라이언트는 입력(스킬 ID · 방향 · 대상 ID)만 보낸다"고 하는데, ②는 서버가 '도착 위치'를 검사한다고 한다. 서버가 RemoteEvent를 받는 시점에 캐릭터 위치 복제가 이미 도착했는지는 순서가 보장되지 않으므로, 서버는 수신 시점에 도착 위치를 알 수 없다. 이동형 스킬의 페이로드에 `startPos` · `endPos`를 추가하고, 다음 순서로 검증한다고 적는다. ① startPos와 서버가 마지막으로 아는 위치의 차이 ≤ WalkSpeed × RTT + MOVE_VALIDATE_TOL. ② |endPos − startPos| ≤ 스킬 거리 + MOVE_VALIDATE_TOL이고 Raycast에 막힘이 없다. ③ 수신 후 RTT + 0.25초 안에 복제된 위치가 endPos ± 2 studs인지 확인하고, 실패하면 롤백. 돌진 경로 피해 판정은 검증된 startPos → endPos 선분으로 서버가 계산한다.

### 05-r2-T-03
- 등급: 경미
- 위치: 11.1 '겹침 0 검산' 표 '클러스터 왼쪽 끝' 열(912~915줄)
- 위반 조항: 1-목표(검산값 오류)
- 수정 제안: 문맥 버튼은 '원점 기준 x = 0.82U'이고 원점은 오른쪽 끝에서 0.05U 안쪽이므로, 오른쪽 끝에서 잰 왼쪽 끝은 0.05U + 0.82U + 0.06U = 0.93U다. 표 값은 원점 오프셋을 빠뜨린 0.88U다. 바르게 고치면 U = 400 → 372(표 352), U = 414 → 385(표 364), U = 600 → 558(표 528)이다. H = 320 · 16:9의 조이스틱 경계 379와의 여유는 7로 줄어든다(겹침은 여전히 0). 표를 고치고, 여유 8 이상을 원하면 문맥 버튼을 x = 0.80U로 옮긴다.

### 05-r2-T-04
- 등급: 경미
- 위치: 14.1 #12(1114줄), 10.3 2-b(809줄)
- 위반 조항: 2-현상황(소규모 팀 · 모바일 비중), 1-목표
- 수정 제안: D-45로 PlayerModule 포크가 이미 정해졌으므로 #12의 '불가하면 자체 구현'을 확정한다. 같은 포크의 ControlModule에서 TouchJump 버튼의 위치 · 크기를 11.1 좌표(점프 r = 0.40U, θ = 77°, 지름 0.13U)로 바꾸고, DynamicThumbstick의 활성 영역을 왼쪽 1/3로 묶는다. 대안인 `GuiService.TouchControlsEnabled = false`는 기본 조이스틱까지 함께 꺼지므로 쓰지 않는다고 적는다. 포크하면 로블록스의 PlayerModule 업데이트를 받지 못하므로 다음을 11에 넘긴다: 포크 기준 버전 기록, 분기마다 원본과 diff 확인, 수정 범위를 CameraInput(R3 · I/O)과 TouchJump · DynamicThumbstick으로 한정.

### 05-r2-T-05
- 등급: 경미
- 위치: 5.4 소환수 행(325줄), 6.2 아래 소환 문단(475줄), 8장 SK-V09 신기루 분신
- 위반 조항: 3-C(공정성), 1-목표
- 수정 제안: '서버 전체 40체 초과 시 가장 오래된 소환수 소멸'을 그대로 구현하면, 다른 플레이어의 소환이 내 소환수를 지우게 된다(서로 방해하는 수단이 됨). 규칙을 이렇게 바꾼다. 서버 합계가 SUMMON_CAP_SERVER에 닿으면 새 소환을 시도한 **본인의 가장 오래된 소환수**를 소멸시키고, 본인 소환수가 없으면 소환을 1체로 줄여 발동한다(자원은 정상 소모). 또 SK-V09 분신(체력 · 도발이 있는 개체)이 소환수 상한에 포함되는지, 서버 개체인지 적는다(권장: 소환수와 같은 Anchored 간이 AI, 상한 포함).

## 확인한 외부 출처
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/ProximityPrompt.yaml — Style: "When set to Custom, no default UI will be provided." KeyboardKeyCode 기본값 E, GamepadKeyCode 기본값 ButtonX. InputHoldBegin/End는 "prompt GUI button press로 발동하려는 개발자용"(05-r1-T-03 재상정 근거)
- https://create.roblox.com/docs/reference/engine/classes/ProximityPrompt — 위와 같은 클래스의 공식 레퍼런스 페이지(본문 설명은 GitHub 원본 yaml에서 확인)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/ProximityPromptService.yaml — Enabled("프롬프트를 켜고 표시할지"), MaxPromptsVisible("플레이어에게 보이는 최대 프롬프트 수") 확인(05-r1-T-03 수정안)
- https://devforum.roblox.com/t/custom-proximity-prompt/1542153 — Custom 스타일에서도 키 입력이 프롬프트를 발동한다는 커뮤니티 보고(공식 yaml과 일치)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Player.yaml — GetNetworkPing: "Returns the round-trip, isolated network latency of the player in seconds." DevEnableMouseLock: Shift로 마우스 잠금을 토글할 수 있는지 결정(10.3 #1 사실 확인, 05-r2-T-01 (d))
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/GuiService.yaml — TouchControlsEnabled(기본 true, 터치 컨트롤 전체 켜기/끄기), AutoSelectGuiEnabled, SelectedObject 확인(05-r2-T-04, 10.2 ButtonSelect 행 사실 확인)
- https://devforum.roblox.com/t/gamepad-buttonr3-does-not-respect-contextactionservice-sinking-input/4625695 — 2026-05 보고된 'R3가 CAS Sink를 무시' 건은 보고자 측 원인으로 종결. 10.3 2-b의 BindActionAtPriority 대안은 유효(D-45 타당성 확인)
- https://devforum.roblox.com/t/how-would-i-disable-gamepad-camera-zoom-on-the-player-module/3124535 — R3 줌 해제에는 PlayerModule 포크가 권장되고, 포크하면 PlayerModule 업데이트를 받지 못한다(05-r2-T-04)
