-- 기본 화면(HUD): 코인·수입·스탯, 메뉴 버튼, 굴리기 버튼, 지구본 굴림 연출, 뉴스 속보, 알림
-- 스타일은 DESIGN.md "UI 스타일 가이드 (v2)" — 통통한 버튼 + 굵은 Ink 테두리 + 3D 미니 아이콘, 이모지 없음

local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState)

local Icons = require(script.Parent.Icons)
local Ui = require(script.Parent.Ui)
local Viewport = require(script.Parent.Viewport)
local Theme = Ui.Theme

-- 등급(Rank)별 지구본이 도는 시간(초). 빠른 모드(자동 굴림)에서는 세계 명소 미만만 절반으로 줄임.
local REVEAL_SECONDS = { 0.9, 1.1, 1.5, 2.1, 2.7, 3.1, 3.3 }
local LAND_SECONDS = 0.4 -- 결과 지역에 멈춘 뒤 결과가 나오기까지
local SUSPENSE_SECONDS = 0.9 -- 불가사의 이상 "? ? ?" 뜸 들이기
local NEWS_SECONDS = 7
local MAX_NEWS = 2
local MAX_TOASTS = 4
local TICK_SOUND = "rbxasset://sounds/electronicpingshort.wav"

local WHITE = Color3.new(1, 1, 1)
local BLACK = Color3.new(0, 0, 0)
local INCOME_GREEN = Color3.fromRGB(150, 255, 150)
local HINT_COLOR = Color3.fromRGB(200, 196, 225)
local STAR_EMPTY_ON_GRAPE = Color3.fromRGB(200, 180, 255)

local MENU_BUTTON = Vector2.new(84, 90) -- 앞면 84x84 + 그림자 6
local ROLL_BUTTON = Vector2.new(270, 90) -- 앞면 270x84
local AUTO_BUTTON = Vector2.new(120, 76) -- 앞면 120x70
local VIEW_SIZE = 230 -- 굴림 연출의 둥근 판 지름
local RAY_COUNT = 12 -- 햇살 막대 수 (막대 하나 = 가운데를 지나는 빛줄기 2개)

-- 햇살 막대: 가운데는 진하고 양 끝으로 갈수록 투명
local RAY_FADE = NumberSequence.new({
	NumberSequenceKeypoint.new(0, 1),
	NumberSequenceKeypoint.new(0.3, 0.55),
	NumberSequenceKeypoint.new(0.5, 0.2),
	NumberSequenceKeypoint.new(0.7, 0.55),
	NumberSequenceKeypoint.new(1, 1),
})

export type RevealInfo = {
	Fast: boolean,
	IsNew: boolean,
	StarUp: boolean,
	Stars: number,
	Bonus: number,
	Luck: number,
}

export type Handlers = {
	Roll: () -> (),
	ToggleAuto: () -> (),
	Menu: (string) -> (),
	Teleport: () -> (),
}

local Hud = {}

local gui: ScreenGui
local flashFrame: Frame
local refs: { [string]: any } = {}
local spinRandom = Random.new()
local hideToken = 0
local shownCoins = -1
local newsItems: { Frame } = {}
local newsOrder = 0
local toasts: { Frame } = {}
local toastOrder = 0
local burstTween: Tween? = nil

local function makeSound(pitch: number, volume: number): Sound
	return Ui.new("Sound", {
		SoundId = TICK_SOUND,
		PlaybackSpeed = pitch,
		Volume = volume,
		Parent = SoundService,
	})
end

local tickSound: Sound
local landSound: Sound
local revealSound: Sound
local rareSound: Sound
local newsSound: Sound

local function play(sound: Sound?)
	if sound then
		sound.TimePosition = 0
		sound:Play()
	end
end

-- 화면 구석에 붙는 투명 컨테이너(화면 크기에 따라 자동 스케일)
local function anchor(name: string, anchorPoint: Vector2, position: UDim2, size: UDim2, zIndex: number?): Frame
	local frame = Ui.new("Frame", {
		Name = name,
		AnchorPoint = anchorPoint,
		Position = position,
		Size = size,
		BackgroundTransparency = 1,
		ZIndex = zIndex or 1,
		Parent = gui,
	})
	Ui.autoScale(frame)
	return frame
end

-- 초당 수입 표시: 작은 값은 소수 한 자리까지 ("1.8"), 큰 값은 축약 ("12.5K")
local function incomeText(income: number): string
	if income < 100 then
		local text = string.format("%.1f", math.floor(income * 10) / 10):gsub("%.0$", "")
		return text
	end
	return Format.short(income)
