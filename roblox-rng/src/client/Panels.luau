-- 메뉴 창: 도감(대표 지정), 여권(지역별 발견 현황 + 도장), 강화(업그레이드), 환생(조건 + 확인), 상점(Robux),
-- 공원 배치(전시 칸마다 명소 고르기 — 도감 머리 줄 [배치] 버튼 / HUD [배치] 버튼 / 내 공원 받침대를 눌러 열림)
-- 크림색 창(Ui.window) 하나를 쓰고, 화면마다 리본 색과 제목(2글자)만 바꿉니다.
-- 글자는 최소로: 설명 문장 없이 아이콘 + 숫자 딱지로 보여 줍니다.
-- 화면마다 카드를 한 번 만들고 상태가 바뀌면 글자/색만 고칩니다. 썸네일(ViewportFrame)은
-- 새로 발견했을 때만 만들어서, 자동 굴림 중에 창을 열어 둬도 매번 다시 만들지 않습니다.

local TweenService = game:GetService("TweenService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState)

local Icons = require(script.Parent.Icons)
local Perks = require(script.Parent.Perks)
local Ui = require(script.Parent.Ui)
local Viewport = require(script.Parent.Viewport)
local Theme = Ui.Theme

type Landmark = Landmarks.Landmark
type Snapshot = PlayerState.Snapshot

export type Handlers = {
	Feature: (string?) -> (),
	Buy: (string) -> (),
	ToggleAutoFeature: () -> (),
	Rebirth: () -> (), -- 확인까지 누른 뒤에만 부름
	BuyPass: (string) -> (), -- Config.GamePasses 키
	BuyProduct: (string) -> (), -- Config.Products 키
	Toast: (text: string, icon: string?, color: Color3?) -> (), -- 짧은 알림 (기본 실패 색, 예: "코인 부족")
	-- 공원 배치: 칸에 명소 놓기(nil = 빼기, expected = 화면에서 그 칸에 보이던 명소 Id, 빈 칸 "") /
	-- 자동 배치 켜기·끄기. 응답이 오면 Panels.parkDone(stale) 을 불러야 함
	SetDisplay: (slot: number, landmarkId: string?, expected: string, expectedFrom: number?) -> (),
	SetAutoPark: (on: boolean) -> (),
}

local REGION_BONUS = math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)

local HEADER_HEIGHT = 50 -- 창 본문 맨 위 딱지 줄 높이

-- 공원 배치: 왼쪽 격자(칸 56 · 간격 4 · 잔디 여백 7 = 한 변 370), 오른쪽 고른 칸 줄 + 명소 목록.
-- 격자 칸은 창(760×500) 안에 6줄이 들어가야 해서 56(배율 0.55 에서 31px)이 최대
local PARK_TILE = 56
local PARK_GAP = 4
local PARK_PAD = 7
local PARK_LAWN = Config.PARK_GRID * PARK_TILE + (Config.PARK_GRID - 1) * PARK_GAP + PARK_PAD * 2
local PARK_SIDE_X = PARK_LAWN + 14 -- 오른쪽 칸(고른 칸 줄 + 목록) 왼쪽 끝
local PARK_BAR = 88 -- 고른 칸 줄 높이 ([빼기] 앞면 73 = 가장 작은 배율 0.55 에서 40px)
local PARK_BAR_TEXT = 24 -- 고른 칸 줄 명소 이름 글자 크기(고정, 길면 두 줄)
local PARK_REMOVE_W = 108 -- [빼기] 폭
local PARK_PICKED_SCALE = 1.1 -- 고른 칸 크기 배율(굵은 Sun 테두리와 함께 휴대폰에서도 눈에 띄게)
local PARK_CARRY_SCALE = 1.2 -- 명소가 있는 칸을 고름(들고 있음): 놓을 자리들의 노란 테두리 사이에서도 떠 보이게
local PARK_ROW = 74 -- 명소 목록 한 줄 높이 (배율 0.55 에서 40px 이상)
local PARK_ROW_GAP = 8
local PARK_NAME_TEXT = 20 -- 목록 명소 이름 글자 크기(고정 — 긴 이름은 줄이지 않고 두 줄로)
local PARK_NAME_X = PARK_ROW + 2 -- 목록 이름·별 왼쪽 끝(사진 오른쪽)
local PARK_MARK_W = 50 -- 전시 중 줄 오른쪽 체크 딱지 자리
local PARK_DIVIDER = 30 -- 목록의 "전시 안 됨 | 전시 중" 구분 줄 높이

local VIEWS = {
	Collection = { Title = "도감", Color = "Sky", Top = HEADER_HEIGHT },
	Passport = { Title = "여권", Color = "Grape", Top = HEADER_HEIGHT },
	Upgrade = { Title = "강화", Color = "Sun", Top = 4 },
	Rebirth = { Title = "환생", Color = "Coral", Top = HEADER_HEIGHT },
	Shop = { Title = "상점", Color = "Sun", Top = 4 },
	Park = { Title = "배치", Color = "Grass", Top = HEADER_HEIGHT + PARK_BAR + 8 },
}

local WHITE = Color3.new(1, 1, 1)
local FEATURED_BG = Color3.fromRGB(255, 218, 128)
local DIM_CHIP = Color3.fromRGB(172, 170, 190) -- 아직 못 받은 보너스 딱지

local WINDOW_SIZE = Vector2.new(760, 500)
local BODY_HEIGHT = WINDOW_SIZE.Y - (45 + 16) -- 창 본문 높이(Ui.window: 창 높이 - 본문 위 45 - 아래 16)
local OPEN_OFFSET = -30 -- 창을 화면 가운데보다 조금 위로 (아래쪽 굴리기 버튼을 가리지 않게)
-- 스크롤 영역 안쪽 여백(오른쪽은 스크롤바 자리)
local PAD_X, PAD_RIGHT, PAD_Y = 6, 14, 6

local COLLECTION_CELL = Vector2.new(128, 184)
local COLLECTION_GAP = 12
local COLLECTION_COLUMNS = 5

local PASSPORT_CELL = Vector2.new(104, 124)
local PASSPORT_GAP = 8
local PASSPORT_COLUMNS = 6
local PASSPORT_HEADER = 98
local SECTION_PAD = 14
local SECTION_GAP = 16

local UPGRADE_ROW = 80
local UPGRADE_GAP = 10

local REBIRTH_COLUMNS = 6 -- 요구 명소 카드(여권 카드와 같은 크기)
local REBIRTH_FOOTER = 104 -- 창 아래 고정 줄: 보상 · 경고 · 환생 버튼
local COIN_BAR = Vector2.new(380, 40)
local CONFIRM_SECONDS = 3

local SHOP_CELL = Vector2.new(216, 196)
local SHOP_GAP = 12
local SHOP_COLUMNS = 3
local SHOP_BAND = 74
local BUY_COOLDOWN = 1

local Panels = {}

local win: Ui.Window
local window: Frame
local body: Frame
local loadingLabel: TextLabel
local handlers: Handlers
local openName: string? = nil
local lastState: Snapshot? = nil
local lastCoins = 0

type View = { Scroller: ScrollingFrame, Header: Frame, Extra: GuiObject? }
local views: { [string]: View } = {}

-- 도감 머리 줄
local collectionCount: Ui.Chip
local autoButton: Ui.ChunkyButton
local autoBadge: Ui.Chip
local emptyIcon: Frame

type CollectionCard = {
	Card: TextButton,
	Photo: Frame,
	Stars: TextLabel,
	Count: Ui.Chip,
	Shown: Ui.Chip?, -- 공원 전시 표시(처음 필요할 때 만듦)
	Dim: Frame?, -- 예전에 발견했지만 지금은 없음(환생 후): 사진을 어둡게 (처음 필요할 때 만듦)
	Badge: Ui.Chip,
}
local collectionCards: { [string]: CollectionCard } = {}

-- 여권 머리 줄
local stampCount: Ui.Chip
local stampBonus: Ui.Chip

type Stamp = {
	Frame: Frame,
	Stroke: UIStroke,
	RingStroke: UIStroke,
	Labels: { TextLabel },
	Outlines: { UIStroke },
	Art: Frame?, -- 도장 그림 아이콘(그림이 있을 때)
	Color: Color3,
}
type PassportSection = { Title: TextLabel, Fill: Frame, Bonus: Ui.Chip, Stamp: Stamp, Grid: Frame }
local passportSections: { [string]: PassportSection } = {}
local passportCards: { [string]: { Card: Frame, Known: boolean } } = {}

type UpgradeRow = {
	Level: Ui.Chip,
	Value: Ui.Chip,
	Step: Ui.Chip,
	Button: Ui.ChunkyButton,
	Price: number?,
}
local upgradeRows: { [string]: UpgradeRow } = {}

-- 환생
local rebirthCount: Ui.Chip
local rebirthLuck: Ui.Chip
local rebirthIncome: Ui.Chip
local rebirthSection: Frame
local rebirthGrid: Frame
local rebirthCoinFill: Frame
local rebirthCoinText: TextLabel
local rebirthCoinCheck: Frame
local rebirthWarning: Ui.Chip
local rebirthButton: Ui.ChunkyButton? = nil
local rebirthCards: { [string]: { Card: Frame, Look: string } } = {}
local confirmUntil = 0 -- 이 시각(os.clock)까지 한 번 더 누르면 환생
local confirmToken = 0
local rebirthLook = ""

-- 상점
type ShopCard = { Item: Perks.Item, Button: Ui.ChunkyButton, Effect: Ui.Chip, Owned: Ui.Chip? }
local shopCards: { ShopCard } = {}

-- 공원 배치
type ParkTile = {
	Button: TextButton,
	Stroke: UIStroke,
	Scale: UIScale, -- 고른 칸은 조금 크게, 마우스를 올리면 살짝 크게
	Plus: TextLabel, -- 빈 칸 "+"
	Lock: GuiObject, -- 잠긴 칸 자물쇠
	View: ViewportFrame?, -- 명소 사진(처음 필요할 때 만듦)
	Look: string, -- "locked" | "empty" | 명소 Id
	Picked: boolean,
	Carried: boolean, -- 고른 칸에 명소가 있음(집어 든 상태) -> 더 크게
	Hovered: boolean,
}
type ParkCard = {
	Card: TextButton,
	Stroke: UIStroke, -- 고른 칸의 명소 줄이면 굵은 Sun
	Photo: Frame,
	Thumb: ViewportFrame?, -- 명소 사진(줄이 화면에 들어올 때 처음 만듦)
	Name: TextLabel,
	Stars: TextLabel,
	Mark: Ui.Chip, -- 전시 중 체크
	Landmark: Landmark,
	Y: number, -- 목록 안 위치(설계 px, 스크롤 영역 안쪽 여백 제외)
}
local parkTiles: { ParkTile } = {} -- 칸 번호 순서
local parkCards: { [string]: ParkCard } = {}
local parkCount: Ui.Chip
local parkIncome: Ui.Chip
local parkAuto: Ui.ChunkyButton
local parkAutoBadge: Ui.Chip
local parkSlotLabel: TextLabel
local parkRemove: Ui.ChunkyButton
local parkDivider: Frame
local parkDividerChip: Ui.Chip
local parkEmpty: Frame? = nil -- 가진 명소가 없을 때 목록 자리: 지구본 + 굴리기 딱지
local parkSelected: number? = nil -- 고른 칸
local parkPreview: Snapshot? = nil -- 서버 응답 전에 미리 보여 주는 배치(응답을 기다리는 요청이 있을 때만)
local parkPending = 0 -- 응답을 기다리는 배치 요청 수
local parkConfirmUntil = 0 -- 이 시각(os.clock)까지 자동 배치를 한 번 더 누르면 켜짐
local parkConfirmToken = 0
local parkWantScroll = false -- 고른 칸이 바뀜 -> 다음 그리기에서 목록을 그 명소 줄(빈 칸이면 맨 위)로 스크롤
local parkAutoNoticed = false -- 배치 편집으로 자동 배치가 꺼졌다는 알림을 이번 접속에서 보였는지
local parkAutoFlip = false -- 자동 배치 중에 보낸 편집이 응답을 기다리는 중(성공하면 "자동 꺼짐" 알림)
local collectionArrangeBadge: Ui.Chip? = nil -- 도감 머리 줄 [배치] 배지
-- 칸·목록 버튼이 부르는 동작 (아래 "공원 배치" 에서 정의)
local selectParkSlot: (slot: number) -> ()
local placeInPark: (id: string) -> ()
local removeFromPark: () -> ()
local toggleAutoPark: () -> ()
local loadParkThumbs: () -> ()

