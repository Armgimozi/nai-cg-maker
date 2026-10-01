# 06 r2 — roblox-tech-reviewer

## 판정: FAIL

## 이슈 수: 치명 0 / 중대 3 / 경미 7

## 이전 이슈 추적

| 이전 이슈 ID | 해결 여부 | 근거 한 줄 |
|---|---|---|
| 06-r1-T-01 | 해결 | 10.4 위협 모델 재작성, #3 허용 폭 W = min(40, 2σ_j + 16) < 완벽 하한 50, 10.5 #2 다변량 지표 (a)~(g), #11 피해 상한 표가 반영됐다. 단 W·t_s 계산식 자체의 편향은 신규 06-r2-T-02로 올린다 |
| 06-r1-T-02 | 해결 | 10.4 #8 재개형(같은 시드의 남은 단계부터 재개, 이전 점수 유지), #9 보관 1칸·만료 시 재료 반환, 10.3 #4 일시정지 2회·60초 상한이 반영됐다 |
| 06-r1-T-03 | 해결 | 8.6에 의뢰 4종의 에스크로(의뢰인 키 잠금), 귀속 장비 원격 작업, 중간 이탈, 한도 귀속, 2단계 기록과 멱등 ID가 표로 정의되고 '11로 넘김' 열이 생겼다 |
| 06-r1-T-04 | 해결 | 14.2·16.2에 limitedStock 단일 키 소유 원장(D-57)이 들어갔다. 획득은 UpdateAsync 1회, 반환은 원장에서만, 로드 시 원장 우선으로 정리됐다. 재시도 멱등성은 신규 경미 06-r2-T-09로 올린다 |
| 06-r1-T-05 | 해결 | Esc·ButtonStart 사용을 없앴고, MenuOpened 자동 일시정지, Cancel 무시, BindActionAtPriority Sink, TouchControlsEnabled = false가 반영됐다. 다만 대체 입력으로 고른 ButtonSelect가 05와 충돌한다. 이건 r1에서 이 검수자가 낸 제안이 불완전했던 탓이며 신규 06-r2-T-03으로 올린다 |
| 06-r1-T-06 | 해결 | 10.4 #1에 가열 띠 1초 구간 선전송, 서버 재시뮬레이션, 결과 화면 교정이 들어갔다 |
| 06-r1-T-07 | 해결 | 10.5 #8에 대체 판정 비율을 단독 플래그로 쓰지 않는 규칙과 RTT 표준편차 40ms 초과 시 끄는 규칙이 들어갔다. 18.3 [3]은 '확인 필요'로 바뀌었다. 이제 공식 설명이 확인되므로 갱신은 06-r2-T-02에서 다룬다 |
| 06-r1-T-08 | 미해결(경미, BACKLOG 이관 유지) | 장비 1개당 서버 처리 잠금과 고가치 결과 즉시 저장 범위가 아직 없다. 12.10의 '다음 시도 입력 차단'은 클라이언트 쪽 규칙일 뿐이다. 경미라 다시 세지 않는다 |
| 06-r1-T-09 | 해결 | 16.2 monthlyEnhStats 샤드 16개를 10분마다 합산하는 방식이 들어갔다 |
| 06-r1-T-10 | 해결 | 16.2 계정 키 하나에 계정 풀과 3캐릭터 카운터를 두고 세션 잠금 메모리에서 함께 증가시키는 방식이 들어갔다 |
| 06-r1-T-11 | 해결 | 16.1 크기 추정을 420~460바이트, 3캐릭터 약 405KB로 고쳤다 |
| 06-r1-T-12 | 해결 | 6.4 강화 이펙트 성능 예산 표(가까운 6명, 이미터 1개·Rate ≤ 10, 끄기 설정)가 들어갔다 |
| 06-r1-T-13 | 해결 | 16.1 uid 설명에 계정 내 중복 검사와 거래·의뢰 로그 기록이 들어갔다 |

## 이슈

