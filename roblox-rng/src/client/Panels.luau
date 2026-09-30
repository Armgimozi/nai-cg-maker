-- 메뉴 창: 도감(대륙 탭 — 예전 여권 창을 합침: 지역별 발견 현황 + 도장, 대표 지정), 강화(업그레이드), 환생(조건 + 확인), 상점(Robux).
-- 공원 배치는 창이 아니라 내 공원에서 하는 3D 배치 모드(ParkEdit) — 도감 머리 줄 [배치] 버튼이 그 모드를 켬
-- 크림색 창(Ui.window) 하나를 쓰고, 화면마다 리본 색과 제목(2글자)만 바꿉니다(도감은 탭 줄만큼 창이 조금 더 높음).
-- 글자는 최소로: 설명 문장 없이 아이콘 + 숫자 딱지로 보여 줍니다.
-- 화면마다 카드를 한 번 만들고 상태가 바뀌면 글자/색만 고칩니다. 썸네일(ViewportFrame)은
-- 새로 발견했을 때만 만들어서, 자동 굴림 중에 창을 열어 둬도 매번 다시 만들지 않습니다.
-- 도감 탭을 바꿔도 카드는 그대로 두고 보이기(Visible)·순서(LayoutOrder)만 바꿉니다(썸네일을 다시 만들지 않음).

local MarketplaceService = game:GetService("MarketplaceService")
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
	Arrange: () -> (), -- 도감 [배치]: 3D 공원 배치 모드 켜기(창은 부르는 쪽이 닫음)
}

local REGION_BONUS = math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)

local HEADER_HEIGHT = 50 -- 창 본문 맨 위 딱지 줄 높이

-- 도감 대륙 탭: [전체] + 대륙마다 하나(예전 여권 창을 합침). 탭 = 세로 통통 버튼(왼쪽 메뉴 버튼처럼 아이콘 위 · 이름 아래),
-- 대륙 아이콘은 도장 그림. 여섯 개가 본문 폭을 똑같이 나눔(휴대폰 배율 0.55 에서 앞면 약 63×37px, 이름 10px)
local TAB_HEIGHT = 74 -- 앞면 68 + 그림자 6
local TAB_GAP = 6 -- 탭 줄 ~ 머리 줄
local TAB_SPACING = 8 -- 탭 사이
local TAB_ICON = 50 -- 도장 그림은 둘레가 비어 있어 크게, 앞면 위 끝에 붙임
local TAB_LABEL_Y = 45 -- 이름 칸 위 끝(아이콘 그림 아래 빈 곳과 조금 겹침)
local TAB_LABEL_HEIGHT = 20
local TAB_TEXT = 19
local COLLECTION_TOP = TAB_HEIGHT + TAB_GAP + HEADER_HEIGHT
local ALL_TAB = "All"

-- Height: 창 높이(없으면 WINDOW_SIZE.Y). 도감은 탭 줄만큼 더 높게(카드 두 줄 가까이 보이게)
local VIEWS: { [string]: { Title: string, Color: string, Top: number, Height: number? } } = {
	Collection = { Title = "도감", Color = "Sky", Top = COLLECTION_TOP, Height = 540 },
	Upgrade = { Title = "강화", Color = "Sun", Top = 4 },
	Rebirth = { Title = "환생", Color = "Coral", Top = HEADER_HEIGHT },
	Shop = { Title = "상점", Color = "Grass", Top = 4 }, -- Robux 상점: 코인으로 사는 강화(Sun)와 다른 색
}

local WHITE = Color3.new(1, 1, 1)
local FEATURED_BG = Color3.fromRGB(255, 218, 128)
local DIM_CHIP = Color3.fromRGB(172, 170, 190) -- 아직 못 받은 보너스 딱지
local UNKNOWN_BG = Color3.fromRGB(58, 53, 80) -- 도감 대륙 탭의 못 찾은 명소 카드
local FADED_STAMP = Color3.fromRGB(150, 146, 160) -- 아직 못 받은 도장(흐릿한 자국)

local WINDOW_SIZE = Vector2.new(760, 500)
local BODY_WIDTH = WINDOW_SIZE.X - 36 -- 창 본문 폭(Ui.window: 좌우 18)
local WINDOW_LIP = 8 -- 창 아래 두께(Ui.window 의 Lip)
local OPEN_OFFSET = -30 -- 창을 화면 가운데보다 조금 위로 (아래쪽 굴리기 버튼을 가리지 않게)
-- 스크롤 영역 안쪽 여백(오른쪽은 스크롤바 자리)
local PAD_X, PAD_RIGHT, PAD_Y = 6, 14, 6

local COLLECTION_CELL = Vector2.new(128, 184)
local COLLECTION_GAP = 12
local COLLECTION_COLUMNS = 5

