-- 기본 화면(HUD): 스탯, 메뉴 버튼, 굴리기 버튼, 지구본 굴림 연출, 뉴스 속보, 알림

local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState)

local Ui = require(script.Parent.Ui)
local Viewport = require(script.Parent.Viewport)
local Theme = Ui.Theme

-- 등급(Rank)별 지구본이 도는 시간(초). 빠른 모드(자동 굴림)에서는 세계 명소 미만만 절반으로 줄임.
local REVEAL_SECONDS = { 0.9, 1.1, 1.5, 2.1, 2.7, 3.1, 3.3 }
local LAND_SECONDS = 0.4 -- 지역에 📍 가 꽂힌 뒤 결과가 나오기까지
local SUSPENSE_SECONDS = 0.9 -- 불가사의 이상 "? ? ?" 뜸 들이기
local NEWS_SECONDS = 7
local MAX_NEWS = 2
local TICK_SOUND = "rbxasset://sounds/electronicpingshort.wav"

local NEWS_RED = Color3.fromRGB(215, 35, 50)
local NEWS_WHITE = Color3.fromRGB(250, 250, 252)
local NEWS_INK = Color3.fromRGB(25, 25, 35)

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

local function panel(props: { [string]: any }): Frame
	local frame = Ui.new("Frame", {
		BackgroundColor3 = Theme.Panel,
		BackgroundTransparency = 0.15,
	})
	for key, value in props do
		if key ~= "Parent" then
			(frame :: any)[key] = value
		end
	end
	Ui.corner(14).Parent = frame
	Ui.stroke().Parent = frame
	frame.Parent = props.Parent
	return frame
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

-- 글자 테두리 (UIStroke 기본값 Contextual = 글자에 적용)
local function textOutline(label: TextLabel, thickness: number)
	Ui.new("UIStroke", { Color = Color3.new(0, 0, 0), Thickness = thickness, Transparency = 0.2, Parent = label })
end

-- 초당 수입 표시: 작은 값은 소수 한 자리까지 ("1.8"), 큰 값은 축약 ("12.5K")
local function incomeText(income: number): string
	if income < 100 then
		local text = string.format("%.1f", math.floor(income * 10) / 10):gsub("%.0$", "")
		return text
	end
	return Format.short(income)
end

local function buildStats()
	local container = anchor("Stats", Vector2.new(0, 0), UDim2.new(0, 12, 0, 12), UDim2.fromOffset(270, 150))
	local box = panel({ Size = UDim2.fromScale(1, 1), Parent = container })
	Ui.padding(10).Parent = box
	Ui.list(Enum.FillDirection.Vertical, 2).Parent = box

	local function row(order: number, color: Color3, maxText: number): TextLabel
		return Ui.label({
			LayoutOrder = order,
			Size = UDim2.new(1, 0, 0, 30),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = color,
			Parent = box,
		}, maxText)
	end
	refs.Coins = row(1, Theme.Gold, 26)
	refs.Income = row(2, Theme.Good, 21)
	refs.Rolls = row(3, Theme.Text, 21)
	refs.Luck = row(4, Color3.fromRGB(140, 235, 160), 21)
end

local MENU = {
	{ "Collection", "🗂️ 컬렉션" },
	{ "Passport", "🛂 여권" },
	{ "Upgrade", "🛠️ 업그레이드" },
}

local function buildMenu(onMenu: (string) -> (), onTeleport: () -> ())
	local container = anchor("Menu", Vector2.new(0, 0.5), UDim2.new(0, 12, 0.5, 0), UDim2.fromOffset(160, 266))
	Ui.list(Enum.FillDirection.Vertical, 10).Parent = container
	for order, entry in MENU do
		local button = Ui.button({
			Name = entry[1],
			LayoutOrder = order,
			Size = UDim2.fromOffset(160, 58),
			Text = entry[2],
			Parent = container,
		}, 22)
		button.Activated:Connect(function()
			onMenu(entry[1])
		end)
	end

	refs.TeleportButton = Ui.button({
		Name = "Teleport",
		LayoutOrder = #MENU + 1,
		Size = UDim2.fromOffset(160, 58),
		BackgroundColor3 = Color3.fromRGB(45, 95, 70),
		Text = "🏞️ 내 공원",
		Parent = container,
	}, 22)
	refs.TeleportButton.Activated:Connect(onTeleport)
end