### 06-r2-T-01
- 등급: 중대
- 위치: 10.4 #5 '기기 지연 오프셋'(952줄), 18.2 ③(1514줄)
- 위반 조항: 3-C(대장장이 미니게임은 모바일에서도 공정해야 함 — 입력 지연), 1-목표(추가 질문 없이 구현 가능)
- 수정 제안: 지금 문장은 "오프셋은 표시 시점과 판정 시각 모두에 같은 값만큼 적용(채택 시각 − 오프셋으로 판정) → 판정 중심만 옮긴다"이다. 이대로 구현하면 오프셋은 아무 효과가 없다. 기기 지연을 L(표시 지연 d_v + 입력 처리 지연 d_i)로 두고 검산한다. 노트를 오프셋 o만큼 늦게 그리면 고리 도착은 t_ans + o + d_v에 보이고, 유저는 t_ans + o + d_v + e에 누르며, 채택 시각은 t_ans + o + L + e다. 여기서 o를 빼면 판정 오차는 L + e로, 오프셋을 쓰기 전과 같다. 반대 방향(o만큼 일찍 그림)으로 해석하면 오차는 L − 2o + e로 과보정된다. 어느 해석이든 '판정 중심만 옮긴다'는 문장과 맞지 않고, 개발자가 부호와 대상을 정할 수 없다. 수정안: (1) 판정 오프셋 o_j는 **판정에만** 적용한다(채택 시각 − o_j). 노트 표시는 서버 시각 기준 그대로 둔다. '박자 맞추기'는 표시를 바꾸지 않은 상태에서 탭 8회의 (클라이언트 t_c − 큐 시각) 중앙값을 재고, 그 값을 o_j로 제안한다. (2) 표시 오프셋이 따로 필요하면 '표시 오프셋 o_v'를 별도 설정으로 두고, 판정에는 o_j만 쓴다고 명시한다. (3) 소리 큐는 모바일 블루투스 이어폰에서 시각 큐보다 150ms 이상 늦을 수 있다(추정, 출시 전 실측). 그러니 박자 맞추기는 **시각 큐만**으로 재고, 소리는 보조라고 적는다. 아니면 소리 전용 오프셋을 따로 둔다. 18.2 ③의 '플랫폼별 완벽 판정 비율 차 ≤ 5%p' 실측 목표는 이 수정 뒤의 오프셋 정의로 다시 적는다.

### 06-r2-T-02
- 등급: 중대
- 위치: 10.4 #3 '주장 시각 검증'(950줄), 10.5 #8(969줄), 18.3 [3](1524줄)
- 위반 조항: 3-C(미니게임 모바일 공정성 — 입력 지연), 3-C(사실/추정 구분, 기술 제약 출처)
- 수정 제안: 공식 문서는 이제 `Player:GetNetworkPing`을 "round-trip, isolated network latency … doesn't involve data deserialization or processing"으로 설명한다(아래 출처, 서버에서 다른 플레이어에게도 호출 가능하고 클라이언트 제한은 LocalPlayer만). 그러면 t_s = t_r − RTT/2에서 빼는 값은 실제 지연보다 작다. 빠지는 것은 서버의 역직렬화·처리 시간, 서버가 프레임 경계에서 원격 이벤트를 처리하기까지의 대기(60Hz면 최대 약 16.7ms, 추정), 업링크와 다운링크의 비대칭(셀룰러에서 큼, 추정)이다. 그래서 **t_s는 정직한 입력의 실제 시각보다 일관되게 늦다.** 게다가 σ_j를 '격리된 네트워크 핑 표본 10개'로 재므로 σ_j가 작게 나와 W ≈ 16~26ms가 된다. 그 결과 정직한 유저의 |t_c − t_s|가 위 편향 때문에 W를 자주 넘고, 그 입력은 늦게 잡힌 t_s로 판정된다. 판정 채택값이 t_c(편향 없음)와 t_s(늦음)로 입력마다 섞이니 오차 분포가 두 봉우리가 된다. 이 손해는 셀룰러 모바일에서 가장 크다. 10.5 #8은 RTT 표준편차 > 40ms일 때 '지표'만 끄고 대체 판정 자체는 그대로 둔다. 수정안: (1) 서버 추정 시각을 RTT/2가 아니라 **세션 실측 편차**로 만든다. 세션의 최근 30개 입력과 박자 맞추기 탭으로 b̂ = 중앙값(t_r − t_c)을 구하고, t_s = t_r − b̂로 둔다. (2) σ_j는 잔차 r = (t_r − t_c) − b̂의 강건 표준편차(1.4826 × MAD)로 구하고, W = clamp(2σ_j + 17, 17, 40)ms로 둔다. 하한 17ms는 서버 프레임 대기를 덮는 값이다. b̂는 일정한 편차만 흡수하므로, 위조 클라이언트가 t_c를 옮길 수 있는 폭은 여전히 W(≤ 40) 안이다. (3) 세션 시작 전 b̂ 표본이 부족한 첫 5개 입력은 t_c 채택 폭을 40ms로 두고 통계 지표(10.5 #2)에서만 뺀다. (4) 18.3 [3]을 '사실(공식: 왕복·격리 지연, 처리 제외)'로 고치고, 이 API는 표시용 참고값으로만 쓴다고 적는다.