end

-- "x1.25" -> "×1.25"
local function timesText(value: number): string
	return "×" .. Format.multiplier(value):sub(2)
end

-- 왼쪽 위: 코인 알약 + 수입 알약 + 작은 칩 ------------------------------------

local function buildStats()
	local container = anchor("Stats", Vector2.new(0, 0), UDim2.fromOffset(14, 12), UDim2.fromOffset(300, 146))

	local coins = Ui.pill({
		Name = "Coins",
		Position = UDim2.fromOffset(20, 6),
		Size = UDim2.fromOffset(250, 52),
		Icon = "coin",
		IconSize = 68,
		IconSpin = 50,
		MaxTextSize = 36,
		BackgroundTransparency = 0.2,
		Parent = container,
	})
	refs.CoinLabel = coins.Label

	refs.IncomePill = Ui.pill({
		Name = "Income",
		Position = UDim2.fromOffset(46, 70),
		Size = UDim2.fromOffset(150, 32),
		TextColor3 = INCOME_GREEN,
		TextXAlignment = Enum.TextXAlignment.Center,
		MaxTextSize = 22,
		Parent = container,
	})

	local chips = Ui.new("Frame", {
		Name = "Chips",
		Position = UDim2.fromOffset(20, 112),
		Size = UDim2.fromOffset(280, 30),
		BackgroundTransparency = 1,
		Parent = container,
	})
	Ui.list(Enum.FillDirection.Horizontal, 8).Parent = chips
	refs.RollsChip =
		Ui.chip({ Name = "Rolls", Color = "Sky", Height = 28, TextSize = 17, LayoutOrder = 1, Parent = chips })
	refs.LuckChip =
		Ui.chip({ Name = "Luck", Color = "Grass", Height = 28, TextSize = 17, LayoutOrder = 2, Parent = chips })
end

-- 왼쪽 가운데: 네모 통통 버튼 4개 ---------------------------------------------

local MENU = {
	{ Id = "Collection", Text = "컬렉션", Color = "Sky", Icon = "collection" },
	{ Id = "Passport", Text = "여권", Color = "Grape", Icon = "passport" },
	{ Id = "Upgrade", Text = "업그레이드", Color = "Sun", Icon = "hammer" },
}

local function buildMenu(onMenu: (string) -> (), onTeleport: () -> ())
	local count = #MENU + 1
	local gap = 12
	local container = anchor(
		"Menu",
		Vector2.new(0, 0.5),
		UDim2.new(0, 14, 0.5, 16),
		UDim2.fromOffset(MENU_BUTTON.X + 8, count * MENU_BUTTON.Y + (count - 1) * gap)
	)
	Ui.list(Enum.FillDirection.Vertical, gap).Parent = container

	for order, entry in MENU do
		local button = Ui.chunkyButton({
			Name = entry.Id,
			LayoutOrder = order,
			Size = UDim2.fromOffset(MENU_BUTTON.X, MENU_BUTTON.Y),
			Color = entry.Color,
			Icon = entry.Icon,
			Vertical = true,
			Text = entry.Text,
			TextSize = 18,
			Parent = container,
		})
		button.Activated:Connect(function()
			onMenu(entry.Id)
		end)
	end

	refs.TeleportButton = Ui.chunkyButton({
		Name = "Teleport",
		LayoutOrder = count,
		Size = UDim2.fromOffset(MENU_BUTTON.X, MENU_BUTTON.Y),
		Color = "Grass",
		Icon = "park",
		Vertical = true,
		Text = "내 공원",
		TextSize = 18,
		Parent = container,
	})
	refs.TeleportButton.Activated:Connect(onTeleport)
end

-- 아래 가운데: 굴리기 + 자동 + 여권 도장 알약 ----------------------------------

