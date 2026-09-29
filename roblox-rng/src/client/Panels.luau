-- 메뉴 창: 컬렉션(대표 지정), 여권(지역별 발견 현황), 업그레이드
-- 화면마다 카드를 한 번 만들고 상태가 바뀌면 글자/색만 고칩니다. 썸네일(ViewportFrame)은
-- 새로 발견했을 때만 만들어서, 자동 굴림 중에 창을 열어 둬도 매번 다시 만들지 않습니다.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState)

local Ui = require(script.Parent.Ui)
local Viewport = require(script.Parent.Viewport)
local Theme = Ui.Theme

type Landmark = Landmarks.Landmark
type Snapshot = PlayerState.Snapshot

export type Handlers = {
	Feature: (string?) -> (),
	Buy: (string) -> (),
	ToggleAutoFeature: () -> (),
}

local VIEWS = {
	Collection = { Title = "🗂️ 컬렉션", Hint = "카드를 누르면 대표 명소로 지정/해제돼요" },
	Passport = {
		Title = "🛂 여권",
		Hint = string.format(
			"한 지역의 명소를 모두 모으면 여권 도장 → 영구 행운 +%d%%",
			math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)
		),
	},
	Upgrade = { Title = "🛠️ 업그레이드", Hint = "코인으로 사는 영구 강화" },
}

local WINDOW_SIZE = Vector2.new(720, 480)
local BODY_TOP = 72
-- 스크롤 영역 안쪽 여백(오른쪽은 스크롤바 자리)
local PAD_X, PAD_RIGHT, PAD_Y = 6, 12, 6

local COLLECTION_CELL = Vector2.new(124, 166)
local COLLECTION_GAP = 10
local COLLECTION_COLUMNS = 5

local PASSPORT_CELL = Vector2.new(104, 132)
local PASSPORT_GAP = 8
local PASSPORT_COLUMNS = 6
local PASSPORT_HEADER = 34
local SECTION_GAP = 14

local UPGRADE_ROW = 96
local UPGRADE_GAP = 10

local FEATURED_BG = Color3.fromRGB(70, 60, 30)
local UNKNOWN_BG = Color3.fromRGB(16, 17, 26)
local DARK_TEXT = Color3.fromRGB(20, 22, 30)

local Panels = {}

local window: Frame
local titleLabel: TextLabel
local hintLabel: TextLabel
local headerButton: TextButton
local emptyLabel: TextLabel
local handlers: Handlers
local openName: string? = nil
local lastState: Snapshot? = nil
local lastCoins = 0

local scrollers: { [string]: ScrollingFrame } = {}

type CollectionCard = {
	Card: TextButton,
	Stroke: UIStroke,
	Stars: TextLabel,
	Count: TextLabel,
	Badge: Frame,
}
local collectionCards: { [string]: CollectionCard } = {}

type PassportSection = { Header: TextLabel, Stamp: TextLabel, Grid: Frame }
local passportSections: { [string]: PassportSection } = {}
local passportCards: { [string]: { Card: Frame, Known: boolean } } = {}

type UpgradeRow = {
	Level: TextLabel,
	Effect: TextLabel,
	Button: TextButton,
	Price: number?,
	Affordable: boolean?,
}
local upgradeRows: { [string]: UpgradeRow } = {}

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