local function buildRollBar(onRoll: () -> (), onToggleAuto: () -> ())
	local container = anchor("RollBar", Vector2.new(0.5, 1), UDim2.new(0.5, 0, 1, -18), UDim2.fromOffset(440, 120))

	refs.Info = Ui.label({
		Size = UDim2.new(1, 0, 0, 30),
		TextColor3 = Theme.SubText,
		Parent = container,
	}, 20)
	textOutline(refs.Info, 1)

	local row = Ui.new("Frame", {
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(0, 40),
		Size = UDim2.new(1, 0, 0, 76),
		Parent = container,
	})
	Ui.list(Enum.FillDirection.Horizontal, 12, Enum.HorizontalAlignment.Center).Parent = row

	refs.AutoButton = Ui.button({
		LayoutOrder = 1,
		Size = UDim2.fromOffset(130, 76),
		Text = "자동: 끔",
		Parent = row,
	}, 22)
	refs.AutoButton.Activated:Connect(onToggleAuto)

	local rollButton = Ui.button({
		LayoutOrder = 2,
		Size = UDim2.fromOffset(250, 76),
		BackgroundColor3 = Color3.fromRGB(40, 120, 220),
		Text = "🌍 굴리기",
		ClipsDescendants = true,
		Parent = row,
	}, 32)
	rollButton.Activated:Connect(onRoll)
	refs.RollButton = rollButton

	-- 쿨타임 막대 (버튼 아래쪽)
	refs.CooldownBar = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, -6, 1, 6),
		Size = UDim2.new(0, 0, 0, 6),
		BackgroundColor3 = Color3.new(1, 1, 1),
		BackgroundTransparency = 0.3,
		BorderSizePixel = 0,
		Parent = rollButton,
	})
end

local VIEW_SIZE = 230

local function buildReveal()
	local container = anchor(
		"Reveal",
		Vector2.new(0.5, 0.5),
		UDim2.fromScale(0.5, 0.46),
		UDim2.fromOffset(700, 460),
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

	refs.RevealRegion = Ui.label({
		Size = UDim2.new(1, 0, 0, 40),
		Font = Theme.FontHeavy,
		Parent = inner,
	}, 32)
	textOutline(refs.RevealRegion, 2)

	-- 모형 뒤의 둥근 받침
	local halo = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 44),
		Size = UDim2.fromOffset(VIEW_SIZE, VIEW_SIZE),
		BackgroundColor3 = Color3.fromRGB(8, 10, 20),
		BackgroundTransparency = 0.45,
		Parent = inner,
	})
	Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0), Parent = halo })
	refs.HaloStroke = Ui.stroke(Color3.new(1, 1, 1), 3, 0.3)
	refs.HaloStroke.Parent = halo

	local viewProps = {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 44),
		Size = UDim2.fromOffset(VIEW_SIZE, VIEW_SIZE),
		ZIndex = 2,
	}
	refs.EarthView = Viewport.new(inner, viewProps)
	Viewport.setLandmark(refs.EarthView, Landmarks.ById.earth, 10)
	refs.ResultView = Viewport.new(inner, viewProps)
	refs.ResultView.Visible = false

	refs.RevealTag = Ui.label({
		Position = UDim2.fromOffset(0, 278),
		Size = UDim2.new(1, 0, 0, 30),
		TextColor3 = Theme.Gold,
		Parent = inner,
	}, 26)
	textOutline(refs.RevealTag, 2)
	refs.RevealName = Ui.label({
		Position = UDim2.fromOffset(0, 308),
		Size = UDim2.new(1, 0, 0, 64),
		Font = Theme.FontHeavy,
		Parent = inner,
	}, 60)
	textOutline(refs.RevealName, 3)
	refs.RevealSub = Ui.label({
		Position = UDim2.fromOffset(0, 372),
		Size = UDim2.new(1, 0, 0, 30),
		Parent = inner,
	}, 26)
	textOutline(refs.RevealSub, 2)
	refs.RevealSubtitle = Ui.label({
		Position = UDim2.fromOffset(0, 402),
		Size = UDim2.new(1, 0, 0, 22),
		TextColor3 = Theme.SubText,
		Parent = inner,
	}, 20)
	textOutline(refs.RevealSubtitle, 1)
	refs.RevealBonus = Ui.label({
		Position = UDim2.fromOffset(0, 426),
		Size = UDim2.new(1, 0, 0, 30),
		TextColor3 = Theme.Gold,
		Parent = inner,
	}, 26)
	textOutline(refs.RevealBonus, 2)
end