-- 도감 대륙 머리 줄: [도장] [발견 막대 "찾은 수/필요 수"] …… [+25%]
local STAMP_SIZE = 70
local BAR_HEIGHT = 34
local BAR_LEFT = 86 -- 도장 오른쪽
local BAR_RIGHT = 150 -- 오른쪽 +25% 딱지 자리

-- 환생 요구 명소 카드(작은 카드)
local NEED_CELL = Vector2.new(104, 124)
local NEED_GAP = 8
local SECTION_PAD = 14
local SECTION_GAP = 16

local UPGRADE_ROW = 80
local UPGRADE_GAP = 10

local REBIRTH_COLUMNS = 6 -- 요구 명소 카드
local REBIRTH_FOOTER = 104 -- 창 아래 고정 줄: 보상 · 경고 · 환생 버튼
local COIN_BAR = Vector2.new(380, 40)
local CONFIRM_SECONDS = 3

local SHOP_CELL = Vector2.new(216, 196)
local SHOP_GAP = 12
local SHOP_COLUMNS = 3
local SHOP_BAND = 74
local SHOP_ART = 68 -- 로블록스에서 받은 상품 그림(구매 창과 같은 그림) 크기. 아이콘(62)을 덮음
local BUY_COOLDOWN = 1
local INFO_RETRY = 3 -- 상품 정보(GetProductInfo)를 못 받으면 이만큼 뒤에 한 번 더

local Panels = {}

local win: Ui.Window
local window: Frame
local body: Frame
local loadingLabel: TextLabel
local handlers: Handlers
local openName: string? = nil
local lastState: Snapshot? = nil
local lastCoins = 0
local openTween: Tween? = nil

type View = { Scroller: ScrollingFrame, Header: Frame, Extra: GuiObject? }
local views: { [string]: View } = {}

-- 도감 탭: [전체](도감 아이콘, Sky) + 대륙(도장 그림, 대륙 색). 고른 탭 = 탭 색 그대로, 다른 탭 = 크림 쪽으로 옅게
type Tab = {
	Id: string,
	Name: string,
	Icon: string,
	Selected: Ui.ColorPair,
	Idle: Ui.ColorPair,
	Region: Landmarks.Region?,
	Order: { [string]: number }, -- 명소 Id -> 이 탭에서 몇 번째 (전체 = 희귀한 순서, 대륙 = 흔한 순서)
}
local function tabColors(color: Color3): (Ui.ColorPair, Ui.ColorPair)
	return { Face = color, Shadow = color:Lerp(Theme.Ink, 0.35) }, {
		Face = color:Lerp(Theme.Cream, 0.5),
		Shadow = color:Lerp(Theme.Cream, 0.15),
	}
end
local function orderOf(list: { Landmark }): { [string]: number }
	local order = {}
	for index, landmark in list do
		order[landmark.Id] = index
	end
	return order
end
local TABS: { Tab } = {}
local TAB_BY_ID: { [string]: Tab } = {}
do
	local selected, idle = tabColors(Ui.colorPair("Sky").Face)
	table.insert(TABS, {
		Id = ALL_TAB,
		Name = "전체",
		Icon = "album",
		Selected = selected,
		Idle = idle,
		Region = nil,
		Order = orderOf(Landmarks.RarestFirst),
	})
	for _, region in Landmarks.Regions do
		local on, off = tabColors(region.Color)
		local art = "stamp_" .. string.lower(region.Id)
		table.insert(TABS, {
			Id = region.Id,
			Name = region.Name,
			Icon = if Icons.imageId(art) then art else "globe",
			Selected = on,
			Idle = off,
			Region = region,
			Order = orderOf(Landmarks.ByRegion[region.Id]),
		})
	end
	for _, tab in TABS do
		TAB_BY_ID[tab.Id] = tab
	end
end
local collectionTab = ALL_TAB -- 고른 탭("All" 또는 대륙 Id). 창이 열려 있는 동안 유지, 닫으면 전체로

-- 도감 머리 줄 (전체 탭)
local allRow: Frame
local collectionCount: Ui.Chip
local stampCount: Ui.Chip -- 받은 도장 수
local stampBonus: Ui.Chip -- 도장 행운 합
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
local unknownCards: { [string]: Frame } = {} -- 대륙 탭의 못 찾은 명소(3D 사진 없음, 그 탭을 처음 볼 때 만듦)

