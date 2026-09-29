-- 3D 공원 배치 모드: 놀이공원 시뮬레이션처럼 메뉴 창 없이 내 공원에서 명소를 직접 눌러 집고, 다른 받침대를 눌러 놓음.
-- (DESIGN.md "공원 배치" — 규칙·계획은 Shared/ParkGrid, 편집 규칙은 PlayerState.setDisplay, 서버 상태가 진실)
--
-- 들어가기: HUD [배치] · 도감 [배치] 버튼(내 공원 밖이면 먼저 내 공원으로 순간 이동), 또는 배치 모드 밖에서 내 공원의
--   받침대·명소를 누름(이 클라이언트만의 ClickDetector — 명소면 들어가면서 바로 집음).
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
--   [보관] = 들고 있는 전시 명소를 보관함으로, [자동] = 자동 배치, [시점], [완료] = 나가기.
-- 누르는 즉시 PlayerState 규칙을 스냅샷 사본에 적용해 미리 보여 주고(preview), 옮긴 칸에는 이 화면에서만 보이는
--   모형(proxy)을 두었다가 서버가 칸을 다시 만들면(칸 모델 Look 속성이 맞으면) 치움. 실패·stale 이면 서버 상태로 되돌림.
-- 알림: 배치 편집이 받아들여져 자동 배치가 꺼지면(이번 접속 처음) "자동 꺼짐". "공원 바뀜"(stale)·"공원 꽉 참"은 init 이 띄움.
-- 정리: 나가면(완료, 다른 창 열기, 부지 밖으로 걸어가거나 순간 이동, 죽음·캐릭터 사라짐, 부지 잃음) 이 모듈이 만든
--   연결·모형·강조를 모두 지우고 숨긴 명소를 되돌림. 서버가 칸 모델을 다시 만들면(ChildAdded/Removed) 그때그때 맞춤.
-- 키보드: Esc · Q = 내려놓기(들고 있지 않으면 나가기), Backspace · Delete = 보관. 오른쪽 클릭 = 내려놓기.
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
}

-- 월드 ----------------------------------------------------------------------------
local LIFT = 3.4 -- 들고 있는 명소가 받침대 위로 뜨는 높이(스터드)
local BOB = 0.45 -- 오르내림 폭
local BOB_SPEED = 3.2 -- 오르내림 빠르기(라디안/초)
local SPIN_SPEED = math.rad(55) -- 들고 있는 명소가 도는 빠르기
local FOLLOW = 16 -- 가리키는 곳을 따라가는 빠르기(1/초, 클수록 바로 붙음)
local GHOST_FADE = 0.38 -- 들고 있는 복사본의 투명도(원래 투명도에서 이만큼 더 비침)
local FLY_SECONDS = 0.3 -- 놓기·되돌아가기·자리 바꿈 폴짝
local HOP = 4 -- 자리 바꿈 상대가 폴짝 뛰는 높이
local EDIT_HOLD = 3 -- 옮긴 칸의 로컬 모형(proxy)을 서버 칸이 맞을 때까지 기다리는 최대 시간(초)
local DRAG_PX = 10 -- 이보다 많이 움직이면 끌기(터치: 따라가는 시점에서는 화면 돌리기)
local LEAVE_MARGIN = 14 -- 부지 밖으로 이만큼 나가면 배치 모드 끝(스터드)
local CLICK_DISTANCE = 40 -- 배치 모드 밖에서 내 받침대를 눌러 들어오는 거리
local RAY_LENGTH = 1000
local MARKER_SIZE = ParkGrid.PEDESTAL_SIZE + 1.6 -- 받침대 둘레로 삐져나와 빛나는 판
local HOVER_COLOR = Color3.new(1, 1, 1)

