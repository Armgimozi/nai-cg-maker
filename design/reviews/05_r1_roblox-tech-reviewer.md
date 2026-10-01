# 05 r1 — roblox-tech-reviewer

## 판정: FAIL

## 이슈 수: 치명 0 / 중대 3 / 경미 8

## 이슈

### 05-r1-T-01
- 등급: 중대
- 위치: 10.6 매크로 대책 · 서버 권한 '판정 주체' 행(약 735줄) ↔ 5.5 대시(약 290줄), 10.5 '판정 동등' 행(약 729줄), 이동형 스킬(SK-J1-02 맹렬 돌진 · SK-J3-04 전이 · SK-J5-01 등 뒤 돌기 · SK-H1-03 기록 되감기 · SK-H5-03 첨탑 전이 · SK-W1-02 · SK-W2-03 · SK-W6-03 · SK-V13 등)
- 위반 조항: 1-목표(개발자가 추가 질문 없이 구현 착수), 3-C(모든 대시·스킬을 모바일·패드로 공정하게, 입력 지연)
- 수정 제안: 10.6은 "클라이언트 예측은 애니메이션·이펙트·버튼 쿨타임 표시뿐"이라고 해서 대시와 순간 이동·돌진·도약의 캐릭터 이동까지 서버가 하는 것처럼 읽힌다. 로블록스 플레이어 캐릭터는 클라이언트가 물리를 소유하므로, 서버가 CFrame으로 옮기면 RTT만큼 늦게 움직이고 클라이언트 물리와 부딪친다. 반대로 클라이언트가 옮기면 벽 통과·텔레포트 악용을 서버가 검증해야 한다(출처: network-ownership 문서). 또 대시 무적 0.2초를 서버 수신 시각 기준으로만 판정하면 RTT 150~250ms인 모바일 유저는 화면에서 피했는데 맞는 상황이 생긴다. 10.5 '판정 동등'의 지연 보정은 쿨타임 허용 오차뿐이다. 10.6에 '이동형 스킬 권한' 행을 추가할 것을 제안한다. (a) 대시와 모든 이동형 스킬은 클라이언트가 즉시 이동을 실행한다(클라이언트 소유 유지). 서버는 '시전 전 위치 → 도착 위치' 거리 ≤ 스킬 거리 + 2 studs인지, 경로에 벽이 없는지(Raycast)를 검사하고, 실패하면 시전 전 위치로 되돌린다(롤백). 속도 버프(서리 발 +40% · 갯벌 발 +35% · 연막 +20%)는 서버가 Humanoid.WalkSpeed를 바꾼다. (b) 대시 무적은 서버에서 [수신 시각 − min(RTT/2, 100ms), 그 시각 + 0.2초] 구간으로 적용한다(되감기 상한 100ms). (c) 서버는 기록 되감기용으로 플레이어별 위치 기록을 4초 × 10Hz = 40개 보관한다. 지역 이동이나 인스턴스 진입이 끼어 있으면 되감기를 무효로 하고 마나 50%를 돌려준다. 이 수치들은 13장 파라미터(MOVE_VALIDATE_TOL 2, IFRAME_REWIND_MS 100, POS_HISTORY_HZ 10)로 뺀다.

### 05-r1-T-02
- 등급: 중대
- 위치: 10.2 게임패드 충돌 검사 ButtonR3 행(약 689줄) '충돌 없음', 10.1 #12 · #13(ButtonR3), 10.1 #18 PC 'I(가방 탭)'(약 666줄), 10.3 구현 단계 표
- 위반 조항: 3-C(PC 키 기준이되 모든 스킬을 게임패드로도 플레이 가능. 입력 충돌 해결 명시), 1-목표
- 수정 제안: 로블록스 기본 PlayerModule의 카메라 스크립트는 게임패드 ButtonR3(오른쪽 스틱 누르기)를 카메라 줌 단계 전환('RbxCameraGamepadZoom')에 쓰고, 키보드 I/O를 줌 인/아웃, ←/→를 카메라 회전('RbxCameraKeypress')에 쓴다. 그래서 문서대로라면 R3를 누를 때 조준 모드가 켜지면서 줌도 바뀌고, PC에서 I를 누르면 가방이 열리면서 카메라도 당겨진다. 10.2의 '충돌 없음'은 사실과 다르다. 10.3에 7단계 '기본 카메라 바인딩 해제'를 추가할 것을 제안한다. PlayerModule을 StarterPlayerScripts로 포크해 CameraInput에서 ButtonR3 · I · O 바인딩을 지운다(권장. DevForum은 런타임 UnbindAction에 경합 위험이 있다고 지적한다). 대안은 `ContextActionService:BindActionAtPriority`로 같은 키를 더 높은 우선순위로 바인딩하고 Sink를 반환하는 것이다. 줌은 마우스 휠과 핀치로만 남긴다. 10.4 '금지' 목록은 '예약 키'와 '해제한 기본 키'를 구분해 적는다.

