-- 3D 공원 배치 모드: 놀이공원 시뮬레이션처럼 메뉴 창 없이 내 공원에서 명소를 직접 눌러 집고, 다른 받침대를 눌러 놓음.
-- (DESIGN.md "공원 배치" — 규칙·계획은 Shared/ParkGrid, 편집 규칙은 PlayerState.setDisplay, 서버 상태가 진실)
--
-- 들어가기: 버튼 없이 타이쿤처럼 직접 — 내 공원(부지 + 여유 14)에 있을 때 내 명소를 톡 누르면 배치 모드 + 그 명소를 바로 집음,
--   내 빈 받침대를 누르면 배치 모드 + 그 칸을 채울 준비(칸이 초록으로 숨 쉬고, 보관함 카드를 누르면 바로 그 칸으로).
--   톡 = 누른 곳에서 DRAG_PX 안에서 뗌(터치로 끌면 화면 돌리기라 안 들어감), 두 손가락이면 취소. 광선은 캐릭터만 빼고 쏴서
--   처음 맞은 것이 내 칸 모델일 때만(남의 공원은 눌러도 아무 일 없음). 칸 이름표(BillboardGui — 광선에 안 맞음)를 누르면
--   그 칸(이름표가 맞은 파트보다 가까울 때 — 이름표 바로 뒤 다른 명소를 집지 않게). 창이 열려 있거나 굴림 연출 중·결과 카드
--   위면 안 받음(Handlers.CanTap).
--   마우스는 가리키는 내 칸에 옅은 흰 강조 + 손가락 커서(찾기 쉽게). 배치 모드 동안은 이 누르기를 쓰지 않음(직접 광선).
-- 배치 모드 동안 HUD 는 왼쪽 메뉴·상점·굴리기 줄을 숨기고(부르는 쪽 Changed) 아래 띠만 남김 — 놀이공원 시뮬레이션의
--   건설 모드처럼 공원과 띠에만 집중. 나가기 = [완료] · Esc/Q(들고 있으면 먼저 내려놓기) · 부지 밖으로 나가기.
-- 시점: 들어가면 카메라가 부지 위 3/4 시점으로 날아감(Scriptable, ParkGrid.topView 가 HUD 가 가리지 않은 곳에
--   열린 줄 + 잠긴 줄 하나가 딱 들어오는 거리를 찾음, 휠로 조금 가까이/멀리) — 이 동안 캐릭터 이동은 꺼 둠(카메라가 캐릭터를 따라가지
--   않아서 걸으면 화면 밖으로 나가 버리고, 터치 조이스틱·점프 버튼이 부지 아래쪽을 가리기 때문).
--   [시점] 을 누르면 평소처럼 캐릭터를 따라가는 카메라(이동 켜짐)로, 다시 누르면 위에서 보기. 나갈 때 원래 카메라로.
-- 누르기: 명소를 누르면 "들고 있음" — 원래 명소는 이 화면에서만 숨기고 반투명 복사본이 떠서(살짝 오르내리며 돎)
--   가리키는 받침대 위로 붙음. 다른 열린 칸을 누르면(또는 끌어서 놓으면) 그 칸으로 옮김(명소가 있으면 자리 바꿈 —
--   상대가 원래 칸으로 폴짝). 같은 칸 / Esc / 오른쪽 클릭 / 부지 밖 = 취소, 잠긴 칸 = "공원 확장" 알림.
-- 아래 띠(보관함): 전시 안 된 명소 카드(희귀한 순서, 보이는 카드만 3D 사진) — 누르면 그 명소를 집음(받침대를 눌러 놓음).
--   집은 명소는 첫 빈 칸 위에서 시작, 공원이 꽉 찼으면 가장 약한 전시 명소 위(ParkGrid.storageStart — 휴대폰 좁은
--   화면에서도 보이는 앞쪽), 그 칸 판·강조가 켜짐. 보관함에서 들고 있으면 바꿔 넣을 칸(명소 있는 칸) 판도 또렷하게.
--   [보관] = 들고 있는 전시 명소를 보관함으로, [자동] = 자동 배치, [시점], [완료] = 나가기.
-- 누르는 즉시 PlayerState 규칙을 스냅샷 사본에 적용해 미리 보여 주고(preview), 옮긴 칸에는 이 화면에서만 보이는
--   모형(proxy)을 두었다가 서버가 칸을 다시 만들면(칸 모델 Look 속성이 맞으면) 치움. 실패·stale 이면 서버 상태로 되돌림.
-- 알림: 배치 편집이 받아들여져 자동 배치가 꺼지면(이번 접속 처음) "자동 꺼짐". "공원 바뀜"(stale)·"공원 꽉 참"은 init 이 띄움.
-- 정리: 나가면(완료, 다른 창 열기, 부지 밖으로 걸어가거나 순간 이동, 죽음·캐릭터 사라짐, 부지 잃음) 이 모듈이 만든
--   연결·모형·강조를 모두 지우고 숨긴 명소를 되돌림. 서버가 칸 모델을 다시 만들면(ChildAdded/Removed) 그때그때 맞춤.
-- 키보드: Esc · Q = 내려놓기(들고 있지 않으면 나가기), Backspace · Delete = 보관. 오른쪽 클릭 = 내려놓기.
--   채팅 등 글자 칸에 쓰는 중에는 키를 모두 무시(Esc 는 글자 칸에서 빠져나오는 키 — 배치 모드를 끝내지 않음).
-- 터치 두 손가락: 두 번째 손가락이 닿으면 집기·끌기를 취소(든 명소는 제자리로)하고 벌리기/모으기 = 위에서 보기
--   가까이/멀리(휠과 같은 범위). 손가락이 모두 떨어질 때까지 뗌은 무시(놓기·집기 없음 — 자동 배치도 그대로).
-- 광선: 이 화면에서 숨긴 원래 명소(들고 있는 칸 등)는 광선이 지나감 — 보이지 않는 명소가 뒤쪽 받침대를 가리지 않게.
-- 띠 위 딱지 줄(속이 비친 곳)을 눌러도 뒤의 명소를 집지 않음(띠와 같음).
-- 화면 글자는 최소로(아이콘 + 숫자, 버튼 2글자), 이모지 없음 — DESIGN.md UI 스타일 가이드 v2.

local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local Models = require(Shared.Models)
local ParkGrid = require(Shared.ParkGrid)
local PlayerState = require(Shared.PlayerState)

local Icons = require(script.Parent.Icons)
local Ui = require(script.Parent.Ui)
local Viewport = require(script.Parent.Viewport)
local Theme = Ui.Theme

type Snapshot = PlayerState.Snapshot
type Landmark = Landmarks.Landmark

export type Handlers = {
	-- 서버에 배치 편집 요청(기다림). 반환: 받아들였는지, "stale" 로 거절됐는지. 상태 반영·알림은 부르는 쪽이 함
	SetDisplay: (slot: number, landmarkId: string?, expected: string, expectedFrom: number?) -> (boolean, boolean),
	SetAutoPark: (on: boolean) -> boolean,
	GoToPark: () -> boolean, -- 내 공원으로 순간 이동(기다림). 성공하면 true
	Toast: (text: string, icon: string?, color: Color3?) -> (),
	Changed: (editing: boolean) -> (), -- 배치 모드 켜짐/꺼짐 (HUD 메뉴·굴리기 줄 숨기기, 열린 창 닫기)
	-- 배치 모드 밖에서 내 공원을 이 화면 점(뷰포트 px, 가리키기·누르기 자리)에서 눌러 들어가도 되는지(창이 열려 있음·굴림 연출
	-- 중·결과 카드가 덮은 곳이면 false). 없으면 늘 true
	CanTap: ((at: Vector2?) -> boolean)?,
}

-- 월드 ----------------------------------------------------------------------------
local LIFT = 3.4 -- 들고 있는 명소가 받침대 위로 뜨는 높이(스터드)
local LIFT_CLEAR = 1.2 -- 명소가 있는 칸(자리 바꿈)을 가리키면 그 명소 꼭대기에서 이만큼 위로 떠서 둘 다 보이게
local BOB = 0.45 -- 오르내림 폭
local BOB_SPEED = 3.2 -- 오르내림 빠르기(라디안/초)
local SPIN_SPEED = math.rad(55) -- 들고 있는 명소가 도는 빠르기
local FOLLOW = 16 -- 가리키는 곳을 따라가는 빠르기(1/초, 클수록 바로 붙음)
local GHOST_FADE = 0.3 -- 들고 있는 복사본의 투명도(원래 투명도에서 이만큼 더 비침)
local GHOST_FILL = 0.84 -- 복사본 노란 강조 채우기 투명도(원래 색이 보이게 옅게 — 흰 테두리가 "들고 있음"을 말함)
local FLY_SECONDS = 0.3 -- 놓기·되돌아가기·자리 바꿈 폴짝
local HOP = 4 -- 자리 바꿈 상대가 폴짝 뛰는 높이
local EDIT_HOLD = 3 -- 옮긴 칸의 로컬 모형(proxy)을 서버 칸이 맞을 때까지 기다리는 최대 시간(초)
local DRAG_PX = 10 -- 이보다 많이 움직이면 끌기(터치: 따라가는 시점에서는 화면 돌리기)
local LEAVE_MARGIN = 14 -- 부지 밖으로 이만큼 나가면 배치 모드 끝(스터드)
local POINTING_HAND = "rbxasset://SystemCursors/PointingHand" -- 배치 모드 밖: 내 칸을 가리키면 손가락 커서
local RAY_LENGTH = 1000
local MARKER_SIZE = ParkGrid.PEDESTAL_SIZE + 1.6 -- 받침대 둘레로 삐져나와 빛나는 판
-- 빛나는 판 투명도(들고 있을 때): 놓을 수 있는 칸은 은은하게(빈 칸이 자리 바꿈 칸보다 조금 진하게),
-- 가리키는 칸만 진하게 숨 쉬듯 — 공원 전체가 똑같이 빛나서 어디에 놓일지 안 보이던 것
local MARK_EMPTY, MARK_SWAP, MARK_TARGET, MARK_TARGET_PULSE = 0.55, 0.8, 0.12, 0.1
-- 보관함에서 집은 명소를 들고 있을 때 명소 있는 칸(바꿔 넣기) 판: 공원이 꽉 차면 놓을 곳이 모두 이것이라 또렷하게
local MARK_REPLACE = 0.6
local HOVER_COLOR = Color3.new(1, 1, 1)