-- 위에서 보기(ParkGrid.topView): 화면 위쪽 상단바 아래 여백, 옆 여백(비율). 휠 배율(1 = 맞출 줄이 딱 맞음)
local TOP_MARGIN = 10 -- px
local SIDE_MARGIN = 0.03
local BAR_CLEAR = 8 -- 아래 띠 위로 띄울 거리(px)
local ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.8, 1.45, 0.08
local CAMERA_TWEEN = TweenInfo.new(0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)

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
local markerPulse: { BasePart } = {} -- 들고 있을 때 숨 쉬듯 빛나는 판(놓을 수 있는 칸)
local hoverLight: Highlight? = nil
local hoverSlot: number? = nil
local viewMode = "Top" -- "Top"(위에서 보기) | "Follow"(평소 카메라)
local zoom = 1
local fitRows = Config.PARK_GRID -- 위에서 보기가 맞춘 줄 수(ParkGrid.topRows: 열린 줄 + 잠긴 줄 하나)
local savedCamera: { Type: Enum.CameraType, Subject: Instance? }? = nil
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
	Label: BillboardGui,
}
type Held = {
	Id: string,
	Ghost: Ghost,
	Position: Vector3, -- 받침대 윗면 기준 지금 자리(부드럽게 따라감)
	Target: Vector3,
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

-- 월드 칸 모델의 명소(과 이름표)를 이 화면에서만 숨기기/되돌리기. 받침대는 그대로
local function applyHidden(container: Instance, hide: boolean)
	for _, child in container:GetChildren() do
		if child:IsA("Model") then
			for _, descendant in child:GetDescendants() do
				if descendant:IsA("BasePart") or descendant:IsA("Decal") then
					descendant.LocalTransparencyModifier = if hide then 1 else 0
				end
			end
		elseif child:IsA("BasePart") then
			for _, descendant in child:GetDescendants() do
				if descendant:IsA("BillboardGui") then
					descendant.Enabled = not hide
				end
			end
		end
	end
end

local function setHidden(container: Instance, hide: boolean)
	if (hidden[container] == true) == hide then
		return
	end
	hidden[container] = if hide then true else nil
	applyHidden(container, hide)
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

-- 들고 있는 반투명 복사본: 노란 강조 + 머리 위 이름표(이름 + 별)
local function makeGhost(landmark: Landmark, stars: number): Ghost?
	local model = localModel(landmark)
	if not model then
		return nil
	end
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
		FillTransparency = 0.7,
		OutlineColor = WHITE,
		OutlineTransparency = 0,
		DepthMode = Enum.HighlightDepthMode.AlwaysOnTop,
		Parent = model,
	})
	local height = 6
	pcall(function()
		height = model:GetExtentsSize().Y
	end)
	local anchorPart = model.PrimaryPart or model:FindFirstChildWhichIsA("BasePart", true)
	-- 이름표는 화면 px 고정이라 작은 화면(자동 배율 0.55)에서는 줄임
	local labelScale = math.clamp(Ui.scale() / 0.9, 0.6, 1)
	local label = Ui.new("BillboardGui", {
		Name = "HeldLabel",
		Adornee = anchorPart,
		Size = UDim2.fromOffset(240 * labelScale, 58 * labelScale),
		StudsOffsetWorldSpace = Vector3.new(0, height + 1.6, 0),
		AlwaysOnTop = true,
		LightInfluence = 0,
		ResetOnSpawn = false,
		Parent = model,
	})
	local tier = landmark.Tier.Color
	local name = Ui.chip({
		Name = "Name",
		Color = tier,
		Text = landmark.Name,
		Height = 30,
		TextSize = 19,
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.fromScale(0.5, 0),
		Parent = label,
	})
	name.Label.TextColor3 = WHITE
	local starLabel = Ui.label({
		Name = "Stars",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 32),
		Size = UDim2.fromOffset(140, 24),
		Text = Ui.starsRich(stars, #Config.STAR_THRESHOLDS),
		Parent = label,
	}, 20)
	Ui.outline(starLabel, 2)
	Ui.new("UIScale", { Scale = labelScale, Parent = label })
	return { Model = model, Rig = rig(model), Originals = originals, Light = light, Label = label }
end

-- 들고 있던 복사본을 원래 모습(불투명)으로: 받침대에 내려앉을 때
local function solidify(ghost: Ghost): Rig
	for part, transparency in ghost.Originals do
		part.Transparency = transparency
	end
	ghost.Light:Destroy()
	ghost.Label:Destroy()
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

-- 빛나는 판(놓을 자리) 칠하기
local function paintMarkers(slots: { [number]: string }, unlocked: number, heldFrom: number)
	table.clear(markerPulse)
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
				-- 놓을 수 있는 칸: 빈 칸은 초록, 명소가 있으면(자리 바꿈) 노랑. 숨 쉬듯 빛남(step)
				color, transparency = if id then Ui.colorPair("Sun").Face else Ui.colorPair("Grass").Face, 0.4
				table.insert(markerPulse, marker)
			end
		elseif not locked and not id then
			color, transparency = Ui.colorPair("Grass").Face, 0.62 -- 빈 칸
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
	paintMarkers(slots, unlocked, heldFrom)
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