type Stamp = {
	Frame: Frame,
	Stroke: UIStroke,
	RingStroke: UIStroke,
	Labels: { TextLabel },
	Outlines: { UIStroke },
	Art: Frame?, -- 도장 그림 아이콘(그림이 있을 때)
	Color: Color3,
}
type TabButton = { Button: Ui.ChunkyButton, Stamped: Frame? }
local tabButtons: { [string]: TabButton } = {}
type RegionHeader = { Frame: Frame, Stamp: Stamp, Fill: Frame, Count: TextLabel, Check: Frame, Bonus: Ui.Chip }
local regionHeaders: { [string]: RegionHeader } = {}

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
type ShopCard = {
	Item: Perks.Item,
	Button: Ui.ChunkyButton,
	Effect: Ui.Chip,
	Owned: Ui.Chip?,
	Band: Frame,
	Art: ImageLabel?, -- 로블록스에서 받은 상품 그림(받았을 때만)
}
local shopCards: { ShopCard } = {}
-- 로블록스에서 받은 상품 정보("Pass:123" -> 실제 Robux 가격 · 상품 그림). 한 번 받으면 다시 묻지 않음
type ShopInfo = { Price: number?, Art: string? }
local shopInfo: { [string]: ShopInfo } = {}

local collectionArrangeBadge: Ui.Chip? = nil -- 도감 머리 줄 [배치] 배지
local function owned(state: Snapshot, id: string): number
	return state.Inventory[id] or 0
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

-- 명소 썸네일을 담는 "사진 칸" (등급 색을 옅게 깐 바탕)
local function photo(parent: GuiObject, landmark: Landmark, position: UDim2, size: UDim2, radius: number): Frame
	local frame = Ui.new("Frame", {
		Name = "Photo",
		Position = position,
		Size = size,
		BackgroundColor3 = landmark.Tier.Color:Lerp(WHITE, 0.62),
		Parent = parent,
	})
	Ui.corner(radius).Parent = frame
	Ui.stroke(Theme.Ink, 2).Parent = frame
	Viewport.thumbnail(frame, landmark, THUMB_PROPS)
	return frame
end

-- 버튼 오른쪽 위 숫자 배지 (도감 버튼의 도장 "1/5" 배지와 같은 모양: Ink 딱지 + Sun 숫자, 살짝 기울임)
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

-- 도장 · 보너스 딱지 (도감 대륙 탭) --------------------------------------------

-- 대륙 도장: 그림(ImageIds.stamp_<대륙>)이 있으면 그 그림, 없으면 대륙 색 동그라미(기울임) + 흰 고리 + 대륙 이름
-- place: { AnchorPoint, Position, Size }
local function makeStamp(parent: GuiObject, region: Landmarks.Region, place: { [string]: any }): Stamp
	local frame = Ui.new("Frame", {
		Name = "Stamp",
		AnchorPoint = place.AnchorPoint,
		Position = place.Position,
		Size = place.Size,
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
		Icons.setColor(art, if complete then WHITE else FADED_STAMP)
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

-- 크림 동그라미 + 초록 체크 (도장 받은 대륙 탭 · 다 찬 발견 막대 끝)
local function checkMark(parent: GuiObject, props: { [string]: any }): Frame
	local mark = Ui.new("Frame", {
		Name = props.Name or "Check",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = props.Position,
		Size = props.Size,
		Rotation = props.Rotation or 0,
		BackgroundColor3 = Theme.Cream,
		ZIndex = props.ZIndex or 4,
		Visible = false,
		Parent = parent,
	})
	Ui.round().Parent = mark
	Ui.stroke(Theme.Ink, props.StrokeThickness or 3).Parent = mark
	Icons.view(mark, "check", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.95, 0.95),
		ZIndex = (props.ZIndex or 4) + 1,
	})
	return mark
end

-- 도감 -----------------------------------------------------------------------
-- 위 탭 줄([전체] + 대륙), 그 아래 머리 줄(탭마다 다름), 카드 격자 하나.
--   [전체] = 발견한 명소(Discovered)만 희귀한 순서. 머리 줄: 발견 수 · 받은 도장 수 · 도장 행운 · [배치] · [자동]
--   대륙 = 그 대륙 명소 전부, 흔한 순서(예전 여권 한 쪽). 못 찾은 명소는 어두운 자물쇠 카드.
--          머리 줄: 도장(찍힘/흐림) · 발견 막대(도장 조건 = PlayerState.regionProgress) · +25%(받음 초록 / 아직 회색)
-- 카드는 명소마다 한 번만 만들고, 탭을 바꾸면 보이기·순서만 바꿈(3D 사진을 다시 만들지 않음)

local selectTab: (string) -> () -- 아래 renderCollection 뒤에서 정함

-- 등급 색 띠 + 확률 (위쪽 모서리만 둥글게: 아래 절반을 네모 판으로 덮음). 아는 카드·모르는 카드 같이 씀
local function oddsBand(card: GuiObject, landmark: Landmark)
	local tier = landmark.Tier
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
	-- 확률은 늘 콤마 자연수라 가장 긴 "1 in 10,000,000,000"(세계수)도 들어가게 좌우 여백 4
	local bandLabel = Ui.label({
		Position = UDim2.fromOffset(4, 4),
		Size = UDim2.new(1, -8, 1, -7),
		Text = Format.oneIn(landmark.OneIn),
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = band,
	}, 15)
	Ui.outline(bandLabel, 1.5)
end