### 05-r1-T-03
- 등급: 중대
- 위치: 10.2 ButtonX 행(약 683줄) '없음', 10.2 아래 '조합 판정' 문단(약 695줄), 11.4 '문맥 프롬프트는 ProximityPrompt의 GamepadKeyCode = ButtonX'(약 813줄)
- 위반 조항: 3-C(게임패드로도 플레이 가능, 버튼 충돌 해결), 1-목표
- 수정 제안: ProximityPrompt는 GamepadKeyCode로 지정한 키를 누르면 그대로 발동한다. 공식 문서에는 수식 키(L1/R1)를 조건으로 거는 기능이 없다. 그래서 NPC나 쓰러진 파티원 근처에서 LB+X(무기 스킬 Q)를 누르면 Q 스킬과 상호작용이 동시에 발동한다. '조합 판정'의 "L1/R1을 누른 채 X를 누르면 단독 동작(상호작용)은 발동하지 않는다"는 자체 ContextActionService 핸들러에만 적용되고 엔진이 처리하는 프롬프트에는 적용되지 않는다. 아래 둘 중 하나를 명시할 것을 제안한다. (a) 클라이언트에서 L1/R1을 누르는 동안과 뗀 뒤 100ms(COMBO_MODIFIER_GRACE_MS) 동안 `ProximityPromptService.Enabled = false`로 둔다. (b) 모든 프롬프트를 Style = Custom으로 만들고 GamepadKeyCode를 쓰지 않는다. 대신 ButtonX를 자체 CAS 핸들러에 바인딩하고 조합이 아닐 때만 `prompt:InputHoldBegin()` / `InputHoldEnd()`를 호출한다. 되살림의 '문맥 버튼으로도 발동'(6.1 SK-J4-06)과 '일으키기'(10.7)도 같은 경로를 탄다고 적는다.

### 05-r1-T-04
- 등급: 경미
- 위치: 10.3 구현 단계 2(약 703줄)
- 위반 조항: 1-목표(문서 안 모순)
- 수정 제안: 예시 코드는 `BindAction("Dash", handler, true, …)`로 createTouchButton을 true로 넘기는데, 본문은 "세 번째 인수는 false"라고 한다. 코드를 `false`로 고친다. 기본 시프트 락이 LeftShift와 RightShift를 둘 다 썼으므로 대시 바인딩에도 `Enum.KeyCode.RightShift`를 추가한다(재배치 기본값 포함).

### 05-r1-T-05
- 등급: 경미
- 위치: 11.2 크기 · 간격 · 영역 표(약 785~787줄)
- 위반 조항: 3-C(모바일 화면 크기 공정성)
- 수정 제안: 최소 지름 48px 하한은 0.11H 버튼에만 걸려 있다. 대시 · 점프 · Q · E(0.12H)는 H < 400일 때 48px 아래로 떨어진다. 로블록스 화면 좌표는 폰에서 논리 해상도라 가로 모드 H가 대개 약 360~430이다. 그래서 대부분의 폰에서 Z/X/C(하한 48px)가 대시 · Q · E보다 커지는 역전이 생긴다. '1080p 173px · 720p 115px' 예시도 실제 기기의 Roblox 좌표와 맞지 않는다. 모든 버튼에 하한을 건다: 공격 64px, 대시 · 점프 · Q · E 52px, 나머지 48px. 예시는 'H = 360(일반 폰 가로) · 768(태블릿)' 기준 실제 px로 다시 적는다.

### 05-r1-T-06
- 등급: 경미
- 위치: 11.2 '안전 영역' 행(약 792줄)
- 위반 조항: 3-C(사실/추정 구분, 출처)
- 수정 제안: `IgnoreGuiInset = false`와 `ScreenInsets = DeviceSafeInsets`를 동시에 지정했는데, 두 속성은 서로 연동되는 것으로 알려져 있다(나중에 설정한 값이 다른 쪽을 덮을 수 있음). ScreenGui와 Enum.ScreenInsets 공식 페이지에는 둘의 관계 설명이 없어 확인하지 못했다(확인 필요). ScreenInsets 하나만 지정하는 것으로 줄일 것을 제안한다. 전투 클러스터는 `CoreUISafeInsets`(상단 로블록스 버튼 회피 포함), 전체 화면 연출은 `DeviceSafeInsets`로 둔다. 14.3 출처 [6]에 ScreenGui 페이지 URL을 추가한다.