local function owned(state: Snapshot, id: string): number
	return state.Inventory[id] or 0
end

-- 초당 수입 짧게 (Hud 와 같은 규칙): 작은 값은 소수 한 자리 "1.8", 큰 값은 "12.5K"
local function incomeText(income: number): string
	if income < 100 then
		local text = string.format("%.1f", math.floor(income * 10) / 10):gsub("%.0$", "")
		return text
	end
	return Format.short(income)
end

local function gridHeight(count: number, columns: number, cellHeight: number, gap: number): number
	local rows = math.ceil(count / columns)
	if rows <= 0 then
		return 0
	end
	return rows * (cellHeight + gap) - gap
end

local function newScroller(name: string, top: number): ScrollingFrame
	local scroller = Ui.new("ScrollingFrame", {
		Name = name,
		Position = UDim2.fromOffset(0, top),
		Size = UDim2.new(1, 0, 1, -top),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 8,
		ScrollBarImageColor3 = Theme.Ink,
		ScrollBarImageTransparency = 0.35,
		CanvasSize = UDim2.new(),
		ScrollingDirection = Enum.ScrollingDirection.Y,
		Visible = false,
		Parent = body,
	})
	Ui.new("UIPadding", {
		PaddingLeft = UDim.new(0, PAD_X),
		PaddingRight = UDim.new(0, PAD_RIGHT),
		PaddingTop = UDim.new(0, PAD_Y),
		PaddingBottom = UDim.new(0, PAD_Y),
		Parent = scroller,
	})
	return scroller
end

-- 창 본문 맨 위 딱지 줄 (화면마다 하나)
local function newHeader(name: string): Frame
	return Ui.new("Frame", {
		Name = name .. "Header",
		Size = UDim2.new(1, 0, 0, HEADER_HEIGHT),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = body,
	})
end

-- 머리 줄의 아이콘 + 숫자 딱지
local function headerChip(parent: Instance, icon: string, color: any, order: number): Ui.Chip
	return Ui.chip({
		Color = color,
		Icon = icon,
		IconSize = 44,
		Height = 34,
		TextSize = 21,
		LayoutOrder = order,
		Parent = parent,
	})
end

local function chipRow(parent: Instance): Frame
	local row = Ui.new("Frame", {
		Name = "Chips",
		Position = UDim2.fromOffset(10, 0),
		Size = UDim2.new(1, -200, 1, -6),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	Ui.list(Enum.FillDirection.Horizontal, 14).Parent = row
	return row
end

local function setCanvasHeight(scroller: ScrollingFrame, contentHeight: number)
	scroller.CanvasSize = UDim2.fromOffset(0, contentHeight + PAD_Y * 2)
end

local THUMB_PROPS = { Position = UDim2.fromOffset(2, 2), Size = UDim2.new(1, -4, 1, -4) }

-- 명소 썸네일을 담는 "사진 칸" (등급 색을 옅게 깐 바탕). lazy 면 썸네일은 나중에(Viewport.thumbnail(frame, ...))
local function photo(
	parent: GuiObject,
	landmark: Landmark,
	position: UDim2,
	size: UDim2,
	radius: number,
	lazy: boolean?
): Frame
	local frame = Ui.new("Frame", {
		Name = "Photo",
		Position = position,
		Size = size,
		BackgroundColor3 = landmark.Tier.Color:Lerp(WHITE, 0.62),
		Parent = parent,
	})
	Ui.corner(radius).Parent = frame
	Ui.stroke(Theme.Ink, 2).Parent = frame
	if not lazy then
		Viewport.thumbnail(frame, landmark, THUMB_PROPS)
	end
	return frame
end

-- 버튼 오른쪽 위 숫자 배지 (여권 "1/6" 배지와 같은 모양: Ink 딱지 + Sun 숫자, 살짝 기울임)
local function countBadge(button: Ui.ChunkyButton, name: string): Ui.Chip
	return Ui.chip({
		Name = name,
		Color = Theme.Ink,
		TextColor3 = Ui.colorPair("Sun").Face,
		Height = 24,
		TextSize = 15,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -6, 0, 2),
		Rotation = 8,
		ZIndex = 6,
		Visible = false,
		Parent = button.Face,
	})
end

-- 통통 튀기: 버튼 크기 UIScale(마우스를 올릴 때 쓰는 것)을 몇 번 키웠다 줄임
local function pulse(target: GuiObject)
	local scale = target:FindFirstChildOfClass("UIScale") or Ui.new("UIScale", { Parent = target })
	scale.Scale = 1
	TweenService:Create(scale, TweenInfo.new(0.18, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 2, true), {
		Scale = 1.15,
	}):Play()
end

-- 도감 -----------------------------------------------------------------------

local function buildCollection(): View
	local header = newHeader("Collection")
	local chips = chipRow(header)
	collectionCount = headerChip(chips, "album", Theme.Ink, 1)

	-- 자동 대표 지정: 별 아이콘 + "자동" (켜짐 = 초록 + ON 딱지, 꺼짐 = 회색)
	autoButton = Ui.chunkyButton({
		Name = "AutoFeature",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -8, 0, -4),
		Size = UDim2.fromOffset(136, 50),
		Color = "Gray",
		Icon = "star",
		IconSize = 36,
		Text = "자동",
		TextSize = 22,
		Parent = header,
	})
	autoButton.Activated:Connect(function()
		handlers.ToggleAutoFeature()
	end)
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

	-- 공원 배치 창 열기: 배치 아이콘(2×2 칸 판) + "배치" (자동 버튼 왼쪽). 배지 = 더 좋은데 전시 안 된 명소 수
	local arrange = Ui.chunkyButton({
		Name = "Arrange",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -(8 + 136 + 10), 0, -4),
		Size = UDim2.fromOffset(124, 50),
		Color = "Grass",
		Icon = "arrange",
		IconSize = 36,
		Text = "배치",
		TextSize = 22,
		Parent = header,
	})
	arrange.Activated:Connect(function()
		Panels.openPark(nil)
	end)
	collectionArrangeBadge = countBadge(arrange, "Better")

	-- 아직 아무것도 없을 때: 가운데에 천천히 도는 지구본
	emptyIcon = Icons.view(body, "globe", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0.5, HEADER_HEIGHT / 2),
		Size = UDim2.fromOffset(150, 150),
		Spin = 40,
		Transparency = 0.2,
	})
	emptyIcon.Visible = false

	local scroller = newScroller("Collection", VIEWS.Collection.Top)
	Ui.new("UIGridLayout", {
		CellSize = UDim2.fromOffset(COLLECTION_CELL.X, COLLECTION_CELL.Y),
		CellPadding = UDim2.fromOffset(COLLECTION_GAP, COLLECTION_GAP),
		FillDirectionMaxCells = COLLECTION_COLUMNS,
		SortOrder = Enum.SortOrder.LayoutOrder,
		HorizontalAlignment = Enum.HorizontalAlignment.Center,
		Parent = scroller,
	})
	return { Scroller = scroller, Header = header }
end

local function collectionCard(parent: ScrollingFrame, landmark: Landmark): CollectionCard
	local tier = landmark.Tier
	local card = Ui.new("TextButton", {
		Name = landmark.Id,
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = Theme.Paper,
	})
	Ui.corner(12).Parent = card
	Ui.stroke(Theme.Ink, 3).Parent = card

	-- 등급 색 띠 + 확률 (위쪽 모서리만 둥글게: 아래 절반을 네모 판으로 덮음)
	local band = Ui.new("Frame", {
		Name = "Band",
		Size = UDim2.new(1, 0, 0, 26),
		BackgroundColor3 = tier.Color,
		BorderSizePixel = 0,
		Parent = card,
	})
	Ui.corner(12).Parent = band
	Ui.new("Frame", {
		Position = UDim2.new(0, 0, 1, -12),
		Size = UDim2.new(1, 0, 0, 12),
		BackgroundColor3 = tier.Color,
		BorderSizePixel = 0,
		Parent = band,
	})
	Ui.new("Frame", {
		Position = UDim2.fromScale(0, 1),
		Size = UDim2.new(1, 0, 0, 3),
		BackgroundColor3 = Theme.Ink,
		BorderSizePixel = 0,
		Parent = band,
	})
	local bandLabel = Ui.label({
		Position = UDim2.fromOffset(8, 4),
		Size = UDim2.new(1, -16, 1, -7),
		Text = Format.oneIn(landmark.OneIn),
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = band,
	}, 15)
	Ui.outline(bandLabel, 1.5)

	local picture = photo(card, landmark, UDim2.fromOffset(7, 33), UDim2.new(1, -14, 0, 84), 8)

	Ui.label({
		Position = UDim2.fromOffset(6, 122),
		Size = UDim2.new(1, -12, 0, 24),
		Text = landmark.Name,
		Parent = card,
	}, 19)
	local stars = Ui.label({
		Position = UDim2.fromOffset(6, 149),
		Size = UDim2.new(1, -12, 0, 24),
		Parent = card,
	}, 22)
	Ui.outline(stars, 2)

	local count = Ui.chip({
		Name = "Count",
		Color = Theme.Ink,
		Height = 22,
		TextSize = 14,
		StrokeThickness = 2,
		Outline = false,
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -3, 0, 29),
		ZIndex = 3,
		Parent = card,
	})
	-- "대표" 도장 (왼쪽 위, 기울임)
	local badge = Ui.chip({
		Name = "Featured",
		Color = "Coral",
		Text = "대표",
		Height = 28,
		TextSize = 17,
		CornerRadius = 7,
		Rotation = -14,
		Position = UDim2.fromOffset(-8, 22),
		ZIndex = 4,
		Visible = false,
		Parent = card,
	})

	local hover = Ui.new("UIScale", { Parent = card })
	card.MouseEnter:Connect(function()
		hover.Scale = 1.04
	end)
	card.MouseLeave:Connect(function()
		hover.Scale = 1
	end)
	card.Activated:Connect(function()
		local state = lastState
		local featured = state ~= nil and state.Featured == landmark.Id
		if not featured and (not state or owned(state, landmark.Id) <= 0) then
			return -- 지금 없는 명소(환생 전에 발견)는 대표로 못 씀
		end
		handlers.Feature(if featured then nil else landmark.Id)
	end)

	card.Parent = parent
	return { Card = card, Photo = picture, Stars = stars, Count = count, Shown = nil, Dim = nil, Badge = badge }
end

-- 지금은 없는 명소: 사진 위에 어두운 막 (처음 필요할 때 만듦)
local function setDim(entry: CollectionCard, dim: boolean)
	local shade = entry.Dim
	if not shade then
		if not dim then
			return
		end
		shade = Ui.new("Frame", {
			Name = "Dim",
			Size = UDim2.fromScale(1, 1),
			BackgroundColor3 = Theme.Ink,
			BackgroundTransparency = 0.45,
			ZIndex = 2,
			Parent = entry.Photo,
		})
		Ui.corner(8).Parent = shade
		entry.Dim = shade
	end
	(shade :: Frame).Visible = dim
end

-- 공원에 전시 중: 사진 왼쪽 아래 초록 공원 아이콘 딱지 (처음 필요할 때 만듦)
local function setShown(entry: CollectionCard, shown: boolean)
	local chip = entry.Shown
	if not chip then
		if not shown then
			return
		end
		chip = Ui.chip({
			Name = "Shown",
			Color = "Grass",
			Icon = "park",
			IconOnly = true,
			IconSize = 30,
			Height = 24,
			StrokeThickness = 2,
			Position = UDim2.fromOffset(3, 94),
			ZIndex = 3,
			Parent = entry.Card,
		})
		entry.Shown = chip
	end
	(chip :: Ui.Chip).Root.Visible = shown
end