local function buildRollBar(onRoll: () -> (), onToggleAuto: () -> ())
	local width = ROLL_BUTTON.X + 2 * (AUTO_BUTTON.X + 16)
	local container = anchor("RollBar", Vector2.new(0.5, 1), UDim2.new(0.5, 0, 1, -14), UDim2.fromOffset(width, 140))

	-- 여권 도장 k/6 (+ 키 안내) 알약: 가운데 정렬
	local infoRow = Ui.new("Frame", {
		Name = "InfoRow",
		Size = UDim2.new(1, 0, 0, 36),
		BackgroundTransparency = 1,
		Parent = container,
	})
	Ui.list(Enum.FillDirection.Horizontal, 0, Enum.HorizontalAlignment.Center).Parent = infoRow
	refs.InfoPill = Ui.pill({
		Name = "Info",
		AutoWidth = true,
		Size = UDim2.fromOffset(0, 30),
		Icon = "passport",
		IconBack = Theme.Cream,
		IconSize = 42,
		TextSize = 17,
		Parent = infoRow,
	})

	local roll = Ui.chunkyButton({
		Name = "Roll",
		Position = UDim2.new(0.5, -ROLL_BUTTON.X / 2, 1, -ROLL_BUTTON.Y),
		Size = UDim2.fromOffset(ROLL_BUTTON.X, ROLL_BUTTON.Y),
		Color = "Grass",
		Icon = "globe",
		IconSize = 70,
		IconSpin = 60,
		Text = "굴리기",
		TextSize = 40,
		OutlineThickness = 3,
		Parent = container,
	})
	roll.Activated:Connect(onRoll)
	refs.RollButton = roll
	-- 글자는 쿨타임 막대 위쪽에
	roll.Label.Position = UDim2.fromOffset(82, 2)
	roll.Label.Size = UDim2.new(1, -94, 1, -22)

	-- 쿨타임: 버튼 안 아래쪽 막대가 비었다가 가득 차면 다시 굴릴 수 있음
	local track = Ui.new("Frame", {
		Name = "Cooldown",
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 84, 1, -9),
		Size = UDim2.new(1, -100, 0, 10),
		BackgroundColor3 = Theme.Ink,
		BackgroundTransparency = 0.5,
		BorderSizePixel = 0,
		ZIndex = 5,
		Parent = roll.Face,
	})
	Ui.round().Parent = track
	refs.CooldownFill = Ui.new("Frame", {
		Name = "Fill",
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = WHITE,
		BorderSizePixel = 0,
		ZIndex = 6,
		Parent = track,
	})
	Ui.round().Parent = refs.CooldownFill

	local auto = Ui.chunkyButton({
		Name = "Auto",
		Position = UDim2.new(0.5, ROLL_BUTTON.X / 2 + 16, 1, -(ROLL_BUTTON.Y + AUTO_BUTTON.Y) / 2),
		Size = UDim2.fromOffset(AUTO_BUTTON.X, AUTO_BUTTON.Y),
		Color = "Gray",
		Text = "자동",
		TextSize = 28,
		Parent = container,
	})
	auto.Activated:Connect(onToggleAuto)
	refs.AutoButton = auto
	refs.AutoBadge = Ui.chip({
		Name = "On",
		Color = "Coral",
		Text = "ON",
		Height = 24,
		TextSize = 16,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(1, -10, 0, 2),
		Rotation = 12,
		ZIndex = 6,
		Visible = false,
		Parent = auto.Face,
	})
end

-- 굴림 연출 ------------------------------------------------------------------

