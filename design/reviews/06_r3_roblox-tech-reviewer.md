# 06 r3 — roblox-tech-reviewer

## 판정: PASS

## 이슈 수: 치명 0 / 중대 0 / 경미 3

## 이전 이슈 추적

| 이전 이슈 ID | 해결 여부 | 근거 한 줄 |
|---|---|---|
| 06-r2-T-01 | 해결 | 10.4 #5가 판정 오프셋 o_j(판정에만, 채택 시각 − o_j)와 표시 오프셋 o_v(판정 무관)로 나뉘었다. 검산 t_c = 정답 + L + e, o_j ≈ L → 오차 e가 성립한다. 박자 맞추기는 시각 큐만으로 (t_c − 큐 시각) 중앙값을 재고, 18.2 ③ 실측 목표도 새 정의로 바뀌었다 |
| 06-r2-T-02 | 해결 | t_s는 RTT/2 대신 t_r − b̂(최근 30개 d의 중앙값)로 정했다. σ_j = 1.4826 × MAD, W = clamp(2σ_j + 24, 25, 40)으로 상한 40 < 완벽 하한 50이 유지된다. 대체 대신 클램프, 처리 순서(클램프 → −o_j → 프레임 보정), 첫 3노트 W 40·지표 제외, 18.3 [3] '사실(왕복·격리·처리 제외)'이 반영됐다. 10.5 #8의 'σ_j > 20ms에서 클램프 약 5%'는 정규 가정에서 |r| > 2σ ≈ 4.6%로 맞다 |
| 06-r2-T-03 | 해결 | 게임패드 일시정지는 ButtonY로 바뀌었다. 미니게임 중에는 BindActionAtPriority로 Y 단독(05 10.1 #20 프리셋 전환)을 Sink하고, ButtonSelect는 05의 예약 정책을 따른다. AutoSelectGuiEnabled = false · SelectedObject = nil과 종료 시 복원(10.3 #7)이 들어가 05와의 모순이 없어졌다. 05의 L1+Y · R1+Y 조합은 미니게임 중 전투 불가 상태이고 Y를 Sink하므로 충돌하지 않는다 |
| 06-r2-T-04 ~ T-10 | 경미(BACKLOG 이관) | 메인 지시에 따라 다시 올리지 않는다 |

## 이슈

### 06-r3-T-01
- 등급: 경미
- 위치: 10.4 #5 ③ '저장'(953줄), 16.2 계정 craftOffsetMs(1417줄), 10.4 #3 ③ '상한 근거'(951줄)
- 위반 조항: 3-C(매크로 대책은 서버에서 검증 가능해야 함), 1-목표(구현 가능 수준의 명세)
- 수정 제안: o_j는 '기기 로컬 우선'이라 서버가 판정에 쓰려면 클라이언트가 값을 보내야 한다. 그런데 언제 보내는지, 세션 중에 바꿀 수 있는지가 문서에 없다. 입력마다 o_j를 함께 보내거나 세션 중 변경을 받아 주면, 변조 클라이언트가 노트마다 o_j를 바꿔 ±150ms 폭으로 판정을 옮길 수 있다. 그러면 '위조로 옮길 수 있는 폭은 최대 40ms'라는 10.4 #3 ③의 상한이 깨진다. 산출 피해 자체는 10.5 #11 상한에 묶이므로 경미로 둔다. 다음 문장을 추가한다. "o_j · o_v는 제작 시작 요청에 실어 1회만 보내고, 서버는 그 값을 craftSession에 고정한다. 세션 중 변경은 다음 제작부터 적용한다. 재개(10.4 #8) 때도 보관된 값을 쓴다. 서버는 범위(−150~+150, 10ms 단위) 밖 값을 0으로 처리한다."

### 06-r3-T-02
- 등급: 경미
- 위치: 10.3 #7 마지막 문장(938줄) '일시정지 화면의 버튼(재개 · 보관)은 Y(재개) · 화면 터치 · P로만 조작'
- 위반 조항: 3-C(모든 미니게임은 게임패드로도 플레이할 수 있어야 함)
- 수정 제안: GUI 선택 모드를 끈 상태에서 게임패드에는 Y(재개)만 배정되어 있다. 그래서 패드 유저는 일시정지 화면의 '보관'을 고를 방법이 없다(PC는 P와 마우스, 모바일은 터치로 가능). 일시정지 상태에서만 ButtonX를 '보관'에 바인딩하고, 실수 방지를 위해 0.5초 길게 누르기로 확정하게 한다. ButtonX도 10.3 #5의 Sink 목록에 넣는다. 화면 버튼에는 패드 글리프(Y 재개 / X 길게 보관)를 표시한다.

### 06-r3-T-03
- 등급: 경미
- 위치: 10.3 공정성 표 '일시정지' 행 모바일 칸(928줄) '좌상단 일시정지 버튼(지름 48 이상)'
- 위반 조항: 3-C(미니게임 모바일 공정성 — 화면 크기)
- 수정 제안: 공식 문서상 로블록스 좌측 상단에는 기본 컨트롤(메뉴 버튼 등)이 있다. `GuiService.TopbarInset`은 그 컨트롤을 뺀 빈 영역이다. 좌상단 버튼을 잘못 누르면 로블록스 메뉴가 열리고, 자동 일시정지(10.3 #2)가 일시정지 2회 상한(10.3 #4)을 소모한다. 일시정지 버튼은 `GuiService.TopbarInset` 영역 안(inset.Min.X 오른쪽)이나 그 아래에 둔다고 적는다. 또는 우상단(기기 안전 영역 안)에 두고, 하단 60% 입력 프레임과는 겹치지 않게 한다고 명시한다.

## 확인한 외부 출처
- https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/GuiService.yaml (create.roblox.com/docs/reference/engine/classes/GuiService 원문) — TopbarInset: "Returns a Rect object representing the unoccupied area between the Roblox left-most controls and the edge of the device safe area."(06-r3-T-03 근거). AutoSelectGuiEnabled: "If activated, the Select button on a gamepad or Backslash will automatically set a GUI as the selected object."(10.3 #7 · 18.3 [21] 인용 일치). SelectedObject: "Sets the GuiObject currently being focused on by the GUI navigator."(10.3 #7의 nil 설정 타당)
- https://create.roblox.com/docs/reference/engine/classes/GuiService — 렌더링된 페이지에는 위 설명이 나오지 않아 원문 yaml로 확인했다
- r2에서 확인한 GetNetworkPing("round-trip, isolated network latency … doesn't involve data deserialization or processing") 문구와 18.3 [3] 인용이 같음을 대조했다