local function renderCollection(state: Snapshot)
	local scroller = views.Collection.Scroller
	local autoFeature = state.Settings.AutoFeature
	autoButton.SetColor(if autoFeature then "Grass" else "Gray")
	autoBadge.Root.Visible = autoFeature
	local badge = collectionArrangeBadge
	if badge then
		local better = #PlayerState.betterHidden(state)
		badge.Label.Text = tostring(better)
		badge.Root.Visible = better > 0
	end

	local inPark = {}
	for _, id in PlayerState.park(state) do
		inPark[id] = true
	end

	-- 도감은 역대 발견(Discovered) 기준. 별·개수·전시는 지금 보유(Inventory) 기준
	local shown = 0
	for _, landmark in Landmarks.RarestFirst do
		local count = owned(state, landmark.Id)
		local entry = collectionCards[landmark.Id]
		if Perks.discovered(state, landmark.Id) then
			shown += 1
			if not entry then
				entry = collectionCard(scroller, landmark)
				collectionCards[landmark.Id] = entry
			end
			local featured = state.Featured == landmark.Id
			entry.Card.LayoutOrder = shown
			entry.Card.BackgroundColor3 = if featured then FEATURED_BG else Theme.Paper
			entry.Badge.Root.Visible = featured
			entry.Stars.Text = Ui.starsRich(PlayerState.stars(count), #Config.STAR_THRESHOLDS)
			entry.Count.Label.Text = "×" .. Format.commas(count)
			entry.Count.Root.Visible = count > 0
			setShown(entry, inPark[landmark.Id] == true)
			setDim(entry, count <= 0)
		elseif entry then
			entry.Card:Destroy()
			collectionCards[landmark.Id] = nil
		end
	end

	collectionCount.Label.Text = string.format("%d/%d", shown, #Landmarks.List)
	emptyIcon.Visible = shown == 0
	setCanvasHeight(scroller, gridHeight(shown, COLLECTION_COLUMNS, COLLECTION_CELL.Y, COLLECTION_GAP))
end

-- 여권 -----------------------------------------------------------------------

-- 지역 도장: 그림(ImageIds.stamp_<지역>)이 있으면 그 그림, 없으면 지역 색 동그라미(기울임) + 흰 고리 + 지역 이름
local function makeStamp(parent: Frame, region: Landmarks.Region): Stamp
	local frame = Ui.new("Frame", {
		Name = "Stamp",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -18, 0, 6),
		Size = UDim2.fromOffset(88, 88),
		BackgroundColor3 = region.Color,
		Rotation = -12,
		ZIndex = 2,
		Parent = parent,
	})
	Ui.round().Parent = frame
	local stroke = Ui.stroke(Theme.Ink, 3)
	stroke.Parent = frame
	local ring = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.new(1, -14, 1, -14),
		BackgroundTransparency = 1,
		Parent = frame,
	})
	Ui.round().Parent = ring
	local ringStroke = Ui.stroke(WHITE, 2)
	ringStroke.Parent = ring

	local stamp: Stamp = {
		Frame = frame,
		Stroke = stroke,
		RingStroke = ringStroke,
		Labels = {},
		Outlines = {},
		Art = nil,
		Color = region.Color,
	}

	local art = "stamp_" .. string.lower(region.Id)
	if Icons.imageId(art) then
		frame.BackgroundTransparency = 1
		stroke.Enabled = false
		ring.Visible = false
		stamp.Art = Icons.view(frame, art, {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(1.12, 1.12),
			ZIndex = 2,
		})
	else
		local name = Ui.label({
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.74, 0.4),
			Text = region.Name,
			TextColor3 = WHITE,
			ZIndex = 2,
			Parent = frame,
		}, 20)
		stamp.Labels = { name }
		stamp.Outlines = { Ui.outline(name, 2) }
	end
	return stamp
end

-- 다 모으면 진하게 찍힌 도장, 아니면 흐릿한 도장 자국
local function paintStamp(stamp: Stamp, complete: boolean)
	local art = stamp.Art
	if art then
		Icons.setColor(art, if complete then WHITE else Color3.fromRGB(150, 146, 160))
		Icons.setTransparency(art, if complete then 0 else 0.75)
		return
	end
	stamp.Frame.BackgroundTransparency = if complete then 0 else 0.8
	stamp.Stroke.Transparency = if complete then 0 else 0.65
	stamp.RingStroke.Color = if complete then WHITE else stamp.Color
	stamp.RingStroke.Transparency = if complete then 0.1 else 0.35
	for _, label in stamp.Labels do
		label.TextColor3 = if complete then WHITE else stamp.Color:Lerp(Theme.Ink, 0.25)
		label.TextTransparency = if complete then 0 else 0.35
	end
	for _, outline in stamp.Outlines do
		outline.Enabled = complete
	end
end

-- 행운 보너스 딱지 색: 받았으면 초록 + 진한 아이콘, 아직이면 회색 + 흐린 아이콘
local function paintBonus(chip: Ui.Chip, earned: boolean)
	Ui.tint(chip.Root, if earned then Ui.colorPair("Grass").Face else DIM_CHIP)
	if chip.Icon then
		Icons.setTransparency(chip.Icon, if earned then 0 else 0.45)
	end
end

