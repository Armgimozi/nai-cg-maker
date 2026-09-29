-- 메뉴 창: 컬렉션(대표 지정), 여권(지역별 발견 현황 + 도장), 업그레이드
-- 크림색 창(Ui.window) 하나를 쓰고, 화면마다 리본 색과 제목만 바꿉니다.
-- 화면마다 카드를 한 번 만들고 상태가 바뀌면 글자/색만 고칩니다. 썸네일(ViewportFrame)은
-- 새로 발견했을 때만 만들어서, 자동 굴림 중에 창을 열어 둬도 매번 다시 만들지 않습니다.

local TweenService = game:GetService("TweenService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState)

local Icons = require(script.Parent.Icons)
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

local REGION_BONUS = math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)

local VIEWS = {
	Collection = {
		Title = "컬렉션",
		Color = "Sky",
		Hint = "카드를 누르면 대표 명소로 지정/해제돼요",
	},
	Passport = {
		Title = "여권",
		Color = "Grape",
		Hint = string.format(
			"한 지역의 명소를 모두 모으면 여권 도장 · 영구 행운 +%d%%",
			REGION_BONUS
		),
	},
	Upgrade = { Title = "업그레이드", Color = "Sun", Hint = "코인으로 사는 영구 강화" },
}

local WHITE = Color3.new(1, 1, 1)
local GOOD_DARK = Ui.colorPair("Grass").Shadow
local FEATURED_BG = Color3.fromRGB(255, 218, 128)

local WINDOW_SIZE = Vector2.new(760, 500)
local OPEN_OFFSET = -30 -- 창을 화면 가운데보다 조금 위로 (아래쪽 굴리기 버튼을 가리지 않게)
local BODY_TOP = 54 -- 창 본문 안에서 스크롤 영역이 시작하는 높이(위는 설명 + 머리 버튼)
-- 스크롤 영역 안쪽 여백(오른쪽은 스크롤바 자리)
local PAD_X, PAD_RIGHT, PAD_Y = 6, 14, 6

local COLLECTION_CELL = Vector2.new(128, 184)
local COLLECTION_GAP = 12
local COLLECTION_COLUMNS = 5

local PASSPORT_CELL = Vector2.new(104, 136)
local PASSPORT_GAP = 8
local PASSPORT_COLUMNS = 6
local PASSPORT_HEADER = 98
local SECTION_PAD = 14
local SECTION_GAP = 16

local UPGRADE_ROW = 84
local UPGRADE_GAP = 10
local UPGRADE_ICONS = { Globe = "globe", Agency = "plane", Park = "park", Ticket = "ticket" }

local Panels = {}

local win: Ui.Window
local window: Frame
local body: Frame
local hintLabel: TextLabel
local headerButton: Ui.ChunkyButton
local emptyLabel: TextLabel
local handlers: Handlers
local openName: string? = nil
local lastState: Snapshot? = nil
local lastCoins = 0

local scrollers: { [string]: ScrollingFrame } = {}

type CollectionCard = {
	Card: TextButton,
	Stars: TextLabel,
	Count: Ui.Chip,
	Shown: Ui.Chip,
	Badge: Ui.Chip,
}
local collectionCards: { [string]: CollectionCard } = {}

type Stamp = {
	Frame: Frame,
	Stroke: UIStroke,
	RingStroke: UIStroke,
	Labels: { TextLabel },
	Outlines: { UIStroke },
	Color: Color3,
}
type PassportSection = { Title: TextLabel, Note: TextLabel, Fill: Frame, Stamp: Stamp, Grid: Frame }
local passportSections: { [string]: PassportSection } = {}
local passportCards: { [string]: { Card: Frame, Known: boolean } } = {}