local function buildReveal()
	local container = anchor(
		"Reveal",
		Vector2.new(0.5, 0.5),
		UDim2.fromScale(0.5, 0.45),
		UDim2.fromOffset(700, 500),
		8 -- 메뉴 창보다 위
	)
	container.Visible = false
	refs.Reveal = container

	local inner = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Parent = container,
	})
	refs.RevealScale = Ui.new("UIScale", { Parent = inner })

	-- 지역 이름: 도는 동안은 지역 색 글자, 멈추면 지역 색 딱지
	local regionTag = Ui.new("Frame", {
		Name = "Region",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.fromScale(0.5, 0),
		Size = UDim2.fromOffset(280, 48),
		BackgroundTransparency = 1,
		ZIndex = 4,
		Parent = inner,
	})
	Ui.round().Parent = regionTag
	refs.RegionStroke = Ui.stroke()
	refs.RegionStroke.Parent = regionTag
	refs.RegionTag = regionTag
	refs.RevealRegion = Ui.label({
		Position = UDim2.fromOffset(12, 4),
		Size = UDim2.new(1, -24, 1, -8),
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = regionTag,
	}, 34)
	Ui.outline(refs.RevealRegion, 3)

	local centerY = 62 + VIEW_SIZE / 2

	-- 뒤에서 도는 햇살 (막대 12개를 가운데 기준으로 돌려 놓음)
	local burst = Ui.new("Frame", {
		Name = "Burst",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0, centerY),
		Size = UDim2.fromOffset(500, 500),
		BackgroundTransparency = 1,
		Visible = false,
		ZIndex = 1,
		Parent = inner,
	})
	refs.Burst = burst
	refs.Rays = {}
	for i = 1, RAY_COUNT do
		local ray = Ui.new("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.new(0, 30, 1, 0),
			Rotation = (i - 1) * 180 / RAY_COUNT,
			BackgroundColor3 = WHITE,
			BorderSizePixel = 0,
			Parent = burst,
		})
		Ui.new("UIGradient", { Rotation = 90, Transparency = RAY_FADE, Parent = ray })
		table.insert(refs.Rays, ray)
	end

	-- 모형 뒤의 둥근 판
	local disc = Ui.new("Frame", {
		Name = "Disc",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0, centerY),
		Size = UDim2.fromOffset(VIEW_SIZE, VIEW_SIZE),
		BackgroundColor3 = Theme.Cream,
		ZIndex = 2,
		Parent = inner,
	})
	Ui.round().Parent = disc
	Ui.stroke(Theme.Ink, 5).Parent = disc
	local ring = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.new(1, -18, 1, -18),
		BackgroundTransparency = 1,
		Parent = disc,
	})
	Ui.round().Parent = ring
	Ui.stroke(WHITE, 3, 0.15).Parent = ring
	refs.Disc = disc

	local viewProps = {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0, centerY),
		Size = UDim2.fromOffset(VIEW_SIZE - 16, VIEW_SIZE - 16),
		ZIndex = 3,
	}
	refs.EarthView = Viewport.new(inner, viewProps)
	Viewport.setLandmark(refs.EarthView, Landmarks.ById.earth, 10)
	refs.ResultView = Viewport.new(inner, viewProps)
	refs.ResultView.Visible = false

	-- 등급 리본 (판 아래쪽에 걸침)
	local ribbon = Ui.new("Frame", {
		Name = "TierRibbon",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0, centerY + VIEW_SIZE / 2),
		Size = UDim2.fromOffset(250, 44),
		BackgroundTransparency = 1,
		Visible = false,
		ZIndex = 4,
		Parent = inner,
	})
	refs.RibbonTails = {}
	for _, side in { 0, 1 } do
		local tail = Ui.new("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(side, if side == 0 then -14 else 14, 0.5, 9),
			Size = UDim2.fromOffset(42, 34),
			BorderSizePixel = 0,
			ZIndex = 1,
			Parent = ribbon,
		})
		Ui.corner(8).Parent = tail
		Ui.stroke().Parent = tail
		table.insert(refs.RibbonTails, tail)
	end
	local ribbonMain = Ui.new("Frame", {
		Size = UDim2.fromScale(1, 1),
		BorderSizePixel = 0,
		ZIndex = 2,
		Parent = ribbon,
	})
	Ui.corner(10).Parent = ribbonMain
	Ui.stroke().Parent = ribbonMain
	refs.RibbonLabel = Ui.label({
		Position = UDim2.fromOffset(10, 4),
		Size = UDim2.new(1, -20, 1, -8),
		TextColor3 = WHITE,
		ZIndex = 3,
		Parent = ribbonMain,
	}, 28)
	Ui.outline(refs.RibbonLabel, 2.5)
	refs.Ribbon = ribbon
	refs.RibbonMain = ribbonMain

	local nameTop = centerY + VIEW_SIZE / 2 + 28
	refs.RevealName = Ui.label({
		Position = UDim2.fromOffset(0, nameTop),
		Size = UDim2.new(1, 0, 0, 66),
		Font = Theme.FontTitle,
		ZIndex = 4,
		Parent = inner,
	}, 62)
	Ui.outline(refs.RevealName, 4)
	refs.RevealOdds = Ui.label({
		Position = UDim2.fromOffset(0, nameTop + 66),
		Size = UDim2.new(1, 0, 0, 30),
		Font = Theme.FontTitle,
		TextColor3 = WHITE,
		ZIndex = 4,
		Parent = inner,
	}, 28)
	Ui.outline(refs.RevealOdds, 2.5)
	refs.RevealSubtitle = Ui.label({
		Position = UDim2.fromOffset(0, nameTop + 96),
		Size = UDim2.new(1, 0, 0, 22),
		TextColor3 = Theme.Cream,
		ZIndex = 4,
		Parent = inner,
	}, 20)
	Ui.outline(refs.RevealSubtitle, 2)

	-- 딱지 줄: NEW / 별 상승 / 발견 보너스
	local tagRow = Ui.new("Frame", {
		Name = "Tags",
		Position = UDim2.fromOffset(0, nameTop + 126),
		Size = UDim2.new(1, 0, 0, 36),
		BackgroundTransparency = 1,
		Visible = false,
		ZIndex = 4,
		Parent = inner,
	})
	Ui.list(Enum.FillDirection.Horizontal, 14, Enum.HorizontalAlignment.Center).Parent = tagRow
	refs.TagRow = tagRow
	refs.NewChip = Ui.chip({
		Name = "New",
		Color = "Coral",
		Text = "NEW",
		Font = Theme.FontTitle,
		Height = 32,
		TextSize = 22,
		LayoutOrder = 1,
		Parent = tagRow,
	})
	refs.StarChip = Ui.chip({
		Name = "StarUp",
		Color = "Grape",
		Height = 32,
		TextSize = 19,
		LayoutOrder = 2,
		Parent = tagRow,
	})
	refs.BonusPill = Ui.pill({
		Name = "Bonus",
		AutoWidth = true,
		Size = UDim2.fromOffset(0, 32),
		Icon = "coin",
		IconSize = 44,
		TextSize = 21,
		TextColor3 = Ui.colorPair("Sun").Face,
		LayoutOrder = 3,
		Parent = tagRow,
	})