local function buildPassport(): View
	local header = newHeader("Passport")
	local chips = chipRow(header)
	stampCount = headerChip(chips, "passport", Theme.Ink, 1)
	stampBonus = headerChip(chips, "clover", "Grass", 2)

	local scroller = newScroller("Passport", VIEWS.Passport.Top)
	local layout = Ui.list(Enum.FillDirection.Vertical, SECTION_GAP)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = scroller

	local total = 0
	for order, region in Landmarks.Regions do
		local list = Landmarks.ByRegion[region.Id]
		local height = PASSPORT_HEADER
			+ gridHeight(#list, PASSPORT_COLUMNS, PASSPORT_CELL.Y, PASSPORT_GAP)
			+ SECTION_PAD
		-- 여권 한 쪽
		local section = Ui.new("Frame", {
			Name = region.Id,
			LayoutOrder = order,
			Size = UDim2.new(1, 0, 0, height),
			BackgroundColor3 = Theme.Paper,
			Parent = scroller,
		})
		Ui.corner(14).Parent = section
		Ui.stroke(Theme.Ink, 3).Parent = section

		-- 지역 이름 + 발견 수 "3/7"
		local title = Ui.label({
			Position = UDim2.fromOffset(SECTION_PAD, 8),
			Size = UDim2.new(0.6, 0, 0, 34),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = section,
		}, 28)
		-- 발견 진행 막대
		local track = Ui.new("Frame", {
			Position = UDim2.fromOffset(SECTION_PAD, 46),
			Size = UDim2.new(0.5, 0, 0, 14),
			BackgroundColor3 = Theme.Cream,
			Parent = section,
		})
		Ui.round().Parent = track
		Ui.stroke(Theme.Ink, 2).Parent = track
		local fill = Ui.new("Frame", {
			Size = UDim2.fromScale(0, 1),
			BackgroundColor3 = region.Color,
			BorderSizePixel = 0,
			Parent = track,
		})
		Ui.round().Parent = fill
		-- 도장 보너스 "+25%" (네잎클로버)
		local bonus = Ui.chip({
			Name = "Bonus",
			Color = DIM_CHIP,
			Icon = "clover",
			IconSize = 32,
			Text = string.format("+%d%%", REGION_BONUS),
			Height = 26,
			TextSize = 16,
			Position = UDim2.fromOffset(SECTION_PAD + 2, 66),
			Parent = section,
		})

		local stamp = makeStamp(section, region)

		local grid = Ui.new("Frame", {
			Position = UDim2.fromOffset(SECTION_PAD, PASSPORT_HEADER),
			Size = UDim2.new(1, -SECTION_PAD * 2, 1, -(PASSPORT_HEADER + SECTION_PAD)),
			BackgroundTransparency = 1,
			Parent = section,
		})
		Ui.new("UIGridLayout", {
			CellSize = UDim2.fromOffset(PASSPORT_CELL.X, PASSPORT_CELL.Y),
			CellPadding = UDim2.fromOffset(PASSPORT_GAP, PASSPORT_GAP),
			FillDirectionMaxCells = PASSPORT_COLUMNS,
			SortOrder = Enum.SortOrder.LayoutOrder,
			HorizontalAlignment = Enum.HorizontalAlignment.Left,
			Parent = grid,
		})
		passportSections[region.Id] = { Title = title, Fill = fill, Bonus = bonus, Stamp = stamp, Grid = grid }
		total += height + (if order > 1 then SECTION_GAP else 0)
	end
	setCanvasHeight(scroller, total)
	return { Scroller = scroller, Header = header }
end

local function passportCard(parent: Frame, landmark: Landmark, known: boolean, order: number): Frame
	local tier = landmark.Tier
	local card = Ui.new("Frame", {
		Name = landmark.Id,
		LayoutOrder = order,
		BackgroundColor3 = if known then Theme.Cream else Theme.Ink,
	})
	Ui.corner(10).Parent = card
	Ui.stroke(Theme.Ink, 2.5).Parent = card

	if known then
		photo(card, landmark, UDim2.fromOffset(5, 5), UDim2.new(1, -10, 0, 68), 7)
		Ui.label({
			Position = UDim2.fromOffset(4, 77),
			Size = UDim2.new(1, -8, 0, 20),
			Text = landmark.Name,
			Parent = card,
		}, 16)
		Ui.label({
			Position = UDim2.fromOffset(4, 99),
			Size = UDim2.new(1, -8, 0, 17),
			Text = Format.oneIn(landmark.OneIn),
			TextColor3 = tier.Color:Lerp(Theme.Ink, 0.45),
			Parent = card,
		}, 14)
	else
		-- 아직 못 찾은 명소: 어두운 카드 + 자물쇠 그림(있으면) 또는 "?" + 확률
		-- (3D 자물쇠는 카드가 많아 무거우니 그림이 있을 때만)
		if Icons.imageId("lock") then
			Icons.view(card, "lock", {
				AnchorPoint = Vector2.new(0.5, 0),
				Position = UDim2.new(0.5, 0, 0, 14),
				Size = UDim2.fromOffset(56, 56),
				Transparency = 0.15,
			})
		else
			Ui.label({
				Position = UDim2.fromOffset(5, 5),
				Size = UDim2.new(1, -10, 0, 74),
				Font = Theme.FontTitle,
				Text = "?",
				TextColor3 = Theme.Paper,
				TextTransparency = 0.2,
				Parent = card,
			}, 50)
		end
		Ui.label({
			Position = UDim2.fromOffset(4, 90),
			Size = UDim2.new(1, -8, 0, 20),
			Text = Format.oneIn(landmark.OneIn),
			TextColor3 = tier.Color,
			Parent = card,
		}, 16)
	end

	card.Parent = parent
	return card
end

local function renderPassport(state: Snapshot)
	local stamps = 0
	for _, region in Landmarks.Regions do
		local section = passportSections[region.Id]
		local list = Landmarks.ByRegion[region.Id]
		local discovered = 0
		for order, landmark in list do
			local known = Perks.discovered(state, landmark.Id)
			if known then
				discovered += 1
			end
			-- 발견 여부가 바뀐 카드만 다시 만듦
			local entry = passportCards[landmark.Id]
			if not entry or entry.Known ~= known then
				if entry then
					entry.Card:Destroy()
				end
				passportCards[landmark.Id] =
					{ Card = passportCard(section.Grid, landmark, known, order), Known = known }
			end
		end

		-- 도장은 전설급을 뺀 명소만 셈(PlayerState 규칙). 전설급은 카드로만 보이는 보너스 수집
		local found, required = PlayerState.regionProgress(state, region.Id)
		local complete = required > 0 and found >= required
		if complete then
			stamps += 1
		end
		section.Title.Text = string.format(
			'%s  <font color="%s">%d/%d</font>',
			region.Name,
			Format.hex(region.Color:Lerp(Theme.Ink, 0.3)),
			found,
			required
		)
		section.Fill.Size = UDim2.fromScale(if required > 0 then found / required else 0, 1)
		paintBonus(section.Bonus, complete)
		paintStamp(section.Stamp, complete)
	end

	stampCount.Label.Text = string.format("%d/%d", stamps, #Landmarks.Regions)
	stampBonus.Label.Text = string.format("+%d%%", stamps * REGION_BONUS)
	paintBonus(stampBonus, stamps > 0)
end

-- 강화 -----------------------------------------------------------------------

-- 숫자 뒤의 0 떼기: 1.20 -> "1.2", 0.60 -> "0.6"
local function trim(value: number): string
	local text = string.format("%.2f", value):gsub("0+$", ""):gsub("%.$", "")
	return text
end

-- 지금 레벨의 효과 값 (짧게): 행운 ×1.3 / 굴림 간격 1.14초 / 전시 9칸 / 수입 ×1.4
local function valueText(upgrade: PlayerState.Upgrade, level: number): string
	if upgrade.Id == "Agency" then
		return trim(Config.ROLL_COOLDOWN * (1 - upgrade.PerLevel * level)) .. "초"
	elseif upgrade.Id == "Park" then
		return string.format("%d칸", math.floor(Config.BASE_SLOTS + upgrade.PerLevel * level + 0.5))
	end
	return Ui.times(1 + upgrade.PerLevel * level)
end

-- 한 번 살 때 바뀌는 양: "+10%", "-5%", "+3칸"
local function stepText(upgrade: PlayerState.Upgrade): string
	if upgrade.Id == "Park" then
		return string.format("+%d칸", upgrade.PerLevel)
	end
	local percent = math.floor(upgrade.PerLevel * 100 + 0.5)
	return string.format(if upgrade.Id == "Agency" then "-%d%%" else "+%d%%", percent)
end

-- 살 수 있으면 Sun, 코인이 모자라면 Gray, 최대 레벨이면 Grape (같은 색이면 버튼이 알아서 건너뜀)
local function paintBuyButton(row: UpgradeRow, coins: number)
	local price = row.Price
	row.Button.SetColor(if price == nil then "Grape" elseif coins >= price then "Sun" else "Gray")
end

local function buildUpgrade(): View
	local header = newHeader("Upgrade") -- 비어 있음(모양을 맞추려고 둠)
	local scroller = newScroller("Upgrade", VIEWS.Upgrade.Top)
	local layout = Ui.list(Enum.FillDirection.Vertical, UPGRADE_GAP, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = scroller

	for order, upgrade in Config.Upgrades do
		local row = Ui.new("Frame", {
			Name = upgrade.Id,
			LayoutOrder = order,
			Size = UDim2.new(1, 0, 0, UPGRADE_ROW),
			BackgroundColor3 = Theme.Paper,
			Parent = scroller,
		})
		Ui.corner(14).Parent = row
		Ui.stroke(Theme.Ink, 3).Parent = row

		-- 아이콘 동그라미
		local disc = Ui.new("Frame", {
			AnchorPoint = Vector2.new(0, 0.5),
			Position = UDim2.new(0, 12, 0.5, 0),
			Size = UDim2.fromOffset(62, 62),
			BackgroundColor3 = Theme.Cream,
			Parent = row,
		})
		Ui.round().Parent = disc
		Ui.stroke(Theme.Ink, 3).Parent = disc
		Icons.view(disc, Icons.UPGRADE[upgrade.Id] or "star", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.86, 0.86),
		})

		-- 윗줄: 이름 + "Lv 3"
		local head = Ui.new("Frame", {
			Position = UDim2.fromOffset(88, 6),
			Size = UDim2.new(1, -290, 0, 32),
			BackgroundTransparency = 1,
			Parent = row,
		})
		Ui.list(Enum.FillDirection.Horizontal, 10).Parent = head
		Ui.label({
			LayoutOrder = 1,
			AutomaticSize = Enum.AutomaticSize.X,
			Size = UDim2.fromScale(0, 1),
			TextScaled = false,
			TextSize = 25,
			Text = upgrade.Name,
			Parent = head,
		}, 100)
		local level = Ui.chip({
			Name = "Level",
			Color = Theme.Ink,
			Height = 24,
			TextSize = 15,
			StrokeThickness = 2,
			Outline = false,
			LayoutOrder = 2,
			Parent = head,
		})

		-- 아랫줄: 지금 값 딱지 + 한 번 살 때 바뀌는 양 딱지(위 화살표)
		local effects = Ui.new("Frame", {
			Position = UDim2.fromOffset(92, 42),
			Size = UDim2.new(1, -290, 0, 30),
			BackgroundTransparency = 1,
			Parent = row,
		})
		Ui.list(Enum.FillDirection.Horizontal, 12).Parent = effects
		local value = Ui.chip({
			Name = "Value",
			Color = Theme.Cream,
			TextColor3 = Theme.Ink,
			Outline = false,
			Height = 26,
			TextSize = 17,
			StrokeThickness = 2,
			LayoutOrder = 1,
			Parent = effects,
		})
		local step = Ui.chip({
			Name = "Step",
			Color = "Grass",
			Icon = "arrow_up",
			IconSize = 30,
			Height = 26,
			TextSize = 17,
			LayoutOrder = 2,
			Parent = effects,
		})

		local button = Ui.chunkyButton({
			Name = "Buy",
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, -14, 0.5, 0),
			Size = UDim2.fromOffset(176, 62),
			Color = "Sun",
			Icon = "coin",
			IconSize = 44,
			TextSize = 26,
			Parent = row,
		})
		button.Activated:Connect(function()
			local entry = upgradeRows[upgrade.Id]
			if entry and entry.Price then
				handlers.Buy(upgrade.Id)
			end
		end)
		upgradeRows[upgrade.Id] = { Level = level, Value = value, Step = step, Button = button }
	end
	setCanvasHeight(scroller, #Config.Upgrades * (UPGRADE_ROW + UPGRADE_GAP) - UPGRADE_GAP)
	return { Scroller = scroller, Header = header }
end

local function renderUpgrade(state: Snapshot)
	for _, upgrade in Config.Upgrades do
		local row = upgradeRows[upgrade.Id]
		local level = PlayerState.upgradeLevel(state, upgrade.Id)
		local price = PlayerState.upgradePrice(upgrade.Id, level)
		row.Level.Label.Text = "Lv " .. level
		row.Value.Label.Text = valueText(upgrade, level)
		Ui.showChipIcon(row.Step, price ~= nil) -- 최대 레벨(MAX)에는 위 화살표 없음
		if price then
			row.Step.Label.Text = stepText(upgrade)
			Ui.tint(row.Step.Root, Ui.colorPair("Grass").Face)
			row.Button.SetText(Format.commas(price))
			row.Button.SetIcon("coin")
		else
			row.Step.Label.Text = "MAX"
			Ui.tint(row.Step.Root, Ui.colorPair("Grape").Face)
			row.Button.SetText("MAX")
			row.Button.SetIcon(nil)
		end
		row.Price = price
		paintBuyButton(row, lastCoins)
	end
end

-- 환생 -----------------------------------------------------------------------

-- 버튼이 좌우로 살짝 흔들림 (아직 못 누를 때)
local function shake(target: GuiObject)
	target.Rotation = 0
	local info = TweenInfo.new(0.05, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 3, true)
	TweenService:Create(target, info, { Rotation = 4 }):Play()
end

-- 환생 버튼: 못 함 = 회색 / 가능 = Coral "환생" / 한 번 누름 = Sun "확인?" (3초)
local function paintRebirthButton(ready: boolean)
	local button = rebirthButton
	if not button then
		return
	end
	local confirming = ready and os.clock() < confirmUntil
	local look = if confirming then "confirm" elseif ready then "ready" else "locked"
	if look == rebirthLook then
		return
	end
	rebirthLook = look
	button.SetText(if confirming then "확인?" else "환생")
	button.SetColor(if confirming then "Sun" elseif ready then "Coral" else "Gray")
	if button.Icon then
		Icons.setTransparency(button.Icon, if ready then 0 else 0.45)
	end
end

-- 코인 막대와 버튼만 다시 칠함 (0.25초마다 불려도 가벼움)
local function refreshRebirth(coins: number)
	local state = lastState
	if not state or not rebirthButton then
		return
	end
	local ready, _, short, need = Perks.rebirthCheck(state, coins)
	local required = if need then need.Coins else 0
	local met = need ~= nil and short <= 0
	rebirthCoinFill.Size = UDim2.fromScale(if required > 0 then math.clamp(coins / required, 0, 1) else 1, 1)
	rebirthCoinFill.BackgroundColor3 = Ui.colorPair(if met then "Grass" else "Sun").Face
	local text = Format.short(math.max(0, math.floor(coins))) .. " / " .. Format.short(required)
	if rebirthCoinText.Text ~= text then
		rebirthCoinText.Text = text
	end
	rebirthCoinCheck.Visible = met
	paintRebirthButton(ready)
end

local function onRebirthPressed()
	local state = lastState
	if not state then
		return
	end
	local ready, missing, _, need = Perks.rebirthCheck(state, lastCoins)
	if not need then
		return
	end
	if not ready then
		confirmUntil = 0
		paintRebirthButton(false)
		if rebirthButton then
			shake(rebirthButton.Root)
		end
		if #missing > 0 then
			handlers.Toast("명소 부족", "lock")
		else
			handlers.Toast("코인 부족", "coin")
		end
		return
	end
	if os.clock() < confirmUntil then
		confirmUntil = 0
		confirmToken += 1
		paintRebirthButton(true)
		handlers.Rebirth()
		return
	end
	-- 첫 번째 누름: 3초 동안 "확인?"
	confirmUntil = os.clock() + CONFIRM_SECONDS
	confirmToken += 1
	local token = confirmToken
	paintRebirthButton(true)
	task.delay(CONFIRM_SECONDS, function()
		if token == confirmToken then
			refreshRebirth(lastCoins)
		end
	end)
end

local function buildRebirth(): View
	local header = newHeader("Rebirth")
	local chips = chipRow(header)
	-- 지금: 환생 수 · 행운 배율 · 수입 배율
	rebirthCount = headerChip(chips, "rebirth", Theme.Ink, 1)
	rebirthLuck = headerChip(chips, "clover", "Grape", 2)
	rebirthIncome = headerChip(chips, "coin", "Grass", 3)

	local top = VIEWS.Rebirth.Top
	local scroller = newScroller("Rebirth", top)
	scroller.Size = UDim2.new(1, 0, 1, -(top + REBIRTH_FOOTER))

	-- 다음 환생 조건: 요구 명소 카드(체크) + 코인 막대
	rebirthSection = Ui.new("Frame", {
		Name = "Need",
		Size = UDim2.new(1, 0, 0, 100),
		BackgroundColor3 = Theme.Paper,
		Parent = scroller,
	})
	Ui.corner(14).Parent = rebirthSection
	Ui.stroke(Theme.Ink, 3).Parent = rebirthSection

	rebirthGrid = Ui.new("Frame", {
		Name = "Landmarks",
		Position = UDim2.fromOffset(SECTION_PAD, SECTION_PAD),
		Size = UDim2.new(1, -SECTION_PAD * 2, 0, 0),
		BackgroundTransparency = 1,
		Parent = rebirthSection,
	})
	Ui.new("UIGridLayout", {
		CellSize = UDim2.fromOffset(PASSPORT_CELL.X, PASSPORT_CELL.Y),
		CellPadding = UDim2.fromOffset(PASSPORT_GAP, PASSPORT_GAP),
		FillDirectionMaxCells = REBIRTH_COLUMNS,
		SortOrder = Enum.SortOrder.LayoutOrder,
		HorizontalAlignment = Enum.HorizontalAlignment.Center,
		Parent = rebirthGrid,
	})

	-- 코인 막대: [동전] 12.3K / 50K [체크]
	local bar = Ui.new("Frame", {
		Name = "Coins",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -SECTION_PAD),
		Size = UDim2.fromOffset(COIN_BAR.X, COIN_BAR.Y),
		BackgroundColor3 = Theme.Cream,
		Parent = rebirthSection,
	})
	Ui.round().Parent = bar
	Ui.stroke(Theme.Ink, 3).Parent = bar
	rebirthCoinFill = Ui.new("Frame", {
		Name = "Fill",
		Size = UDim2.fromScale(0, 1),
		BackgroundColor3 = Ui.colorPair("Sun").Face,
		BorderSizePixel = 0,
		Parent = bar,
	})
	Ui.round().Parent = rebirthCoinFill
	rebirthCoinText = Ui.label({
		Position = UDim2.fromOffset(34, 4),
		Size = UDim2.new(1, -68, 1, -8),
		TextColor3 = WHITE,
		ZIndex = 3,
		Parent = bar,
	}, 24)
	Ui.outline(rebirthCoinText, 2.5)
	Icons.view(bar, "coin", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0, 0, 0.5, 0),
		Size = UDim2.fromOffset(56, 56),
		ZIndex = 4,
	})
	-- 코인이 충분하면 오른쪽 끝에 체크 동그라미
	rebirthCoinCheck = Ui.new("Frame", {
		Name = "Check",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -2, 0.5, 0),
		Size = UDim2.fromOffset(40, 40),
		BackgroundColor3 = Theme.Cream,
		Visible = false,
		ZIndex = 4,
		Parent = bar,
	})
	Ui.round().Parent = rebirthCoinCheck
	Ui.stroke(Theme.Ink, 3).Parent = rebirthCoinCheck
	Icons.view(rebirthCoinCheck, "check", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.95, 0.95),
		ZIndex = 5,
	})

	-- 아래 고정 줄: [위 화살표][행운 +20%][수입 +50%] / [코인·강화 초기화]   [환생]
	local footer = Ui.new("Frame", {
		Name = "RebirthFooter",
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.fromScale(0, 1),
		Size = UDim2.new(1, 0, 0, REBIRTH_FOOTER),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = body,
	})
	local rewards = Ui.new("Frame", {
		Name = "Rewards",
		Position = UDim2.fromOffset(8, 10),
		Size = UDim2.new(1, -290, 0, 38),
		BackgroundTransparency = 1,
		Parent = footer,
	})
	Ui.list(Enum.FillDirection.Horizontal, 10).Parent = rewards
	Icons.view(rewards, "arrow_up", { Size = UDim2.fromOffset(38, 38), LayoutOrder = 1 })
	headerChip(rewards, "clover", "Grape", 2).Label.Text =
		string.format("+%d%%", math.floor(Perks.REBIRTH_LUCK * 100 + 0.5))
	headerChip(rewards, "coin", "Grass", 3).Label.Text =
		string.format("+%d%%", math.floor(Perks.REBIRTH_INCOME * 100 + 0.5))

	rebirthWarning = Ui.chip({
		Name = "Warning",
		Color = Theme.Ink,
		TextColor3 = Ui.colorPair("Coral").Face,
		Text = "코인·강화 초기화",
		Height = 30,
		TextSize = 17,
		Position = UDim2.fromOffset(12, 60),
		Parent = footer,
	})

	local button = Ui.chunkyButton({
		Name = "Rebirth",
		AnchorPoint = Vector2.new(1, 1),
		Position = UDim2.new(1, -6, 1, -6),
		Size = UDim2.fromOffset(260, 88),
		Color = "Gray",
		Icon = "rebirth",
		IconSize = 62,
		Text = "환생",
		TextSize = 36,
		OutlineThickness = 3,
		Parent = footer,
	})
	button.Activated:Connect(onRebirthPressed)
	rebirthButton = button
	rebirthLook = ""

	return { Scroller = scroller, Header = header, Extra = footer }