type UpgradeRow = {
	Level: Ui.Chip,
	Effect: TextLabel,
	Button: Ui.ChunkyButton,
	Price: number?,
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
		Position = UDim2.fromOffset(0, BODY_TOP),
		Size = UDim2.new(1, 0, 1, -BODY_TOP),
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

local function setCanvasHeight(scroller: ScrollingFrame, contentHeight: number)
	scroller.CanvasSize = UDim2.fromOffset(0, contentHeight + PAD_Y * 2)
end

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
	Viewport.thumbnail(frame, landmark, {
		Position = UDim2.fromOffset(2, 2),
		Size = UDim2.new(1, -4, 1, -4),
	})
	return frame
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
		AutoButtonColor = false,
		BackgroundColor3 = Theme.Paper,
	})
	Ui.corner(12).Parent = card
	Ui.stroke(Theme.Ink, 3).Parent = card

	-- 등급 색 띠 (위쪽 모서리만 둥글게: 아래 절반을 네모 판으로 덮음)
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
		Text = tier.Name,
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = band,
	}, 15)
	Ui.outline(bandLabel, 1.5)

	photo(card, landmark, UDim2.fromOffset(7, 33), UDim2.new(1, -14, 0, 84), 8)

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
	local shown = Ui.chip({
		Name = "Shown",
		Color = "Grass",
		Text = "전시 중",
		Height = 20,
		TextSize = 13,
		StrokeThickness = 2,
		Position = UDim2.fromOffset(3, 96),
		ZIndex = 3,
		Visible = false,
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
		handlers.Feature(if featured then nil else landmark.Id)
	end)

	card.Parent = parent
	return { Card = card, Stars = stars, Count = count, Shown = shown, Badge = badge }
end

local function renderCollection(state: Snapshot)
	local scroller = scrollers.Collection
	local autoFeature = state.Settings.AutoFeature
	headerButton.Root.Visible = true
	headerButton.SetText(if autoFeature then "자동 대표: 켬" else "자동 대표: 끔")
	headerButton.SetColor(if autoFeature then "Grass" else "Gray")

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
			entry.Card.BackgroundColor3 = if featured then FEATURED_BG else Theme.Paper
			entry.Badge.Root.Visible = featured
			entry.Stars.Text = Ui.starsRich(PlayerState.stars(count), #Config.STAR_THRESHOLDS)
			entry.Count.Label.Text = "×" .. Format.commas(count)
			entry.Shown.Root.Visible = inPark[landmark.Id] == true
		elseif entry then
			entry.Card:Destroy()
			collectionCards[landmark.Id] = nil
		end
	end

	win.Title.Text = string.format("%s (%d종)", VIEWS.Collection.Title, shown)
	emptyLabel.Visible = shown == 0
	setCanvasHeight(scroller, gridHeight(shown, COLLECTION_COLUMNS, COLLECTION_CELL.Y, COLLECTION_GAP))
end

-- 여권 -----------------------------------------------------------------------

-- 지역 도장: 지역 색 동그라미(기울임) + 흰 안쪽 고리 + 지역 이름 + 보너스
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

	local name = Ui.label({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.42),
		Size = UDim2.fromScale(0.78, 0.3),
		Text = region.Name,
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = frame,
	}, 18)
	local bonus = Ui.label({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.7),
		Size = UDim2.fromScale(0.66, 0.18),
		Text = string.format("행운 +%d%%", REGION_BONUS),
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = frame,
	}, 13)
	return {
		Frame = frame,
		Stroke = stroke,
		RingStroke = ringStroke,
		Labels = { name, bonus },
		Outlines = { Ui.outline(name, 2), Ui.outline(bonus, 1.5) },
		Color = region.Color,
	}
end

-- 다 모으면 진하게 찍힌 도장, 아니면 흐릿한 도장 자국
local function paintStamp(stamp: Stamp, complete: boolean)
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