end

-- 뉴스 속보 / 알림 자리 ------------------------------------------------------

local function buildNotices()
	-- 뉴스 속보(맨 위)
	local news = anchor("News", Vector2.new(0.5, 0), UDim2.new(0.5, 0, 0, 10), UDim2.fromOffset(720, 118), 9)
	local newsLayout = Ui.list(Enum.FillDirection.Vertical, 8, Enum.HorizontalAlignment.Center)
	newsLayout.VerticalAlignment = Enum.VerticalAlignment.Top
	newsLayout.Parent = news
	refs.News = news

	-- 잠깐 떴다 사라지는 알림(뉴스 아래)
	local notices = anchor("Notices", Vector2.new(0.5, 0), UDim2.new(0.5, 0, 0, 134), UDim2.fromOffset(600, 200), 9)
	local layout = Ui.list(Enum.FillDirection.Vertical, 8, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = notices
	refs.Notices = notices
end

function Hud.init(playerGui: PlayerGui, handlers: Handlers): ScreenGui
	gui = Ui.new("ScreenGui", {
		Name = "LandmarkRNG",
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = playerGui,
	})
	local flashGui = Ui.new("ScreenGui", {
		Name = "LandmarkRNGFlash",
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		DisplayOrder = 5,
		Parent = playerGui,
	})
	flashFrame = Ui.new("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Parent = flashGui,
	})

	tickSound = makeSound(1.4, 0.25)
	landSound = makeSound(1.1, 0.4)
	revealSound = makeSound(0.9, 0.6)
	rareSound = makeSound(0.5, 1)
	newsSound = makeSound(0.7, 0.5)

	buildStats()
	buildMenu(handlers.Menu, handlers.Teleport)
	buildRollBar(handlers.Roll, handlers.ToggleAuto)
	buildReveal()
	buildNotices()
	Hud.render(nil)
	return gui
end

function Hud.render(state: PlayerState.Snapshot?)
	if not state then
		refs.CoinLabel.Text = "불러오는 중..."
		refs.IncomePill.Root.Visible = false
		refs.RollsChip.Root.Visible = false
		refs.LuckChip.Root.Visible = false
		refs.InfoPill.Root.Visible = false
		shownCoins = -1
		return
	end
	refs.IncomePill.Label.Text = "+" .. incomeText(state.Income) .. "/초"
	refs.IncomePill.Root.Visible = true
	refs.RollsChip.Label.Text = "굴림 " .. Format.commas(state.Rolls)
	refs.RollsChip.Root.Visible = true
	refs.LuckChip.Label.Text = "행운 " .. timesText(state.Luck)
	refs.LuckChip.Root.Visible = true

	local stamps = #PlayerState.completedRegions(state)
	local info = string.format(
		'여권 도장 <font color="%s">%d/%d</font>',
		Format.hex(if stamps > 0 then Ui.colorPair("Sun").Face else WHITE),
		stamps,
		#Landmarks.Regions
	)
	if UserInputService.KeyboardEnabled then
		info ..= string.format('   <font color="%s">R 굴리기 · T 자동</font>', Format.hex(HINT_COLOR))
	end
	refs.InfoPill.Label.Text = info
	refs.InfoPill.Root.Visible = true