### 05-r1-T-07
- 등급: 경미
- 위치: 10.6 '매크로' 행(약 739줄), 13장 MACRO_STDDEV_MS
- 위반 조항: 3-C(매크로 · 오토클릭 대책이 서버에서 검증 가능해야 함)
- 수정 제안: '입력 간격 표준편차 < 15ms'를 어디서 잴지 정해져 있지 않다. 서버 수신 간격으로 재면 네트워크 지터(보통 10~40ms)가 섞여 실제 매크로도 15ms를 넘는다. 클라이언트가 보고한 시각으로 재면 위조할 수 있다. 기준을 '서버 수신 간격'으로 정한다. 지표는 표준편차 대신 (a) 같은 스킬을 쿨타임 종료 후 첫 요청까지 걸린 시간의 분포가 30분 동안 ±1틱(1/60초) 안에 몰리는지, (b) 기본 공격 길게 누르기와 탭 연타를 구분하는 방식으로 바꾼다. 결과는 즉시 제재가 아니라 '검토 큐 적재'(11)로 한다.

### 05-r1-T-08
- 등급: 경미
- 위치: 5.4 소환수 행, 6.2 SK-H3-01 · SK-H3-04 · SK-H1-04, 8장 SK-V03 · SK-V09(분신), 11.3 '저사양' 행
- 위반 조항: 2-현상황(모바일 비중 높음, 소규모 팀), 3-C
- 수정 제안: 묘역 서기관 한 명이 소환수 4체(유령 1 + 호명 3)에 자동인형(V03)까지 최대 5체를 동시에 운용할 수 있다. 필드 서버 30~50명(AS-04) 기준 서버 NPC 수 상한이 없다. 상한을 13장 파라미터로 둘 것을 제안한다: 플레이어당 동시 소환 4(SUMMON_CAP_PER_PLAYER), 필드 서버 전체 40(SUMMON_CAP_SERVER), 초과 시 가장 오래된 소환수 소멸. 구현 방식도 정한다. 소환수는 Humanoid 없는 Anchored 모델로 서버 간이 AI(초당 1타, 경로 탐색 없이 시전자 주변 추적)를 돌린다. 다른 플레이어의 스킬 이펙트는 서버가 RemoteEvent로 알리고 각 클라이언트가 직접 재생하며, 저사양 단계에서는 타인 이펙트를 생략한다고 명시하고 세부는 11로 넘긴다.

### 05-r1-T-09
- 등급: 경미
- 위치: 10.2 ButtonStart / ButtonSelect 행(약 692줄), 14.1 #6 · #7, 14.3 #3
- 위반 조항: 3-C(사실/추정 구분 · 출처)
- 수정 제안: 검수자가 확인한 결과를 반영한다. (a) ButtonSelect(PC 백슬래시)는 로블록스 기본 게임패드 UI 내비게이션 토글이다(GuiService.AutoSelectGuiEnabled). '미사용'으로 두되, 자체 메뉴(DPadUp)를 열 때 `GuiService.SelectedObject`를 첫 탭으로 지정하고 닫을 때 nil로 돌리는 처리를 10.2 UI 모드 열에 적는다. (b) ContextActionService 공식 페이지에는 '자동 터치 버튼 최대 7개'라는 기술이 없다. 14.3 #3에 '공식 문서 미기재'로 적고, 02 [P-6-02]의 근거 표기 정정을 메인에 요청한다. 05는 자체 GUI를 쓰므로 영향은 없다. (c) Backpack이 L1/R1을 쓴다는 것은 공식 문서에서 확인하지 못했다(확인 필요). Backpack을 끄는 처리(10.3 #6)는 어느 쪽이든 유효하므로 유지한다.

### 05-r1-T-10
- 등급: 경미
- 위치: 6.1 SK-J6-06 무기 개조 '속성 3택 팝업(탭)', 6.2 SK-H2-04 명장의 서명 '속성 선택 팝업'
- 위반 조항: 3-C(모든 스킬을 모바일 · 패드로 플레이 가능)
- 수정 제안: 전투 중에 팝업을 띄우면 패드는 UI 모드로 들어가 Thumbstick1이 커서 이동이 되므로(10.2) 그동안 캐릭터가 멈춘다. 모바일도 팝업을 탭하는 동안 조이스틱을 쓸 수 없다. 속성은 비전투 시 스킬 설정에서 미리 정해 두고(기본 속성 1종, 명장의 서명은 2종), 버튼 1회로 바로 발동하게 바꿀 것을 제안한다. 전투 중 변경은 버튼 길게 누르기(0.4초)로 여는 선택 링에서 하고, 링이 열려 있는 동안에도 이동 입력은 유지한다.