-- 명소 집기. from: 전시 칸(0 = 보관함). 이미 들고 있으면 그것은 제자리로
local function pickUp(id: string, from: number)
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
	local ghost = makeGhost(landmark, PlayerState.stars(view.Inventory[id] or 0))
	if not ghost then
		return
	end
	-- 처음 자리: 전시 칸이면 그 받침대 위, 보관함이면 첫 빈 칸(없으면 부지 가운데) 위 — 가리키면 그리로 감
	local start: Vector3
	if from > 0 then
		start = slotTop(from).Position
	else
		local slots, unlocked = PlayerState.parkSlots(view)
		start = (origin :: CFrame):PointToWorldSpace(Vector3.new(0, ParkGrid.BASE_TOP, 0))
		for slot = 1, unlocked do
			if not slots[slot] then
				start = slotTop(slot).Position
				break
			end
		end
	end
	moveRig(ghost.Rig, CFrame.new(start + Vector3.new(0, LIFT, 0)) * plotRotation())
	ghost.Model.Parent = localFolder
	held = { Id = id, Ghost = ghost, Position = start, Target = start, Angle = 0 }
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

-- 화면 한 점이 가리키는 칸: 먼저 내 부지 칸 모델(받침대·명소)에 광선을 쏘고, 안 맞으면 부지 바닥 높이 평면과
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
		rayParams.FilterDescendantsInstances = { folder }
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

local function onInputBegan(input: InputObject, processed: boolean)
	local kind = input.UserInputType
	if kind == Enum.UserInputType.Keyboard then
		local key = input.KeyCode
		if key == Enum.KeyCode.Escape then
			cancelOrExit() -- Esc 는 로블록스 메뉴가 먼저 가져갈 수 있어서 Q 도 같은 동작
		elseif processed then
			return -- 채팅 입력 중
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
	if kind == Enum.UserInputType.MouseButton1 or kind == Enum.UserInputType.Touch then
		pointerKind = if kind == Enum.UserInputType.Touch then "Touch" else "Mouse"
		local at = if kind == Enum.UserInputType.Touch
			then toViewport(input.Position)
			else UserInputService:GetMouseLocation()
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
		zoom = math.clamp(zoom - input.Position.Z * ZOOM_STEP, ZOOM_MIN, ZOOM_MAX)
		local camera = workspace.CurrentCamera
		if camera and not cameraTween then
			camera.CFrame = ParkEdit.topCFrame()
		end
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
		end
	end
end

-- 매 프레임 ------------------------------------------------------------------------

local function setHover(slot: number?, color: Color3)
	local light = hoverLight
	if not light then
		return
	end
	local target: Instance? = nil
	if slot then
		local proxy = proxies[slot]
		target = if proxy then proxy.Model else containers[slot]
	end
	hoverSlot = slot
	if light.Adornee ~= target then
		light.Adornee = target
	end
	light.Enabled = target ~= nil
	light.OutlineColor = color
	light.FillColor = color
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

	-- 가리키는 칸 강조: 들고 있으면 놓을 수 있는 칸 노랑 / 잠긴 칸 빨강, 아니면 명소 노랑 · 빈 칸 초록
	local slot = hit and hit.Slot
	local look = if slot then viewLook(slot) else nil
	if slot and look then
		local color = if look == ParkGrid.LOOK_LOCKED
			then Ui.colorPair("Coral").Face
			elseif held or Landmarks.ById[look] then Ui.colorPair("Sun").Face
			else Ui.colorPair("Grass").Face
		setHover(slot, color)
	elseif hoverSlot then
		setHover(nil, HOVER_COLOR)
	end

	-- 들고 있는 명소: 가리키는 칸 위(칸이 없으면 바닥 위)로 부드럽게 따라가며 오르내리고 돎
	local current = held
	if current then
		if hit and hit.Slot then
			current.Target = slotTop(hit.Slot).Position
		elseif hit and hit.Ground then
			-- 칸이 없는 곳: 가리키는 바닥 위(부지 밖이면 부지 가장자리에서 멈춤), 받침대 윗면 높이
			local cf = origin :: CFrame
			local p = cf:PointToObjectSpace(hit.Ground)
			current.Target = cf:PointToWorldSpace(
				Vector3.new(
					math.clamp(p.X, -ParkGrid.PLOT_WIDTH / 2, ParkGrid.PLOT_WIDTH / 2),
					ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT,
					math.clamp(p.Z, -ParkGrid.PLOT_DEPTH / 2, ParkGrid.PLOT_DEPTH / 2)
				)
			)
		end
		current.Position = current.Position:Lerp(current.Target, 1 - math.exp(-FOLLOW * dt))
		current.Angle = (current.Angle + SPIN_SPEED * dt) % (2 * math.pi)
		local lift = LIFT + math.sin(now * BOB_SPEED) * BOB
		moveRig(
			current.Ghost.Rig,
			CFrame.new(current.Position + Vector3.new(0, lift, 0)) * plotRotation() * CFrame.Angles(0, current.Angle, 0)
		)
		local locked = look == ParkGrid.LOOK_LOCKED
		current.Ghost.Light.FillColor = if locked then Ui.colorPair("Coral").Face else Ui.colorPair("Sun").Face
		-- 놓을 자리 판이 숨 쉬듯 빛남
		local glow = 0.42 + math.sin(now * 5) * 0.14
		for _, marker in markerPulse do
			marker.Transparency = glow
		end
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
		Fov = if camera then camera.FieldOfView else 70,
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
		local tween = TweenService:Create(camera, CAMERA_TWEEN, { CFrame = ParkEdit.topCFrame() })
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
		setMovement(true)
	end
	if viewButton then
		viewButton.SetColor(if viewMode == "Top" then "Sky" else "Grape")
	end