local function collectionCard(parent: ScrollingFrame, landmark: Landmark): CollectionCard
	local card = Ui.new("TextButton", {
		Name = landmark.Id,
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = Theme.Paper,
	})
	Ui.corner(12).Parent = card
	Ui.stroke(Theme.Ink, 3).Parent = card
	oddsBand(card, landmark)

	local picture = photo(card, landmark, UDim2.fromOffset(7, 33), UDim2.new(1, -14, 0, 84), 8)

	Ui.label({
		Position = UDim2.fromOffset(6, 122),
		Size = UDim2.new(1, -12, 0, 24),
		Text = landmark.Name,
		Parent = card,
	}, 19)
	local stars = Ui.label({
		Name = "Stars",
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

-- 대륙 탭의 아직 못 찾은 명소: 아는 카드와 같은 자리(확률 띠 · 사진 칸 · 이름 줄)의 어두운 카드 + 사진 칸에 자물쇠
-- (그림이 없으면 "?"), 이름 대신 "???". 3D 모형은 만들지 않음(가볍게)
local function unknownCard(parent: ScrollingFrame, landmark: Landmark): Frame
	local card = Ui.new("Frame", {
		Name = landmark.Id,
		BackgroundColor3 = UNKNOWN_BG,
	})
	card:SetAttribute("Unknown", true)
	Ui.corner(12).Parent = card
	Ui.stroke(Theme.Ink, 3).Parent = card
	oddsBand(card, landmark)

	local hole = Ui.new("Frame", {
		Name = "Photo",
		Position = UDim2.fromOffset(7, 33),
		Size = UDim2.new(1, -14, 0, 84),
		BackgroundColor3 = Theme.Ink,
		Parent = card,
	})
	Ui.corner(8).Parent = hole
	Ui.stroke(Theme.Ink, 2).Parent = hole
	if Icons.imageId("lock") then
		Icons.view(hole, "lock", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromOffset(58, 58),
			Transparency = 0.1,
		})
	else
		Ui.label({
			Size = UDim2.fromScale(1, 1),
			Font = Theme.FontTitle,
			Text = "?",
			TextColor3 = Theme.Paper,
			TextTransparency = 0.2,
			Parent = hole,
		}, 50)
	end
	Ui.label({
		Position = UDim2.fromOffset(6, 124),
		Size = UDim2.new(1, -12, 0, 24),
		Text = "???",
		TextColor3 = Theme.Paper,
		TextTransparency = 0.45,
		Parent = card,
	}, 20)

	card.Parent = parent
	return card
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

-- 탭 줄: 세로 통통 버튼 여섯 개가 본문 폭을 똑같이 나눔. 도장을 받은 대륙 탭은 오른쪽 위에 작은 체크
local function buildTabs(): Frame
	local row = Ui.new("Frame", {
		Name = "Tabs",
		Size = UDim2.new(1, 0, 0, TAB_HEIGHT),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = body,
	})
	local layout = Ui.list(Enum.FillDirection.Horizontal, TAB_SPACING, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = row
	local width = math.floor((BODY_WIDTH - TAB_SPACING * (#TABS - 1)) / #TABS)
	for order, tab in TABS do
		local button = Ui.chunkyButton({
			Name = "Tab" .. tab.Id,
			LayoutOrder = order,
			ZIndex = 2, -- 체크가 옆 탭에 가리지 않게
			Size = UDim2.fromOffset(width, TAB_HEIGHT),
			Color = tab.Idle,
			Icon = tab.Icon,
			IconSize = TAB_ICON,
			Vertical = true,
			Text = tab.Name,
			TextSize = TAB_TEXT,
			Parent = row,
		})
		-- 이름 칸은 아이콘 그림 아래 빈 곳과 조금 겹치게(도장 그림은 둘레가 비어 있음). 탭 글자·아이콘은 바뀌지 않아 그대로 유지됨
		button.Label.Position = UDim2.fromOffset(4, TAB_LABEL_Y)
		button.Label.Size = UDim2.new(1, -8, 0, TAB_LABEL_HEIGHT)
		button.Activated:Connect(function()
			selectTab(tab.Id)
		end)
		local stamped: Frame? = nil
		if tab.Region then
			stamped = checkMark(button.Face, {
				Name = "Stamped",
				Position = UDim2.new(1, -5, 0, 3),
				Size = UDim2.fromOffset(26, 26),
				Rotation = 8,
				StrokeThickness = 2.5,
				ZIndex = 6,
			})
		end
		tabButtons[tab.Id] = { Button = button, Stamped = stamped }
	end
	return row
end

-- 대륙 머리 줄: [도장] [발견 막대(대륙 색) "찾은 수/필요 수" + 다 차면 체크] …… [클로버 +25%]
local function buildRegionHeader(parent: Frame, region: Landmarks.Region): RegionHeader
	local frame = Ui.new("Frame", {
		Name = region.Id,
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = parent,
	})
	local stamp = makeStamp(frame, region, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0, STAMP_SIZE / 2 + 2, 0.5, 0),
		Size = UDim2.fromOffset(STAMP_SIZE, STAMP_SIZE),
	})
	local bar = Ui.new("Frame", {
		Name = "Progress",
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, BAR_LEFT, 0.5, 0),
		Size = UDim2.new(1, -(BAR_LEFT + BAR_RIGHT), 0, BAR_HEIGHT),
		BackgroundColor3 = Theme.Cream,
		Parent = frame,
	})
	Ui.round().Parent = bar
	Ui.stroke(Theme.Ink, 3).Parent = bar
	local fill = Ui.new("Frame", {
		Name = "Fill",
		Size = UDim2.fromScale(0, 1),
		BackgroundColor3 = region.Color,
		BorderSizePixel = 0,
		Parent = bar,
	})
	Ui.round().Parent = fill
	local count = Ui.label({
		Name = "Count",
		Position = UDim2.fromOffset(30, 3),
		Size = UDim2.new(1, -60, 1, -6),
		TextColor3 = WHITE,
		ZIndex = 3,
		Parent = bar,
	}, 24)
	Ui.outline(count, 2.5)
	local check = checkMark(bar, {
		Position = UDim2.new(1, -2, 0.5, 0),
		Size = UDim2.fromOffset(40, 40),
	})
	local bonus = Ui.chip({
		Name = "Bonus",
		Color = DIM_CHIP,
		Icon = "clover",
		IconSize = 44,
		Height = 34,
		TextSize = 21,
		Text = string.format("+%d%%", REGION_BONUS),
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -8, 0.5, 0),
		Parent = frame,
	})
	return { Frame = frame, Stamp = stamp, Fill = fill, Count = count, Check = check, Bonus = bonus }
end

local function buildCollection(): View
	local tabs = buildTabs()

	-- 머리 줄: 탭 줄 아래. [전체] 줄 하나 + 대륙마다 한 줄(고른 탭만 보임)
	local header = Ui.new("Frame", {
		Name = "CollectionHeader",
		Position = UDim2.fromOffset(0, TAB_HEIGHT + TAB_GAP),
		Size = UDim2.new(1, 0, 0, HEADER_HEIGHT),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = body,
	})
	allRow = Ui.new("Frame", {
		Name = ALL_TAB,
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Parent = header,
	})
	local chips = chipRow(allRow)
	collectionCount = headerChip(chips, "album", Theme.Ink, 1)
	collectionCount.Root.Name = "Count"
	-- 받은 도장 수 · 도장 행운 합(예전 여권 머리 줄)
	stampCount = headerChip(chips, "passport", Theme.Ink, 2)
	stampCount.Root.Name = "Stamps"
	stampBonus = headerChip(chips, "clover", "Grass", 3)
	stampBonus.Root.Name = "StampBonus"

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
		Parent = allRow,
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

	-- 3D 공원 배치 모드 켜기: 배치 아이콘(2×2 칸 판) + "배치" (자동 버튼 왼쪽). 배지 = 더 좋은데 전시 안 된 명소 수
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
		Parent = allRow,
	})
	arrange.Activated:Connect(function()
		handlers.Arrange()
	end)
	collectionArrangeBadge = countBadge(arrange, "Better")

	for _, region in Landmarks.Regions do
		regionHeaders[region.Id] = buildRegionHeader(header, region)
	end

	-- 아직 아무것도 없을 때(전체 탭): 가운데에 천천히 도는 지구본
	emptyIcon = Icons.view(body, "globe", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0.5, COLLECTION_TOP / 2),
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
	return { Scroller = scroller, Header = header, Extra = tabs }