local function buildPassport(): ScrollingFrame
	local scroller = newScroller("Passport")
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

		local title = Ui.label({
			Position = UDim2.fromOffset(SECTION_PAD, 10),
			Size = UDim2.new(0.6, 0, 0, 34),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = section,
		}, 28)
		-- 발견 진행 막대
		local track = Ui.new("Frame", {
			Position = UDim2.fromOffset(SECTION_PAD, 50),
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
		local note = Ui.label({
			Position = UDim2.fromOffset(SECTION_PAD, 70),
			Size = UDim2.new(0.6, 0, 0, 20),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = section,
		}, 17)

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
		passportSections[region.Id] = { Title = title, Note = note, Fill = fill, Stamp = stamp, Grid = grid }
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
			Position = UDim2.fromOffset(4, 98),
			Size = UDim2.new(1, -8, 0, 16),
			Text = Format.oneIn(landmark.OneIn),
			TextTransparency = 0.3,
			Parent = card,
		}, 14)
		Ui.label({
			Position = UDim2.fromOffset(4, 115),
			Size = UDim2.new(1, -8, 0, 16),
			Text = tier.Name,
			TextColor3 = tier.Color:Lerp(Theme.Ink, 0.4),
			Parent = card,
		}, 13)
	else
		-- 아직 못 찾은 명소: 어두운 카드 + "?" + 확률
		Ui.label({
			Position = UDim2.fromOffset(5, 5),
			Size = UDim2.new(1, -10, 0, 70),
			Font = Theme.FontTitle,
			Text = "?",
			TextColor3 = Theme.Paper,
			TextTransparency = 0.2,
			Parent = card,
		}, 50)
		Ui.label({
			Position = UDim2.fromOffset(4, 82),
			Size = UDim2.new(1, -8, 0, 20),
			Text = Format.oneIn(landmark.OneIn),
			TextColor3 = tier.Color,
			Parent = card,
		}, 16)
		Ui.label({
			Position = UDim2.fromOffset(4, 106),
			Size = UDim2.new(1, -8, 0, 18),
			Text = tier.Name,
			TextColor3 = Theme.Cream,
			TextTransparency = 0.4,
			Parent = card,
		}, 13)
	end

	card.Parent = parent
	return card
end