### 06-r2-T-03
- 등급: 중대
- 위치: 10.3 공정성 표 '일시정지' 행 게임패드 칸(928줄), 10.3 #1(932줄) ↔ 05 10.1 #22(800줄) · 10.2 ButtonSelect 행(823줄) · 10.4 금지 ① 예약 키(848줄)
- 위반 조항: 1-목표(문서 간 모순으로 구현 불가), 3-C(기본 기능과의 입력 충돌 해결 방식 명시, 미니게임은 게임패드로도 플레이 가능)
- 수정 제안: 06은 미니게임 일시정지를 게임패드 **ButtonSelect**에 바인딩한다. 그런데 05는 ButtonSelect를 '로블록스 예약(게임패드 UI 내비게이션 토글) · 우리 바인딩 없음 · 배정 불가 목록'으로 정해 두었다. 개발자는 어느 쪽을 따라야 할지 알 수 없다. 공식 문서상 ButtonSelect는 재정의 불가 예약 입력은 아니다(Input Action System의 예약 목록은 Esc · F9 · F11 · F12 · PrintScreen · ButtonStart뿐). 하지만 `GuiService.AutoSelectGuiEnabled`(기본 켜짐)는 "the Select button on a gamepad … will automatically set a GUI as the selected object"로 동작한다. 그래서 미니게임 중 Select를 누르면 GUI 선택 모드가 함께 켜진다. 그 상태에서 ButtonA가 선택된 GUI를 누르는 데 쓰이면 단조 탭 입력과 충돌할 수 있다(CAS 바인딩과 GUI 선택 중 어느 쪽이 A를 먼저 받는지는 공식 문서 미기재, 확인 필요). 이 제안은 r1에서 이 검수자가 낸 것이라 바로잡는다. 둘 중 하나를 고른다. (a) 일시정지를 **ButtonY**로 바꾼다. 미니게임은 비전투이므로 ButtonY의 단독 동작(프리셋 전환)은 미니게임 중 우선순위 바인딩으로 Sink한다. 10.3 #5의 바인딩 목록에 Y를 추가한다. (b) ButtonSelect를 유지하려면 미니게임 시작 시 `GuiService.AutoSelectGuiEnabled = false`, `GuiService.SelectedObject = nil`로 두고 종료 시 복원하는 규칙을 10.3 #6 옆에 적는다. 그리고 05 10.2 · 10.4에 '미니게임 화면에서만 예외 바인딩'을 추가해 달라고 18.1에 요청한다. 권장은 (a)다(05 수정 불필요).

### 06-r2-T-04
- 등급: 경미
- 위치: 10.3 #5 `Enum.ContextActionPriority.High + 100`(936줄)
- 위반 조항: 1-목표(구현에 바로 옮길 수 있는 표기)
- 수정 제안: `BindActionAtPriority`의 priority 인수는 정수다(공식: Default.Value = 2000). Luau에서 EnumItem에 숫자를 더할 수 없으므로 `Enum.ContextActionPriority.High.Value + 100`으로 고친다.