end

-- 대륙 머리 줄 숫자·색 (도장 규칙은 PlayerState.regionProgress 그대로: 불가사의 등급까지, 역대 발견 기준)
local function paintRegionHeader(state: Snapshot, region: Landmarks.Region)
	local header = regionHeaders[region.Id]
	local found, required = PlayerState.regionProgress(state, region.Id)
	local complete = required > 0 and found >= required
	header.Count.Text = string.format("%d/%d", found, required)
	header.Fill.Size = UDim2.fromScale(if required > 0 then math.clamp(found / required, 0, 1) else 0, 1)
	header.Fill.Visible = found > 0
	header.Check.Visible = complete
	paintBonus(header.Bonus, complete)
	paintStamp(header.Stamp, complete)
end

local function renderCollection(state: Snapshot)
	local scroller = views.Collection.Scroller
	local tab = TAB_BY_ID[collectionTab] or TABS[1]
	local region = tab.Region

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

	-- 도감은 역대 발견(Discovered — 서버가 자동 발견한 명소도 들어 있음) 기준. 별·개수·전시는 지금 보유(Inventory) 기준.
	-- 별은 가챠식(처음 발견 = 빈 별 5개 ☆0, 또 뽑을 때마다 ★+1): 보유하면 빈 별까지 보이고, 지금 없으면 별 줄을 비움.
	-- 못 찾은 명소 카드(자물쇠)는 그 대륙 탭을 처음 볼 때 만들고, 발견하면 지움
	local discovered = 0
	for _, landmark in Landmarks.RarestFirst do
		local id = landmark.Id
		local count = owned(state, id)
		local entry = collectionCards[id]
		if Perks.discovered(state, id) then
			discovered += 1
			if not entry then
				entry = collectionCard(scroller, landmark)
				collectionCards[id] = entry
			end
			local featured = state.Featured == id
			entry.Card.BackgroundColor3 = if featured then FEATURED_BG else Theme.Paper
			entry.Badge.Root.Visible = featured
			entry.Stars.Text = if count > 0 then Ui.starsRich(PlayerState.stars(count), PlayerState.MAX_STARS) else ""
			entry.Count.Label.Text = "×" .. Format.commas(count)
			entry.Count.Root.Visible = count > 0
			setShown(entry, inPark[id] == true)
			setDim(entry, count <= 0)
			local unknown = unknownCards[id]
			if unknown then
				unknown:Destroy()
				unknownCards[id] = nil
			end
		else
			if entry then
				entry.Card:Destroy()
				collectionCards[id] = nil
			end
			if region and landmark.Region == region.Id and not unknownCards[id] then
				unknownCards[id] = unknownCard(scroller, landmark)
			end
		end
	end

	-- 고른 탭의 카드만 보이게 + 탭 순서대로 (카드는 그대로 두고 Visible · LayoutOrder 만)
	local order = tab.Order
	local visible = 0
	for id, entry in collectionCards do
		local index = order[id]
		entry.Card.Visible = index ~= nil
		if index then
			entry.Card.LayoutOrder = index
			visible += 1
		end
	end
	for id, card in unknownCards do
		local index = if region then order[id] else nil
		card.Visible = index ~= nil
		if index then
			card.LayoutOrder = index
			visible += 1
		end
	end

	-- 탭: 고른 탭 = 제 색, 다른 탭 = 옅은 색. 도장을 받은 대륙 탭은 작은 체크
	local stamped = {}
	for _, id in PlayerState.completedRegions(state) do
		stamped[id] = true
	end
	for _, other in TABS do
		local button = tabButtons[other.Id]
		local selected = other == tab
		button.Button.SetColor(if selected then other.Selected else other.Idle)
		button.Button.Root:SetAttribute("Selected", selected)
		local mark = button.Stamped
		if mark then
			mark.Visible = stamped[other.Id] == true
		end
	end

	-- 머리 줄: 전체 = 발견 수 · 받은 도장 수 · 도장 행운 합, 대륙 = 그 대륙 도장 · 발견 막대 · +25%
	allRow.Visible = region == nil
	for id, header in regionHeaders do
		header.Frame.Visible = region ~= nil and id == region.Id
	end
	if region then
		paintRegionHeader(state, region)
	end
	local stamps = 0
	for _ in stamped do
		stamps += 1
	end
	collectionCount.Label.Text = string.format("%d/%d", discovered, #Landmarks.List)
	stampCount.Label.Text = string.format("%d/%d", stamps, #Landmarks.Regions)
	stampBonus.Label.Text = string.format("+%d%%", stamps * REGION_BONUS)
	paintBonus(stampBonus, stamps > 0)

	emptyIcon.Visible = region == nil and discovered == 0
	setCanvasHeight(scroller, gridHeight(visible, COLLECTION_COLUMNS, COLLECTION_CELL.Y, COLLECTION_GAP))
end

-- 탭 고르기: 카드는 그대로(보이기·순서만), 스크롤은 맨 위로
selectTab = function(id: string)
	if not TAB_BY_ID[id] or id == collectionTab then
		return
	end
	collectionTab = id
	local built = views.Collection
	if built then
		built.Scroller.CanvasPosition = Vector2.zero
	end
	local state = lastState
	if openName == "Collection" and built and state then
		renderCollection(state)
	end
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

-- 환생 버튼: 못 함 = 회색 / 가능 = Coral "환생" / 한 번 누름 = Sun "확인?" (3초) / 최대까지 함 = Grass "최대"
local function paintRebirthButton(ready: boolean, maxed: boolean?)
	local button = rebirthButton
	if not button then
		return
	end
	local confirming = ready and os.clock() < confirmUntil
	local look = if maxed then "max" elseif confirming then "confirm" elseif ready then "ready" else "locked"
	if look == rebirthLook then
		return
	end
	rebirthLook = look
	button.SetText(if maxed then "최대" elseif confirming then "확인?" else "환생")
	button.SetColor(if maxed then "Grass" elseif confirming then "Sun" elseif ready then "Coral" else "Gray")
	if button.Icon then
		Icons.setTransparency(button.Icon, if ready or maxed then 0 else 0.45)
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
	paintRebirthButton(ready, need == nil and Perks.rebirths(state) >= Config.MAX_REBIRTHS)
end

local function onRebirthPressed()
	local state = lastState
	if not state then
		return
	end
	local ready, missing, _, need = Perks.rebirthCheck(state, lastCoins)
	if not need then
		handlers.Toast("최대 환생", "rebirth")
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
		CellSize = UDim2.fromOffset(NEED_CELL.X, NEED_CELL.Y),
		CellPadding = UDim2.fromOffset(NEED_GAP, NEED_GAP),
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

	-- 아래 고정 줄: [위 화살표][행운 ×2][수입 +50%] / [코인·강화 초기화]   [환생]
	-- (환생 1번마다: 행운은 곱해짐 ×2 → ×4 → … ×1,024, 수입은 더해짐 +50%)
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
	headerChip(rewards, "clover", "Grape", 2).Label.Text = Ui.times(Perks.REBIRTH_LUCK_MULT)
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
		Position = UDim2.fromOffset(2, 99),
		Size = UDim2.new(1, -4, 0, 17),
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
	rebirthCount.Label.Text = Format.commas(rebirths) .. "/" .. Config.MAX_REBIRTHS
	rebirthLuck.Label.Text = Ui.times(luck)
	rebirthIncome.Label.Text = Ui.times(income)
	-- 발견 기록(Discovered)이 따로 있으면 보유 명소도 초기화되는 규칙(DESIGN v3)
	rebirthWarning.Label.Text = if rebirths >= Config.MAX_REBIRTHS
		then "최대 환생 달성"
		elseif (state :: any).Discovered ~= nil then "코인·강화·명소 초기화"
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

	local gridSize = gridHeight(#list, REBIRTH_COLUMNS, NEED_CELL.Y, NEED_GAP)
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

-- 가격 버튼 글자: Robux 숫자(가격을 모르면 "구매"). 버튼 왼쪽에 Robux 표시(육각형 아이콘)가 붙음
local function priceText(price: number?): string
	return if price then Format.commas(price) else "구매"
end

-- 상품 카드: 색 띠 + 큰 아이콘 / 이름 / 효과 딱지(+시간) / 초록 [Robux 표시 + 가격] 버튼
-- (게임패스를 가졌으면 버튼 대신 "보유" 도장). 가격은 Config 값으로 먼저 그리고, 로블록스에서 실제 가격을 받으면 바꿈
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
		Icon = "robux",
		Text = priceText(item.Price),
		TextSize = 26,
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
	return { Item = item, Button = button, Effect = effect, Owned = ownedStamp, Band = band, Art = nil }
end

-- 로블록스에서 상품 정보(실제 가격 · 상품 그림)를 받아 옴. 실패하면 INFO_RETRY 초 뒤 한 번 더, 그래도 안 되면 nil
local function fetchShopInfo(item: Perks.Item): ShopInfo?
	local key = item.Kind .. ":" .. item.Id
	local cached = shopInfo[key]
	if cached then
		return cached
	end
	local infoType = if item.Kind == "Pass" then Enum.InfoType.GamePass else Enum.InfoType.Product
	for attempt = 1, 2 do
		-- 새 이름(GetProductInfoAsync)을 먼저, 없거나 실패하면 옛 이름(GetProductInfo)
		local ok, info = pcall(function()
			return (MarketplaceService :: any):GetProductInfoAsync(item.Id, infoType)
		end)
		if not ok then
			ok, info = pcall(function()
				return MarketplaceService:GetProductInfo(item.Id, infoType)
			end)
		end
		if ok and type(info) == "table" then
			local price = info.PriceInRobux
			local art = tonumber(info.IconImageAssetId)
			local result: ShopInfo = {
				Price = if type(price) == "number" and price > 0 then price else nil,
				Art = if art and art > 0 then "rbxassetid://" .. string.format("%d", art) else nil,
			}
			shopInfo[key] = result
			return result
		end
		if attempt == 1 then
			task.wait(INFO_RETRY)
		end
	end
	return nil
end

-- 받은 정보로 카드 고치기: 가격 글자, 띠 가운데 상품 그림(구매 창과 같은 그림. 아이콘 위에 덮어서, 그림을
-- 못 불러오면 아래 아이콘이 그대로 보임)
local function applyShopInfo(entry: ShopCard, info: ShopInfo)
	if info.Price then
		entry.Button.Label.Text = priceText(info.Price)
	end
	local art = info.Art
	if art and not entry.Art then
		entry.Art = Ui.new("ImageLabel", {
			Name = "Art",
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromOffset(SHOP_ART, SHOP_ART),
			BackgroundTransparency = 1,
			Image = art,
			ScaleType = Enum.ScaleType.Fit,
			ZIndex = 3,
			Parent = entry.Band,
		})
	end
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
	-- 실제 가격 · 상품 그림은 기다리지 않고 받는 대로 채움
	for _, entry in shopCards do
		task.spawn(function()
			local info = fetchShopInfo(entry.Item)
			if info then
				applyShopInfo(entry, info)
			end
		end)
	end
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

-- 공통 -----------------------------------------------------------------------

local BUILDERS = {
	Collection = buildCollection,
	Upgrade = buildUpgrade,
	Rebirth = buildRebirth,
	Shop = buildShop,
}

local RENDERERS = {
	Collection = renderCollection,
	Upgrade = renderUpgrade,
	Rebirth = renderRebirth,
	Shop = renderShop,
}

local function showView(built: View, visible: boolean)
	built.Scroller.Visible = visible
	built.Header.Visible = visible
	local extra = built.Extra
	if extra then
		extra.Visible = visible
	end
end

-- 창 가운데 세로 자리(화면 가운데 기준 px): 화면 가운데 + OPEN_OFFSET(아래 굴리기 줄을 덜 가리게 조금 위).
-- 창(배율 적용, 아래 두께 포함)이 화면(ScreenGui) 위아래를 넘으면 넘지 않는 쪽으로 옮김 — 휴대폰(배율 0.55)에서 창 위 끝이
-- 상단바 밑으로 들어가지 않게. 창이 화면보다 크면 가운데
local function openOffset(height: number): number
	local parent = window.Parent
	local guiHeight = if parent and parent:IsA("GuiBase2d") then parent.AbsoluteSize.Y else 0
	if guiHeight <= 0 then
		return OPEN_OFFSET
	end
	local half = (height + WINDOW_LIP) * Ui.scale() / 2
	if half * 2 > guiHeight then
		return 0
	end
	return math.clamp(guiHeight / 2 + OPEN_OFFSET, half, guiHeight - half) - guiHeight / 2
end

-- 화면마다 창 높이(도감은 탭 줄만큼 높음)와 자리. animate = 아래에서 톡 튀어 오르며 열림
local function placeWindow(animate: boolean)
	local name = openName
	if not name then
		return
	end
	local height = VIEWS[name].Height or WINDOW_SIZE.Y
	window.Size = UDim2.fromOffset(WINDOW_SIZE.X, height)
	local offset = openOffset(height)
	local tween = openTween
	if tween then
		tween:Cancel()
		openTween = nil
	end
	if animate then
		window.Position = UDim2.new(0.5, 0, 0.5, offset + 40)
		local rise = TweenService:Create(window, TweenInfo.new(0.25, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {
			Position = UDim2.new(0.5, 0, 0.5, offset),
		})
		openTween = rise
		rise:Play()
	else
		window.Position = UDim2.new(0.5, 0, 0.5, offset)
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
	-- 화면 크기·배율이 바뀌면 열린 창 자리를 다시 잡음(휴대폰을 돌렸을 때 등)
	Ui.onRescale(function()
		if window.Visible then
			placeWindow(false)
		end
	end)

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

-- 창 열기(이미 열려 있으면 그 화면으로 바꿈). tab: 도감 탭("All" 또는 대륙 Id) — 도장 알림을 누르면 그 대륙 탭으로 바로 열림.
-- tab 을 안 주면 지금 탭 그대로(창이 열려 있는 동안 유지, 닫혀 있었으면 전체)
function Panels.open(name: string, tab: string?)
	if not VIEWS[name] or (name == "Shop" and not Perks.anyForSale()) then
		return
	end
	if name == "Collection" and tab and TAB_BY_ID[tab] and tab ~= collectionTab then
		collectionTab = tab
		local built = views.Collection
		if built then
			built.Scroller.CanvasPosition = Vector2.zero
		end
	end
	local wasOpen = window.Visible
	local changed = openName ~= name
	openName = name
	window.Visible = true
	if not wasOpen or changed then
		placeWindow(not wasOpen)
	end
	render()
end

-- 같은 창 버튼을 다시 누르면 닫힘
function Panels.toggle(name: string)
	if openName == name then
		Panels.close()
		return
	end
	Panels.open(name)
end

function Panels.close()
	openName = nil
	window.Visible = false
	confirmUntil = 0 -- 닫으면 환생 "확인?" 도 취소
	confirmToken += 1
	-- 도감 탭은 창이 열려 있는 동안만 기억: 다음에 열면 전체부터
	if collectionTab ~= ALL_TAB then
		collectionTab = ALL_TAB
		local built = views.Collection
		if built then
			built.Scroller.CanvasPosition = Vector2.zero
		end
	end
end

-- 지금 열린 화면 이름(닫혀 있으면 nil)과 도감 탭 ("All" 또는 대륙 Id)
function Panels.current(): (string?, string)
	return openName, collectionTab
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