local function renderPassport(state: Snapshot)
	local found = 0
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

		local complete = #list > 0 and discovered == #list
		section.Title.Text = string.format(
			'%s  <font color="%s">%d/%d</font>',
			region.Name,
			Format.hex(region.Color:Lerp(Theme.Ink, 0.3)),
			discovered,
			#list
		)
		section.Fill.Size = UDim2.fromScale(if #list > 0 then discovered / #list else 0, 1)
		if complete then
			section.Note.Text = string.format("도장 획득! 행운 +%d%%", REGION_BONUS)
			section.Note.TextColor3 = GOOD_DARK
		else
			section.Note.Text = string.format("도장까지 %d곳", #list - discovered)
			section.Note.TextColor3 = Theme.Ink
		end
		paintStamp(section.Stamp, complete)
	end
	win.Title.Text = string.format("%s (%d/%d 발견)", VIEWS.Passport.Title, found, #Landmarks.List)
end

-- 업그레이드 -----------------------------------------------------------------

-- 레벨별 효과 표시
local function effectText(upgrade: PlayerState.Upgrade, level: number): string
	if upgrade.Id == "Globe" then
		return string.format("행운 ×%.2f", 1 + upgrade.PerLevel * level)
	elseif upgrade.Id == "Agency" then
		return string.format("굴림 간격 %.2f초", Config.ROLL_COOLDOWN * (1 - upgrade.PerLevel * level))
	elseif upgrade.Id == "Park" then
		return string.format("전시 칸 %d", math.floor(Config.BASE_SLOTS + upgrade.PerLevel * level + 0.5))
	elseif upgrade.Id == "Ticket" then
		return string.format("관광 수입 ×%.2f", 1 + upgrade.PerLevel * level)
	end
	return "Lv " .. level
end

-- 살 수 있으면 Sun, 코인이 모자라면 Gray, 최대 레벨이면 Grape (같은 색이면 버튼이 알아서 건너뜀)
local function paintBuyButton(row: UpgradeRow, coins: number)
	local price = row.Price
	row.Button.SetColor(if price == nil then "Grape" elseif coins >= price then "Sun" else "Gray")
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
			BackgroundColor3 = Theme.Paper,
			Parent = scroller,
		})
		Ui.corner(14).Parent = row
		Ui.stroke(Theme.Ink, 3).Parent = row

		-- 아이콘 동그라미
		local disc = Ui.new("Frame", {
			AnchorPoint = Vector2.new(0, 0.5),
			Position = UDim2.new(0, 12, 0.5, 0),
			Size = UDim2.fromOffset(64, 64),
			BackgroundColor3 = Theme.Cream,
			Parent = row,
		})
		Ui.round().Parent = disc
		Ui.stroke(Theme.Ink, 3).Parent = disc
		Icons.view(disc, UPGRADE_ICONS[upgrade.Id] or "star", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.86, 0.86),
		})

		-- 이름 + 레벨 칩
		local head = Ui.new("Frame", {
			Position = UDim2.fromOffset(90, 6),
			Size = UDim2.new(1, -290, 0, 30),
			BackgroundTransparency = 1,
			Parent = row,
		})
		Ui.list(Enum.FillDirection.Horizontal, 10).Parent = head
		Ui.label({
			LayoutOrder = 1,
			AutomaticSize = Enum.AutomaticSize.X,
			Size = UDim2.fromScale(0, 1),
			TextScaled = false,
			TextSize = 24,
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

		Ui.label({
			Position = UDim2.fromOffset(90, 38),
			Size = UDim2.new(1, -290, 0, 18),
			TextXAlignment = Enum.TextXAlignment.Left,
			Text = upgrade.Description,
			TextTransparency = 0.35,
			Parent = row,
		}, 17)
		local effect = Ui.label({
			Position = UDim2.fromOffset(90, 58),
			Size = UDim2.new(1, -290, 0, 22),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = row,
		}, 19)

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
		row.Level.Label.Text = string.format("Lv %d/%d", level, upgrade.MaxLevel)
		if price then
			row.Effect.Text = string.format(
				'%s  <font color="%s">→ %s</font>',
				effectText(upgrade, level),
				Format.hex(GOOD_DARK),
				effectText(upgrade, level + 1)
			)
			row.Button.SetText(Format.commas(price))
			row.Button.SetIcon("coin")
		else
			row.Effect.Text = effectText(upgrade, level) .. " (최대)"
			row.Button.SetText("최대")
			row.Button.SetIcon(nil)
		end
		row.Price = price
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
	win.SetColor(view.Color)
	win.Title.Text = view.Title
	hintLabel.Text = view.Hint
	headerButton.Root.Visible = false
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

	win = Ui.window({
		Name = "Window",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0.5, OPEN_OFFSET),
		Size = UDim2.fromOffset(WINDOW_SIZE.X, WINDOW_SIZE.Y),
		Color = "Sky",
		RibbonWidth = 360,
		ZIndex = 5,
		Visible = false,
		Parent = parent,
	})
	window = win.Root
	body = win.Body
	Ui.autoScale(window)
	win.Close.Activated:Connect(Panels.close)

	hintLabel = Ui.label({
		Position = UDim2.fromOffset(4, 2),
		Size = UDim2.new(1, -250, 0, 40),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextTransparency = 0.25,
		Parent = body,
	}, 18)

	headerButton = Ui.chunkyButton({
		Name = "AutoFeature",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -4, 0, -2),
		Size = UDim2.fromOffset(220, 50),
		Color = "Grass",
		TextSize = 20,
		Visible = false,
		Parent = body,
	})
	headerButton.Activated:Connect(function()
		handlers.ToggleAutoFeature()
	end)

	emptyLabel = Ui.label({
		Position = UDim2.fromOffset(0, BODY_TOP + 30),
		Size = UDim2.new(1, 0, 0, 40),
		TextTransparency = 0.3,
		Visible = false,
		Parent = body,
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