end

-- 요구 명소 카드: 보유 = 사진 + 체크 / 예전에 발견 = 어두운 사진 / 미발견 = 어두운 "?" (이름·확률은 늘 보임)
local function rebirthCard(parent: Frame, landmark: Landmark, look: string, order: number): Frame
	local tier = landmark.Tier
	local known = look ~= "unknown"
	local card = Ui.new("Frame", {
		Name = landmark.Id,
		LayoutOrder = order,
		BackgroundColor3 = if known then Theme.Cream else Theme.Ink,
	})
	Ui.corner(10).Parent = card
	Ui.stroke(Theme.Ink, 2.5).Parent = card

	if known then
		local picture = photo(card, landmark, UDim2.fromOffset(5, 5), UDim2.new(1, -10, 0, 68), 7)
		if look == "seen" then
			local shade = Ui.new("Frame", {
				Size = UDim2.fromScale(1, 1),
				BackgroundColor3 = Theme.Ink,
				BackgroundTransparency = 0.45,
				ZIndex = 2,
				Parent = picture,
			})
			Ui.corner(7).Parent = shade
		end
	else
		Ui.label({
			Position = UDim2.fromOffset(5, 5),
			Size = UDim2.new(1, -10, 0, 68),
			Font = Theme.FontTitle,
			Text = "?",
			TextColor3 = Theme.Paper,
			TextTransparency = 0.2,
			Parent = card,
		}, 50)
	end
	Ui.label({
		Position = UDim2.fromOffset(4, 77),
		Size = UDim2.new(1, -8, 0, 20),
		Text = landmark.Name,
		TextColor3 = if known then Theme.Ink else Theme.Paper,
		Parent = card,
	}, 16)
	Ui.label({
		Position = UDim2.fromOffset(4, 99),
		Size = UDim2.new(1, -8, 0, 17),
		Text = Format.oneIn(landmark.OneIn),
		TextColor3 = if known then tier.Color:Lerp(Theme.Ink, 0.45) else tier.Color,
		Parent = card,
	}, 14)

	-- 체크 동그라미 (오른쪽 위 모서리에 걸침): 보유 = 크림 + 초록 체크, 아니면 빈 어두운 동그라미
	local have = look == "owned"
	local mark = Ui.new("Frame", {
		Name = "Check",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -6, 0, 6),
		Size = UDim2.fromOffset(32, 32),
		BackgroundColor3 = if have then Theme.Cream else Theme.Ink,
		BackgroundTransparency = if have then 0 else 0.15,
		ZIndex = 4,
		Parent = card,
	})
	Ui.round().Parent = mark
	Ui.stroke(if have then Theme.Ink else Theme.Paper, 2.5).Parent = mark
	if have then
		Icons.view(mark, "check", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.95, 0.95),
			ZIndex = 5,
		})
	end

	card.Parent = parent
	return card
end

local function renderRebirth(state: Snapshot)
	local rebirths = Perks.rebirths(state)
	local luck, income = Perks.rebirthMults(rebirths)
	rebirthCount.Label.Text = Format.commas(rebirths)
	rebirthLuck.Label.Text = Ui.times(luck)
	rebirthIncome.Label.Text = Ui.times(income)
	-- 발견 기록(Discovered)이 따로 있으면 보유 명소도 초기화되는 규칙(DESIGN v3)
	rebirthWarning.Label.Text = if (state :: any).Discovered ~= nil
		then "코인·강화·명소 초기화"
		else "코인·강화 초기화"

	local need = Perks.rebirthNeed(state)
	local list = if need then need.Landmarks else {}
	local wanted: { [string]: boolean } = {}
	for order, id in list do
		wanted[id] = true
		local look = if owned(state, id) > 0 then "owned" elseif Perks.discovered(state, id) then "seen" else "unknown"
		local entry = rebirthCards[id]
		if not entry or entry.Look ~= look then
			if entry then
				entry.Card:Destroy()
			end
			entry = { Card = rebirthCard(rebirthGrid, Landmarks.ById[id], look, order), Look = look }
			rebirthCards[id] = entry
		end
		entry.Card.LayoutOrder = order
	end
	for id, entry in rebirthCards do
		if not wanted[id] then
			entry.Card:Destroy()
			rebirthCards[id] = nil
		end
	end

	local gridSize = gridHeight(#list, REBIRTH_COLUMNS, PASSPORT_CELL.Y, PASSPORT_GAP)
	rebirthGrid.Size = UDim2.new(1, -SECTION_PAD * 2, 0, gridSize)
	local height = SECTION_PAD + gridSize + (if gridSize > 0 then 14 else 0) + COIN_BAR.Y + SECTION_PAD
	rebirthSection.Size = UDim2.new(1, 0, 0, height)
	rebirthSection.Visible = need ~= nil
	setCanvasHeight(views.Rebirth.Scroller, height)
	refreshRebirth(lastCoins)
end

-- 상점 -----------------------------------------------------------------------

-- 효과 딱지 글자: ×2 / 굴림 간격 -30% / 코인 팩은 render 에서 "+12.3K"
local function effectText(item: Perks.Item): string
	local mult = item.Mult
	if not mult then
		return ""
	elseif mult < 1 then
		return string.format("-%d%%", math.floor((1 - mult) * 100 + 0.5))
	end
	return Ui.times(mult)
end

local function durationText(seconds: number): string
	if seconds % 60 == 0 then
		return string.format("%d분", seconds // 60)
	end
	return Format.duration(seconds)
end

-- 상품 카드: 색 띠 + 큰 아이콘 / 이름 / 효과 딱지(+시간) / 초록 "구매" 버튼 (게임패스를 가졌으면 "보유" 도장)
local function shopCard(parent: Frame, item: Perks.Item, order: number): ShopCard
	local pair = Ui.colorPair(item.Color)
	local card = Ui.new("Frame", {
		Name = item.Key,
		LayoutOrder = order,
		BackgroundColor3 = Theme.Paper,
	})
	Ui.corner(14).Parent = card
	Ui.stroke(Theme.Ink, 3).Parent = card

	-- 위쪽 모서리만 둥근 색 띠 (아래 절반은 네모 판으로 덮음)
	local band = Ui.new("Frame", {
		Name = "Band",
		Size = UDim2.new(1, 0, 0, SHOP_BAND),
		BackgroundColor3 = WHITE,
		BorderSizePixel = 0,
		Parent = card,
	})
	Ui.corner(14).Parent = band
	Ui.new("UIGradient", { Rotation = 90, Color = Ui.faceGradient(pair.Face), Parent = band })
	Ui.new("Frame", {
		Position = UDim2.new(0, 0, 1, -14),
		Size = UDim2.new(1, 0, 0, 14),
		BackgroundColor3 = pair.Face,
		BorderSizePixel = 0,
		Parent = band,
	})
	Ui.new("Frame", {
		Position = UDim2.fromScale(0, 1),
		Size = UDim2.new(1, 0, 0, 3),
		BackgroundColor3 = Theme.Ink,
		BorderSizePixel = 0,
		Parent = band,
	})
	Icons.view(band, item.Icon, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(62, 62),
		ZIndex = 2,
	})

	Ui.label({
		Position = UDim2.fromOffset(6, SHOP_BAND + 5),
		Size = UDim2.new(1, -12, 0, 24),
		Text = item.Name,
		Parent = card,
	}, 22)

	local chips = Ui.new("Frame", {
		Name = "Effects",
		Position = UDim2.fromOffset(0, SHOP_BAND + 32),
		Size = UDim2.new(1, 0, 0, 28),
		BackgroundTransparency = 1,
		Parent = card,
	})
	Ui.list(Enum.FillDirection.Horizontal, 8, Enum.HorizontalAlignment.Center).Parent = chips
	local effect = Ui.chip({
		Name = "Effect",
		Color = Theme.Ink,
		Icon = item.EffectIcon,
		IconSize = 32,
		Text = effectText(item),
		Height = 26,
		TextSize = 17,
		LayoutOrder = 1,
		Parent = chips,
	})
	local seconds = item.Seconds
	if item.Kind == "Product" and seconds then
		Ui.chip({
			Name = "Time",
			Color = Theme.Ink,
			Text = durationText(seconds),
			Height = 26,
			TextSize = 16,
			LayoutOrder = 2,
			Parent = chips,
		})
	end

	local button = Ui.chunkyButton({
		Name = "Buy",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -6),
		Size = UDim2.fromOffset(150, 52),
		Color = "Grass",
		Text = "구매",
		TextSize = 24,
		Parent = card,
	})
	local lastPress = -math.huge
	button.Activated:Connect(function()
		if os.clock() - lastPress < BUY_COOLDOWN then
			return
		end
		lastPress = os.clock()
		if item.Kind == "Pass" then
			if lastState and Perks.ownsPass(lastState, item.Key) then
				return
			end
			handlers.BuyPass(item.Key)
		else
			handlers.BuyProduct(item.Key)
		end
	end)

	local ownedStamp: Ui.Chip? = nil
	if item.Kind == "Pass" then
		ownedStamp = Ui.chip({
			Name = "Owned",
			Color = "Grass",
			Text = "보유",
			Font = Theme.FontTitle,
			Height = 40,
			TextSize = 24,
			CornerRadius = 8,
			StrokeThickness = 3,
			Rotation = -8,
			AnchorPoint = Vector2.new(0.5, 1),
			Position = UDim2.new(0.5, 0, 1, -12),
			ZIndex = 4,
			Visible = false,
			Parent = card,
		})
	end

	card.Parent = parent
	return { Item = item, Button = button, Effect = effect, Owned = ownedStamp }
end