### 06-r2-T-05
- 등급: 경미
- 위치: 10.3 #2 · #3(933~934줄), 10.4 #8 가열 재개(955줄)
- 위반 조항: 3-C(미니게임 모바일 공정성, 서버 검증 가능한 대책)
- 수정 제안: (1) 일시정지 요청의 시각을 무엇으로 정하는지 적는다. 가열·담금질은 '즉시 정지'라서 정지 시각이 곧 바늘·온도 판정 시각이 된다. 그러므로 일시정지 요청 시각도 입력과 같은 t_c/W 검증(10.4 #3)을 거친다고 명시한다. (2) 모바일에서 전화 수신·앱 전환으로 앱이 백그라운드로 가도 `MenuOpened`는 발생하지 않는다. 서버가 연결 끊김을 감지할 때까지 노트는 빗나감으로 처리된다. `UserInputService.WindowFocusReleased`가 모바일 백그라운드 전환에서도 발생하는지는 공식 문서에 없다(확인 필요). 확인되면 이 이벤트도 자동 일시정지로 받고 10.3 #4 상한에 산입한다. (3) 가열 단계를 재개할 때 온도 초기값(끊긴 순간 값 유지인지, 0인지)을 적는다. 띠 밖에서 끊고 재개했을 때 온도가 띠 안 값으로 돌아가는 이득이 없도록 '끊긴 순간 서버 시뮬레이션 온도 유지'를 권장한다.

### 06-r2-T-06
- 등급: 경미
- 위치: 16.2 pendingCraft · commissionCraft(1414줄), craftSession_<userId>(1415줄), 10.4 #9(956줄), 8.6 '중간 이탈'(860줄)
- 위반 조항: 1-목표(데이터 키 정의)
- 수정 제안: pendingCraft는 캐릭터 단위이고 대장장이는 의뢰 작업 칸이 따로 있는데, MemoryStore 키는 `craftSession_<userId>` 하나다. 같은 유저의 다른 캐릭터나 의뢰 작업 칸이 동시에 보관 상태면 키가 충돌한다. 키를 `craftSession_<userId>_<charId>_<own|comm>`으로 정한다(50자 이내). '보관 1칸'이 유저 단위인지 캐릭터 단위인지도 10.4 #9에 적는다.

### 06-r2-T-07
- 등급: 경미
- 위치: 8.6 '조회'(851줄), 16.2 commissions '게시판 색인'(1418줄)
- 위반 조항: 1-목표(서버 간 공유 데이터 처리 방식 — 한도 검산)
- 수정 제안: MemoryStore 메모리 한도는 게임 단위 64KB + 1.2KB × 동시 접속자다(공식). 그런데 열린 의뢰 수는 동시 접속자가 아니라 **일일 이용자 × 최대 72시간 보관**에 비례한다. 계산 예: 동접 1,000명이면 한도 약 1.26MB다. 일일 이용자를 동접의 10배로 잡고 그중 30%가 하루 1건씩 등록해 평균 48시간 열려 있으면 열린 의뢰는 6,000건이다. 색인 항목을 약 150바이트(키 + 종류 · 도안 · 티어 · 수수료 · 최소 숙련 JSON)로 잡으면 약 0.9MB로 한도의 약 70%를 쓴다. craftSession(보관 24시간)과 08 · 09의 MemoryStore 사용분도 같은 한도를 나눠 쓴다. 다음을 적는다. 색인 값은 정렬 키(수수료)와 필터용 최소 필드만 담고 항목당 100바이트 이하로 둔다. 원본은 DataStore에 둔다. 정렬 맵을 '의뢰 종류 4 × 티어 6 = 24개'로 나눠 필터 조회가 한 맵만 읽게 한다. 열린 의뢰 총수 상한과 넘쳤을 때의 처리(등록 대기 또는 오래된 순 색인 제외)를 둔다. 11에 넘길 항목으로 표에 추가한다.

### 06-r2-T-08
- 등급: 경미
- 위치: 8.6 '결과 기록'(858줄), 16.2 계정 mailbox(1417줄)
- 위반 조항: 1-목표(서버 간 공유 데이터 처리 방식)
- 수정 제안: 16.2는 mailbox를 '계정' 범위 필드로 적었다. 하지만 8.6은 세션 잠금이 걸린 의뢰인에게 '우편함 키'로 적재한다고 했다. 우편함이 세션 잠금된 계정 키 안에 있으면 다른 서버가 쓸 수 없다. 우편함은 **세션 잠금 밖의 별도 키**(`mail_<userId>`)라고 명시한다. 처리한 mailId 집합은 세션 잠금 키에 기록해 멱등을 보장한다고도 적는다. 또 접속 중인 의뢰인은 '다음 로드 시 반영'이 아니라, 세션을 가진 서버가 MessagingService 알림을 받는 즉시 우편함을 읽어 반영하게 한다. MessagingService는 전달이 보장되지 않으므로 5분 주기 폴링을 보조로 둔다.

### 06-r2-T-09
- 등급: 경미
- 위치: 14.2 '원장' · '획득' · '소유 유지 조건'(1287~1290줄), 16.2 limitedStock(1419줄)
- 위반 조항: 1-목표(복제 방지), 3-C(추정의 근거)
- 수정 제안: (1) 획득 UpdateAsync가 서버에는 실패로 보고됐지만 실제로는 기록된 경우(타임아웃 등)에 재시도하면 같은 플레이어에게 일련번호가 2개 기록될 수 있다. 변환 함수 안에서 '같은 획득 토큰(보스 처치 ID) 또는 같은 owner가 이미 이 아이템의 번호를 가짐'을 먼저 검사해 멱등으로 만든다. 1인 다수 보유 허용 여부도 적는다. (2) '27칸, 1KB 미만'은 맞지 않는다. 칸당 {owner, charId, acquiredAt, lastSeen, returnAt} JSON은 약 90~110바이트라 27칸이면 약 2.5~3KB다. 4MB 한도에는 문제가 없으니 수치만 고친다. (3) 모든 서버가 시작 시와 1시간마다 하는 반환 검사는, 먼저 캐시된 GetAsync로 만료 번호가 있는지 보고 있을 때만 UpdateAsync한다고 적는다. 변환 함수는 바꿀 것이 없으면 nil을 반환해 쓰기를 취소한다고도 적는다(게임 단위 쓰기 한도 300 + 동접 × 20/분, 공식).

### 06-r2-T-10
- 등급: 경미
- 위치: 10.5 #10 '검토 근거 보존 … 30일 보관(계정 키, 세션당 약 1KB)'(971줄), 16.2 craftSession 설명(1415줄)
- 위반 조항: 1-목표(데이터 저장 한도)
- 수정 제안: 의심 플래그가 계속 붙는 계정(실제 봇)은 하루 최대 90제작(계정 상한) × 30일 = 2,700세션 × 1KB ≈ 2.7MB를 **계정 키**에 쌓는다. 그러면 계정 키 값이 4MB 한도에 가까워진다. 또 자동 저장 때마다 2.7MB를 다시 쓰게 되어, 키당 쓰기 처리량 4MB/분 안에서 분당 1회 남짓밖에 저장하지 못한다. 저장이 실패하면 롤백이 생긴다. 로그는 별도 DataStore의 날짜 키(`macroLog_<userId>_<YYYYMMDD>`, 하루 최대 90KB)에 쓰고, 30일 뒤 정리(또는 만료 처리)한다고 고친다.

## 확인한 외부 출처
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/Player.yaml (create.roblox.com/docs/reference/engine/classes/Player#GetNetworkPing 원문) — GetNetworkPing: "Returns the round-trip, isolated network latency of the player in seconds … doesn't involve data deserialization or processing." 클라이언트에서는 LocalPlayer에만 호출 가능, security None(서버 호출 가능). 06-r2-T-02 근거
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/GuiService.yaml (create.roblox.com/docs/reference/engine/classes/GuiService 원문) — AutoSelectGuiEnabled: "If activated, the Select button on a gamepad or Backslash will automatically set a GUI as the selected object." TouchControlsEnabled: "Used to enable and disable touch controls and touch control display UI. Defaults to true", 쓰기 security None(10.3 #6 타당). MenuOpened: "Fires when the user opens the Roblox CoreGui escape menu."(10.3 #2 타당). 06-r2-T-03 근거
- https://create.roblox.com/docs/input/input-action-system — 예약 입력은 Escape · F9 · F11 · F12 · PrintScreen · 게임패드 ButtonStart이며 "cannot be overridden". ButtonSelect는 이 목록에 없다(06-r2-T-03)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/ContextActionService.yaml — BindActionAtPriority priority 인수는 int이고 "higher considered before lower". Default.Value = 2000. GUI 선택 중 ButtonA 처리 순서는 미기재(06-r2-T-03 확인 필요, 06-r2-T-04)
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/UserInputService.yaml — WindowFocusReleased는 "typically when it is minimized by the user"로만 설명되고 모바일 백그라운드 언급은 없다(06-r2-T-05 확인 필요)
- https://create.roblox.com/docs/cloud-services/memory-stores — 메모리 한도 64KB + 1.2KB × 사용자, 요청 1000 + 120 × 동접/분, 만료 0~3,888,000초(45일). craftSession TTL 24시간은 범위 안(D-56 타당). 06-r2-T-07 근거
- https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits — 서버당 읽기·쓰기 60 + numPlayers × 40/분, 게임 단위 쓰기 300 + concurrentUsers × 20/분, 키당 쓰기 4MB/분(요청당 1KB 단위 올림), 키 이름 50자, 값 4,194,304자. 06-r2-T-06 · T-09 · T-10 근거, D-57 단일 키 원장 크기·빈도는 한도 안