end

-- 월드 칸 모델 · ClickDetector ---------------------------------------------------------

-- 배치 모드 밖: 내 부지의 열린 칸에 이 클라이언트에서만 ClickDetector (누르면 배치 모드 + 그 칸 명소를 집음).
-- 남의 공원 받침대에는 손가락 커서가 안 뜸
local function addDetector(container: Instance)
	local slot = slotOf(container)
	if not slot or not container:IsA("Model") or container:FindFirstChild("ParkClick") then
		return
	end
	if container:GetAttribute("Look") == ParkGrid.LOOK_LOCKED then
		return
	end
	local detector = Instance.new("ClickDetector")
	detector.Name = "ParkClick"
	detector.MaxActivationDistance = CLICK_DISTANCE
	detector.MouseClick:Connect(function()
		ParkEdit.enter(slot)
	end)
	detector.Parent = container
end

local function removeDetectors()
	for _, container in containers do
		local detector = container:FindFirstChild("ParkClick")
		if detector then
			detector:Destroy()
		end
	end
end

local function addDetectors()
	for _, container in containers do
		addDetector(container)
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
	else
		addDetector(container)
	end
end

local function onContainerRemoved(container: Instance)
	local slot = slotOf(container)
	if slot and containers[slot] == container then
		containers[slot] = nil
	end
	hidden[container] = nil
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
		else
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
			card.Stars.Text = Ui.starsRich(PlayerState.stars(view.Inventory[id] or 0), #Config.STAR_THRESHOLDS)
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

	gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(layoutBar)
	Ui.onRescale(function()
		layoutBar()
	end)
end

-- 들어가기 · 나가기 ------------------------------------------------------------------

local function connectEdit(signal: RBXScriptSignal, callback: (...any) -> ())
	table.insert(editConnections, signal:Connect(callback))
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

	removeDetectors()
	-- HUD 를 먼저 바꾸고(메뉴·굴리기 줄 숨김, 열린 창 닫기) 띠 자리를 잡은 뒤에 카메라(띠 위 영역에 맞춤)
	handlers.Changed(true)
	bar.Visible = true
	layoutBar()
	scroller.CanvasPosition = Vector2.zero
	local camera = workspace.CurrentCamera
	if camera then
		savedCamera = { Type = camera.CameraType, Subject = camera.CameraSubject }
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
		local view = viewState()
		local id = if view then PlayerState.parkSlots(view)[slot] else nil
		if id then
			pickUp(id, slot)
		end
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

-- 배치 모드 켜기. slot: 받침대를 눌러 들어왔으면 그 칸 명소를 바로 집음. 내 공원 밖이면 먼저 순간 이동
function ParkEdit.enter(slot: number?)
	if editing then
		if slot then
			local view = viewState()
			local id = if view then PlayerState.parkSlots(view)[slot] else nil
			if id then
				pickUp(id, slot)
			end
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
	table.clear(localEdits)
	table.clear(markers)
	table.clear(markerPulse)
	hoverLight = nil
	hoverSlot = nil
	local folder = localFolder
	localFolder = nil
	if folder then
		folder:Destroy()
	end
	press, rightStart, pointer = nil, nil, nil
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
	end
	setMovement(true)

	bar.Visible = false
	addDetectors()
	handlers.Changed(false)
end

function ParkEdit.toggle()
	if editing or entering then
		ParkEdit.exit()
	else
		ParkEdit.enter(nil)
	end
end

function ParkEdit.isEditing(): boolean
	return editing
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
	removeDetectors()
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
	pickSound = makeSound(1.35, 0.3)
	dropSound = makeSound(0.9, 0.45)
	cancelSound = makeSound(0.65, 0.3)
	buildBar()
end

return ParkEdit