end

-- 매 프레임 호출: 부드럽게 올라가는 코인 표시 (정수가 바뀔 때만 글자 갱신)
function Hud.setCoins(amount: number)
	local whole = math.max(0, math.floor(amount))
	if whole == shownCoins then
		return
	end
	shownCoins = whole
	refs.CoinLabel.Text = Format.commas(whole)
end

function Hud.setAuto(enabled: boolean)
	refs.AutoButton.SetColor(if enabled then "Sun" else "Gray")
	refs.AutoBadge.Root.Visible = enabled
end

function Hud.setRolling(rolling: boolean)
	local button = refs.RollButton
	button.SetText(if rolling then "굴리는 중" else "굴리기")
	if button.Icon then
		Viewport.setSpin(button.Icon, if rolling then 420 else 60)
	end
end

-- where: 지금 있는 곳 ("Plaza" | "Park"). 버튼은 반대쪽으로 가는 버튼이 됨
function Hud.setLocation(where: string)
	local button = refs.TeleportButton
	if where == "Park" then
		button.SetText("광장")
		button.SetIcon("plaza")
	else
		button.SetText("내 공원")
		button.SetIcon("park")
	end
end

-- 쿨타임 막대가 비었다가 seconds 동안 가득 참
function Hud.startCooldown(seconds: number)
	local fill = refs.CooldownFill
	fill.Size = UDim2.fromScale(0, 1)
	TweenService:Create(fill, TweenInfo.new(seconds, Enum.EasingStyle.Linear), { Size = UDim2.fromScale(1, 1) }):Play()
end

local function flash(color: Color3, strength: number)
	flashFrame.BackgroundColor3 = color
	flashFrame.BackgroundTransparency = 1 - strength
	TweenService:Create(flashFrame, TweenInfo.new(1.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		BackgroundTransparency = 1,
	}):Play()
end

-- landed: 결과 지역에 멈췄으면 지역 색 딱지, 아니면 지역 색 글자만
local function showRegion(region: Landmarks.Region, landed: boolean)
	local label = refs.RevealRegion
	label.Text = region.Name
	if landed then
		refs.RegionTag.BackgroundColor3 = region.Color
		refs.RegionTag.BackgroundTransparency = 0
		refs.RegionStroke.Enabled = true
		label.TextColor3 = WHITE
	else
		refs.RegionTag.BackgroundTransparency = 1
		refs.RegionStroke.Enabled = false
		label.TextColor3 = region.Color
	end
end

local function showBurst(color: Color3)
	for _, ray in refs.Rays do
		ray.BackgroundColor3 = color
	end
	refs.Burst.Visible = true
	if not burstTween then
		refs.Burst.Rotation = 0
		local tween = TweenService:Create(
			refs.Burst,
			TweenInfo.new(10, Enum.EasingStyle.Linear, Enum.EasingDirection.InOut, -1),
			{ Rotation = 360 }
		)
		tween:Play()
		burstTween = tween
	end
end

local function hideBurst()
	refs.Burst.Visible = false
	local tween = burstTween
	if tween then
		tween:Cancel()
		burstTween = nil
	end
end

local function showRibbon(tier: Landmarks.Tier)
	refs.RibbonMain.BackgroundColor3 = tier.Color
	for _, tail in refs.RibbonTails do
		tail.BackgroundColor3 = tier.Color:Lerp(Theme.Ink, 0.35)
	end
	refs.RibbonLabel.Text = tier.Name
	refs.Ribbon.Visible = true
end