local function buildShop(): View
	local header = newHeader("Shop") -- 비어 있음(모양을 맞추려고 둠)
	local scroller = newScroller("Shop", VIEWS.Shop.Top)
	local layout = Ui.list(Enum.FillDirection.Vertical, SECTION_GAP, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = scroller

	-- 윗줄: 게임패스(영구), 아랫줄: 개발자 상품(여러 번)
	local total = 0
	local sections = 0
	for _, group in { Perks.Passes, Perks.Products } do
		if #group == 0 then
			continue
		end
		sections += 1
		local height = gridHeight(#group, SHOP_COLUMNS, SHOP_CELL.Y, SHOP_GAP)
		local grid = Ui.new("Frame", {
			Name = if group == Perks.Passes then "Passes" else "Products",
			LayoutOrder = sections,
			Size = UDim2.new(1, 0, 0, height),
			BackgroundTransparency = 1,
			Parent = scroller,
		})
		Ui.new("UIGridLayout", {
			CellSize = UDim2.fromOffset(SHOP_CELL.X, SHOP_CELL.Y),
			CellPadding = UDim2.fromOffset(SHOP_GAP, SHOP_GAP),
			FillDirectionMaxCells = SHOP_COLUMNS,
			SortOrder = Enum.SortOrder.LayoutOrder,
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			Parent = grid,
		})
		for index, item in group do
			table.insert(shopCards, shopCard(grid, item, index))
		end
		total += height + (if sections > 1 then SECTION_GAP else 0)
	end
	setCanvasHeight(scroller, total)
	return { Scroller = scroller, Header = header }
end

local function renderShop(state: Snapshot)
	for _, entry in shopCards do
		local item = entry.Item
		local stamp = entry.Owned
		if stamp then
			local owns = Perks.ownsPass(state, item.Key)
			entry.Button.Root.Visible = not owns
			stamp.Root.Visible = owns
		elseif item.Key == "CoinPack" then
			entry.Effect.Label.Text = "+" .. Format.short(Perks.coinPackAmount(state.Income))
		end
	end
end

-- 공원 배치 ---------------------------------------------------------------------
-- 왼쪽: 공원을 위에서 본 6×6 격자(아래 = 입구, 칸 자리는 PlayerState.slotCell = 월드 받침대와 같음).
--   열린 칸 = 명소 사진(등급 색 바탕) / 빈 칸 "+", 잠긴 칸 = 회색 + 자물쇠, 고른 칸 = 굵은 Sun 테두리 + 1.1배.
-- 오른쪽: 고른 칸 줄(명소 이름 [빼기]) + 가진 명소 목록: 위 = 전시 안 된 명소(희귀한 순서), 구분 줄
--   [공원 전시 수], 아래 = 전시 중인 명소(칸 번호 순서, 오른쪽 초록 체크). 칸 번호 글자는 쓰지 않음.
-- 칸을 누르면 고르고, 명소를 누르면 고른 칸(없으면 첫 빈 칸)에 놓음. 이미 다른 칸에 있으면 자리를 바꿈.
-- 명소가 있는 칸을 고른 채 다른 칸을 누르면 그 칸으로 옮김(집어서 옮기기).
-- 누르는 즉시 PlayerState 규칙을 스냅샷 사본에 적용해 미리 보여 주고(parkPreview), 서버 응답이 오면 그 상태로 바꿈.
-- 요청마다 그 칸에 보이던 명소(expected)를 같이 보내서, 화면이 늦은 사이 서버에서 놓인 명소를 덮어쓰지 않음.

-- 잠긴 칸 자물쇠: 그림이 있으면 그림(3D 자물쇠는 칸이 많아 무거우니 쓰지 않음), 없으면 Frame 으로 그림.
-- 잠긴 칸은 많게는 30개라 작고 흐리게(열린 칸·명소가 눈에 먼저 들어오게)
local function lockGlyph(parent: GuiObject): GuiObject
	if Icons.imageId("lock") then
		return Icons.view(parent, "lock", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.44, 0.44),
			Transparency = 0.5,
			ZIndex = 3,
		})
	end
	-- 그림이 없을 때: 고리(테두리만 있는 동그라미) + 몸통(Ink 네모)
	local glyph = Ui.new("Frame", {
		Name = "Lock",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.32, 0.36),
		BackgroundTransparency = 1,
		ZIndex = 3,
		Parent = parent,
	})
	local ring = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.fromScale(0.5, 0),
		Size = UDim2.fromScale(0.7, 0.6),
		BackgroundTransparency = 1,
		ZIndex = 3,
		Parent = glyph,
	})
	Ui.round().Parent = ring
	Ui.stroke(Theme.Ink, 3, 0.3).Parent = ring
	local lockBody = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.fromScale(0.5, 1),
		Size = UDim2.fromScale(1, 0.58),
		BackgroundColor3 = Theme.Ink,
		BackgroundTransparency = 0.3,
		ZIndex = 4,
		Parent = glyph,
	})
	Ui.corner(4).Parent = lockBody
	return glyph
end

-- 칸의 평소 크기 배율(고른 칸 1.1, 집어 든 칸 1.2, 마우스를 올린 칸 1.06)
local function tileScale(tile: ParkTile): number
	if tile.Picked then
		return if tile.Carried then PARK_CARRY_SCALE else PARK_PICKED_SCALE
	end
	return if tile.Hovered then 1.06 else 1
end

local function sizeTile(tile: ParkTile)
	tile.Scale.Scale = tileScale(tile)
end

local function parkTile(parent: Frame, slot: number): ParkTile
	local row, column = PlayerState.slotCell(slot)
	local step = PARK_TILE + PARK_GAP
	local button = Ui.new("TextButton", {
		Name = "Slot" .. slot,
		Text = "",
		AutoButtonColor = false,
		-- 가운데 기준(AnchorPoint 0.5) -> UIScale 로 커질 때 네 방향으로 고르게
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset(
			PARK_PAD + (column - 1) * step + PARK_TILE / 2,
			PARK_PAD + (Config.PARK_GRID - row) * step + PARK_TILE / 2
		),
		Size = UDim2.fromOffset(PARK_TILE, PARK_TILE),
		BackgroundColor3 = Theme.Cream,
		ZIndex = 1,
	})
	Ui.corner(10).Parent = button
	local stroke = Ui.stroke(Theme.Ink, 2.5)
	stroke.Parent = button
	-- 빈 칸: 초록 "+" (눌러서 채우는 칸)
	local plus = Ui.label({
		Name = "Plus",
		Size = UDim2.fromScale(1, 1),
		Font = Theme.FontTitle,
		Text = "+",
		TextColor3 = Ui.colorPair("Grass").Face,
		Visible = false,
		ZIndex = 2,
		Parent = button,
	}, 40)
	Ui.outline(plus, 2)
	local lock = lockGlyph(button)
	lock.Visible = false
	local tile: ParkTile = {
		Button = button,
		Stroke = stroke,
		Scale = Ui.new("UIScale", { Parent = button }),
		Plus = plus,
		Lock = lock,
		View = nil,
		Look = "",
		Picked = false,
		Carried = false,
		Hovered = false,
	}
	button.MouseEnter:Connect(function()
		tile.Hovered = true
		sizeTile(tile)
	end)
	button.MouseLeave:Connect(function()
		tile.Hovered = false
		sizeTile(tile)
	end)
	button.Activated:Connect(function()
		selectParkSlot(slot)
	end)
	button.Parent = parent
	return tile
end

-- 칸 모양(Look = "locked" | "empty" | 명소 Id) 바꾸기, 바뀐 칸만. 명소 사진은 처음 필요할 때 ViewportFrame 하나를 만들고 그 뒤로는 모형만 바꿈
local function paintTile(tile: ParkTile, look: string)
	if tile.Look == look then
		return
	end
	tile.Look = look
	local landmark = Landmarks.ById[look]
	tile.Plus.Visible = look == "empty"
	tile.Lock.Visible = look == "locked"
	if landmark then
		tile.Button.BackgroundColor3 = landmark.Tier.Color:Lerp(WHITE, 0.55)
		tile.Button.BackgroundTransparency = 0
		tile.Stroke.Transparency = 0
		local view = tile.View
		if not view then
			view = Viewport.new(tile.Button, {
				Position = UDim2.fromOffset(2, 2),
				Size = UDim2.new(1, -4, 1, -4),
				ZIndex = 2,
			})
			tile.View = view
		end
		local vf = view :: ViewportFrame
		vf.Visible = true
		Viewport.setLandmark(vf, landmark, 10)
	else
		-- 잠긴 칸: 흐린 회색 + 흐린 테두리(격자 모양만 보이게)
		tile.Button.BackgroundColor3 = if look == "locked" then DIM_CHIP else Theme.Cream
		tile.Button.BackgroundTransparency = if look == "locked" then 0.55 else 0
		tile.Stroke.Transparency = if look == "locked" then 0.6 else 0
		local view = tile.View
		if view then
			view.Visible = false
			Viewport.setModel(view, nil)
		end
	end
end

-- 명소 목록 한 줄: 사진 · 이름(고정 크기, 길면 두 줄) · 별 · (전시 중이면) 오른쪽 초록 체크.
-- 사진(ViewportFrame)은 줄이 스크롤 영역에 들어올 때 처음 만듦(loadParkThumbs) — 명소가 많아도 창을 여는 게 가벼움
local function parkCard(parent: ScrollingFrame, landmark: Landmark): ParkCard
	local card = Ui.new("TextButton", {
		Name = landmark.Id,
		Text = "",
		AutoButtonColor = false,
		Size = UDim2.new(1, 0, 0, PARK_ROW),
		BackgroundColor3 = Theme.Paper,
	})
	Ui.corner(12).Parent = card
	local stroke = Ui.stroke(Theme.Ink, 3)
	stroke.Parent = card
	local picture =
		photo(card, landmark, UDim2.fromOffset(6, 6), UDim2.fromOffset(PARK_ROW - 12, PARK_ROW - 12), 8, true)
	-- 이름: 글자 크기는 그대로 두고 길면 두 줄. 한 줄이면 별 바로 위에 붙게 아래 정렬
	local name = Ui.label({
		Name = "Name",
		Position = UDim2.fromOffset(PARK_NAME_X, 3),
		Size = UDim2.new(1, -(PARK_NAME_X + 8), 0, 44),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Bottom,
		TextScaled = false,
		TextSize = PARK_NAME_TEXT,
		TextWrapped = true,
		TextTruncate = Enum.TextTruncate.AtEnd,
		LineHeight = 0.95,
		Text = landmark.Name,
		Parent = card,
	}, PARK_NAME_TEXT)
	local stars = Ui.label({
		Name = "Stars",
		Position = UDim2.fromOffset(PARK_NAME_X, 48),
		Size = UDim2.fromOffset(130, 22),
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = card,
	}, 20)
	Ui.outline(stars, 2)
	-- 전시 중: 도감 카드와 같은 아이콘만 있는 초록 딱지(체크)
	local mark = Ui.chip({
		Name = "Shown",
		Color = "Grass",
		Icon = "check",
		IconOnly = true,
		IconSize = 36,
		Height = 30,
		StrokeThickness = 2,
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -10, 0.5, 0),
		ZIndex = 3,
		Visible = false,
		Parent = card,
	})
	local hover = Ui.new("UIScale", { Parent = card })
	card.MouseEnter:Connect(function()
		hover.Scale = 1.03
	end)
	card.MouseLeave:Connect(function()
		hover.Scale = 1
	end)
	card.Activated:Connect(function()
		placeInPark(landmark.Id)
	end)
	card.Parent = parent
	return {
		Card = card,
		Stroke = stroke,
		Photo = picture,
		Thumb = nil,
		Name = name,
		Stars = stars,
		Mark = mark,
		Landmark = landmark,
		Y = 0,
	}
end

-- 목록 가운데 구분 줄: 가는 선 + 가운데 [공원 아이콘 전시 수] 딱지. 위 = 전시 안 된 명소, 아래 = 전시 중(칸 순서)
local function buildParkDivider(scroller: ScrollingFrame)
	parkDivider = Ui.new("Frame", {
		Name = "Divider",
		Size = UDim2.new(1, 0, 0, PARK_DIVIDER),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = scroller,
	})
	Ui.new("Frame", {
		Name = "Line",
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 6, 0.5, 0),
		Size = UDim2.new(1, -12, 0, 3),
		BackgroundColor3 = Theme.Ink,
		BackgroundTransparency = 0.72,
		BorderSizePixel = 0,
		Parent = parkDivider,
	})
	parkDividerChip = Ui.chip({
		Name = "Shown",
		Color = "Grass",
		Icon = "park",
		IconSize = 34,
		Height = 26,
		TextSize = 17,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		ZIndex = 2,
		Parent = parkDivider,
	})
end

-- 가진 명소가 없을 때(처음 굴리기 전 · 환생 직후) 목록 자리: 천천히 도는 지구본 + 작은 "굴리기" 딱지 (도감과 같은 지구본)
local function buildParkEmpty(): Frame
	local frame = Ui.new("Frame", {
		Name = "ParkEmpty",
		Position = UDim2.fromOffset(PARK_SIDE_X, VIEWS.Park.Top),
		Size = UDim2.new(1, -PARK_SIDE_X, 1, -VIEWS.Park.Top),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = body,
	})
	Icons.view(frame, "globe", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0.5, -22),
		Size = UDim2.fromOffset(124, 124),
		Spin = 40,
		Transparency = 0.2,
	})
	Ui.chip({
		Name = "Roll",
		Color = "Grass",
		Text = "굴리기",
		Height = 32,
		TextSize = 20,
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0.5, 50),
		Parent = frame,
	})
	return frame
end