local function buildNotices()
	-- 뉴스 속보(맨 위)
	local news = anchor("News", Vector2.new(0.5, 0), UDim2.new(0.5, 0, 0, 12), UDim2.fromOffset(720, 100), 9)
	local newsLayout = Ui.list(Enum.FillDirection.Vertical, 6, Enum.HorizontalAlignment.Center)
	newsLayout.VerticalAlignment = Enum.VerticalAlignment.Top
	newsLayout.Parent = news
	refs.News = news

	-- 잠깐 떴다 사라지는 알림(뉴스 아래)
	local notices = anchor("Notices", Vector2.new(0.5, 0), UDim2.new(0.5, 0, 0, 118), UDim2.fromOffset(560, 200), 9)
	local layout = Ui.list(Enum.FillDirection.Vertical, 6, Enum.HorizontalAlignment.Center)
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
		refs.Coins.Text = "💰 불러오는 중..."
		refs.Income.Text = ""
		refs.Rolls.Text = ""
		refs.Luck.Text = ""
		refs.Info.Text = ""
		shownCoins = -1
		return
	end
	refs.Income.Text = "📈 관광 수입 +" .. incomeText(state.Income) .. "/초"
	refs.Rolls.Text = "🎲 굴림 " .. Format.commas(state.Rolls) .. "회"
	refs.Luck.Text = "🍀 행운 " .. Format.multiplier(state.Luck)

	local stamps = #PlayerState.completedRegions(state)
	local info = string.format("여권 도장 %d/%d", stamps, #Landmarks.Regions)
	if UserInputService.KeyboardEnabled then
		info ..= " · [R] 굴리기 [T] 자동"
	end
	refs.Info.Text = info
	refs.Info.TextColor3 = if stamps > 0 then Theme.Gold else Theme.SubText
end

-- 매 프레임 호출: 부드럽게 올라가는 코인 표시 (정수가 바뀔 때만 글자 갱신)
function Hud.setCoins(amount: number)
	local whole = math.max(0, math.floor(amount))
	if whole == shownCoins then
		return
	end
	shownCoins = whole
	refs.Coins.Text = "💰 " .. Format.commas(whole)
end

function Hud.setAuto(enabled: boolean)
	refs.AutoButton.Text = if enabled then "자동: 켬" else "자동: 끔"
	refs.AutoButton.BackgroundColor3 = if enabled then Theme.Good else Theme.PanelLight
end

function Hud.setRolling(rolling: boolean)
	refs.RollButton.Text = if rolling then "돌리는 중..." else "🌍 굴리기"
	refs.RollButton.BackgroundTransparency = if rolling then 0.4 else 0
end

-- where: 지금 있는 곳 ("Plaza" | "Park"). 버튼은 반대쪽으로 가는 버튼이 됨
function Hud.setLocation(where: string)
	local button = refs.TeleportButton
	if where == "Park" then
		button.Text = "🏛️ 광장"
		button.BackgroundColor3 = Color3.fromRGB(70, 70, 110)
	else
		button.Text = "🏞️ 내 공원"
		button.BackgroundColor3 = Color3.fromRGB(45, 95, 70)
	end
end

function Hud.startCooldown(seconds: number)
	local bar = refs.CooldownBar
	bar.Size = UDim2.new(1, 12, 0, 6)
	TweenService:Create(bar, TweenInfo.new(seconds, Enum.EasingStyle.Linear), { Size = UDim2.new(0, 0, 0, 6) }):Play()
end

local function flash(color: Color3, strength: number)
	flashFrame.BackgroundColor3 = color
	flashFrame.BackgroundTransparency = 1 - strength
	TweenService:Create(flashFrame, TweenInfo.new(1.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		BackgroundTransparency = 1,
	}):Play()
end

local function showRegion(region: Landmarks.Region, pinned: boolean)
	refs.RevealRegion.Text = (if pinned then "📍 " else "") .. region.Emoji .. " " .. region.Name
	refs.RevealRegion.TextColor3 = region.Color
end

-- 굴림 연출. 결과를 보여 줄 때까지 기다립니다(yield).
-- 1) 지구본이 빠르게 돌며 지역 이름이 바뀌다 점점 느려짐 → 2) 결과 지역에 📍 → 3) 명소 공개
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
	refs.RevealTag.Text = ""
	refs.RevealName.Text = ""
	refs.RevealSub.Text = ""
	refs.RevealSubtitle.Text = ""
	refs.RevealBonus.Text = ""
	refs.HaloStroke.Color = Color3.new(1, 1, 1)
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
		Ui.paintTier(refs.RevealName, tier)
		refs.RevealSub.Text = tier.Name .. " 등급..."
		refs.RevealSub.TextColor3 = tier.Color
		refs.HaloStroke.Color = tier.Color
		flash(Color3.new(0, 0, 0), 0.6)
		task.wait(SUSPENSE_SECONDS)
	end

	-- 3) 결과 공개: 지구본 → 명소 모형
	Viewport.setSpin(refs.EarthView, 0)
	refs.EarthView.Visible = false
	Viewport.setLandmark(refs.ResultView, landmark, 10)
	refs.ResultView.Visible = true
	Viewport.setSpin(refs.ResultView, 40)
	refs.HaloStroke.Color = tier.Color

	refs.RevealName.Text = landmark.Name
	Ui.paintTier(refs.RevealName, tier)
	refs.RevealSub.Text = Format.oneIn(landmark.OneIn) .. " · " .. tier.Name
	refs.RevealSub.TextColor3 = tier.Color
	refs.RevealSubtitle.Text = landmark.Subtitle

	local tags = {}
	if info.IsNew then
		table.insert(tags, "🆕 새로 발견!")
	end
	if info.StarUp then
		table.insert(tags, "⭐ 별 상승! " .. Ui.stars(info.Stars or 0, #Config.STAR_THRESHOLDS))
	end
	refs.RevealTag.Text = table.concat(tags, "   ")
	refs.RevealBonus.Text = if (info.Bonus or 0) > 0 then "+" .. Format.commas(info.Bonus) .. " 💰" else ""

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
		end
	end)
end

-- 잠깐 떴다 사라지는 알림 (색은 선택)
function Hud.toast(text: string, color: Color3?, seconds: number?)
	local box = panel({
		Size = UDim2.fromOffset(520, 44),
		Parent = refs.Notices,
	})
	Ui.padding(8).Parent = box
	Ui.label({
		Size = UDim2.fromScale(1, 1),
		Text = text,
		TextColor3 = color or Theme.Text,
		Parent = box,
	}, 22)
	task.delay(seconds or 3, function()
		box:Destroy()
	end)
end

-- 서버 전체 "📰 속보": 오른쪽에서 밀려 들어와 잠시 머문 뒤 왼쪽으로 빠짐
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
		Size = UDim2.new(1, 0, 0, 46),
		BackgroundTransparency = 1,
		ClipsDescendants = true,
		Parent = refs.News,
	})
	table.insert(newsItems, item)

	local slide = Ui.new("Frame", {
		Position = UDim2.fromScale(1, 0),
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Parent = item,
	})

	local bar = Ui.new("Frame", {
		Position = UDim2.fromOffset(96, 0),
		Size = UDim2.new(1, -96, 1, 0),
		BackgroundColor3 = NEWS_WHITE,
		Parent = slide,
	})
	Ui.corner(8).Parent = bar
	Ui.stroke(tier.Color, 2, 0).Parent = bar
	Ui.new("UIPadding", {
		PaddingLeft = UDim.new(0, 22),
		PaddingRight = UDim.new(0, 10),
		PaddingTop = UDim.new(0, 6),
		PaddingBottom = UDim.new(0, 6),
		Parent = bar,
	})
	Ui.label({
		Size = UDim2.fromScale(1, 1),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = NEWS_INK,
		Text = string.format(
			'%s 님이 <font color="%s"><b>%s</b></font>(%s) 발견! — %s번째 탐험',
			Format.escape(playerName),
			Format.hex(tier.Color:Lerp(Color3.new(0, 0, 0), 0.35)),
			Format.escape(landmark.Name),
			Format.oneIn(landmark.OneIn),
			Format.commas(rollNumber)
		),
		Parent = bar,
	}, 22)

	local tag = Ui.new("Frame", {
		Size = UDim2.new(0, 110, 1, 0),
		BackgroundColor3 = NEWS_RED,
		ZIndex = 2,
		Parent = slide,
	})
	Ui.corner(8).Parent = tag
	Ui.label({
		Size = UDim2.fromScale(1, 1),
		Font = Theme.FontHeavy,
		Text = "📰 속보",
		TextColor3 = Color3.new(1, 1, 1),
		ZIndex = 3,
		Parent = tag,
	}, 22)

	play(newsSound)
	TweenService:Create(slide, TweenInfo.new(0.45, Enum.EasingStyle.Quint, Enum.EasingDirection.Out), {
		Position = UDim2.fromScale(0, 0),
	}):Play()

	task.delay(NEWS_SECONDS, function()
		if not item.Parent then
			return -- 이미 밀려나서 지워짐
		end
		TweenService:Create(slide, TweenInfo.new(0.4, Enum.EasingStyle.Quad, Enum.EasingDirection.In), {
			Position = UDim2.fromScale(-1, 0),
		}):Play()
		task.wait(0.45)
		local index = table.find(newsItems, item)
		if index then
			table.remove(newsItems, index)
		end
		item:Destroy()
	end)
end

return Hud