-- 위에서 보기(ParkGrid.topView): 화면 위쪽 상단바 아래 여백, 옆 여백(비율). 휠 배율(1 = 맞출 줄이 딱 맞음)
local TOP_MARGIN = 10 -- px
local SIDE_MARGIN = 0.03
local BAR_CLEAR = 8 -- 아래 띠 위로 띄울 거리(px)
local ZOOM_STEP = ParkGrid.ZOOM_STEP -- 범위는 ParkGrid.ZOOM_MIN..ZOOM_MAX(두 손가락 벌리기/모으기도 같은 범위)
local TEXT_GRACE = 0.25 -- 글자 칸에서 빠져나온 직후 이 시간(초) 안의 Esc 도 무시(빠져나오는 Esc 가 늦게 올 수 있음)
-- 위에서 보기 시야각(도, 기본 카메라 70). 좁혀서 멀리서 보면 원근이 줄어 건설 게임처럼 판이 반듯하고, 떠 있는 복사본·
-- 이름표가 칸 바로 위에 옴(70 이면 카메라가 30~50 스터드로 가까워 화면 가장자리 칸 위의 것이 바깥으로 크게 밀려남)
local EDIT_FOV = 40
local CAMERA_TWEEN = TweenInfo.new(0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
-- 채울 빈 칸을 정하면 보관함 앞 카드들이 한 번 톡(커졌다 제자리)
local CARD_NUDGE = TweenInfo.new(0.14, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 0, true)

-- 아래 띠 (설계 px, Ui.autoScale 배율을 받음) --------------------------------------
local BAR_HEIGHT = 132
local BAR_BOTTOM = 12 -- 화면 아래 끝에서(화면 px)
local BAR_JUMP = { Small = 100, Large = 180 } -- 터치 기기: 오른쪽 아래 점프 버튼 자리(화면 짧은 쪽 500 이하 / 초과)
local BAR_EDGE = 16 -- 화면 양옆 여백(화면 px)
local BAR_MAX_WIDTH = 1180
local BAR_PAD = 10
local BUTTON = Vector2.new(92, 108) -- 앞면 92×102 (배율 0.55 에서 50×56px)
local BUTTON_GAP = 8
local CARD = Vector2.new(96, 104) -- 보관함 카드 (배율 0.55 에서 53×57px)
local CARD_GAP = 10
local CHIP_ROW = 30 -- 띠 위 딱지 줄 높이(띠 위 테두리에 걸침)
local CONFIRM_SECONDS = 3
local TAG = Vector2.new(240, 58) -- 화면 이름표(이름 딱지 + 별, 설계 px)
local TAG_GAP = 1 -- 모형 꼭대기 위 이 높이(스터드)에 이름표 아래 끝
local TAG_EDGE = 6 -- 화면 가장자리·띠에서 띄울 거리(px)
local FEATURED_BG = Color3.fromRGB(255, 218, 128)
local WHITE = Color3.new(1, 1, 1)
local SOUND_ID = "rbxasset://sounds/electronicpingshort.wav"

local ParkEdit = {}

local player = Players.LocalPlayer
local handlers: Handlers
local gui: ScreenGui

-- 상태
local lastState: Snapshot? = nil -- 서버에서 받은 최신 상태
local preview: Snapshot? = nil -- 응답을 기다리는 편집이 있을 때 미리 보여 주는 상태
local pending = 0 -- 응답을 기다리는 배치 요청 수
local autoFlip = false -- 자동 배치 중에 보낸 편집이 응답을 기다리는 중(받아들여지면 "자동 꺼짐")
local autoNoticed = false -- "자동 꺼짐" 알림을 이번 접속에서 보였는지
local confirmUntil = 0 -- 이 시각(os.clock)까지 [자동] 을 한 번 더 누르면 켜짐
local confirmToken = 0

-- 내 부지
local plot: Instance? = nil
local origin: CFrame? = nil -- 부지 CFrame(중앙 바닥, -Z = 입구)
local slotsFolder: Instance? = nil
local containers: { [number]: Instance } = {} -- 칸 번호 -> 월드 칸 모델
local plotConnections: { RBXScriptConnection } = {}

-- 배치 모드
local editing = false
local entering = false
local entryToken = 0
local editToken = 0
local editConnections: { RBXScriptConnection } = {}
local localFolder: Folder? = nil -- 이 화면에서만 있는 것(빛나는 판·강조·들고 있는 모형·proxy)
local markers: { [number]: BasePart } = {}
local markerPulse: BasePart? = nil -- 들고 있을 때 숨 쉬듯 빛나는 판(가리키는 놓을 칸)
local painted: { Slots: { [number]: string }, Unlocked: number, HeldFrom: number }? = nil -- 마지막 reconcile 값
local hoverLight: Highlight? = nil
local hoverSlot: number? = nil
-- 채울 빈 칸: 빈 받침대를 눌러 들어왔거나(배치 모드 밖) 들고 있지 않을 때 빈 받침대를 누름. 그 칸 판이 초록으로 숨 쉬고,
-- 보관함 카드를 누르면 집어 들 필요 없이 바로 그 칸으로 날아감. 칸이 차거나 다른 명소를 집으면 풂
local fillSlot: number? = nil
local viewMode = "Top" -- "Top"(위에서 보기) | "Follow"(평소 카메라)
local zoom = 1
local fitRows = Config.PARK_GRID -- 위에서 보기가 맞춘 줄 수(ParkGrid.topRows: 열린 줄 + 잠긴 줄 하나)
local savedCamera: { Type: Enum.CameraType, Subject: Instance?, Fov: number }? = nil
local cameraTween: Tween? = nil
local controls: any = nil

-- 매 프레임 움직이는 로컬 모형(들고 있는 복사본·날아가는 모형): 만들 때 파트마다 피벗 기준 자리를 적어 두고
-- 매번 절대 자리로 옮김(Model:PivotTo 를 매 프레임 되풀이하면 파트 사이 오차가 쌓임). Pivot = 지금 피벗
type Rig = { Model: Model, Parts: { BasePart }, Offsets: { CFrame }, Pivot: CFrame }
type Ghost = {
	Model: Model,
	Rig: Rig,
	Originals: { [BasePart]: number },
	Light: Highlight,
	Height: number, -- 모형 높이(피벗 = 바닥 가운데에서 꼭대기까지)
}
type Held = {
	Id: string,
	Ghost: Ghost,
	Position: Vector3, -- 받침대 윗면 기준 지금 자리(부드럽게 따라감)
	Target: Vector3,
	Lift: number, -- 받침대 윗면 위로 뜬 높이(부드럽게 따라감: 명소가 있는 칸 위면 그 명소 위로)
	Angle: number,
}
local held: Held? = nil

type Flyer = {
	Rig: Rig,
	From: CFrame,
	To: CFrame,
	Start: number,
	Seconds: number,
	Hop: number,
	Slot: number?, -- 날아가 앉을 칸(도착하면 필요하면 그 칸의 proxy 가 됨)
	Id: string?,
	Fade: boolean, -- 도착하면 사라짐(보관함으로 밀려난 명소)
}
local flyers: { Flyer } = {}
local proxies: { [number]: { Id: string, Model: Model } } = {}
local localEdits: { [number]: number } = {} -- 이 화면에서 옮긴 칸 -> 서버 칸이 맞을 때까지 기다릴 시각(os.clock)
local hidden: { [Instance]: boolean } = {} -- 이 화면에서 명소를 숨긴 월드 칸 모델

-- 입력
type Press = { Input: InputObject, Kind: Enum.UserInputType, Start: Vector2, Moved: boolean, Picked: boolean }
local press: Press? = nil
local rightStart: Vector2? = nil
local pointer: Vector2? = nil -- 화면(뷰포트) 좌표. 마우스는 매 프레임, 터치는 누르고 있는 동안만
local pointerKind: string? = nil -- "Mouse" | "Touch"
local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Include
local rayDirty = true -- 광선이 맞출 목록(rayTargets)을 다시 만들어야 함(숨긴 명소·칸 모델이 바뀜)
-- 터치: 화면(3D)에 닿아 있는 손가락 -> 뷰포트 자리. 둘 이상이면 두 손가락 모드(pinch: 시작 거리·배율)
local touches: { [InputObject]: Vector2 } = {}
type Pinch = { Distance: number, Zoom: number }
local pinch: Pinch? = nil
-- 글자 칸(채팅 등)에 쓰는 중인지: TextBoxFocused / TextBoxFocusReleased(+ GetFocusedTextBox)
local textFocused = false
local textReleasedAt = -math.huge

-- 아래 띠
local bar: Frame
local tray: TextButton
local storeButton: Ui.ChunkyButton
local autoButton: Ui.ChunkyButton
local autoBadge: Ui.Chip
local viewButton: Ui.ChunkyButton
local doneButton: Ui.ChunkyButton
local scroller: ScrollingFrame
local emptyHint: Frame
local countChip: Ui.Chip
local incomeChip: Ui.Chip
local barTop: number? = nil -- 아래 띠(+ 위 딱지 줄) 위 끝(이 ScreenGui 좌표, 화면 px). 위에서 보기 카메라가 비켜 감
type Card = {
	Button: TextButton,
	Stroke: UIStroke,
	Scale: UIScale,
	Photo: Frame,
	Thumb: ViewportFrame?,
	Stars: TextLabel,
	Better: Ui.Chip,
	Landmark: Landmark,
	X: number, -- 목록 안 위치(설계 px)
}
local cards: { [string]: Card } = {}

-- 화면 이름표(들고 있는 명소 / 가리키는 명소). 월드 BillboardGui 대신 ScreenGui 로 — 화면 안(띠 위)에 가둠
local tag: Frame
local tagStars: TextLabel
local tagChip: Ui.Chip? = nil
local tagKey: string? = nil -- 지금 이름표 내용(명소 Id | 별)
local tagAnchor: Vector3? = nil -- 이름표 아래 끝이 붙는 월드 점(보일 때만, ParkEdit.tagAnchor)

-- 소리
local pickSound: Sound
local dropSound: Sound
local cancelSound: Sound

local function makeSound(pitch: number, volume: number): Sound
	return Ui.new("Sound", { SoundId = SOUND_ID, PlaybackSpeed = pitch, Volume = volume, Parent = SoundService })
end

local function play(sound: Sound?)
	if sound then
		sound.TimePosition = 0
		sound:Play()
	end
end

local function disconnectAll(list: { RBXScriptConnection })
	for _, connection in list do
		connection:Disconnect()
	end
	table.clear(list)
end

-- 지금 화면에 보여 줄 배치: 응답을 기다리는 편집이 있으면 미리 보기, 아니면 서버 상태
local function viewState(): Snapshot?
	return preview or lastState
end

-- 화면 상태의 칸 모습("#locked" | "#empty" | 명소 Id, 상태가 없으면 nil). 매 프레임 가리키는 칸을 보므로
-- 상태 표(스냅샷·미리 보기 사본은 바뀌지 않고 새 표로 갈림)마다 parkSlots 를 한 번만 셈
local lookCache: { View: Snapshot?, Slots: { [number]: string }, Unlocked: number } =
	{ View = nil, Slots = {}, Unlocked = 0 }
local function viewLook(slot: number): string?
	local view = viewState()
	if not view then
		return nil
	end
	if lookCache.View ~= view then
		local slots, unlocked = PlayerState.parkSlots(view)
		lookCache.View, lookCache.Slots, lookCache.Unlocked = view, slots, unlocked
	end
	if slot < 1 or slot > PlayerState.MAX_SLOTS then
		return nil
	elseif slot > lookCache.Unlocked then
		return ParkGrid.LOOK_LOCKED
	end
	return lookCache.Slots[slot] or ParkGrid.LOOK_EMPTY
end

-- 캐릭터 · 부지 ------------------------------------------------------------------

local function rootPart(): BasePart?
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	return if root and root:IsA("BasePart") then root else nil
end

local function humanoid(): Humanoid?
	local character = player.Character
	return character and character:FindFirstChildOfClass("Humanoid")
end

-- 캐릭터가 내 부지(+ margin) 안에 있는지
local function atPlot(margin: number): boolean
	local root = rootPart()
	local cf = origin
	if not root or not cf then
		return false
	end
	local p = cf:PointToObjectSpace(root.Position)
	return ParkGrid.onPlot(p.X, p.Z, margin)
end

-- 칸 받침대 윗면 가운데(명소 피벗 자리). ParkService 가 미니어처를 놓는 자리와 같음
local function slotTop(slot: number): CFrame
	local x, z = ParkGrid.slotOffset(slot)
	return (origin :: CFrame) * CFrame.new(x, ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT, z)
end

local function slotOf(container: Instance): number?
	local slot = container:GetAttribute("Slot")
	if type(slot) == "number" then
		return slot
	end
	local digits = container.Name:match("^Slot(%d+)$")
	return if digits then tonumber(digits) else nil
end

-- 월드 칸 모델의 모습("#locked" | "#empty" | 명소 Id). Look 속성이 없는 옛 서버는 모름(nil)
local function worldLook(slot: number): string?
	local container = containers[slot]
	if not container then
		return nil
	end
	local look = container:GetAttribute("Look")
	return if type(look) == "string" then look else nil
end

-- 월드 칸 모델의 명소를 이 화면에서만 숨기기/되돌리기. 받침대는 그대로(이름표는 paintLabels)
local function applyHidden(container: Instance, hide: boolean)
	for _, child in container:GetChildren() do
		if child:IsA("Model") then
			for _, descendant in child:GetDescendants() do
				if descendant:IsA("BasePart") or descendant:IsA("Decal") then
					descendant.LocalTransparencyModifier = if hide then 1 else 0
				end
			end
		end
	end
end

-- 칸 이름표(ParkService 가 받침대에 붙인 BillboardGui: 스터드 크기, MaxDistance 60) 켜기/끄기
local function setLabel(container: Instance, on: boolean)
	for _, child in container:GetChildren() do
		if child:IsA("BasePart") then
			for _, descendant in child:GetDescendants() do
				if descendant:IsA("BillboardGui") and descendant.Enabled ~= on then
					descendant.Enabled = on
				end
			end
		end
	end
end

-- 배치 모드 동안 칸 이름표는 모두 끔: 이름표는 스터드 크기라 가까운 카메라에서 크게 나와(MaxDistance 60 안) 12개가
-- 명소를 덮음. 대신 들고 있는 명소 / 가리키는 명소 하나만 화면 이름표(setTag). 밖에서는 모두 켬
local function paintLabels()
	for _, container in containers do
		setLabel(container, not editing)
	end
end

local function setHidden(container: Instance, hide: boolean)
	if (hidden[container] == true) == hide then
		return
	end
	hidden[container] = if hide then true else nil
	applyHidden(container, hide)
end

-- 부지 입구 간판(ParkService 의 "Sign": 내 이름·수입)을 이 화면에서만 숨기기/되돌리기. 위에서 보기에서는 간판이
-- 아래 띠 바로 위에 걸려 띠 딱지 뒤로 검은 판·기둥 끝이 삐져나옴(배치 모드 동안에는 필요 없는 정보)
local signHidden = false
local function hideSign(hide: boolean)
	local sign = plot and plot:FindFirstChild("Sign")
	if signHidden == hide or not sign then
		signHidden = hide and sign ~= nil
		return
	end
	signHidden = hide
	for _, descendant in sign:GetDescendants() do
		if descendant:IsA("BasePart") then
			descendant.LocalTransparencyModifier = if hide then 1 else 0
		elseif descendant:IsA("SurfaceGui") then
			descendant.Enabled = not hide
		end
	end
end

-- 모형 ------------------------------------------------------------------------------

-- 이 화면에서만 쓰는 명소 모형(누를 수 없음, 그림자 없음). 못 만들면 nil
local function localModel(landmark: Landmark): Model?
	local ok, model = pcall(Models.create, landmark, ParkGrid.MINIATURE_SIZE)
	if not ok or typeof(model) ~= "Instance" or not model:IsA("Model") then
		warn("[LandmarkRNG] 배치 모형을 만들지 못했어요 (" .. landmark.Id .. "): " .. tostring(model))
		return nil
	end
	for _, descendant in model:GetDescendants() do
		if descendant:IsA("BasePart") then
			descendant.Anchored = true
			descendant.CanCollide = false
			descendant.CanQuery = false
			descendant.CanTouch = false
			descendant.CastShadow = false
		end
	end
	return model
end

local function rig(model: Model): Rig
	local pivot = model:GetPivot()
	local parts: { BasePart } = {}
	local offsets: { CFrame } = {}
	for _, descendant in model:GetDescendants() do
		if descendant:IsA("BasePart") then
			table.insert(parts, descendant)
			table.insert(offsets, pivot:ToObjectSpace(descendant.CFrame))
		end
	end
	return { Model = model, Parts = parts, Offsets = offsets, Pivot = pivot }
end

local moveBuffer: { CFrame } = {}
local function moveRig(target: Rig, cf: CFrame)
	target.Pivot = cf
	table.clear(moveBuffer)
	for index, offset in target.Offsets do
		moveBuffer[index] = cf * offset
	end
	-- BulkMoveTo: 파트 여러 개를 한 번에(가짜 환경처럼 없으면 하나씩)
	local ok = pcall(function()
		workspace:BulkMoveTo(target.Parts, moveBuffer, Enum.BulkMoveMode.FireCFrameChanged)
	end)
	if not ok then
		for index, part in target.Parts do
			part.CFrame = moveBuffer[index]
		end
	end
end

-- 들고 있는 반투명 복사본: 원래 색이 비치는 옅은 노란 강조 + 흰 테두리(이름 + 별은 화면 이름표 setTag)
local function makeGhost(landmark: Landmark): Ghost?
	local model = localModel(landmark)
	if not model then
		return nil
	end
	local height = 6
	pcall(function()
		height = model:GetExtentsSize().Y
	end)
	local originals: { [BasePart]: number } = {}
	for _, descendant in model:GetDescendants() do
		if descendant:IsA("BasePart") then
			originals[descendant] = descendant.Transparency
			descendant.Transparency = descendant.Transparency + (1 - descendant.Transparency) * GHOST_FADE
		end
	end
	local light = Ui.new("Highlight", {
		Name = "Held",
		Adornee = model,
		FillColor = Ui.colorPair("Sun").Face,
		FillTransparency = GHOST_FILL,
		OutlineColor = WHITE,
		OutlineTransparency = 0,
		DepthMode = Enum.HighlightDepthMode.AlwaysOnTop,
		Parent = model,
	})
	return { Model = model, Rig = rig(model), Originals = originals, Light = light, Height = height }
end

-- 들고 있던 복사본을 원래 모습(불투명)으로: 받침대에 내려앉을 때
local function solidify(ghost: Ghost): Rig
	for part, transparency in ghost.Originals do
		part.Transparency = transparency
	end
	ghost.Light:Destroy()
	return ghost.Rig
end

-- 부지 회전(위쪽 = 월드 위쪽)만 남긴 CFrame
local function plotRotation(): CFrame
	local cf = origin :: CFrame
	return cf - cf.Position
end

-- proxy: 이 화면에서 옮긴 칸에 서버 칸이 맞을 때까지 보여 주는 모형
local function setProxy(slot: number, id: string?)
	local current = proxies[slot]
	if current and current.Id == id then
		return
	end
	if current then
		current.Model:Destroy()
		proxies[slot] = nil
	end
	local landmark = if id then Landmarks.ById[id] else nil
	if not landmark or not localFolder or not origin then
		return
	end
	local model = localModel(landmark)
	if model then
		model:PivotTo(slotTop(slot))
		model.Parent = localFolder
		proxies[slot] = { Id = landmark.Id, Model = model }
	end
end

-- 빛나는 판(놓을 자리) 칠하기. 가리키는 칸(hoverSlot)이 놓을 수 있는 칸이면 그 판만 진하게 숨 쉬듯(step)
local function paintMarkers(slots: { [number]: string }, unlocked: number, heldFrom: number)
	markerPulse = nil
	for slot, marker in markers do
		local locked = slot > unlocked
		local id = if locked then nil else slots[slot]
		local color: Color3? = nil
		local transparency = 1
		if held then
			if locked then
				-- 잠긴 칸은 아주 흐린 빨강(가리키면 강조·복사본이 빨개짐) — 잠긴 칸이 많아도 놓을 자리가 먼저 보이게
				color, transparency = Ui.colorPair("Coral").Face, 0.9
			elseif slot == heldFrom then
				color, transparency = WHITE, 0.5
			else
				-- 놓을 수 있는 칸: 빈 칸은 초록, 명소가 있으면(자리 바꿈) 노랑 — 은은하게, 가리키는 칸만 진하게.
				-- 보관함에서 집었으면(heldFrom 0) 명소 있는 칸 = 바꿔 넣을 곳이라 조금 더 또렷하게
				color = if id then Ui.colorPair("Sun").Face else Ui.colorPair("Grass").Face
				transparency = if not id then MARK_EMPTY elseif heldFrom == 0 then MARK_REPLACE else MARK_SWAP
				if slot == hoverSlot then
					transparency = MARK_TARGET
					markerPulse = marker
				end
			end
		elseif not locked and not id then
			color, transparency = Ui.colorPair("Grass").Face, 0.62 -- 빈 칸
			if slot == fillSlot then
				transparency = MARK_TARGET -- 채울 빈 칸: 진하게 숨 쉬듯(step)
				markerPulse = marker
			end
		end
		if color then
			marker.Color = color
		end
		marker.Transparency = transparency
	end
end

-- 화면 상태(preview/서버)와 월드 칸 모델을 맞춤: 들고 있는 칸·날아오는 칸·이 화면에서 옮긴 칸은 월드 명소를 숨기고,
-- 옮긴 칸에 서버 칸이 아직 옛 모습이면 로컬 모형(proxy)을 둠. 빛나는 판도 다시 칠함
local function reconcile()
	if not editing then
		return
	end
	local view = viewState()
	if not view or not origin then
		return
	end
	local slots, unlocked = PlayerState.parkSlots(view)
	local fill = fillSlot
	if fill and (held or fill > unlocked or slots[fill] ~= nil) then
		fillSlot = nil -- 칸이 참(자동 굴림이 새 명소를 놓음 등)·잠김·명소를 집음
	end
	local heldFrom = 0
	if held then
		for slot = 1, unlocked do
			if slots[slot] == held.Id then
				heldFrom = slot
				break
			end
		end
	end
	local flying: { [number]: boolean } = {}
	for _, flyer in flyers do
		if flyer.Slot then
			flying[flyer.Slot] = true
		end
	end
	local now = os.clock()
	for slot = 1, PlayerState.MAX_SLOTS do
		local want = if slot > unlocked then ParkGrid.LOOK_LOCKED else slots[slot] or ParkGrid.LOOK_EMPTY
		local have = worldLook(slot)
		local edited = localEdits[slot]
		if edited and (have == want or now > edited) then
			localEdits[slot] = nil -- 서버 칸이 맞았거나 너무 오래 기다림
			edited = nil
		end
		local covered = slot == heldFrom or flying[slot] == true
		local mismatch = edited ~= nil and have ~= want
		local container = containers[slot]
		if container then
			setHidden(container, covered or mismatch)
		end
		setProxy(slot, if mismatch and not covered then want else nil)
	end
	for container in hidden do
		if not container.Parent then
			hidden[container] = nil -- 서버가 칸 모델을 다시 만듦
		end
	end
	painted = { Slots = slots, Unlocked = unlocked, HeldFrom = heldFrom }
	rayDirty = true -- 숨긴 명소·로컬 모형이 바뀌었을 수 있음
	paintMarkers(slots, unlocked, heldFrom)
	paintLabels()
end

-- 가리키는 칸이 바뀜: 판·이름표만 다시(칸 배치는 그대로)
local function repaintHover()
	local last = painted
	if editing and last then
		paintMarkers(last.Slots, last.Unlocked, last.HeldFrom)
		paintLabels()
	end
end

-- 날아가기(놓기·되돌아가기·자리 바꿈). 도착하면 그 칸 서버 모습이 아직 옛것이면 proxy 로 남음
local function fly(mover: Rig, from: CFrame, to: CFrame, slot: number?, id: string?, hop: number, fade: boolean?)
	table.insert(flyers, {
		Rig = mover,
		From = from,
		To = to,
		Start = os.clock(),
		Seconds = FLY_SECONDS,
		Hop = hop,
		Slot = slot,
		Id = id,
		Fade = fade == true,
	})
end

local function landFlyer(flyer: Flyer)
	local slot, id = flyer.Slot, flyer.Id
	local view = viewState()
	local adopt = false
	if slot and id and view and not flyer.Fade and not proxies[slot] then
		local want = ParkGrid.look(view, slot)
		adopt = want == id and worldLook(slot) ~= want and localEdits[slot] ~= nil
	end
	if adopt and slot and id then
		proxies[slot] = { Id = id, Model = flyer.Rig.Model }
	else
		flyer.Rig.Model:Destroy()
	end
end

-- 들고 있기 ------------------------------------------------------------------------

local renderBar: () -> ()

-- 들고 있는 명소를 원래 자리로 돌려놓음(취소). 전시 중이었으면 받침대로 날아가 앉음
local function returnHeld(silent: boolean?)
	local current = held
	if not current then
		return
	end
	held = nil
	local view = viewState()
	local from = if view then ParkGrid.slotOf(view, current.Id) else 0
	if from > 0 and origin and not silent then
		local mover = solidify(current.Ghost)
		fly(mover, mover.Pivot, slotTop(from), from, current.Id, 1)
	else
		current.Ghost.Model:Destroy()
	end
	if not silent then
		play(cancelSound)
	end
	reconcile()
	renderBar()
end

-- 명소 집기. from: 전시 칸(0 = 보관함). 이미 들고 있으면 그것은 제자리로.
-- at: 보관함에서 집을 때 떠오를 칸(없으면 ParkGrid.storageStart — 채울 빈 칸이 있으면 그 칸)
local function pickUp(id: string, from: number, at: number?)
	local landmark = Landmarks.ById[id]
	local view = viewState()
	if not landmark or not view or not localFolder or not origin then
		return
	end
	if held then
		if held.Id == id then
			return
		end
		returnHeld()
	end
	local ghost = makeGhost(landmark)
	if not ghost then
		return
	end
	if from > 0 then
		fillSlot = nil -- 전시 명소를 집음 = 빈 칸 채우기는 그만
	end
	-- 처음 자리: 전시 칸이면 그 받침대 위, 보관함이면 첫 빈 칸(꽉 찼으면 가장 약한 전시 명소 칸) 위 — 가리키면 그리로 감
	local start = slotTop(if from > 0 then from else at or ParkGrid.storageStart(view)).Position
	moveRig(ghost.Rig, CFrame.new(start + Vector3.new(0, LIFT, 0)) * plotRotation())
	ghost.Model.Parent = localFolder
	held = { Id = id, Ghost = ghost, Position = start, Target = start, Lift = LIFT, Angle = 0 }
	play(pickSound)
	reconcile()
	renderBar()
end

-- 배치 편집 응답(성공·실패 모두). 기다리는 요청이 더 없으면(또는 stale 이면) 미리 보기를 버리고 서버 상태로
local function finishRequest(ok: boolean?, stale: boolean?)
	if autoFlip and ok and lastState and lastState.Settings.AutoPark == false then
		local button = autoButton
		if button then
			local scale = button.Root:FindFirstChildOfClass("UIScale")
			if scale then
				scale.Scale = 1
				TweenService
					:Create(scale, TweenInfo.new(0.18, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 2, true), {
						Scale = 1.15,
					})
					:Play()
			end
		end
		if not autoNoticed then
			autoNoticed = true
			handlers.Toast("자동 꺼짐", "podium", Theme.Ink)
		end
	end
	if ok ~= nil then
		autoFlip = false
	end
	pending = math.max(0, pending - 1)
	if pending == 0 or stale then
		preview = nil
	end
	if ok == false or stale then
		table.clear(localEdits) -- 서버 상태로 되돌림(옮긴 칸 로컬 모형 치움)
		if editing then
			play(cancelSound)
		end
	end
	reconcile()
	renderBar()
end

-- 미리 보기를 걸고 서버에 보냄. edited: 이 편집으로 모습이 바뀌는 칸(서버 칸이 맞을 때까지 로컬 모형)
local function send(copy: Snapshot, wasAuto: boolean, edited: { number }, request: () -> (boolean?, boolean?))
	preview = copy
	pending += 1
	if wasAuto then
		autoFlip = true -- 알림은 서버가 받아들인 뒤(finishRequest)에만
	end
	local until_ = os.clock() + EDIT_HOLD
	for _, slot in edited do
		localEdits[slot] = until_
	end
	task.spawn(function()
		local ok, stale = request()
		finishRequest(ok, stale)
	end)
end

-- 놓기 계획 실행: 복사본이 받침대에 내려앉고, 자리 바꿈 상대는 원래 칸으로 폴짝, 바꿔 넣기 상대는 위로 사라짐
local function commit(plan: ParkGrid.DropPlan)
	local current = held
	local view = viewState()
	if not current or not view or not origin then
		return
	end
	local copy = ParkGrid.preview(view, function(c)
		return (PlayerState.setDisplay(c, plan.Slot, plan.Id, plan.Expected, plan.From))
	end)
	if not copy then
		handlers.Toast("배치 실패", "close")
		returnHeld()
		return
	end
	local wasAuto = view.Settings.AutoPark ~= false
	held = nil
	local edited = { plan.Slot }
	local mover = solidify(current.Ghost)
	fly(mover, mover.Pivot, slotTop(plan.Slot), plan.Slot, plan.Id, 0.6)
	local partner = if plan.Partner then Landmarks.ById[plan.Partner] else nil
	if partner then
		local other = localModel(partner)
		if other and localFolder then
			local partnerRig = rig(other)
			moveRig(partnerRig, slotTop(plan.Slot))
			other.Parent = localFolder
			if plan.From > 0 then
				fly(partnerRig, slotTop(plan.Slot), slotTop(plan.From), plan.From, partner.Id, HOP)
			else
				-- 보관함으로 밀려남: 위로 톡 튀어 오르며 사라짐
				fly(partnerRig, slotTop(plan.Slot), slotTop(plan.Slot) + Vector3.new(0, 7, 0), nil, nil, 1, true)
			end
		end
	end
	if plan.From > 0 then
		table.insert(edited, plan.From)
	end
	play(dropSound)
	send(copy, wasAuto, edited, function()
		return handlers.SetDisplay(plan.Slot, plan.Id, plan.Expected, plan.From)
	end)
	reconcile()
	renderBar()
end

-- 보관: 들고 있는 전시 명소를 보관함으로(보관함에서 집은 것이면 그냥 내려놓음)
local function storeHeld()
	local current = held
	local view = viewState()
	if not current or not view then
		return
	end
	local plan = ParkGrid.storePlan(view, current.Id)
	if not plan then
		returnHeld()
		return
	end
	local copy = ParkGrid.preview(view, function(c)
		return (PlayerState.setDisplay(c, plan.Slot, nil, plan.Expected))
	end)
	if not copy then
		returnHeld()
		return
	end
	local wasAuto = view.Settings.AutoPark ~= false
	held = nil
	local mover = solidify(current.Ghost)
	fly(mover, mover.Pivot, mover.Pivot + Vector3.new(0, 6, 0), nil, nil, 0, true)
	play(dropSound)
	send(copy, wasAuto, { plan.Slot }, function()
		return handlers.SetDisplay(plan.Slot, nil, plan.Expected, nil)
	end)
	reconcile()
	renderBar()
end

-- 채울 빈 칸 정하기(nil = 풂). 정하면 보관함을 맨 앞(가장 희귀한 명소)으로 돌리고 앞 카드들이 톡 — "여기서 골라 넣어요"
local function setFill(slot: number?)
	if fillSlot == slot then
		return
	end
	fillSlot = slot
	reconcile()
	if slot and scroller then
		scroller.CanvasPosition = Vector2.zero
		for _, card in cards do
			if card.Button.LayoutOrder <= 4 then
				TweenService:Create(card.Scale, CARD_NUDGE, { Scale = 1.12 }):Play()
			end
		end
	end
end

-- 보관함 카드를 누름: 채울 빈 칸이 있으면 집어서 누를 필요 없이 바로 그 칸으로 날아감(true). 없으면 false(보통 집기)
local function fillWith(id: string): boolean
	local target = fillSlot
	local view = viewState()
	if not target or not view or viewLook(target) ~= ParkGrid.LOOK_EMPTY or ParkGrid.slotOf(view, id) > 0 then
		return false
	end
	fillSlot = nil
	pickUp(id, 0, target) -- 그 칸 위에 떠오름
	local current = held
	if not current or current.Id ~= id then
		return true
	end
	local plan = ParkGrid.dropPlan(view, id, target)
	if plan.Kind == "place" then
		commit(plan) -- 받침대로 내려앉음
	end
	return true
end

-- [자동]: 켜기/끄기. 끄면 지금 배치 그대로(화면 안 바뀜). 켜서 직접 고른 배치가 바뀌면 3초 안에 한 번 더 눌러야 함
local paintAuto: () -> ()
local function toggleAuto()
	local view = viewState()
	if not view then
		return
	end
	local on = view.Settings.AutoPark ~= false
	if not on and os.clock() >= confirmUntil and ParkGrid.autoWouldChange(view) then
		confirmUntil = os.clock() + CONFIRM_SECONDS
		confirmToken += 1
		local token = confirmToken
		paintAuto()
		task.delay(CONFIRM_SECONDS, function()
			if token == confirmToken then
				paintAuto()
			end
		end)
		return
	end
	confirmUntil = 0
	confirmToken += 1
	returnHeld()
	local want = not on
	local copy = ParkGrid.preview(view, function(c)
		PlayerState.setAutoPark(c, want)
		return true
	end)
	if not copy then
		return
	end
	send(copy, false, {}, function()
		handlers.SetAutoPark(want)
		return nil, nil
	end)
	reconcile()
	renderBar()
end

-- 입력 → 칸 ------------------------------------------------------------------------

type Hit = { Slot: number?, Ground: Vector3?, OnPlot: boolean }

local function guiInset(): Vector2
	local ok, inset = pcall(function()
		return (GuiService:GetGuiInset())
	end)
	return if ok and typeof(inset) == "Vector2" then inset else Vector2.zero
end

-- InputObject.Position(상단바 아래 기준) -> 뷰포트 좌표
local function toViewport(position: Vector3): Vector2
	return Vector2.new(position.X, position.Y) + guiInset()
end

-- 뷰포트 좌표가 아래 띠(+ 위 딱지 줄) 위인지
local function overBar(at: Vector2): boolean
	if not bar or not bar.Visible then
		return false
	end
	local p = at - guiInset()
	local top = tray.AbsolutePosition.Y - CHIP_ROW * Ui.scale()
	local left, right = tray.AbsolutePosition.X, tray.AbsolutePosition.X + tray.AbsoluteSize.X
	return p.X >= left and p.X <= right and p.Y >= top and p.Y <= tray.AbsolutePosition.Y + tray.AbsoluteSize.Y
end

local function containerOf(instance: Instance): Instance?
	local node: Instance? = instance
	local folder = slotsFolder
	while node and folder and node.Parent ~= folder do
		node = node.Parent
	end
	return node
end

-- 광선이 맞출 것: 내 칸 모델들. 단 이 화면에서 숨긴 명소(들고 있는 칸·날아와 앉을 칸 — 로컬 모형이 대신 서 있는
-- 칸은 빼고)는 받침대만: 안 보이는 원래 명소가 뒤쪽 받침대를 가려서, 거기에 놓으면 원래 칸으로 되돌아가던 것
local rayList: { Instance } = {}
local function rayTargets(folder: Instance): { Instance }
	if not rayDirty then
		return rayList
	end
	rayDirty = false
	local list: { Instance } = {}
	for _, container in folder:GetChildren() do
		local slot = slotOf(container)
		if hidden[container] and not (slot and proxies[slot]) then
			for _, child in container:GetChildren() do
				if not child:IsA("Model") then
					table.insert(list, child)
				end
			end
		else
			table.insert(list, container)
		end
	end
	rayList = list
	rayParams.FilterDescendantsInstances = list
	return list
end

-- 화면 한 점이 가리키는 칸: 먼저 내 부지 칸 모델(받침대·보이는 명소)에 광선을 쏘고, 안 맞으면 부지 바닥 높이 평면과
-- 만나는 점에서 가장 가까운 칸(ParkGrid.slotAt)
local function pick(at: Vector2): Hit
	local result: Hit = { Slot = nil, Ground = nil, OnPlot = false }
	local camera = workspace.CurrentCamera
	local cf = origin
	if not camera or not cf then
		return result
	end
	local ray = camera:ViewportPointToRay(at.X, at.Y)
	local groundY = cf.Position.Y + ParkGrid.BASE_TOP
	if ray.Direction.Y < -1e-4 then
		local t = (groundY - ray.Origin.Y) / ray.Direction.Y
		if t > 0 then
			local point = ray.Origin + ray.Direction * t
			local p = cf:PointToObjectSpace(point)
			result.Ground = point
			result.OnPlot = ParkGrid.onPlot(p.X, p.Z, 1)
			result.Slot = ParkGrid.slotAt(p.X, p.Z)
		end
	end
	local folder = slotsFolder
	if folder then
		rayTargets(folder)
		local hit = workspace:Raycast(ray.Origin, ray.Direction * RAY_LENGTH, rayParams)
		local container = if hit then containerOf(hit.Instance) else nil
		local slot = if container then slotOf(container) else nil
		if slot then
			result.Slot = slot
			result.OnPlot = true
		end
	end
	return result
end

-- 들고 있는 명소를 가리키는 곳에 놓음(누름 또는 끌어서 뗌): 다른 열린 칸 = 옮기기·자리 바꾸기, 같은 칸 · 부지 밖 = 내려놓기,
-- 잠긴 칸 = 알림(계속 들고 있음), 부지 안 칸 없는 곳 = 그대로
local function placeAt(hit: Hit)
	local current = held
	local view = viewState()
	if not current or not view then
		return
	end
	local slot = hit.Slot
	if not slot then
		if not hit.OnPlot then
			returnHeld() -- 부지 밖 = 취소
		end
		return
	end
	local plan = ParkGrid.dropPlan(view, current.Id, slot)
	if plan.Kind == "locked" then
		handlers.Toast("공원 확장", "lock")
	elseif plan.Kind == "cancel" then
		returnHeld() -- 같은 칸 = 제자리에 내려놓기
	else
		commit(plan)
	end
end

local function cancelOrExit()
	if held then
		returnHeld()
	else
		ParkEdit.exit()
	end
end

-- 채팅 등 글자 칸에 쓰는 중인지(빠져나온 직후 잠깐 포함: 빠져나오는 Esc 가 포커스가 풀린 뒤에 올 수 있음)
local function typing(): boolean
	if textFocused or os.clock() - textReleasedAt < TEXT_GRACE then
		return true
	end
	local ok, box = pcall(function()
		return UserInputService:GetFocusedTextBox()
	end)
	return ok and box ~= nil
end

-- 위에서 보기 배율을 바꾸고 카메라를 바로 옮김(들어갈 때 날아가는 중이면 배율만)
local function setZoom(value: number)
	zoom = math.clamp(value, ParkGrid.ZOOM_MIN, ParkGrid.ZOOM_MAX)
	local camera = workspace.CurrentCamera
	if camera and not cameraTween and viewMode == "Top" and origin then
		camera.CFrame = ParkEdit.topCFrame()
	end
end

-- 닿아 있는 손가락 둘(없으면 nil)의 사이 거리
local function touchSpan(): number?
	local first: Vector2? = nil
	for _, at in touches do
		if first then
			return (at - first).Magnitude
		end
		first = at
	end
	return nil
end

-- 두 손가락 모드의 기준(시작 거리·배율)을 지금으로: 손가락이 늘거나 줄면 배율이 튀지 않게
local function rebasePinch()
	local gesture = pinch
	if gesture then
		gesture.Distance = touchSpan() or 0
		gesture.Zoom = zoom
	end
end

-- 손가락이 닿음. 두 번째 손가락이면 두 손가락 모드: 진행 중인 집기·끌기를 취소(든 명소는 제자리로).
-- 이 손가락으로 집기·놓기를 해도 되면(한 손가락) true
local function touchBegan(input: InputObject): boolean
	for other in touches do
		-- 뗌(InputEnded)을 못 받고 끝난 손가락은 뺌
		local state = (other :: any).UserInputState
		if state == Enum.UserInputState.End or state == Enum.UserInputState.Cancel then
			touches[other] = nil
		end
	end
	touches[input] = toViewport(input.Position)
	if pinch then
		rebasePinch()
		return false
	end
	if touchSpan() == nil then
		return true
	end
	press = nil
	pointer = nil
	pinch = { Distance = 0, Zoom = zoom }
	rebasePinch()
	if held then
		returnHeld()
	end
	return false
end

local function onInputBegan(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	if kind == Enum.UserInputType.Keyboard then
		local key = input.KeyCode
		if typing() then
			return -- 채팅 입력 중(Esc = 글자 칸에서 빠져나오기, 배치 모드는 그대로)
		elseif key == Enum.KeyCode.Escape then
			cancelOrExit() -- Esc 는 로블록스 메뉴가 먼저 가져갈 수 있어서(processed) Q 도 같은 동작
		elseif processed then
			return
		elseif key == Enum.KeyCode.Q then
			cancelOrExit()
		elseif key == Enum.KeyCode.Backspace or key == Enum.KeyCode.Delete then
			storeHeld()
		end
		return
	end
	if processed then
		return -- 화면 버튼·조이스틱
	end
	local pointed = kind == Enum.UserInputType.MouseButton1 or kind == Enum.UserInputType.Touch
	local at = if kind == Enum.UserInputType.Touch
		then toViewport(input.Position)
		else UserInputService:GetMouseLocation()
	if pointed and overBar(at) then
		-- 띠 위 딱지 줄의 비친 곳(버튼이 아니라 processed 가 아님): 띠처럼 뒤의 명소를 집지 않고, 손가락으로도
		-- 세지 않음(띠에 손가락을 올려 둔 채 다른 손가락으로 칸을 톡 누르면 두 손가락으로 잘못 잡히지 않게)
		return
	end
	if kind == Enum.UserInputType.Touch and not touchBegan(input) then
		return -- 두 손가락
	end
	if pointed then
		pointerKind = if kind == Enum.UserInputType.Touch then "Touch" else "Mouse"
		pointer = at
		local current: Press = { Input = input, Kind = kind, Start = at, Moved = false, Picked = false }
		press = current
		-- 명소를 누르면 바로 집음(끌어서 놓거나, 손을 뗀 뒤 놓을 칸을 누름). 평소 카메라에서 터치로 끌면 화면이
		-- 돌아가므로 그때는 누를 때 집지 않고 톡 누르면(뗄 때) 집음
		if not held and not (kind == Enum.UserInputType.Touch and viewMode ~= "Top") then
			local hit = pick(at)
			local slot = hit.Slot
			local look = if slot then viewLook(slot) else nil
			if slot and look then
				if Landmarks.ById[look] then
					pickUp(look, slot)
					current.Picked = held ~= nil
				end
			end
		end
	elseif kind == Enum.UserInputType.MouseButton2 then
		rightStart = UserInputService:GetMouseLocation()
	end
end

local function onInputChanged(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	if kind == Enum.UserInputType.MouseMovement then
		pointerKind = "Mouse"
	elseif kind == Enum.UserInputType.Touch then
		if touches[input] then
			touches[input] = toViewport(input.Position)
		end
		local gesture = pinch
		if gesture then
			-- 두 손가락: 위에서 보기면 벌리기/모으기 = 가까이/멀리(평소 카메라는 로블록스 카메라가 함)
			local span = touchSpan()
			if span and viewMode == "Top" and origin then
				if gesture.Distance <= 0 then
					rebasePinch()
				else
					setZoom(ParkGrid.pinchZoom(gesture.Zoom, gesture.Distance, span))
				end
			end
			return
		end
		local current = press
		if current and current.Input == input then
			local at = toViewport(input.Position)
			pointer = at
			if (at - current.Start).Magnitude > DRAG_PX then
				current.Moved = true
			end
		end
	elseif kind == Enum.UserInputType.MouseWheel and not processed and viewMode == "Top" and origin then
		-- 위에서 보기: 휠로 가까이/멀리
		setZoom(zoom - input.Position.Z * ZOOM_STEP)
	end
end

local function onInputEnded(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	if kind == Enum.UserInputType.MouseButton2 then
		local start = rightStart
		rightStart = nil
		if held and start and (UserInputService:GetMouseLocation() - start).Magnitude <= DRAG_PX then
			returnHeld() -- 오른쪽 클릭 = 취소 (끌면 화면 돌리기)
		end
		return
	end
	if kind == Enum.UserInputType.Touch then
		touches[input] = nil
		if pinch then
			-- 두 손가락 모드: 손가락이 모두 떨어질 때까지 뗌은 무시(놓기·집기 없음)
			if next(touches) == nil then
				pinch = nil
			else
				rebasePinch()
			end
			return
		end
	end
	if kind ~= Enum.UserInputType.MouseButton1 and kind ~= Enum.UserInputType.Touch then
		return
	end
	local current = press
	if not current or current.Kind ~= kind or (kind == Enum.UserInputType.Touch and current.Input ~= input) then
		return
	end
	press = nil
	local at = if kind == Enum.UserInputType.Touch
		then toViewport(input.Position)
		else UserInputService:GetMouseLocation()
	local moved = current.Moved or (at - current.Start).Magnitude > DRAG_PX
	if kind == Enum.UserInputType.Touch then
		pointer = nil -- 터치는 손을 떼면 가리키는 곳이 없음(들고 있는 명소는 마지막 자리에 떠 있음)
	end
	if overBar(at) then
		if held and current.Picked and moved then
			storeHeld() -- 끌어서 아래 띠에 놓음 = 보관
		end
		return
	end
	if processed then
		return -- 다른 화면 버튼 위에서 뗌
	end
	local hit = pick(at)
	if current.Picked then
		-- 누르면서 집음: 끌어서 다른 칸에 놓으면 거기로, 거의 안 움직였으면 계속 들고 있음(다음 누름에 놓기)
		if held and moved then
			placeAt(hit)
		end
		return
	end
	if held then
		if kind == Enum.UserInputType.Touch and moved and viewMode ~= "Top" then
			return -- 평소 카메라: 터치로 끌면 화면 돌리기
		end
		placeAt(hit)
	elseif hit.Slot and not moved then
		local look = viewLook(hit.Slot)
		if look == ParkGrid.LOOK_LOCKED then
			handlers.Toast("공원 확장", "lock")
		elseif look and Landmarks.ById[look] then
			pickUp(look, hit.Slot) -- 평소 카메라에서 터치로 톡
		elseif look == ParkGrid.LOOK_EMPTY then
			setFill(if fillSlot == hit.Slot then nil else hit.Slot) -- 빈 받침대 = 채울 칸(다시 누르면 풂)
		end
	elseif not moved and not hit.OnPlot then
		setFill(nil)
	end
end

-- 매 프레임 ------------------------------------------------------------------------

local function setHover(slot: number?, color: Color3, outline: Color3?)
	local light = hoverLight
	if not light then
		return
	end
	local target: Instance? = nil
	if slot then
		local proxy = proxies[slot]
		target = if proxy then proxy.Model else containers[slot]
	end
	local changed = hoverSlot ~= slot
	hoverSlot = slot
	if light.Adornee ~= target then
		light.Adornee = target
	end
	light.Enabled = target ~= nil
	light.OutlineColor = outline or color
	light.FillColor = color
	if changed then
		repaintHover()
	end
end

-- 칸에 서 있는 명소 모형의 높이(스터드, 받침대 윗면부터). 로컬 모형(proxy)이 있으면 그것. 없으면 0
local heightCache: { [Instance]: number } = setmetatable({}, { __mode = "k" }) :: any
local function statueHeight(slot: number): number
	local proxy = proxies[slot]
	local model: Instance? = if proxy then proxy.Model else nil
	if not model then
		local container = containers[slot]
		model = container and container:FindFirstChildWhichIsA("Model")
	end
	if not model or not model:IsA("Model") then
		return 0
	end
	local cached = heightCache[model]
	if cached then
		return cached
	end
	local height = 0
	pcall(function()
		height = (model :: Model):GetExtentsSize().Y
	end)
	heightCache[model] = height
	return height
end

-- 화면 이름표: 명소 id 의 이름 딱지(등급 색) + 별을 월드 점 point(모형 꼭대기 위) 바로 위에. 화면 밖으로 나가지 않게
-- 상단바 아래 ~ 아래 띠 위, 양옆 안쪽에 가둠. id 가 nil 이면 숨김
local function setTag(id: string?, point: Vector3?)
	local camera = workspace.CurrentCamera
	local landmark = if id then Landmarks.ById[id] else nil
	local view = viewState()
	tagAnchor = nil
	if not tag or not landmark or not point or not camera or not view then
		if tag then
			tag.Visible = false
		end
		return
	end
	local stars = PlayerState.stars(view.Inventory[landmark.Id] or 0)
	local key = landmark.Id .. "|" .. stars
	if key ~= tagKey then
		tagKey = key
		if tagChip then
			tagChip.Root:Destroy()
		end
		local chip = Ui.chip({
			Name = "Name",
			Color = landmark.Tier.Color,
			Text = landmark.Name,
			Height = 30,
			TextSize = 19,
			AnchorPoint = Vector2.new(0.5, 0),
			Position = UDim2.fromScale(0.5, 0),
			ZIndex = 2,
			Parent = tag,
		})
		chip.Label.TextColor3 = WHITE
		tagChip = chip
		tagStars.Text = Ui.starsRich(stars, PlayerState.MAX_STARS)
	end
	local screen, _ = camera:WorldToViewportPoint(point)
	if screen.Z <= 0 then
		tag.Visible = false
		return
	end
	local inset = guiInset()
	local size = gui.AbsoluteSize
	local scale = Ui.scale()
	local half = TAG.X * scale / 2
	local x = math.clamp(screen.X - inset.X, half + TAG_EDGE, math.max(half + TAG_EDGE, size.X - half - TAG_EDGE))
	local lowest = (barTop or size.Y) - TAG_EDGE
	local y = math.clamp(screen.Y - inset.Y, TAG.Y * scale + TAG_EDGE, math.max(TAG.Y * scale + TAG_EDGE, lowest))
	tag.Position = UDim2.fromOffset(x, y)
	tag.Visible = true
	tagAnchor = point
end

local nextSweep = 0
local function step(dt: number)
	if not editing or not origin then
		return
	end
	local now = os.clock()
	if pointerKind == "Mouse" then
		pointer = UserInputService:GetMouseLocation()
		local current = press
		if current and pointer and (pointer - current.Start).Magnitude > DRAG_PX then
			current.Moved = true
		end
	end
	local at = pointer
	local hit: Hit? = nil
	if at and not overBar(at) then
		hit = pick(at)
	end
	local slot = hit and hit.Slot

	-- 들고 있는 명소가 갈 곳: 가리키는 칸 위(칸이 없으면 바닥 위 — 부지 밖이면 부지 가장자리에서 멈춤)
	local current = held
	local under: number? = nil -- 들고 있는 명소가 가는 곳 아래 칸(그 칸 명소 위로 뜸)
	if current then
		local cf = origin :: CFrame
		if hit and hit.Slot then
			current.Target = slotTop(hit.Slot).Position
		elseif hit and hit.Ground then
			local p = cf:PointToObjectSpace(hit.Ground)
			current.Target = cf:PointToWorldSpace(
				Vector3.new(
					math.clamp(p.X, -ParkGrid.PLOT_WIDTH / 2, ParkGrid.PLOT_WIDTH / 2),
					ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT,
					math.clamp(p.Z, -ParkGrid.PLOT_DEPTH / 2, ParkGrid.PLOT_DEPTH / 2)
				)
			)
		end
		local resting = cf:PointToObjectSpace(current.Target)
		under = ParkGrid.slotAt(resting.X, resting.Z)
		if not at then
			-- 가리키는 곳이 없으면(터치를 뗌) 떠 있는 칸을 가리키는 칸으로: 그 칸 판·강조가 켜짐(보관함에서 집어
			-- 꽉 찬 공원의 가장 약한 명소 위에서 시작할 때 = 누르면 바꿔 넣을 곳)
			slot = under
		end
	end

	if not slot and not current and fillSlot then
		slot = fillSlot -- 가리키는 곳이 없으면 채울 빈 칸을 강조
	end

	-- 가리키는 칸 강조: 잠긴 칸 빨강. 들고 있으면 놓을 칸 = 흰 테두리(빈 칸 초록 · 자리 바꿈 노랑 채우기 — 둘레에
	-- 노랗게 빛나는 판들 사이에서도 어느 칸인지 보이게), 아니면 명소 노랑 · 빈 칸 초록
	local look = if slot then viewLook(slot) else nil
	local occupied = look ~= nil and Landmarks.ById[look] ~= nil
	if slot and look then
		if look == ParkGrid.LOOK_LOCKED then
			setHover(slot, Ui.colorPair("Coral").Face)
		elseif held and look == held.Id then
			setHover(nil, HOVER_COLOR) -- 들고 나온 원래 칸: 누르면 그냥 내려놓기라 놓을 칸처럼 빛내지 않음
		elseif held then
			local fill = if occupied then Ui.colorPair("Sun").Face else Ui.colorPair("Grass").Face
			setHover(slot, fill, WHITE)
		else
			setHover(slot, if occupied then Ui.colorPair("Sun").Face else Ui.colorPair("Grass").Face)
		end
	elseif hoverSlot then
		setHover(nil, HOVER_COLOR)
	end

	-- 들고 있는 명소: 갈 곳으로 부드럽게 따라가며 오르내리고 돎
	if current then
		-- 아래 칸에 다른 명소가 있으면(자리 바꿈·바꿔 넣기) 그 명소 위로 떠서 둘 다 보이게
		local wantLift = LIFT
		local below = if under then viewLook(under) else nil
		if under and below and below ~= current.Id and Landmarks.ById[below] then
			wantLift = math.max(LIFT, statueHeight(under) + LIFT_CLEAR)
		end
		local follow = 1 - math.exp(-FOLLOW * dt)
		current.Position = current.Position:Lerp(current.Target, follow)
		current.Lift += (wantLift - current.Lift) * follow
		current.Angle = (current.Angle + SPIN_SPEED * dt) % (2 * math.pi)
		local lift = current.Lift + math.sin(now * BOB_SPEED) * BOB
		moveRig(
			current.Ghost.Rig,
			CFrame.new(current.Position + Vector3.new(0, lift, 0)) * plotRotation() * CFrame.Angles(0, current.Angle, 0)
		)
		local locked = look == ParkGrid.LOOK_LOCKED
		current.Ghost.Light.FillColor = if locked then Ui.colorPair("Coral").Face else Ui.colorPair("Sun").Face
		-- 가리키는 놓을 칸의 판이 진하게 숨 쉬듯 빛남
		local marker = markerPulse
		if marker then
			marker.Transparency = MARK_TARGET + math.sin(now * 5) * MARK_TARGET_PULSE
		end
		setTag(current.Id, current.Ghost.Rig.Pivot.Position + Vector3.new(0, current.Ghost.Height + TAG_GAP, 0))
	elseif slot and occupied and look then
		-- 들고 있지 않을 때: 가리키는 명소 이름 + 별
		setTag(look, slotTop(slot).Position + Vector3.new(0, statueHeight(slot) + TAG_GAP, 0))
	else
		setTag(nil)
	end
	local pulse = markerPulse
	if not current and pulse then
		pulse.Transparency = MARK_TARGET + math.sin(now * 5) * MARK_TARGET_PULSE -- 채울 빈 칸의 판도 숨 쉬듯
	end

	-- 날아가는 모형
	local landed = false
	for index = #flyers, 1, -1 do
		local flyer = flyers[index]
		local t = math.clamp((now - flyer.Start) / flyer.Seconds, 0, 1)
		local eased = 1 - (1 - t) ^ 3
		local cf = flyer.From:Lerp(flyer.To, eased) + Vector3.new(0, 4 * flyer.Hop * t * (1 - t), 0)
		moveRig(flyer.Rig, cf)
		if flyer.Fade then
			for _, part in flyer.Rig.Parts do
				part.LocalTransparencyModifier = t
			end
		end
		if t >= 1 then
			table.remove(flyers, index)
			landFlyer(flyer)
			landed = true
		end
	end
	if landed or (next(localEdits) ~= nil and now >= nextSweep) then
		nextSweep = now + 0.25
		reconcile()
	end
end

-- 카메라 · 이동 ----------------------------------------------------------------------

-- 위에서 보기에서 맞출 줄 수: 열린 칸이 있는 줄 + 잠긴 줄 하나(칸이 적을 때 명소가 작게 보이지 않게)
local function wantRows(): number
	local view = viewState()
	if not view then
		return Config.PARK_GRID
	end
	local _, unlocked = PlayerState.parkSlots(view)
	return ParkGrid.topRows(unlocked)
end

-- 위에서 보기 카메라 자리: 상단바 아래 ~ 아래 띠 위 영역에 앞 fitRows 줄이 딱 들어오게(ParkGrid.topView), 휠로 가까이/멀리
function ParkEdit.topCFrame(): CFrame
	local cf = origin :: CFrame
	local camera = workspace.CurrentCamera
	local viewport = if camera then camera.ViewportSize else Vector2.new(1280, 720)
	local height = math.max(viewport.Y, 1)
	local inset = guiInset()
	local bottom = 0
	if barTop then
		bottom = (height - (barTop + inset.Y) + BAR_CLEAR) / height
	end
	local view = ParkGrid.topView({
		Aspect = viewport.X / height,
		Fov = EDIT_FOV,
		Top = (inset.Y + TOP_MARGIN) / height,
		Bottom = bottom,
		Left = SIDE_MARGIN,
		Right = SIDE_MARGIN,
		Rows = fitRows,
		Zoom = zoom,
	})
	local eye = Vector3.new(view.Eye[1], view.Eye[2], view.Eye[3])
	local target = Vector3.new(view.Target[1], view.Target[2], view.Target[3])
	return CFrame.lookAt(cf:PointToWorldSpace(eye), cf:PointToWorldSpace(target))
end

local function playerControls(): any
	if controls then
		return controls
	end
	local ok, result = pcall(function()
		local scripts = player:FindFirstChild("PlayerScripts")
		local module = scripts and scripts:FindFirstChild("PlayerModule")
		return if module and module:IsA("ModuleScript") then (require(module) :: any):GetControls() else nil
	end)
	if ok and result then
		controls = result
	end
	return controls
end

local function setMovement(enabled: boolean)
	local module = playerControls()
	if module then
		pcall(function()
			if enabled then
				module:Enable()
			else
				module:Disable()
			end
		end)
	end
end

local function stopCameraTween()
	local tween = cameraTween
	cameraTween = nil
	if tween then
		tween:Cancel()
	end
end

local function applyView()
	local camera = workspace.CurrentCamera
	if not camera or not origin then
		return
	end
	stopCameraTween()
	if viewMode == "Top" then
		fitRows = wantRows()
		camera.CameraType = Enum.CameraType.Scriptable
		local tween =
			TweenService:Create(camera, CAMERA_TWEEN, { CFrame = ParkEdit.topCFrame(), FieldOfView = EDIT_FOV })
		cameraTween = tween
		tween.Completed:Connect(function()
			if cameraTween == tween then
				cameraTween = nil
			end
		end)
		tween:Play()
		setMovement(false)
	else
		local saved = savedCamera
		camera.CameraType = if saved and saved.Type ~= Enum.CameraType.Scriptable
			then saved.Type
			else Enum.CameraType.Custom
		camera.CameraSubject = humanoid() or (saved and saved.Subject) or nil
		camera.FieldOfView = if saved then saved.Fov else 70
		setMovement(true)
	end
	if viewButton then
		viewButton.SetColor(if viewMode == "Top" then "Sky" else "Grape")
	end
end

-- 배치 모드 밖: 내 공원 누르기 ---------------------------------------------------------
-- 버튼 없이 타이쿤처럼: 내 공원(부지 + 여유 LEAVE_MARGIN)에 있을 때 내 명소·빈 받침대를 톡 누르면 배치 모드
-- (명소 = 바로 집음, 빈 받침대 = 그 칸을 채울 준비). 톡 = 누른 곳에서 DRAG_PX 안에서 뗌 — 터치로 끌면 화면 돌리기라
-- 안 들어감, 두 번째 손가락이 닿으면 취소(두 손가락 확대). 광선은 캐릭터만 빼고 쏴서 처음 맞은 것이 내 칸 모델일 때만
-- (남의 공원·나무 뒤에 가린 명소는 아님). 잠긴 칸은 안 받음. 서버 ClickDetector 없이 이 클라이언트 입력만 봄.
-- 마우스로 가리키면 그 칸에 옅은 흰 강조(Highlight 하나) + 손가락 커서 — 누를 수 있다는 것이 보이게

type OutsidePress = { Input: InputObject, Kind: Enum.UserInputType, Start: Vector2, Slot: number, Moved: boolean }
local outsidePress: OutsidePress? = nil
local outsideFingers: { [InputObject]: boolean } = {} -- 3D 화면에 닿아 있는 손가락(화면 버튼·조이스틱 제외)
local outsideParams = RaycastParams.new()
outsideParams.FilterType = Enum.RaycastFilterType.Exclude
local outsideLight: Highlight? = nil
local outsideSlot: number? = nil -- 마우스가 가리키는 내 칸(강조 중)
local cursorSet = false -- 손가락 커서를 이 모듈이 켰는지(끌 때 남의 커서를 덮지 않게)

-- 지금 내 공원을 (at 에서) 눌러 배치 모드에 들어갈 수 있는지
local function canTap(at: Vector2?): boolean
	if editing or entering or not plot or not origin or not slotsFolder then
		return false
	end
	local allowed = handlers and handlers.CanTap
	if allowed and not allowed(at) then
		return false
	end
	return atPlot(LEAVE_MARGIN)
end

-- GuiObject 의 화면 네모(부모 네모 기준 Size·Position·AnchorPoint, 스케일 + 픽셀 — 이름표에는 UIScale·SizeConstraint 없음)
local function childRect(gui: GuiObject, parentAt: Vector2, parentSize: Vector2): (Vector2, Vector2)
	local size = Vector2.new(
		gui.Size.X.Scale * parentSize.X + gui.Size.X.Offset,
		gui.Size.Y.Scale * parentSize.Y + gui.Size.Y.Offset
	)
	local at = parentAt
		+ Vector2.new(
			gui.Position.X.Scale * parentSize.X + gui.Position.X.Offset,
			gui.Position.Y.Scale * parentSize.Y + gui.Position.Y.Offset
		)
		- gui.AnchorPoint * size
	return at, size
end

-- 화면 점이 GuiObject 들의 보이는 판에 닿는지(투명한 틀 Frame 은 속으로 — 이름표 Body·Head)
local function guiHits(parent: Instance, parentAt: Vector2, parentSize: Vector2, point: Vector2, depth: number): boolean
	for _, child in parent:GetChildren() do
		if child:IsA("GuiObject") and child.Visible then
			local at, size = childRect(child, parentAt, parentSize)
			if child:IsA("Frame") and child.BackgroundTransparency >= 1 and depth < 3 then
				if guiHits(child, at, size, point, depth + 1) then
					return true
				end
			elseif point.X >= at.X and point.X <= at.X + size.X and point.Y >= at.Y and point.Y <= at.Y + size.Y then
				return true
			end
		end
	end
	return false
end

-- 화면 점(뷰포트 px)이 이 칸 이름표(ParkService "Label": 스터드 + 픽셀 크기, 거리 단계로 Head 가 꺼지면 수입 알약만)의
-- 보이는 부분에 닿으면 카메라에서 이름표까지 거리
local function tagHit(container: Instance, point: Vector2, camera: Camera): number?
	local pedestal = container:FindFirstChild("Pedestal")
	if not pedestal or not pedestal:IsA("BasePart") then
		return nil
	end
	local eye = camera.CFrame.Position
	if (pedestal.Position - eye).Magnitude > 90 then
		return nil -- 이름표 MaxDistance(60) + 모형 높이 밖
	end
	local billboard = pedestal:FindFirstChild("Label", true)
	if not billboard or not billboard:IsA("BillboardGui") or not billboard.Enabled then
		return nil
	end
	local anchor = billboard.Adornee
	local world = if anchor
			and anchor:IsA("Attachment")
			and anchor.Parent
			and anchor.Parent:IsA("BasePart")
		then (anchor.Parent :: BasePart).CFrame:PointToWorldSpace(anchor.Position)
		elseif anchor and anchor:IsA("BasePart") then anchor.Position
		else nil
	if not world then
		return nil
	end
	local distance = (world - eye).Magnitude
	local screen = camera:WorldToViewportPoint(world)
	if distance > billboard.MaxDistance or screen.Z <= 0 then
		return nil
	end
	local perStud = camera.ViewportSize.Y / (2 * math.tan(math.rad(camera.FieldOfView) / 2) * screen.Z)
	local size = Vector2.new(
		billboard.Size.X.Scale * perStud + billboard.Size.X.Offset,
		billboard.Size.Y.Scale * perStud + billboard.Size.Y.Offset
	)
	local at = Vector2.new(screen.X, screen.Y) - size / 2
	return if guiHits(billboard, at, size, point, 0) then distance else nil
end

-- 화면 점(뷰포트 px)에서 처음 맞는 것이 내 열린 칸이면 그 칸 번호. 이름표는 광선에 안 맞으므로 먼저 봄: 내 칸 이름표가
-- 광선이 맞은 파트보다 가까우면 그 칸(가장 가까운 이름표) — 앞 명소 이름표 뒤로 보이는 뒷줄 명소를 집지 않게
local function tapSlot(at: Vector2): number?
	local camera = workspace.CurrentCamera
	local folder = slotsFolder
	if not camera or not folder then
		return nil
	end
	local ray = camera:ViewportPointToRay(at.X, at.Y)
	local character = player.Character
	outsideParams.FilterDescendantsInstances = if character then { character } else {}
	local hit = workspace:Raycast(ray.Origin, ray.Direction * RAY_LENGTH, outsideParams)
	local nearest = if hit then (hit.Position - ray.Origin).Magnitude else math.huge
	local tagged: Instance? = nil
	for _, candidate in containers do
		if candidate.Parent == folder then
			local distance = tagHit(candidate, at, camera)
			if distance and distance < nearest then
				tagged, nearest = candidate, distance
			end
		end
	end
	local container = tagged or (if hit then containerOf(hit.Instance) else nil)
	if not container or container.Parent ~= folder then
		return nil
	end
	local slot = slotOf(container)
	if not slot or container:GetAttribute("Look") == ParkGrid.LOOK_LOCKED then
		return nil
	end
	return slot
end

-- 가리키는 내 칸 강조 + 손가락 커서(nil = 끔)
local function setOutsideHover(slot: number?)
	local target = if slot then containers[slot] else nil
	if not target then
		slot = nil
	end
	if outsideSlot == slot and (not outsideLight or outsideLight.Adornee == target) then
		return
	end
	outsideSlot = slot
	local light = outsideLight
	if target and not light then
		light = Ui.new("Highlight", {
			Name = "ParkTapHover",
			FillColor = WHITE,
			FillTransparency = 0.86,
			OutlineColor = WHITE,
			OutlineTransparency = 0.25,
			DepthMode = Enum.HighlightDepthMode.Occluded,
			Enabled = false,
			Parent = workspace,
		})
		outsideLight = light
	end
	if light then
		light.Adornee = target
		light.Enabled = target ~= nil
	end
	local want = target ~= nil
	if want ~= cursorSet then
		cursorSet = want
		pcall(function()
			UserInputService.MouseIcon = if want then POINTING_HAND else ""
		end)
	end
end

local function outsideBegan(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	if kind == Enum.UserInputType.Touch then
		if processed then
			return -- 화면 버튼·조이스틱(그 손가락은 세지 않음 — 조이스틱으로 걸으며 다른 손가락으로 톡 누를 수 있음)
		end
		for other in outsideFingers do
			-- 뗌(InputEnded)을 못 받고 끝난 손가락은 뺌
			local state = (other :: any).UserInputState
			if state == Enum.UserInputState.End or state == Enum.UserInputState.Cancel then
				outsideFingers[other] = nil
			end
		end
		outsideFingers[input] = true
		if next(outsideFingers, next(outsideFingers)) ~= nil then
			outsidePress = nil -- 두 손가락 = 확대/돌리기
			return
		end
	elseif kind ~= Enum.UserInputType.MouseButton1 or processed then
		return
	end
	local at = if kind == Enum.UserInputType.Touch
		then toViewport(input.Position)
		else UserInputService:GetMouseLocation()
	if not canTap(at) then
		return
	end
	local slot = tapSlot(at)
	outsidePress = if slot then { Input = input, Kind = kind, Start = at, Slot = slot, Moved = false } else nil
end

local function outsideChanged(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	local current = outsidePress
	if kind == Enum.UserInputType.Touch then
		if current and current.Input == input and (toViewport(input.Position) - current.Start).Magnitude > DRAG_PX then
			current.Moved = true -- 끌기 = 화면 돌리기
		end
	elseif kind == Enum.UserInputType.MouseMovement then
		local at = UserInputService:GetMouseLocation()
		if current and current.Kind == Enum.UserInputType.MouseButton1 and (at - current.Start).Magnitude > DRAG_PX then
			current.Moved = true
		end
		-- 화면 버튼 위(processed)면 강조를 끔(버튼 뒤 명소가 빛나 보이지 않게)
		setOutsideHover(if not processed and canTap(at) then tapSlot(at) else nil)
	end
end

-- 마우스를 가만히 두고 걷거나 카메라가 돌아도 강조가 옛 칸에 남지 않게: 강조 중일 때만 가끔 다시 봄
local function refreshOutsideHover()
	if outsideSlot == nil then
		return
	end
	local at = UserInputService:GetMouseLocation()
	setOutsideHover(if canTap(at) then tapSlot(at) else nil)
end

local function outsideEnded(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	if kind == Enum.UserInputType.Touch then
		outsideFingers[input] = nil
	end
	local current = outsidePress
	if not current or current.Kind ~= kind or (kind == Enum.UserInputType.Touch and current.Input ~= input) then
		return
	end
	outsidePress = nil
	local at = if kind == Enum.UserInputType.Touch
		then toViewport(input.Position)
		else UserInputService:GetMouseLocation()
	if processed or current.Moved or (at - current.Start).Magnitude > DRAG_PX or not canTap(at) then
		return
	end
	if tapSlot(at) == current.Slot then
		setOutsideHover(nil)
		ParkEdit.enter(current.Slot)
	end
end

local function onContainerAdded(container: Instance)
	local slot = slotOf(container)
	if not slot then
		return
	end
	containers[slot] = container
	if editing then
		reconcile()
	end
end

local function onContainerRemoved(container: Instance)
	local slot = slotOf(container)
	if slot and containers[slot] == container then
		containers[slot] = nil
	end
	hidden[container] = nil
	if outsideSlot == slot then
		setOutsideHover(nil)
	end
	if editing then
		if hoverSlot == slot then
			setHover(nil, HOVER_COLOR)
		end
		reconcile()
	end
end

-- 부지 Origin 속성(없는 옛 서버면 바닥 파트에서 셈)
local function readOrigin(model: Instance): CFrame?
	local value = model:GetAttribute("Origin")
	if typeof(value) == "CFrame" then
		return value
	end
	local base = model:FindFirstChild("Base")
	if base and base:IsA("BasePart") then
		return base.CFrame * CFrame.new(0, -base.Size.Y / 2, 0)
	end
	return nil
end

-- 아래 띠 --------------------------------------------------------------------------

-- 초당 수입 짧게: "1.8", "12.5K"
local function incomeText(income: number): string
	if income < 100 then
		local text = string.format("%.1f", math.floor(income * 10) / 10):gsub("%.0$", "")
		return text
	end
	return Format.short(income)
end

function paintAuto()
	local view = viewState()
	if not view or not autoButton then
		return
	end
	local on = view.Settings.AutoPark ~= false
	local confirming = not on and os.clock() < confirmUntil
	autoButton.SetColor(if on then "Grass" elseif confirming then "Sun" else "Gray")
	autoButton.SetText(if confirming then "확인?" else "자동")
	autoBadge.Root.Visible = on
end

-- 보이는 카드(좌우 한 장 여유)만 3D 사진(ViewportFrame)을 만듦. 한 번 만든 사진은 그대로
local function loadThumbs()
	if not editing then
		return
	end
	local k = math.max(0.01, Ui.scale())
	local left = scroller.CanvasPosition.X / k
	local width = scroller.AbsoluteWindowSize.X / k
	if width <= 1 then
		width = BAR_MAX_WIDTH
	end
	for _, card in cards do
		if not card.Thumb and card.X + CARD.X >= left - CARD.X and card.X <= left + width + CARD.X then
			card.Thumb = Viewport.thumbnail(card.Photo, card.Landmark, {
				Position = UDim2.fromOffset(2, 2),
				Size = UDim2.new(1, -4, 1, -4),
			})
		end
	end
end

-- 보관함 카드: 사진(등급 색 바탕) + 별 + (더 좋은 명소면) 오른쪽 위 노란 위 화살표 딱지. 누르면 집음
local function newCard(landmark: Landmark): Card
	local button = Ui.new("TextButton", {
		Name = landmark.Id,
		Text = "",
		AutoButtonColor = false,
		Size = UDim2.fromOffset(CARD.X, CARD.Y),
		BackgroundColor3 = Theme.Paper,
	})
	Ui.corner(12).Parent = button
	local stroke = Ui.stroke(Theme.Ink, 3)
	stroke.Parent = button
	local scale = Ui.new("UIScale", { Parent = button })
	local photo = Ui.new("Frame", {
		Name = "Photo",
		Position = UDim2.fromOffset(5, 5),
		Size = UDim2.new(1, -10, 0, CARD.Y - 34),
		BackgroundColor3 = landmark.Tier.Color:Lerp(WHITE, 0.62),
		Parent = button,
	})
	Ui.corner(8).Parent = photo
	Ui.stroke(Theme.Ink, 2).Parent = photo
	local stars = Ui.label({
		Name = "Stars",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -4),
		Size = UDim2.new(1, -8, 0, 22),
		Parent = button,
	}, 19)
	Ui.outline(stars, 2)
	local better = Ui.chip({
		Name = "Better",
		Color = "Sun",
		Icon = "arrow_up",
		IconOnly = true,
		IconSize = 30,
		Height = 24,
		StrokeThickness = 2,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -8, 0, 6),
		Rotation = 8,
		ZIndex = 4,
		Visible = false,
		Parent = button,
	})
	button.MouseEnter:Connect(function()
		if not (held and held.Id == landmark.Id) then
			scale.Scale = 1.05
		end
	end)
	button.MouseLeave:Connect(function()
		if not (held and held.Id == landmark.Id) then
			scale.Scale = 1
		end
	end)
	button.Activated:Connect(function()
		if held and held.Id == landmark.Id then
			returnHeld() -- 같은 카드를 다시 누름 = 내려놓기
		elseif not fillWith(landmark.Id) then
			pickUp(landmark.Id, 0)
		end
	end)
	button.Parent = scroller
	return {
		Button = button,
		Stroke = stroke,
		Scale = scale,
		Photo = photo,
		Thumb = nil,
		Stars = stars,
		Better = better,
		Landmark = landmark,
		X = 0,
	}
end

function renderBar()
	local view = viewState()
	if not editing or not view then
		return
	end
	local slots, unlocked = PlayerState.parkSlots(view)
	local shown = 0
	for slot = 1, unlocked do
		if slots[slot] then
			shown += 1
		end
	end
	countChip.Label.Text = string.format("%d/%d", shown, unlocked)
	incomeChip.Label.Text = "+" .. incomeText(PlayerState.incomePerSecond(view, view)) .. "/s"
	paintAuto()
	local heldShown = held ~= nil and ParkGrid.slotOf(view, held.Id) > 0
	storeButton.SetColor(if heldShown then "Coral" else "Gray")

	-- 보관함: 전시 안 된 명소(희귀한 순서). 더 좋은 명소(전시 칸의 가장 약한 명소보다 수입이 큼)는 노란 딱지
	local better: { [string]: boolean } = {}
	for _, id in PlayerState.betterHidden(view) do
		better[id] = true
	end
	local list = ParkGrid.storage(view)
	-- 들고 있는 보관함 명소는 카드 자리를 그대로 둠(눌러서 다시 내려놓을 수 있게)
	if held and not table.find(list, held.Id) and ParkGrid.slotOf(view, held.Id) == 0 then
		table.insert(list, held.Id)
	end
	local keep: { [string]: boolean } = {}
	for index, id in list do
		keep[id] = true
		local card = cards[id]
		local landmark = Landmarks.ById[id]
		if not card and landmark then
			card = newCard(landmark)
			cards[id] = card
		end
		if card then
			card.X = (index - 1) * (CARD.X + CARD_GAP)
			card.Button.LayoutOrder = index
			local picked = held ~= nil and held.Id == id
			card.Button.BackgroundColor3 = if picked then FEATURED_BG else Theme.Paper
			card.Stroke.Color = if picked then Ui.colorPair("Sun").Face else Theme.Ink
			card.Stroke.Thickness = if picked then 4 else 3
			card.Scale.Scale = if picked then 1.08 else 1
			card.Stars.Text = Ui.starsRich(PlayerState.stars(view.Inventory[id] or 0), PlayerState.MAX_STARS)
			card.Better.Root.Visible = better[id] == true
		end
	end
	for id, card in cards do
		if not keep[id] then
			card.Button:Destroy()
			cards[id] = nil
		end
	end
	scroller.CanvasSize = UDim2.fromOffset(math.max(0, #list * (CARD.X + CARD_GAP) - CARD_GAP + BAR_PAD * 2), 0)
	emptyHint.Visible = #list == 0
	loadThumbs()
	task.defer(loadThumbs) -- 처음 보이는 프레임에는 스크롤 영역 크기가 아직 0 일 수 있음
end

-- 띠 자리: 아래 가운데(배치 모드 동안 HUD 왼쪽 메뉴·굴리기 줄은 숨김). 터치 전용 기기는 오른쪽 아래 점프 버튼 자리를
-- 비움([시점] 으로 평소 카메라를 쓰면 이동 조이스틱·점프 버튼이 다시 나옴). 자리가 바뀌면 위에서 보기 카메라도 다시 맞춤
local function layoutBar()
	if not bar then
		return
	end
	local size = gui.AbsoluteSize
	if size.X <= 0 or size.Y <= 0 then
		return
	end
	local scale = Ui.scale()
	local left, right = BAR_EDGE, size.X - BAR_EDGE
	if Ui.touchOnly() then
		right -= if math.min(size.X, size.Y) <= 500 then BAR_JUMP.Small else BAR_JUMP.Large
	end
	local width = math.clamp(right - left, 200, BAR_MAX_WIDTH * scale)
	local center = math.clamp(size.X / 2, left + width / 2, right - width / 2)
	bar.Position = UDim2.fromOffset(center, size.Y - BAR_BOTTOM)
	bar.Size = UDim2.fromOffset(width / scale, BAR_HEIGHT)
	barTop = size.Y - BAR_BOTTOM - (BAR_HEIGHT + CHIP_ROW) * scale
	loadThumbs()
	-- 위에서 보기 중이면(들어갈 때 날아가는 중이 아니고, 카메라를 이미 넘겨받았을 때만) 새 띠 자리에 맞춰 카메라도 다시
	local camera = workspace.CurrentCamera
	if
		editing
		and viewMode == "Top"
		and origin
		and camera
		and not cameraTween
		and camera.CameraType == Enum.CameraType.Scriptable
	then
		camera.CFrame = ParkEdit.topCFrame()
	end
end

local function barButton(name: string, icon: string, text: string, color: string, x: number, anchorRight: boolean)
	return Ui.chunkyButton({
		Name = name,
		AnchorPoint = Vector2.new(if anchorRight then 1 else 0, 0.5),
		Position = if anchorRight then UDim2.new(1, -x, 0.5, 0) else UDim2.new(0, x, 0.5, 0),
		Size = UDim2.fromOffset(BUTTON.X, BUTTON.Y),
		Color = color,
		Icon = icon,
		IconSize = 54,
		Vertical = true,
		Text = text,
		TextSize = 20,
		ZIndex = 3,
		Parent = tray,
	})
end

local function buildBar()
	bar = Ui.new("Frame", {
		Name = "ParkEditBar",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -BAR_BOTTOM),
		Size = UDim2.fromOffset(BAR_MAX_WIDTH, BAR_HEIGHT),
		BackgroundTransparency = 1,
		ZIndex = 3,
		Visible = false,
		Parent = gui,
	})
	Ui.autoScale(bar)

	-- 크림 쟁반(창과 같은 바탕·테두리). 빈 곳을 누르면(또는 끌어 온 명소를 놓으면) 보관
	tray = Ui.new("TextButton", {
		Name = "Tray",
		Text = "",
		AutoButtonColor = false,
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Theme.Cream,
		ZIndex = 1,
		Parent = bar,
	})
	Ui.corner(18).Parent = tray
	Ui.stroke(Theme.Ink, 4).Parent = tray
	Ui.skin(tray, "panel_paper", { Radius = 18, Height = BAR_HEIGHT, CenterColor = Theme.Cream })
	tray.Activated:Connect(function()
		if held then
			storeHeld()
		end
	end)

	-- 왼쪽: [보관] [자동]
	storeButton = barButton("Store", "crate", "보관", "Gray", BAR_PAD, false)
	storeButton.Activated:Connect(storeHeld)
	autoButton = barButton("AutoPark", "podium", "자동", "Gray", BAR_PAD + BUTTON.X + BUTTON_GAP, false)
	autoButton.Activated:Connect(toggleAuto)
	autoBadge = Ui.chip({
		Name = "On",
		Color = "Coral",
		Text = "ON",
		Height = 22,
		TextSize = 15,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -8, 0, 2),
		Rotation = 12,
		ZIndex = 6,
		Visible = false,
		Parent = autoButton.Face,
	})

	-- 오른쪽: [시점] [완료]
	doneButton = barButton("Done", "check", "완료", "Grass", BAR_PAD, true)
	doneButton.Activated:Connect(function()
		ParkEdit.exit()
	end)
	viewButton = barButton("View", "camera", "시점", "Sky", BAR_PAD + BUTTON.X + BUTTON_GAP, true)
	viewButton.Activated:Connect(function()
		viewMode = if viewMode == "Top" then "Follow" else "Top"
		applyView()
	end)

	-- 가운데: 보관함 카드(가로 스크롤)
	local side = BAR_PAD + 2 * (BUTTON.X + BUTTON_GAP) + 4
	scroller = Ui.new("ScrollingFrame", {
		Name = "Storage",
		Position = UDim2.fromOffset(side, 4),
		Size = UDim2.new(1, -side * 2, 1, -8),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 6,
		ScrollBarImageColor3 = Theme.Ink,
		ScrollBarImageTransparency = 0.4,
		ScrollingDirection = Enum.ScrollingDirection.X,
		CanvasSize = UDim2.new(),
		ElasticBehavior = Enum.ElasticBehavior.Always,
		ZIndex = 2,
		Parent = tray,
	})
	Ui.new("UIPadding", {
		PaddingLeft = UDim.new(0, BAR_PAD),
		PaddingRight = UDim.new(0, BAR_PAD),
		Parent = scroller,
	})
	Ui.list(Enum.FillDirection.Horizontal, CARD_GAP).Parent = scroller
	scroller:GetPropertyChangedSignal("CanvasPosition"):Connect(loadThumbs)
	scroller:GetPropertyChangedSignal("AbsoluteWindowSize"):Connect(loadThumbs)

	-- 보관함이 비었을 때: 천천히 도는 지구본 + 작은 "굴리기" 딱지(도감과 같은 지구본)
	emptyHint = Ui.new("Frame", {
		Name = "Empty",
		Position = UDim2.fromOffset(side, 0),
		Size = UDim2.new(1, -side * 2, 1, 0),
		BackgroundTransparency = 1,
		ZIndex = 2,
		Visible = false,
		Parent = tray,
	})
	Icons.view(emptyHint, "globe", {
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(0.5, -4, 0.5, 0),
		Size = UDim2.fromOffset(78, 78),
		Spin = 40,
		Transparency = 0.2,
		ZIndex = 3,
	})
	Ui.chip({
		Name = "Roll",
		Color = "Grass",
		Text = "굴리기",
		Height = 32,
		TextSize = 20,
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0.5, 4, 0.5, 0),
		ZIndex = 3,
		Parent = emptyHint,
	})

	-- 쟁반 위 테두리에 걸친 딱지: [공원 전시 수/열린 칸] [동전 +X/s]
	local chips = Ui.new("Frame", {
		Name = "Chips",
		Position = UDim2.fromOffset(side + 6, -CHIP_ROW + 8),
		Size = UDim2.new(1, -(side + 6) * 2, 0, CHIP_ROW),
		BackgroundTransparency = 1,
		ZIndex = 4,
		Parent = bar,
	})
	Ui.list(Enum.FillDirection.Horizontal, 10).Parent = chips
	countChip = Ui.chip({
		Name = "Shown",
		Color = Theme.Ink,
		Icon = "park",
		IconSize = 38,
		Height = 30,
		TextSize = 19,
		LayoutOrder = 1,
		ZIndex = 4,
		Parent = chips,
	})
	incomeChip = Ui.chip({
		Name = "Income",
		Color = "Grass",
		Icon = "coin",
		IconSize = 38,
		Height = 30,
		TextSize = 19,
		LayoutOrder = 2,
		ZIndex = 4,
		Parent = chips,
	})

	-- 화면 이름표(띠보다 아래 층): setTag 가 자리·내용을 정함
	tag = Ui.new("Frame", {
		Name = "ParkEditTag",
		AnchorPoint = Vector2.new(0.5, 1),
		Size = UDim2.fromOffset(TAG.X, TAG.Y),
		BackgroundTransparency = 1,
		ZIndex = 2,
		Visible = false,
		Parent = gui,
	})
	Ui.autoScale(tag)
	tagStars = Ui.label({
		Name = "Stars",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 32),
		Size = UDim2.fromOffset(140, 24),
		ZIndex = 2,
		Parent = tag,
	}, 20)
	Ui.outline(tagStars, 2)

	gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(layoutBar)
	Ui.onRescale(function()
		layoutBar()
	end)
end

-- 들어가기 · 나가기 ------------------------------------------------------------------

local function connectEdit(signal: RBXScriptSignal, callback: (...any) -> ())
	table.insert(editConnections, signal:Connect(callback))
end

-- 들어오게 한 칸(배치 모드 밖에서 누른 칸): 명소면 바로 집고, 빈 받침대면 그 칸을 채울 준비
local function pressSlot(slot: number)
	local look = viewLook(slot)
	if look and Landmarks.ById[look] then
		pickUp(look, slot)
	elseif look == ParkGrid.LOOK_EMPTY then
		setFill(slot)
	end
end

local function begin(slot: number?)
	if editing or not origin or not plot then
		return
	end
	editing = true
	editToken += 1
	local token = editToken
	viewMode = "Top"
	zoom = 1
	press, rightStart, pointer = nil, nil, nil
	table.clear(touches)
	pinch = nil
	rayDirty = true
	pointerKind = if UserInputService.MouseEnabled and not Ui.touchOnly() then "Mouse" else nil

	-- 이 화면에서만 있는 것: 칸마다 빛나는 판(받침대 둘레로 삐져나옴) + 가리키는 칸 강조
	local folder = Instance.new("Folder")
	folder.Name = "ParkEditLocal"
	localFolder = folder
	for index = 1, PlayerState.MAX_SLOTS do
		local x, z = ParkGrid.slotOffset(index)
		local marker = Instance.new("Part")
		marker.Name = "Mark" .. index
		marker.Anchored = true
		marker.CanCollide = false
		marker.CanQuery = false
		marker.CanTouch = false
		marker.CastShadow = false
		marker.Material = Enum.Material.Neon
		marker.Size = Vector3.new(MARKER_SIZE, 0.1, MARKER_SIZE)
		marker.CFrame = (origin :: CFrame) * CFrame.new(x, ParkGrid.BASE_TOP + 0.06, z)
		marker.Transparency = 1
		marker.Parent = folder
		markers[index] = marker
	end
	hoverLight = Ui.new("Highlight", {
		Name = "Hover",
		FillTransparency = 0.82,
		OutlineTransparency = 0,
		DepthMode = Enum.HighlightDepthMode.Occluded,
		Enabled = false,
		Parent = folder,
	})
	folder.Parent = workspace
	hideSign(true)

	outsidePress = nil
	setOutsideHover(nil)
	-- HUD 를 먼저 바꾸고(메뉴·굴리기 줄 숨김, 열린 창 닫기) 띠 자리를 잡은 뒤에 카메라(띠 위 영역에 맞춤)
	handlers.Changed(true)
	bar.Visible = true
	layoutBar()
	scroller.CanvasPosition = Vector2.zero
	local camera = workspace.CurrentCamera
	if camera then
		savedCamera = { Type = camera.CameraType, Subject = camera.CameraSubject, Fov = camera.FieldOfView }
	end
	applyView()

	connectEdit(UserInputService.InputBegan, onInputBegan)
	connectEdit(UserInputService.InputChanged, onInputChanged)
	connectEdit(UserInputService.InputEnded, onInputEnded)
	connectEdit(RunService.RenderStepped, step)
	local character = player.Character
	local body = character and character:FindFirstChildOfClass("Humanoid")
	if body then
		connectEdit(body.Died, function()
			ParkEdit.exit()
		end)
	end

	renderBar()
	reconcile()
	if slot then
		pressSlot(slot)
	end

	-- 부지 밖으로 걸어가거나 순간 이동하면 끝
	task.spawn(function()
		while editing and token == editToken do
			if not atPlot(LEAVE_MARGIN) then
				ParkEdit.exit()
				break
			end
			task.wait(0.3)
		end
	end)
end

-- 배치 모드 켜기. slot: 내 공원의 칸을 눌러 들어왔으면 그 칸 명소를 바로 집음(빈 받침대면 그 칸을 채울 준비).
-- 내 공원 밖이면 먼저 순간 이동
function ParkEdit.enter(slot: number?)
	if editing then
		if slot then
			pressSlot(slot)
		end
		return
	end
	if entering then
		return
	end
	if not plot or not origin then
		handlers.Toast("공원 없음", "park")
		return
	end
	if not lastState then
		handlers.Toast("로딩 중", "globe")
		return
	end
	entering = true
	entryToken += 1
	local token = entryToken
	task.spawn(function()
		if not atPlot(LEAVE_MARGIN) then
			local ok = handlers.GoToPark()
			if token ~= entryToken then
				return
			end
			if not ok then
				entering = false
				return
			end
			-- 순간 이동이 이 화면에 보일 때까지 잠깐 기다림
			local deadline = os.clock() + 2
			while not atPlot(LEAVE_MARGIN) and os.clock() < deadline do
				task.wait(0.05)
			end
			if token ~= entryToken then
				return
			end
		end
		entering = false
		begin(slot)
	end)
end

-- 배치 모드 끄기: 들고 있던 것 내려놓기(연출 없이), 로컬 모형·강조·연결 정리, 숨긴 명소 되돌리기, 카메라·이동 되돌리기
function ParkEdit.exit()
	entryToken += 1
	entering = false
	if not editing then
		return
	end
	editing = false
	editToken += 1
	returnHeld(true)
	disconnectAll(editConnections)
	for _, flyer in flyers do
		flyer.Rig.Model:Destroy()
	end
	table.clear(flyers)
	for _, proxy in proxies do
		proxy.Model:Destroy()
	end
	table.clear(proxies)
	for container in hidden do
		if container.Parent then
			applyHidden(container, false)
		end
	end
	table.clear(hidden)
	paintLabels() -- 배치 모드 밖: 칸 이름표 모두 다시 켬
	hideSign(false)
	table.clear(localEdits)
	table.clear(markers)
	markerPulse = nil
	painted = nil
	hoverLight = nil
	hoverSlot = nil
	fillSlot = nil
	local folder = localFolder
	localFolder = nil
	if folder then
		folder:Destroy()
	end
	press, rightStart, pointer = nil, nil, nil
	table.clear(touches)
	pinch = nil
	rayDirty = true
	table.clear(rayList)
	confirmUntil = 0
	confirmToken += 1

	stopCameraTween()
	local camera = workspace.CurrentCamera
	local saved = savedCamera
	savedCamera = nil
	if camera then
		camera.CameraType = if saved and saved.Type ~= Enum.CameraType.Scriptable
			then saved.Type
			else Enum.CameraType.Custom
		camera.CameraSubject = humanoid() or (saved and saved.Subject) or nil
		if saved then
			camera.FieldOfView = saved.Fov
		end
	end
	setMovement(true)

	bar.Visible = false
	tag.Visible = false
	tagKey = nil
	if tagChip then
		tagChip.Root:Destroy()
		tagChip = nil
	end
	handlers.Changed(false)
end

function ParkEdit.isEditing(): boolean
	return editing
end

-- 화면 이름표가 붙은 월드 점(이름표 아래 끝, 화면 밖으로 안 나가게 가두기 전). 이름표가 없으면 nil — 스모크 테스트용
function ParkEdit.tagAnchor(): Vector3?
	return tagAnchor
end

-- 채울 빈 칸(빈 받침대를 눌러 정함, 없으면 nil) — 스모크 테스트용
function ParkEdit.fillTarget(): number?
	return fillSlot
end

-- 서버 상태가 바뀜(applyState). 들고 있던 명소를 더는 갖고 있지 않으면(환생) 내려놓음
function ParkEdit.render(state: Snapshot?)
	lastState = state
	local current = held
	if current and (not state or (state.Inventory[current.Id] or 0) <= 0) then
		returnHeld(true)
	end
	if editing then
		reconcile()
		renderBar()
		-- 공원 확장으로 열린 줄이 바뀌면 위에서 보기를 다시 맞춤
		if viewMode == "Top" and not cameraTween and wantRows() ~= fitRows then
			applyView()
		end
	end
end

-- 내 부지(workspace.Parks 의 OwnerUserId = 내 UserId 인 부지 모델, 없으면 nil)
function ParkEdit.setPlot(model: Instance?)
	if model == plot then
		return
	end
	ParkEdit.exit()
	disconnectAll(plotConnections)
	outsidePress = nil
	setOutsideHover(nil)
	table.clear(containers)
	plot = model
	origin = nil
	slotsFolder = nil
	if not model then
		return
	end
	origin = readOrigin(model)
	table.insert(
		plotConnections,
		model:GetAttributeChangedSignal("Origin"):Connect(function()
			origin = readOrigin(model)
		end)
	)
	task.spawn(function()
		local folder = model:FindFirstChild("Slots") or model:WaitForChild("Slots", 30)
		if plot ~= model or not folder then
			return
		end
		slotsFolder = folder
		origin = origin or readOrigin(model)
		table.insert(plotConnections, folder.ChildAdded:Connect(onContainerAdded))
		table.insert(plotConnections, folder.ChildRemoved:Connect(onContainerRemoved))
		for _, container in folder:GetChildren() do
			onContainerAdded(container)
		end
	end)
end

function ParkEdit.init(parent: ScreenGui, callbacks: Handlers)
	gui = parent
	handlers = callbacks
	-- 글자 칸(채팅 등)에 쓰는 중인지: 배치 모드 밖에서 포커스를 얻었어도 알도록 늘 지켜봄
	pcall(function()
		UserInputService.TextBoxFocused:Connect(function()
			textFocused = true
		end)
		UserInputService.TextBoxFocusReleased:Connect(function()
			textFocused = false
			textReleasedAt = os.clock()
		end)
	end)
	pickSound = makeSound(1.35, 0.3)
	dropSound = makeSound(0.9, 0.45)
	cancelSound = makeSound(0.65, 0.3)
	buildBar()
	-- 배치 모드 밖: 내 공원의 명소·빈 받침대를 톡 누르면 들어감(늘 지켜보지만 내 공원에 없으면 바로 돌아감 — 광선도 안 쏨)
	UserInputService.InputBegan:Connect(outsideBegan)
	UserInputService.InputChanged:Connect(outsideChanged)
	UserInputService.InputEnded:Connect(outsideEnded)
	task.spawn(function()
		while true do
			task.wait(0.2)
			refreshOutsideHover()
		end
	end)
end

return ParkEdit