local function buildPark(): View
	local header = newHeader("Park")
	local chips = chipRow(header)
	parkCount = headerChip(chips, "park", Theme.Ink, 1) -- 전시 수 / 열린 칸 수
	parkIncome = headerChip(chips, "coin", "Grass", 2) -- 이 배치의 초당 수입

	-- 자동 배치: 시상대 아이콘(가장 희귀한 명소가 입구부터 = 1·2·3등) + "자동". 켜짐 = 초록 + ON 딱지, 꺼짐 = 회색.
	-- 가운데 기준(AnchorPoint 0.5) — 자동 배치가 꺼질 때 통통 튀는(pulse) 크기 변화가 네 방향으로 고르게
	parkAuto = Ui.chunkyButton({
		Name = "AutoPark",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -(8 + 68), 0, -4 + 25),
		Size = UDim2.fromOffset(136, 50),
		Color = "Gray",
		Icon = "podium",
		IconSize = 36,
		Text = "자동",
		TextSize = 22,
		Parent = header,
	})
	parkAuto.Activated:Connect(function()
		toggleAutoPark()
	end)
	parkAutoBadge = Ui.chip({
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
		Parent = parkAuto.Face,
	})

	-- 창 본문에 붙는 부분(격자 + 고른 칸 줄)을 묶는 투명 틀. 틀 자체는 머리 줄 아래 고른 칸 줄 높이만 차지해서
	-- 머리 줄 버튼·오른쪽 스크롤 목록 위를 덮지 않음(격자는 틀 아래로 삐져나오지만 목록과는 옆으로 떨어져 있음)
	local board = Ui.new("Frame", {
		Name = "ParkBoard",
		Position = UDim2.fromOffset(0, HEADER_HEIGHT),
		Size = UDim2.new(1, 0, 0, PARK_BAR),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = body,
	})

	-- 공원 잔디 + 격자
	local lawn = Ui.new("Frame", {
		Name = "Lawn",
		Position = UDim2.fromOffset(0, 0),
		Size = UDim2.fromOffset(PARK_LAWN, PARK_LAWN),
		BackgroundColor3 = Ui.colorPair("Grass").Face:Lerp(WHITE, 0.6),
		Parent = board,
	})
	Ui.corner(14).Parent = lawn
	Ui.stroke(Theme.Ink, 3).Parent = lawn
	for slot = 1, PlayerState.MAX_SLOTS do
		parkTiles[slot] = parkTile(lawn, slot)
	end
	-- 입구 표시(아래 가운데, 위 화살표 = 공원 안쪽)
	Ui.chip({
		Name = "Entrance",
		Color = Theme.Ink,
		Icon = "arrow_up",
		IconSize = 30,
		Text = "입구",
		Height = 26,
		TextSize = 16,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 1, 2),
		ZIndex = 4,
		Parent = lawn,
	})

	-- 고른 칸 줄: 명소 이름(또는 빈 칸 / 칸 선택 — 고정 크기, 길면 두 줄) + 오른쪽 [빼기]
	local bar = Ui.new("Frame", {
		Name = "Selected",
		Position = UDim2.fromOffset(PARK_SIDE_X, 0),
		Size = UDim2.new(1, -PARK_SIDE_X, 0, PARK_BAR),
		BackgroundColor3 = Theme.Paper,
		Parent = board,
	})
	Ui.corner(12).Parent = bar
	Ui.stroke(Theme.Ink, 3).Parent = bar
	parkSlotLabel = Ui.label({
		Name = "Name",
		Position = UDim2.fromOffset(14, 6),
		Size = UDim2.new(1, -(14 + PARK_REMOVE_W + 16), 1, -12),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextScaled = false,
		TextSize = PARK_BAR_TEXT,
		TextWrapped = true,
		TextTruncate = Enum.TextTruncate.AtEnd,
		LineHeight = 0.95,
		Parent = bar,
	}, PARK_BAR_TEXT)
	parkRemove = Ui.chunkyButton({
		Name = "Remove",
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -8, 0.5, 0),
		Size = UDim2.fromOffset(PARK_REMOVE_W, 79),
		Color = "Gray",
		Text = "빼기",
		TextSize = 28,
		Parent = bar,
	})
	parkRemove.Activated:Connect(function()
		removeFromPark()
	end)

	local scroller = newScroller("Park", VIEWS.Park.Top)
	scroller.Position = UDim2.fromOffset(PARK_SIDE_X, VIEWS.Park.Top)
	scroller.Size = UDim2.new(1, -PARK_SIDE_X, 1, -VIEWS.Park.Top)
	local layout = Ui.list(Enum.FillDirection.Vertical, PARK_ROW_GAP, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = scroller
	buildParkDivider(scroller)
	parkEmpty = buildParkEmpty()
	-- 스크롤하면 새로 보이는 줄의 사진을 만듦
	scroller:GetPropertyChangedSignal("CanvasPosition"):Connect(function()
		loadParkThumbs()
	end)
	scroller:GetPropertyChangedSignal("AbsoluteWindowSize"):Connect(function()
		loadParkThumbs()
	end)
	return { Scroller = scroller, Header = header, Extra = board }
end

-- 목록에서 지금 보이는 범위(스크롤 캔버스 좌표, 설계 px): 위 끝, 높이.
-- CanvasPosition·AbsoluteWindowSize 는 화면 px(창 UIScale = Ui.scale() 이 곱해진 값)라서 배율로 나눔
local function parkWindow(): (number, number)
	local scroller = views.Park.Scroller
	local k = math.max(0.01, Ui.scale())
	local height = scroller.AbsoluteWindowSize.Y / k
	if height <= 1 then
		height = BODY_HEIGHT - VIEWS.Park.Top -- 아직 화면에 안 붙음(처음 여는 프레임)
	end
	return scroller.CanvasPosition.Y / k, height
end

-- 보이는 줄(위아래 한 줄 여유)만 사진(ViewportFrame)을 만듦. 한 번 만든 사진은 그대로 둠
function loadParkThumbs()
	local built = views.Park
	if not built or openName ~= "Park" then
		return
	end
	local top, height = parkWindow()
	for _, card in parkCards do
		if not card.Thumb then
			local y = PAD_Y + card.Y
			if y + PARK_ROW >= top - PARK_ROW and y <= top + height + PARK_ROW then
				card.Thumb = Viewport.thumbnail(card.Photo, card.Landmark, THUMB_PROPS)
			end
		end
	end
end

-- 목록을 y(목록 안 위치) ~ y + height 가 보이게 스크롤(이미 보이면 그대로). 부드럽게 미끄러짐
local function scrollParkTo(y: number, height: number)
	local scroller = views.Park.Scroller
	local top, window = parkWindow()
	local rowTop = PAD_Y + y
	local target = top
	if rowTop < top then
		target = rowTop - PARK_ROW_GAP
	elseif rowTop + height > top + window then
		target = rowTop + height - window + PARK_ROW_GAP
	end
	target = math.clamp(target, 0, math.max(0, scroller.CanvasSize.Y.Offset - window))
	if math.abs(target - top) < 1 then
		return
	end
	TweenService:Create(scroller, TweenInfo.new(0.22, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		CanvasPosition = Vector2.new(0, target * Ui.scale()),
	}):Play()
end

-- 지금 화면에 보여 줄 공원 상태: 응답을 기다리는 편집이 있으면 미리 보기, 아니면 서버 상태
local function parkState(): Snapshot?
	return parkPreview or lastState
end

-- 스냅샷 사본(배치에 필요한 필드만 새 표)에 편집을 적용해서 미리 보기로. 규칙에 맞지 않으면 false
local function previewPark(edit: (any) -> boolean): boolean
	local base = parkState()
	if not base then
		return false
	end
	local copy = table.clone(base) :: any
	copy.Settings = table.clone(base.Settings)
	copy.Display = table.clone((base :: any).Display or {})
	if not edit(copy) then
		return false
	end
	copy.Income = PlayerState.incomePerSecond(copy, copy)
	parkPreview = copy
	parkPending += 1
	return true
end

-- 자동 배치를 켜면 지금 배치가 바뀌는지 (바뀌면 "확인?" 을 한 번 더 받음)
local function autoWouldChange(state: Snapshot): boolean
	local slots, unlocked = PlayerState.parkSlots(state)
	local auto = table.clone(state) :: any
	auto.Settings = table.clone(state.Settings)
	auto.Settings.AutoPark = true
	local best = PlayerState.parkSlots(auto)
	for slot = 1, unlocked do
		if slots[slot] ~= best[slot] then
			return true
		end
	end
	return false
end

local function paintParkAuto(state: Snapshot)
	local on = state.Settings.AutoPark ~= false
	local confirming = not on and os.clock() < parkConfirmUntil
	parkAuto.SetColor(if on then "Grass" elseif confirming then "Sun" else "Gray")
	parkAuto.SetText(if confirming then "확인?" else "자동")
	parkAutoBadge.Root.Visible = on
end

-- 목록 한 줄 칠하기. slot = 전시 중인 칸(nil = 전시 안 됨)
local function paintParkCard(card: ParkCard, state: Snapshot, slot: number?, selected: number?)
	-- 고른 칸의 명소 줄 = 노란 바탕 + 굵은 Sun 테두리(격자의 고른 칸과 같은 표시 — 목록이 그 줄로 미끄러져 와도 한눈에)
	local picked = slot ~= nil and slot == selected
	card.Card.BackgroundColor3 = if picked then FEATURED_BG else Theme.Paper
	card.Stroke.Color = if picked then Ui.colorPair("Sun").Face else Theme.Ink
	card.Stroke.Thickness = if picked then 4 else 3
	card.Stars.Text = Ui.starsRich(PlayerState.stars(owned(state, card.Landmark.Id)), #Config.STAR_THRESHOLDS)
	card.Mark.Root.Visible = slot ~= nil
	-- 전시 안 된 줄은 이름이 줄 끝까지, 전시 중인 줄은 체크 자리만큼 비움
	card.Name.Size = UDim2.new(1, -(PARK_NAME_X + 8 + (if slot then PARK_MARK_W else 0)), 0, 44)
end

local function renderPark(real: Snapshot)
	local state = parkPreview or real
	local slots, unlocked = PlayerState.parkSlots(state)
	local selected = parkSelected
	if selected and (selected < 1 or selected > unlocked) then
		selected = nil
		parkSelected = nil
	end
	-- 명소가 있는 칸을 골랐으면 "들고 있는" 상태: 다른 열린 칸이 놓을 자리(얇은 Sun 테두리)
	local carrying = selected ~= nil and slots[selected] ~= nil

	-- 격자
	local shown = 0
	local sun = Ui.colorPair("Sun").Face
	for slot, tile in parkTiles do
		local id = slots[slot]
		if id then
			shown += 1
		end
		paintTile(tile, if id then id elseif slot <= unlocked then "empty" else "locked")
		local picked = slot == selected
		local target = carrying and not picked and slot <= unlocked
		tile.Stroke.Color = if picked or target then sun else Theme.Ink
		tile.Stroke.Thickness = if picked then 5 elseif target then 3 else 2.5
		tile.Button.ZIndex = if picked then 2 else 1
		tile.Picked = picked
		tile.Carried = picked and carrying
		sizeTile(tile)
	end

	-- 머리 줄: 전시 수 / 열린 칸 수 · 초당 수입 · 자동 배치
	parkCount.Label.Text = string.format("%d/%d", shown, unlocked)
	parkIncome.Label.Text = "+" .. incomeText(PlayerState.incomePerSecond(state, state)) .. "/s"
	paintParkAuto(state)

	-- 고른 칸 줄
	local selectedId = if selected then slots[selected] else nil
	local selectedLandmark = if selectedId then Landmarks.ById[selectedId] else nil
	parkSlotLabel.Text = if selectedLandmark then selectedLandmark.Name elseif selected then "빈 칸" else "칸 선택"
	parkSlotLabel.TextTransparency = if selectedLandmark then 0 else 0.45
	parkRemove.SetColor(if selectedLandmark then "Coral" else "Gray")

	-- 가진 명소 목록: 위 = 전시 안 된 명소(희귀한 순서), 구분 줄, 아래 = 전시 중인 명소(칸 번호 순서)
	local scroller = views.Park.Scroller
	local order = 0
	local y = 0
	local function place(card: ParkCard)
		order += 1
		card.Card.LayoutOrder = order
		card.Y = y
		y += PARK_ROW + PARK_ROW_GAP
	end
	local function cardFor(landmark: Landmark): ParkCard
		local card = parkCards[landmark.Id]
		if not card then
			card = parkCard(scroller, landmark)
			parkCards[landmark.Id] = card
		end
		return card :: ParkCard
	end
	local count = 0
	local inPark: { [string]: boolean } = {}
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			inPark[id] = true
		end
	end
	for _, landmark in Landmarks.RarestFirst do
		if owned(state, landmark.Id) > 0 then
			count += 1
			if not inPark[landmark.Id] then
				local card = cardFor(landmark)
				place(card)
				paintParkCard(card, state, nil, selected)
			end
		else
			local card = parkCards[landmark.Id]
			if card then
				card.Card:Destroy()
				parkCards[landmark.Id] = nil
			end
		end
	end
	parkDivider.Visible = shown > 0
	if shown > 0 then
		order += 1
		parkDivider.LayoutOrder = order
		parkDividerChip.Label.Text = tostring(shown)
		y += PARK_DIVIDER + PARK_ROW_GAP
	end
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			local card = cardFor(Landmarks.ById[id])
			place(card)
			paintParkCard(card, state, slot, selected)
		end
	end
	setCanvasHeight(scroller, math.max(0, y - PARK_ROW_GAP))
	local empty = parkEmpty
	if empty then
		empty.Visible = count == 0
	end

	-- 고른 칸이 바뀌었으면 그 명소 줄로(빈 칸이면 맨 위 = 놓을 수 있는 명소들) 스크롤
	if parkWantScroll then
		parkWantScroll = false
		local card = if selectedId then parkCards[selectedId] else nil
		if card then
			scrollParkTo(card.Y, PARK_ROW)
		elseif selected then
			scrollParkTo(0, PARK_ROW)
		end
	end
	loadParkThumbs()
	task.defer(loadParkThumbs) -- 처음 여는 프레임에는 목록 크기가 아직 0 일 수 있음
end

-- 공원 배치 창이 열려 있으면 다시 그림
local function refreshPark()
	if openName == "Park" and lastState then
		renderPark(lastState)
	end
end

-- 칸이 톡 튀어 오름(옮긴 두 칸)
local function popTile(slot: number)
	local tile = parkTiles[slot]
	if not tile then
		return
	end
	tile.Scale.Scale = 1.28
	TweenService:Create(tile.Scale, TweenInfo.new(0.3, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {
		Scale = tileScale(tile),
	}):Play()
end

-- 배치 편집으로 자동 배치가 꺼짐: 자동 버튼이 통통 튀고, 이번 접속에서 처음이면 "자동 꺼짐" 알림(시상대 아이콘, 중립 색)
local function noticeAutoOff()
	pulse(parkAuto.Root)
	if not parkAutoNoticed then
		parkAutoNoticed = true
		handlers.Toast("자동 꺼짐", "podium", Theme.Ink)
	end
end

-- 칸에 명소 놓기(id)/빼기(nil)를 미리 보여 주고 서버에 보냄. expected = 지금 화면에서 그 칸에 보이는 것 —
-- 서버 쪽이 그사이 바뀌었으면(예: 자동 굴림이 빈 칸에 새 명소를 놓음) 서버가 "stale" 로 거절하고 새 상태를 줌
local function sendPlacement(slot: number, id: string?): boolean
	local state = parkState()
	if not state then
		return false
	end
	local slots, unlocked = PlayerState.parkSlots(state)
	local expected = slots[slot] or ""
	-- 옮기는 명소가 지금 화면에서 있는 칸(0 = 전시 안 됨). 서버에서 그사이 밀려났으면 stale
	local from: number? = nil
	if id then
		from = 0
		for s = 1, unlocked do
			if slots[s] == id then
				from = s
				break
			end
		end
	end
	if not previewPark(function(copy)
		return (PlayerState.setDisplay(copy, slot, id, expected, from))
	end) then
		return false
	end
	if state.Settings.AutoPark ~= false then
		parkAutoFlip = true -- 알림은 서버가 받아들인 뒤(Panels.parkDone)에만
	end
	handlers.SetDisplay(slot, id, expected, from)
	return true
end

-- 칸 누름. 잠긴 칸은 알림만. 같은 칸 = 고르기 해제.
-- 명소가 있는 칸을 고른 채로 다른 열린 칸을 누르면 집어서 옮기기: 그 칸으로 옮김(명소가 있으면 자리 바꿈),
-- 고른 칸은 해제하고 두 칸이 톡 튐. 빈 칸을 고른 채면 고른 칸만 옮겨 감
function selectParkSlot(slot: number)
	local state = parkState()
	if not state then
		return
	end
	local slots, unlocked = PlayerState.parkSlots(state)
	if slot > unlocked then
		handlers.Toast("공원 확장", "lock") -- 강화의 공원 확장으로 열림
		return
	end
	local picked = parkSelected
	local carried = if picked then slots[picked] else nil
	if picked == slot then
		parkSelected = nil
	elseif picked and carried then
		parkSelected = nil
		local moved = sendPlacement(slot, carried)
		refreshPark()
		if moved then
			popTile(picked)
			popTile(slot)
		end
		return
	else
		parkSelected = slot
		parkWantScroll = true
	end
	refreshPark()
end

-- 명소 누름: 고른 칸에 놓음(고른 칸은 그대로 골라진 채 — 다른 명소를 눌러 바로 바꿔 볼 수 있음).
-- 고른 칸이 없으면 첫 빈 칸에 놓음
function placeInPark(id: string)
	local state = parkState()
	if not state then
		return
	end
	local slots, unlocked = PlayerState.parkSlots(state)
	local target = parkSelected
	if not target then
		-- 고른 칸이 없을 때: 이미 전시 중인 명소면 그 칸을 골라 보여 주기만, 아니면 첫 빈 칸에 놓음.
		-- (고른 칸은 그대로 비워 둬서 명소를 연달아 누르면 빈 칸이 차례로 참)
		for slot = 1, unlocked do
			if slots[slot] == id then
				parkSelected = slot
				parkWantScroll = true
				refreshPark()
				return
			end
		end
		for slot = 1, unlocked do
			if not slots[slot] then
				target = slot
				break
			end
		end
	end
	if not target then
		handlers.Toast("칸 선택", "park") -- 빈 칸이 없으면 바꿀 칸을 먼저 골라야 함
		return
	end
	local slot = target :: number
	local moved = slots[slot] ~= id and sendPlacement(slot, id)
	refreshPark()
	if moved then
		popTile(slot)
	end
end

-- 빼기: 고른 칸을 비움
function removeFromPark()
	local state = parkState()
	local slot = parkSelected
	if not state or not slot then
		return
	end
	local slots = PlayerState.parkSlots(state)
	if slots[slot] and sendPlacement(slot, nil) then
		refreshPark()
	end
end

-- 자동 배치 켜기/끄기. 끄면 지금 배치 그대로(화면 안 바뀜). 켜서 직접 고른 배치가 바뀌면 3초 안에 한 번 더 눌러야 함
function toggleAutoPark()
	local state = parkState()
	if not state then
		return
	end
	local on = state.Settings.AutoPark ~= false
	if not on and os.clock() >= parkConfirmUntil and autoWouldChange(state) then
		parkConfirmUntil = os.clock() + CONFIRM_SECONDS
		parkConfirmToken += 1
		local token = parkConfirmToken
		paintParkAuto(state)
		task.delay(CONFIRM_SECONDS, function()
			if token == parkConfirmToken then
				refreshPark()
			end
		end)
		return
	end
	parkConfirmUntil = 0
	parkConfirmToken += 1
	local want = not on
	if previewPark(function(copy)
		PlayerState.setAutoPark(copy, want)
		return true
	end) then
		handlers.SetAutoPark(want)
	end
	refreshPark()
end

-- 공통 -----------------------------------------------------------------------

local BUILDERS = {
	Collection = buildCollection,
	Passport = buildPassport,
	Upgrade = buildUpgrade,
	Rebirth = buildRebirth,
	Shop = buildShop,
	Park = buildPark,
}

local RENDERERS = {
	Collection = renderCollection,
	Passport = renderPassport,
	Upgrade = renderUpgrade,
	Rebirth = renderRebirth,
	Shop = renderShop,
	Park = renderPark,
}

local function showView(built: View, visible: boolean)
	built.Scroller.Visible = visible
	built.Header.Visible = visible
	local extra = built.Extra
	if extra then
		extra.Visible = visible
	end
end

local function render()
	local name = openName
	if not name then
		return
	end
	local view = VIEWS[name]
	win.SetColor(view.Color)
	win.Title.Text = view.Title
	if emptyIcon then
		emptyIcon.Visible = false
	end
	if parkEmpty then
		parkEmpty.Visible = false
	end

	for other, built in views do
		showView(built, other == name)
	end

	local state = lastState
	loadingLabel.Visible = state == nil
	if not state then
		return
	end

	local built = views[name]
	if not built then
		built = BUILDERS[name]()
		views[name] = built
	end
	showView(built, true)
	RENDERERS[name](state)
end

function Panels.init(parent: ScreenGui, callbacks: Handlers)
	handlers = callbacks

	win = Ui.window({
		Name = "Window",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0.5, OPEN_OFFSET),
		Size = UDim2.fromOffset(WINDOW_SIZE.X, WINDOW_SIZE.Y),
		Color = "Sky",
		RibbonWidth = 220,
		ZIndex = 5,
		Visible = false,
		Parent = parent,
	})
	window = win.Root
	body = win.Body
	Ui.autoScale(window)
	win.Close.Activated:Connect(Panels.close)

	-- 서버 데이터를 받기 전
	loadingLabel = Ui.label({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.new(1, 0, 0, 60),
		Font = Theme.FontTitle,
		Text = "...",
		TextTransparency = 0.3,
		Visible = false,
		Parent = body,
	}, 56)
end

-- 같은 창 버튼을 다시 누르면 닫힘
function Panels.toggle(name: string)
	if not VIEWS[name] or (name == "Shop" and not Perks.anyForSale()) then
		return
	end
	if openName == name then
		Panels.close()
		return
	end
	local wasOpen = window.Visible
	openName = name
	window.Visible = true
	if not wasOpen then
		-- 아래에서 톡 튀어 오르며 열림
		window.Position = UDim2.new(0.5, 0, 0.5, OPEN_OFFSET + 40)
		TweenService:Create(window, TweenInfo.new(0.25, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {
			Position = UDim2.new(0.5, 0, 0.5, OPEN_OFFSET),
		}):Play()
	end
	render()
end

function Panels.close()
	openName = nil
	window.Visible = false
	confirmUntil = 0 -- 닫으면 환생 "확인?" 도 취소
	confirmToken += 1
	parkSelected = nil -- 공원 배치: 고른 칸 · 자동 배치 "확인?" 취소
	parkConfirmUntil = 0
	parkConfirmToken += 1
end

-- 공원 배치 창 열기. slot: 공원 받침대를 눌러 열었으면 그 칸을 골라 둠(nil 이면 고른 칸 없음).
-- 목록은 그 칸의 명소 줄로(빈 칸이거나 고른 칸이 없으면 맨 위) 스크롤
function Panels.openPark(slot: number?)
	parkSelected = if type(slot) == "number" and slot % 1 == 0 then slot else nil
	parkWantScroll = true
	local built = views.Park
	if not parkSelected and built then
		built.Scroller.CanvasPosition = Vector2.zero
	end
	if openName == "Park" then
		refreshPark()
	else
		Panels.toggle("Park")
	end
end

-- 배치 요청(SetDisplay / 자동 배치 설정)의 응답을 받은 뒤(성공·실패 모두) 부름.
-- 기다리는 요청이 더 없으면 미리 보기를 버리고 서버 상태(Panels.render 로 받은 값)로 그림.
-- stale(서버가 "화면이 늦음" 으로 거절)이면 기다리는 요청이 있어도 미리 보기를 바로 버림(새 서버 상태로 다시 그림).
-- ok: 서버가 편집을 받아들였는지. 자동 배치 중 보낸 편집이 받아들여져 자동이 꺼졌을 때만 "자동 꺼짐" 알림
function Panels.parkDone(stale: boolean?, ok: boolean?)
	if parkAutoFlip and ok and lastState and lastState.Settings.AutoPark == false then
		noticeAutoOff()
	end
	if ok ~= nil then
		parkAutoFlip = false
	end
	parkPending = math.max(0, parkPending - 1)
	if parkPending == 0 or stale then
		parkPreview = nil
		refreshPark()
	end
end

-- 서버 상태가 실제로 바뀌었을 때만 호출됨 (열린 화면만 갱신, 나머지는 열 때 갱신)
function Panels.render(state: Snapshot?)
	lastState = state
	if state then
		lastCoins = state.Coins -- 곧 refreshCoins 가 부드러운 값으로 덮어씀
	end
	render()
end

-- 자주 호출해도 되는 가벼운 갱신: 업그레이드 버튼의 "살 수 있음" 색 / 환생 코인 막대·버튼만 다시 칠함
function Panels.refreshCoins(coins: number)
	lastCoins = coins
	if openName == "Upgrade" then
		for _, row in upgradeRows do
			paintBuyButton(row, coins)
		end
	elseif openName == "Rebirth" and lastState then
		refreshRebirth(coins)
	end
end

return Panels