### 05-r1-T-11
- 등급: 경미
- 위치: 12.1 저장 데이터 항목 표 `inputBindings` 행(약 843줄)
- 위반 조항: 1-목표(11이 그대로 옮길 수 있는 저장 구조)
- 수정 제안: 표 제목은 '캐릭터 단위'인데 `inputBindings`만 계정 단위다. 이 행을 따로 빼서 '계정 키(D-25 계정 합산 카운터와 같은 키)'에 저장한다고 적는다. 크기 추정도 추가한다: 플랫폼 3 × 동작 25 × (키 이름 약 20자 + 동작 이름 약 15자) ≈ 2.6KB.

## 확인한 외부 출처
- https://devforum.roblox.com/t/how-would-i-disable-gamepad-camera-zoom-on-the-player-module/3124535 — 기본 카메라 게임패드 줌 액션 이름 'RbxCameraGamepadZoom', UnbindAction보다 PlayerModule 포크를 권장(경합 위험)
- https://devforum.roblox.com/t/cameramaxzoomdistance-being-changed-disables-gamepad-r3-from-being-able-to-zoom-the-camera/2733026 , https://devforum.roblox.com/t/pressing-right-thumbstick-on-gamepad-does-not-zoom-camera-out-if-starterplayercameraminzoomdistance-is-used/1564397 — 기본 카메라가 게임패드 R3(오른쪽 스틱 누르기)로 줌을 전환함(T-02)
- https://devforum.roblox.com/t/disabling-i-and-o-keys-to-zoom-the-camera-in-and-out/620825 , https://devforum.roblox.com/t/disable-camera-move-with-the-keys-ioleftright/2709868 — 기본 카메라 'RbxCameraKeypress'가 I/O 줌, ←/→ 회전을 바인딩. 우선순위가 더 높은 Sink 바인딩이나 PlayerModule 포크로 해제(T-02)
- https://create.roblox.com/docs/ui/proximity-prompts — KeyboardKeyCode/GamepadKeyCode는 "사용자가 누르거나 누르고 있으면 발동". 수식 키 조건이나 기본 입력을 끄는 방법에 대한 언급 없음(T-03)
- https://create.roblox.com/docs/reference/engine/classes/ProximityPromptService — Enabled(bool) 속성 존재, 프롬프트 기능 전체를 켜고 끔(T-03 해결안)
- https://create.roblox.com/docs/physics/network-ownership — 클라이언트가 소유한 파트는 서버가 물리를 검증할 수 없고, 텔레포트 · 벽 통과 악용이 가능하니 서버 검증이 필요하다(T-01)
- https://create.roblox.com/docs/input/gamepad — 권장 관례만 있음(A 확인/점프, B 취소/회피, R2 주 동작, L1/R1/X/Y 보조). 예약 버튼 목록은 없음
- https://devforum.roblox.com/t/how-to-disable-gui-navigation-non-permanently/2200446 , https://robloxapi.github.io/ref/class/GuiService.html — ButtonSelect(백슬래시)가 게임패드 UI 내비게이션 토글(AutoSelectGuiEnabled)(T-09)
- https://create.roblox.com/docs/reference/engine/classes/ContextActionService — 자동 터치 버튼 수 상한 기술 없음, Sink/Pass 우선순위 처리(T-09, T-02)
- https://create.roblox.com/docs/reference/engine/classes/UserInputService — PreferredInput(Touch / Gamepad / KeyboardAndMouse) 존재 확인(10.3 #5 사실 확인)
- https://create.roblox.com/docs/reference/engine/classes/StarterPlayer — EnableMouseLockOption(bool) 존재, 기본값 미기재(10.3 #1 기술과 일치)
- https://create.roblox.com/docs/reference/engine/classes/ScreenGui , https://create.roblox.com/docs/reference/engine/enums/ScreenInsets — ScreenInsets 열거값(None / DeviceSafeInsets / CoreUISafeInsets / TopbarSafeInsets) 확인. IgnoreGuiInset과의 관계는 페이지에 설명 없음(T-06 확인 필요)