-- 굴림 연출. 결과를 보여 줄 때까지 기다립니다(yield).
-- 1) 지구본이 빠르게 돌며 지역 이름이 바뀌다 점점 느려짐 → 2) 결과 지역에 멈춤 → 3) 명소 공개
function Hud.reveal(landmark: Landmarks.Landmark, info: RevealInfo)
	hideToken += 1
	local tier = landmark.Tier
	local rank = tier.Rank
	local duration = REVEAL_SECONDS[rank] or 3
	if info.Fast and rank < 4 then
		duration = math.max(0.35, duration * 0.5)
	end
	local region = Landmarks.RegionById[landmark.Region] or Landmarks.Regions[1]
	local regions = Landmarks.Regions

	local container = refs.Reveal
	container.Visible = true
	refs.RevealScale.Scale = 1
	hideBurst()
	refs.Ribbon.Visible = false
	refs.RevealName.Text = ""
	refs.RevealOdds.Text = ""
	refs.RevealSubtitle.Text = ""
	refs.TagRow.Visible = false
	refs.Disc.BackgroundColor3 = Theme.Cream
	refs.ResultView.Visible = false
	Viewport.setSpin(refs.ResultView, 0)
	refs.EarthView.Visible = true

	-- 1) 지구본이 돌며 지역이 바뀜. 실제로 지난 시간을 더해야 연출 길이가 늘어지지 않음
	local index = spinRandom:NextInteger(1, #regions)
	local elapsed = 0
	while elapsed < duration do
		index = index % #regions + 1
		showRegion(regions[index], false)
		play(tickSound)
		local t = elapsed / duration
		Viewport.setSpin(refs.EarthView, 60 + 840 * (1 - t) * (1 - t))
		local interval = 0.05 + t * t * 0.22
		elapsed += task.wait(interval)
	end

	-- 2) 결과 지역에 착지
	showRegion(region, true)
	Viewport.setSpin(refs.EarthView, 30)
	play(landSound)
	task.wait(if info.Fast and rank < 4 then LAND_SECONDS * 0.5 else LAND_SECONDS)

	-- 불가사의 이상은 한 박자 뜸 들이기
	if rank >= 5 then
		refs.RevealName.Text = "? ? ?"
		refs.RevealName.TextColor3 = tier.Color
		showRibbon(tier)
		showBurst(tier.Color)
		flash(BLACK, 0.6)
		task.wait(SUSPENSE_SECONDS)
	end

	-- 3) 결과 공개: 지구본 → 명소 모형
	Viewport.setSpin(refs.EarthView, 0)
	refs.EarthView.Visible = false
	Viewport.setLandmark(refs.ResultView, landmark, 10)
	refs.ResultView.Visible = true
	Viewport.setSpin(refs.ResultView, 40)
	refs.Disc.BackgroundColor3 = tier.Color:Lerp(WHITE, 0.6)
	showBurst(tier.Color)
	showRibbon(tier)

	refs.RevealName.Text = landmark.Name
	refs.RevealName.TextColor3 = tier.Color
	refs.RevealOdds.Text = Format.oneIn(landmark.OneIn)
	refs.RevealSubtitle.Text = landmark.Subtitle

	local bonus = info.Bonus or 0
	refs.NewChip.Root.Visible = info.IsNew
	refs.StarChip.Root.Visible = info.StarUp
	if info.StarUp then
		refs.StarChip.Label.Text = "별 상승 "
			.. Ui.starsRich(info.Stars or 0, #Config.STAR_THRESHOLDS, STAR_EMPTY_ON_GRAPE)
	end
	refs.BonusPill.Root.Visible = bonus > 0
	if bonus > 0 then
		refs.BonusPill.Label.Text = "+" .. Format.commas(bonus)
	end
	refs.TagRow.Visible = info.IsNew or info.StarUp or bonus > 0

	refs.RevealScale.Scale = 1.35
	TweenService:Create(refs.RevealScale, TweenInfo.new(0.35, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {
		Scale = 1,
	}):Play()
	if rank >= 4 then
		flash(tier.Color, math.min(0.25 + rank * 0.08, 0.8))
		play(rareSound)
	else
		play(revealSound)
	end

	-- 결과를 잠깐 보여 줌 (자동 굴림 중에도 희귀 명소는 바로 덮이지 않게)
	local hold = if rank >= 4 then (if info.Fast then 1.8 else 0.6) else (if info.Fast then 0.2 else 0.1)
	task.wait(hold)

	local token = hideToken
	task.delay(if info.Fast then 1 else 2.5, function()
		if token == hideToken then
			container.Visible = false
			Viewport.setSpin(refs.ResultView, 0)
			hideBurst()
		end
	end)
end

-- 잠깐 떴다 사라지는 알림: 색(종류) 알약. color 는 알약 바탕색
function Hud.toast(text: string, color: Color3?, seconds: number?)
	toastOrder += 1
	while #toasts >= MAX_TOASTS do
		local oldest = table.remove(toasts, 1)
		if oldest then
			oldest:Destroy()
		end
	end

	local chip = Ui.chip({
		Name = "Toast",
		Color = color or Ui.colorPair("Sky").Face,
		Text = text,
		Height = 40,
		TextSize = 20,
		StrokeThickness = 3,
		LayoutOrder = toastOrder,
		Parent = refs.Notices,
	})
	local box = chip.Root
	table.insert(toasts, box)
	local scale = Ui.new("UIScale", { Scale = 0.4, Parent = box })
	TweenService:Create(scale, TweenInfo.new(0.22, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 })
		:Play()

	task.delay(seconds or 3, function()
		if not box.Parent then
			return -- 이미 밀려나서 지워짐
		end
		TweenService:Create(scale, TweenInfo.new(0.16, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { Scale = 0 })
			:Play()
		task.wait(0.18)
		local index = table.find(toasts, box)
		if index then
			table.remove(toasts, index)
		end
		box:Destroy()
	end)
end

-- 서버 전체 "속보": 신문 띠가 오른쪽에서 밀려 들어와 잠시 머문 뒤 쏙 사라짐
function Hud.news(playerName: string, landmark: Landmarks.Landmark, rollNumber: number)
	local tier = landmark.Tier
	newsOrder += 1

	-- 너무 많이 쌓이면 가장 오래된 것부터 지움
	while #newsItems >= MAX_NEWS do
		local oldest = table.remove(newsItems, 1)
		if oldest then
			oldest:Destroy()
		end
	end

	local item = Ui.new("Frame", {
		LayoutOrder = newsOrder,
		Size = UDim2.new(1, 0, 0, 54),
		BackgroundTransparency = 1,
		Parent = refs.News,
	})
	table.insert(newsItems, item)

	local slide = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(2, 0.5),
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Parent = item,
	})
	local scale = Ui.new("UIScale", { Parent = slide })

	-- 신문 띠: 크림 바탕 + Ink 테두리 + Ink 글자
	local bar = Ui.new("Frame", {
		Position = UDim2.fromOffset(56, 4),
		Size = UDim2.new(1, -56, 1, -8),
		BackgroundColor3 = Theme.Cream,
		ZIndex = 1,
		Parent = slide,
	})
	Ui.corner(10).Parent = bar
	Ui.stroke(Theme.Ink, 3).Parent = bar
	Ui.label({
		Position = UDim2.fromOffset(66, 5),
		Size = UDim2.new(1, -66 - 56, 1, -10),
		TextXAlignment = Enum.TextXAlignment.Left,
		Text = string.format(
			'%s 님이 <font color="%s">%s</font>(%s) 발견! · %s번째 탐험',
			Format.escape(playerName),
			Format.hex(tier.Color:Lerp(Theme.Ink, 0.35)),
			Format.escape(landmark.Name),
			Format.oneIn(landmark.OneIn),
			Format.commas(rollNumber)
		),
		Parent = bar,
	}, 22)
	Icons.view(bar, "news", {
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -6, 0.5, 0),
		Size = UDim2.fromOffset(46, 46),
		ZIndex = 2,
	})

	-- 빨간 "속보" 도장 딱지 (살짝 기울임)
	local stamp = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 0, 0.5, 0),
		Size = UDim2.fromOffset(112, 46),
		BackgroundColor3 = Ui.colorPair("Coral").Face,
		Rotation = -6,
		ZIndex = 2,
		Parent = slide,
	})
	Ui.corner(10).Parent = stamp
	Ui.stroke(Theme.Ink, 3).Parent = stamp
	local stampRing = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.new(1, -10, 1, -10),
		BackgroundTransparency = 1,
		Parent = stamp,
	})
	Ui.corner(7).Parent = stampRing
	Ui.stroke(WHITE, 2, 0.25).Parent = stampRing
	local stampLabel = Ui.label({
		Position = UDim2.fromOffset(8, 6),
		Size = UDim2.new(1, -16, 1, -12),
		Font = Theme.FontTitle,
		Text = "속보",
		TextColor3 = WHITE,
		ZIndex = 2,
		Parent = stamp,
	}, 26)
	Ui.outline(stampLabel, 2.5)

	play(newsSound)
	TweenService:Create(slide, TweenInfo.new(0.45, Enum.EasingStyle.Quint, Enum.EasingDirection.Out), {
		Position = UDim2.fromScale(0.5, 0.5),
	}):Play()

	task.delay(NEWS_SECONDS, function()
		if not item.Parent then
			return -- 이미 밀려나서 지워짐
		end
		TweenService:Create(scale, TweenInfo.new(0.3, Enum.EasingStyle.Back, Enum.EasingDirection.In), {
			Scale = 0,
		}):Play()
		task.wait(0.32)
		local index = table.find(newsItems, item)
		if index then
			table.remove(newsItems, index)
		end
		item:Destroy()
	end)
end

return Hud