local function newScroller(name: string): ScrollingFrame
	local scroller = Ui.new("ScrollingFrame", {
		Name = name,
		Position = UDim2.fromOffset(12, BODY_TOP),
		Size = UDim2.new(1, -24, 1, -(BODY_TOP + 12)),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 6,
		CanvasSize = UDim2.new(),
		ScrollingDirection = Enum.ScrollingDirection.Y,
		Visible = false,
		Parent = window,
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

local function setCanvasHeight(scroller: ScrollingFrame, contentHeight: number)
	scroller.CanvasSize = UDim2.fromOffset(0, contentHeight + PAD_Y * 2)
end

-- 컬렉션 ---------------------------------------------------------------------

local function buildCollection(): ScrollingFrame
	local scroller = newScroller("Collection")
	Ui.new("UIGridLayout", {
		CellSize = UDim2.fromOffset(COLLECTION_CELL.X, COLLECTION_CELL.Y),
		CellPadding = UDim2.fromOffset(COLLECTION_GAP, COLLECTION_GAP),
		FillDirectionMaxCells = COLLECTION_COLUMNS,
		SortOrder = Enum.SortOrder.LayoutOrder,
		HorizontalAlignment = Enum.HorizontalAlignment.Center,
		Parent = scroller,
	})
	return scroller
end

local function collectionCard(parent: ScrollingFrame, landmark: Landmark): CollectionCard
	local tier = landmark.Tier
	local card = Ui.new("TextButton", {
		Name = landmark.Id,
		Text = "",
		AutoButtonColor = true,
		BackgroundColor3 = Theme.PanelLight,
	})
	Ui.corner(12).Parent = card
	local stroke = Ui.stroke(tier.Color, 2, 0.15)
	stroke.Parent = card

	Viewport.thumbnail(card, landmark, {
		Position = UDim2.fromOffset(6, 6),
		Size = UDim2.new(1, -12, 0, 90),
	})
	Ui.label({
		Position = UDim2.fromOffset(6, 98),
		Size = UDim2.new(1, -12, 0, 22),
		Font = Theme.FontHeavy,
		Text = landmark.Name,
		TextColor3 = tier.Color,
		Parent = card,
	}, 20)
	local stars = Ui.label({
		Position = UDim2.fromOffset(6, 121),
		Size = UDim2.new(1, -12, 0, 18),
		TextColor3 = Theme.Gold,
		Parent = card,
	}, 16)
	local count = Ui.label({
		Position = UDim2.fromOffset(6, 141),
		Size = UDim2.new(1, -12, 0, 18),
		TextColor3 = Theme.SubText,
		Parent = card,
	}, 15)

	local badge = Ui.new("Frame", {
		Position = UDim2.fromOffset(6, 6),
		Size = UDim2.fromOffset(46, 22),
		BackgroundColor3 = Theme.Gold,
		Visible = false,
		ZIndex = 3,
		Parent = card,
	})
	Ui.corner(8).Parent = badge
	Ui.label({
		Size = UDim2.fromScale(1, 1),
		Font = Theme.FontHeavy,
		Text = "대표",
		TextColor3 = DARK_TEXT,
		ZIndex = 4,
		Parent = badge,
	}, 15)

	card.Activated:Connect(function()
		local state = lastState
		local featured = state ~= nil and state.Featured == landmark.Id
		handlers.Feature(if featured then nil else landmark.Id)
	end)

	card.Parent = parent
	return { Card = card, Stroke = stroke, Stars = stars, Count = count, Badge = badge }
end

local function renderCollection(state: Snapshot)
	local scroller = scrollers.Collection
	headerButton.Visible = true
	headerButton.Text = if state.Settings.AutoFeature
		then "더 희귀하면 자동 대표 지정: 켬"
		else "더 희귀하면 자동 대표 지정: 끔"
	headerButton.BackgroundColor3 = if state.Settings.AutoFeature then Color3.fromRGB(45, 110, 70) else Theme.PanelLight

	local inPark = {}
	for _, id in PlayerState.park(state) do
		inPark[id] = true
	end

	local shown = 0
	for _, landmark in Landmarks.RarestFirst do
		local count = owned(state, landmark.Id)
		local entry = collectionCards[landmark.Id]
		if count > 0 then
			shown += 1
			if not entry then
				entry = collectionCard(scroller, landmark)
				collectionCards[landmark.Id] = entry
			end
			local featured = state.Featured == landmark.Id
			entry.Card.LayoutOrder = shown
			entry.Card.BackgroundColor3 = if featured then FEATURED_BG else Theme.PanelLight
			entry.Stroke.Color = if featured then Theme.Gold else landmark.Tier.Color
			entry.Stroke.Thickness = if featured then 3 else 2
			entry.Badge.Visible = featured
			entry.Stars.Text = Ui.stars(PlayerState.stars(count), #Config.STAR_THRESHOLDS)
			entry.Count.Text = "x" .. Format.commas(count) .. (if inPark[landmark.Id] then " · 전시 중" else "")
		elseif entry then
			entry.Card:Destroy()
			collectionCards[landmark.Id] = nil
		end
	end

	titleLabel.Text = string.format("%s  (%d종)", VIEWS.Collection.Title, shown)
	emptyLabel.Visible = shown == 0
	setCanvasHeight(scroller, gridHeight(shown, COLLECTION_COLUMNS, COLLECTION_CELL.Y, COLLECTION_GAP))
end

-- 여권 -----------------------------------------------------------------------

local function buildPassport(): ScrollingFrame
	local scroller = newScroller("Passport")
	local layout = Ui.list(Enum.FillDirection.Vertical, SECTION_GAP)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = scroller

	local total = 0
	for order, region in Landmarks.Regions do
		local list = Landmarks.ByRegion[region.Id]
		local height = PASSPORT_HEADER + 6 + gridHeight(#list, PASSPORT_COLUMNS, PASSPORT_CELL.Y, PASSPORT_GAP)
		local section = Ui.new("Frame", {
			Name = region.Id,
			LayoutOrder = order,
			Size = UDim2.new(1, 0, 0, height),
			BackgroundTransparency = 1,
			Parent = scroller,
		})
		local header = Ui.label({
			Size = UDim2.new(0.55, 0, 0, PASSPORT_HEADER),
			TextXAlignment = Enum.TextXAlignment.Left,
			Font = Theme.FontHeavy,
			TextColor3 = region.Color,
			Parent = section,
		}, 24)
		local stamp = Ui.label({
			AnchorPoint = Vector2.new(1, 0),
			Position = UDim2.fromScale(1, 0),
			Size = UDim2.new(0.45, 0, 0, PASSPORT_HEADER),
			TextXAlignment = Enum.TextXAlignment.Right,
			TextColor3 = Theme.Good,
			Parent = section,
		}, 19)
		local grid = Ui.new("Frame", {
			Position = UDim2.fromOffset(0, PASSPORT_HEADER + 6),
			Size = UDim2.new(1, 0, 1, -(PASSPORT_HEADER + 6)),
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
		passportSections[region.Id] = { Header = header, Stamp = stamp, Grid = grid }
		total += height + (if order > 1 then SECTION_GAP else 0)
	end
	setCanvasHeight(scroller, total)
	return scroller
end

local function passportCard(parent: Frame, landmark: Landmark, known: boolean, order: number): Frame
	local tier = landmark.Tier
	local card = Ui.new("Frame", {
		Name = landmark.Id,
		LayoutOrder = order,
		BackgroundColor3 = if known then Theme.PanelLight else UNKNOWN_BG,
	})
	Ui.corner(10).Parent = card
	Ui.stroke(if known then tier.Color else Theme.Stroke, 2, if known then 0.2 else 0.65).Parent = card

	if known then
		Viewport.thumbnail(card, landmark, {
			Position = UDim2.fromOffset(5, 5),
			Size = UDim2.new(1, -10, 0, 66),
		})
	else
		Ui.label({
			Position = UDim2.fromOffset(5, 5),
			Size = UDim2.new(1, -10, 0, 66),
			Font = Theme.FontHeavy,
			Text = "?",
			TextColor3 = Theme.Stroke,
			Parent = card,
		}, 46)
	end
	Ui.label({
		Position = UDim2.fromOffset(4, 73),
		Size = UDim2.new(1, -8, 0, 20),
		Font = Theme.FontHeavy,
		Text = if known then landmark.Name else "???",
		TextColor3 = if known then tier.Color else Theme.SubText,
		Parent = card,
	}, 16)
	Ui.label({
		Position = UDim2.fromOffset(4, 94),
		Size = UDim2.new(1, -8, 0, 16),
		Text = Format.oneIn(landmark.OneIn),
		TextColor3 = tier.Color,
		Parent = card,
	}, 14)
	Ui.label({
		Position = UDim2.fromOffset(4, 111),
		Size = UDim2.new(1, -8, 0, 16),
		Text = tier.Name,
		TextColor3 = Theme.SubText,
		Parent = card,
	}, 13)

	card.Parent = parent
	return card
end

local function renderPassport(state: Snapshot)
	local found = 0
	local bonus = math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)
	for _, region in Landmarks.Regions do
		local section = passportSections[region.Id]
		local list = Landmarks.ByRegion[region.Id]
		local discovered = 0
		for order, landmark in list do
			local known = owned(state, landmark.Id) > 0
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
		found += discovered

		section.Header.Text = string.format("%s %s  %d/%d", region.Emoji, region.Name, discovered, #list)
		if #list > 0 and discovered == #list then
			section.Stamp.Text = string.format("✅ 도장 획득 (행운 +%d%%)", bonus)
			section.Stamp.TextColor3 = Theme.Good
		else
			section.Stamp.Text = string.format("도장까지 %d곳", #list - discovered)
			section.Stamp.TextColor3 = Theme.SubText
		end
	end
	titleLabel.Text = string.format("%s  (%d / %d 발견)", VIEWS.Passport.Title, found, #Landmarks.List)
end

-- 업그레이드 -----------------------------------------------------------------

-- 레벨별 효과 표시
local function effectText(upgrade: PlayerState.Upgrade, level: number): string
	if upgrade.Id == "Globe" then
		return string.format("행운 x%.2f", 1 + upgrade.PerLevel * level)
	elseif upgrade.Id == "Agency" then
		return string.format("굴림 간격 %.2f초", Config.ROLL_COOLDOWN * (1 - upgrade.PerLevel * level))
	elseif upgrade.Id == "Park" then
		return string.format("전시 칸 %d", math.floor(Config.BASE_SLOTS + upgrade.PerLevel * level + 0.5))
	elseif upgrade.Id == "Ticket" then
		return string.format("관광 수입 x%.2f", 1 + upgrade.PerLevel * level)
	end
	return "Lv " .. level
end

local function paintBuyButton(row: UpgradeRow, coins: number)
	local affordable = row.Price ~= nil and coins >= row.Price
	if row.Affordable == affordable then
		return
	end
	row.Affordable = affordable
	row.Button.BackgroundColor3 = if affordable then Theme.Good else Theme.PanelLight
	row.Button.TextColor3 = if affordable then DARK_TEXT else Theme.SubText
	row.Button.AutoButtonColor = affordable
end

local function buildUpgrade(): ScrollingFrame
	local scroller = newScroller("Upgrade")
	local layout = Ui.list(Enum.FillDirection.Vertical, UPGRADE_GAP, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = scroller

	for order, upgrade in Config.Upgrades do
		local row = Ui.new("Frame", {
			Name = upgrade.Id,
			LayoutOrder = order,
			Size = UDim2.new(1, 0, 0, UPGRADE_ROW),
			BackgroundColor3 = Theme.PanelLight,
			Parent = scroller,
		})
		Ui.corner(12).Parent = row
		Ui.stroke(Theme.Accent, 2, 0.35).Parent = row
		Ui.padding(10).Parent = row

		Ui.label({
			Size = UDim2.new(0.44, 0, 0, 30),
			TextXAlignment = Enum.TextXAlignment.Left,
			Font = Theme.FontHeavy,
			Text = upgrade.Emoji .. " " .. upgrade.Name,
			Parent = row,
		}, 24)
		local level = Ui.label({
			Position = UDim2.fromScale(0.44, 0),
			Size = UDim2.new(0.24, 0, 0, 30),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = Theme.Gold,
			Parent = row,
		}, 20)
		Ui.label({
			Position = UDim2.fromOffset(0, 32),
			Size = UDim2.new(0.68, 0, 0, 20),
			TextXAlignment = Enum.TextXAlignment.Left,
			Text = upgrade.Description,
			TextColor3 = Theme.SubText,
			Parent = row,
		}, 17)
		local effect = Ui.label({
			Position = UDim2.fromOffset(0, 54),
			Size = UDim2.new(0.68, 0, 0, 22),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = Theme.Good,
			Parent = row,
		}, 18)
		local button = Ui.button({
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.fromScale(1, 0.5),
			Size = UDim2.new(0.3, 0, 1, 0),
			Parent = row,
		}, 24)
		button.Activated:Connect(function()
			local entry = upgradeRows[upgrade.Id]
			if entry and entry.Price then
				handlers.Buy(upgrade.Id)
			end
		end)
		upgradeRows[upgrade.Id] = { Level = level, Effect = effect, Button = button }
	end
	setCanvasHeight(scroller, #Config.Upgrades * (UPGRADE_ROW + UPGRADE_GAP) - UPGRADE_GAP)
	return scroller
end

local function renderUpgrade(state: Snapshot)
	for _, upgrade in Config.Upgrades do
		local row = upgradeRows[upgrade.Id]
		local level = PlayerState.upgradeLevel(state, upgrade.Id)
		local price = PlayerState.upgradePrice(upgrade.Id, level)
		row.Level.Text = string.format("Lv %d/%d", level, upgrade.MaxLevel)
		if price then
			row.Effect.Text = effectText(upgrade, level) .. " → " .. effectText(upgrade, level + 1)
			row.Button.Text = "💰 " .. Format.commas(price)
		else
			row.Effect.Text = effectText(upgrade, level) .. " (최대)"
			row.Button.Text = "최대 레벨"
		end
		row.Price = price
		row.Affordable = nil -- 가격이 바뀌었을 수 있으니 버튼 색을 다시 칠함
		paintBuyButton(row, lastCoins)
	end
end

-- 공통 -----------------------------------------------------------------------

local BUILDERS = {
	Collection = buildCollection,
	Passport = buildPassport,
	Upgrade = buildUpgrade,
}

local RENDERERS = {
	Collection = renderCollection,
	Passport = renderPassport,
	Upgrade = renderUpgrade,
}

local function render()
	local name = openName
	if not name then
		return
	end
	local view = VIEWS[name]
	titleLabel.Text = view.Title
	hintLabel.Text = view.Hint
	headerButton.Visible = false
	emptyLabel.Visible = false

	for other, scroller in scrollers do
		scroller.Visible = other == name
	end

	local state = lastState
	if not state then
		emptyLabel.Text = "불러오는 중..."
		emptyLabel.Visible = true
		return
	end
	emptyLabel.Text = "아직 발견한 명소가 없어요. 지구본을 돌려 보세요!"

	local scroller = scrollers[name]
	if not scroller then
		scroller = BUILDERS[name]()
		scrollers[name] = scroller
	end
	scroller.Visible = true
	RENDERERS[name](state)
end

function Panels.init(parent: ScreenGui, callbacks: Handlers)
	handlers = callbacks

	window = Ui.new("Frame", {
		Name = "Window",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(WINDOW_SIZE.X, WINDOW_SIZE.Y),
		BackgroundColor3 = Theme.Panel,
		BackgroundTransparency = 0.05,
		Visible = false,
		ZIndex = 5,
		Parent = parent,
	})
	Ui.corner(16).Parent = window
	Ui.stroke(Theme.Accent, 2, 0.2).Parent = window
	Ui.autoScale(window)

	titleLabel = Ui.label({
		Position = UDim2.fromOffset(16, 10),
		Size = UDim2.new(0.5, 0, 0, 34),
		TextXAlignment = Enum.TextXAlignment.Left,
		Font = Theme.FontHeavy,
		Parent = window,
	}, 28)
	hintLabel = Ui.label({
		Position = UDim2.fromOffset(16, 46),
		Size = UDim2.new(1, -32, 0, 20),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Theme.SubText,
		Parent = window,
	}, 16)

	headerButton = Ui.button({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -64, 0, 10),
		Size = UDim2.fromOffset(280, 36),
		Visible = false,
		Parent = window,
	}, 17)
	headerButton.Activated:Connect(function()
		handlers.ToggleAutoFeature()
	end)

	local close = Ui.button({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -12, 0, 10),
		Size = UDim2.fromOffset(40, 36),
		BackgroundColor3 = Theme.Bad,
		Text = "✕",
		Parent = window,
	}, 22)
	close.Activated:Connect(Panels.close)

	emptyLabel = Ui.label({
		Position = UDim2.fromOffset(12, BODY_TOP + 20),
		Size = UDim2.new(1, -24, 0, 40),
		TextColor3 = Theme.SubText,
		Visible = false,
		Parent = window,
	}, 24)
end

-- 같은 창 버튼을 다시 누르면 닫힘
function Panels.toggle(name: string)
	if not VIEWS[name] then
		return
	end
	if openName == name then
		Panels.close()
		return
	end
	openName = name
	window.Visible = true
	render()
end

function Panels.close()
	openName = nil
	window.Visible = false
end

-- 서버 상태가 실제로 바뀌었을 때만 호출됨 (열린 화면만 갱신, 나머지는 열 때 갱신)
function Panels.render(state: Snapshot?)
	lastState = state
	if state then
		lastCoins = state.Coins -- 곧 refreshCoins 가 부드러운 값으로 덮어씀
	end
	render()
end

-- 자주 호출해도 되는 가벼운 갱신: 업그레이드 버튼의 "살 수 있음" 색만 다시 칠함
function Panels.refreshCoins(coins: number)
	lastCoins = coins
	if openName ~= "Upgrade" then
		return
	end
	for _, row in upgradeRows do
		paintBuyButton(row, coins)
	end
end

return Panels
