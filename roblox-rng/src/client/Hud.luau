-- 기본 화면(HUD): 스탯, 물약 타이머, 메뉴 버튼, 굴리기 버튼, 굴림 연출, 알림

local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Auras = require(Shared.Auras)
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local PlayerState = require(Shared.PlayerState)
local RollLogic = require(Shared.RollLogic)

local Ui = require(script.Parent.Ui)
local Theme = Ui.Theme

-- 등급(Rank)별 굴림 연출 길이(초). 빠른 모드(자동 굴림)에서는 에픽 미만만 절반으로 줄임.
local REVEAL_SECONDS = { 0.8, 1.0, 1.4, 2.0, 2.6, 3.0, 3.0 }
local FAKE_SPIN_LUCK = 25 -- 돌아가는 동안 보여줄 가짜 결과는 조금 더 화려하게
local TICK_SOUND = "rbxasset://sounds/electronicpingshort.wav"

local Hud = {}

local gui: ScreenGui
local flashFrame: Frame
local refs: { [string]: any } = {}
local spinRandom = Random.new()
local hideToken = 0

local function makeSound(pitch: number, volume: number): Sound
	return Ui.new("Sound", {
		SoundId = TICK_SOUND,
		PlaybackSpeed = pitch,
		Volume = volume,
		Parent = SoundService,
	})
end

local tickSound: Sound
local revealSound: Sound
local rareSound: Sound

local function play(sound: Sound)
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
local function anchor(name: string, anchorPoint: Vector2, position: UDim2, size: UDim2): Frame
	local frame = Ui.new("Frame", {
		Name = name,
		AnchorPoint = anchorPoint,
		Position = position,
		Size = size,
		BackgroundTransparency = 1,
		Parent = gui,
	})
	Ui.autoScale(frame)
	return frame
end

local function buildStats()
	local container = anchor("Stats", Vector2.new(0, 0), UDim2.new(0, 12, 0, 12), UDim2.fromOffset(250, 118))
	local box = panel({ Size = UDim2.fromScale(1, 1), Parent = container })
	Ui.padding(10).Parent = box
	Ui.list(Enum.FillDirection.Vertical, 4).Parent = box

	local function row(order: number, color: Color3): TextLabel
		return Ui.label({
			LayoutOrder = order,
			Size = UDim2.new(1, 0, 0, 30),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = color,
			Parent = box,
		}, 24)
	end
	refs.Coins = row(1, Theme.Gold)
	refs.Rolls = row(2, Theme.Text)
	refs.Luck = row(3, Theme.Good)
end

local function buildPotions()
	local container = anchor("Potions", Vector2.new(1, 0), UDim2.new(1, -12, 0, 12), UDim2.fromOffset(230, 200))
	local layout = Ui.list(Enum.FillDirection.Vertical, 6, Enum.HorizontalAlignment.Right)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = container
	refs.PotionList = container
	refs.PotionRows = {}
end

local function buildMenu(onMenu: (string) -> ())
	local container = anchor("Menu", Vector2.new(0, 0.5), UDim2.new(0, 12, 0.5, 0), UDim2.fromOffset(120, 230))
	Ui.list(Enum.FillDirection.Vertical, 10).Parent = container
	for order, entry in { { "Inventory", "🎒 가방" }, { "Index", "📖 도감" }, { "Shop", "🛒 상점" } } do
		local button = Ui.button({
			Name = entry[1],
			LayoutOrder = order,
			Size = UDim2.fromOffset(120, 64),
			Text = entry[2],
			Parent = container,
		}, 22)
		button.Activated:Connect(function()
			onMenu(entry[1])
		end)
	end
end

local function buildRollBar(onRoll: () -> (), onToggleAuto: () -> ())
	local container = anchor("RollBar", Vector2.new(0.5, 1), UDim2.new(0.5, 0, 1, -18), UDim2.fromOffset(420, 120))

	refs.LuckyInfo = Ui.label({
		Size = UDim2.new(1, 0, 0, 30),
		TextColor3 = Theme.SubText,
		Parent = container,
	}, 22)

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
		Size = UDim2.fromOffset(240, 76),
		BackgroundColor3 = Theme.Accent,
		Text = "🎲 굴리기",
		ClipsDescendants = true,
		Parent = row,
	}, 32)
	rollButton.Activated:Connect(onRoll)
	refs.RollButton = rollButton

	-- 쿨타임 막대 (버튼 아래쪽)
	local bar = Ui.new("Frame", {
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, -6, 1, 6),
		Size = UDim2.new(0, 0, 0, 6),
		BackgroundColor3 = Color3.new(1, 1, 1),
		BackgroundTransparency = 0.3,
		BorderSizePixel = 0,
		Parent = rollButton,
	})
	refs.CooldownBar = bar
end

-- 글자 테두리 (UIStroke 기본값 Contextual = 글자에 적용)
local function textOutline(label: TextLabel, thickness: number)
	Ui.new("UIStroke", { Color = Color3.new(0, 0, 0), Thickness = thickness, Transparency = 0.2, Parent = label })
end

local function buildReveal()
	local container = anchor("Reveal", Vector2.new(0.5, 0.5), UDim2.fromScale(0.5, 0.42), UDim2.fromOffset(760, 230))
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

	refs.RevealTag = Ui.label({
		Size = UDim2.new(1, 0, 0, 34),
		TextColor3 = Theme.Gold,
		Parent = inner,
	}, 28)
	refs.RevealName = Ui.label({
		Position = UDim2.fromOffset(0, 36),
		Size = UDim2.new(1, 0, 0, 110),
		Font = Theme.FontHeavy,
		Parent = inner,
	}, 96)
	textOutline(refs.RevealName, 3)
	refs.RevealSub = Ui.label({
		Position = UDim2.fromOffset(0, 148),
		Size = UDim2.new(1, 0, 0, 40),
		Parent = inner,
	}, 32)
	textOutline(refs.RevealSub, 2)
	refs.RevealReward = Ui.label({
		Position = UDim2.fromOffset(0, 192),
		Size = UDim2.new(1, 0, 0, 32),
		TextColor3 = Theme.Gold,
		Parent = inner,
	}, 26)
end

local function buildNotices()
	local container = anchor("Notices", Vector2.new(0.5, 0), UDim2.new(0.5, 0, 0, 12), UDim2.fromOffset(680, 220))
	local layout = Ui.list(Enum.FillDirection.Vertical, 6, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = container
	refs.Notices = container
end

function Hud.init(playerGui: PlayerGui, handlers: { Roll: () -> (), ToggleAuto: () -> (), Menu: (string) -> () })
	gui = Ui.new("ScreenGui", {
		Name = "AuraRNG",
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = playerGui,
	})
	local flashGui = Ui.new("ScreenGui", {
		Name = "AuraRNGFlash",
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
	revealSound = makeSound(0.9, 0.6)
	rareSound = makeSound(0.5, 1)

	buildStats()
	buildPotions()
	buildMenu(handlers.Menu)
	buildRollBar(handlers.Roll, handlers.ToggleAuto)
	buildReveal()
	buildNotices()
	Hud.render(nil)
	return gui
end

function Hud.render(state: PlayerState.Snapshot?)
	if not state then
		refs.Coins.Text = "🪙 불러오는 중..."
		refs.Rolls.Text = ""
		refs.Luck.Text = ""
		refs.LuckyInfo.Text = ""
		return
	end
	refs.Coins.Text = "🪙 " .. Format.commas(state.Coins)
	refs.Rolls.Text = "🎲 굴림 " .. Format.commas(state.Rolls) .. "회"
	refs.Luck.Text = "🍀 행운 " .. Format.multiplier(state.Luck)

	local untilLucky = PlayerState.rollsUntilLucky(state.Rolls)
	if untilLucky == 1 then
		refs.LuckyInfo.Text = string.format("✨ 다음 굴림은 행운 굴림! (행운 x%d)", Config.LUCKY_ROLL_MULT)
		refs.LuckyInfo.TextColor3 = Theme.Gold
	else
		refs.LuckyInfo.Text =
			string.format("행운 굴림까지 %d회 · [R] 키로도 굴릴 수 있어요", untilLucky)
		refs.LuckyInfo.TextColor3 = Theme.SubText
	end

	-- 물약 줄: 활성 물약이 바뀌었을 때만 다시 만듦
	local rows = refs.PotionRows
	for id, row in rows do
		if not state.Potions[id] then
			row.Frame:Destroy()
			rows[id] = nil
		end
	end
	for order, potion in Config.Potions do
		if state.Potions[potion.Id] and not rows[potion.Id] then
			local row = panel({
				LayoutOrder = order,
				Size = UDim2.fromOffset(230, 40),
				Parent = refs.PotionList,
			})
			Ui.padding(6).Parent = row
			local label = Ui.label({
				Size = UDim2.fromScale(1, 1),
				TextXAlignment = Enum.TextXAlignment.Right,
				TextColor3 = potion.Color,
				Parent = row,
			}, 22)
			rows[potion.Id] = { Frame = row, Label = label }
		end
	end
end

-- 매 프레임 가까이 호출: 물약 남은 시간 표시 (elapsed = 스냅샷 받은 뒤 지난 시간)
function Hud.updateTimers(state: PlayerState.Snapshot?, elapsed: number)
	if not state then
		return
	end
	for id, row in refs.PotionRows do
		local remaining = (state.Potions[id] or 0) - elapsed
		local potion = PlayerState.PotionsById[id]
		row.Label.Text = string.format("%s  %s", potion.Name, Format.duration(remaining))
	end
end

function Hud.setAuto(enabled: boolean)
	refs.AutoButton.Text = if enabled then "자동: 켬" else "자동: 끔"
	refs.AutoButton.BackgroundColor3 = if enabled then Theme.Good else Theme.PanelLight
end

function Hud.setRolling(rolling: boolean)
	refs.RollButton.Text = if rolling then "굴리는 중..." else "🎲 굴리기"
	refs.RollButton.BackgroundTransparency = if rolling then 0.4 else 0
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

local function showAura(aura: Auras.Aura)
	refs.RevealName.Text = aura.Name
	Ui.paintAura(refs.RevealName, aura)
	refs.RevealSub.Text = Format.oneIn(aura.OneIn)
	refs.RevealSub.TextColor3 = aura.Tier.Color
end

-- 굴림 연출. 끝날 때까지 기다립니다(yield).
function Hud.reveal(
	aura: Auras.Aura,
	info: { Fast: boolean, Lucky: boolean, IsNew: boolean, Coins: number, Luck: number }
)
	hideToken += 1
	local rank = aura.Tier.Rank
	local duration = REVEAL_SECONDS[rank] or 3
	if info.Fast and rank < 4 then
		duration = math.max(0.35, duration * 0.5)
	end

	local container = refs.Reveal
	container.Visible = true
	refs.RevealScale.Scale = 1
	refs.RevealTag.Text = if info.Lucky
		then string.format("✨ 행운 굴림! (행운 %s)", Format.multiplier(info.Luck))
		else ""
	refs.RevealReward.Text = ""

	-- 1) 룰렛처럼 가짜 결과가 빠르게 돌다가 점점 느려짐
	local elapsed = 0
	while elapsed < duration do
		local fake = RollLogic.roll(Auras.RarestFirst, FAKE_SPIN_LUCK, function()
			return spinRandom:NextNumber()
		end)
		showAura(fake)
		play(tickSound)
		local t = elapsed / duration
		local interval = 0.04 + t * t * 0.2
		task.wait(interval)
		elapsed += interval
	end

	-- 2) 전설 이상은 한 박자 뜸 들이기
	if rank >= 5 then
		refs.RevealName.Text = "? ? ?"
		Ui.paintAura(refs.RevealName, { Color = aura.Tier.Color })
		refs.RevealSub.Text = aura.Tier.Name .. " 등급..."
		flash(Color3.new(0, 0, 0), 0.6)
		task.wait(0.9)
	end

	-- 3) 결과 공개
	showAura(aura)
	refs.RevealSub.Text = Format.oneIn(aura.OneIn) .. " · " .. aura.Tier.Name
	local tags = {}
	if info.IsNew then
		table.insert(tags, "🆕 새로 발견!")
	end
	if info.Lucky then
		table.insert(tags, "✨ 행운 굴림")
	end
	refs.RevealTag.Text = table.concat(tags, "   ")
	refs.RevealReward.Text = "+" .. Format.commas(info.Coins) .. " 🪙"

	refs.RevealScale.Scale = 1.35
	TweenService:Create(refs.RevealScale, TweenInfo.new(0.35, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {
		Scale = 1,
	}):Play()
	if rank >= 4 then
		flash(aura.Color, math.min(0.25 + rank * 0.08, 0.8))
		play(rareSound)
	else
		play(revealSound)
	end

	local token = hideToken
	task.delay(if info.Fast then 1 else 2.5, function()
		if token == hideToken then
			container.Visible = false
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

-- 서버 전체 희귀 획득 알림
function Hud.banner(playerName: string, aura: Auras.Aura, rollNumber: number)
	local box = panel({
		Size = UDim2.fromOffset(660, 76),
		BackgroundColor3 = Color3.new(0, 0, 0),
		BackgroundTransparency = 0.25,
		Parent = refs.Notices,
	})
	box:FindFirstChildOfClass("UIStroke").Color = aura.Tier.Color
	Ui.padding(8).Parent = box
	Ui.label({
		Size = UDim2.new(1, 0, 0.45, 0),
		Text = string.format(
			"🎉 %s 님이 %s번째 굴림에서 획득!",
			Format.escape(playerName),
			Format.commas(rollNumber)
		),
		Parent = box,
	}, 22)
	local name = Ui.label({
		Position = UDim2.fromScale(0, 0.45),
		Size = UDim2.new(1, 0, 0.55, 0),
		Font = Theme.FontHeavy,
		Text = string.format("%s  (%s · %s)", aura.Name, Format.oneIn(aura.OneIn), aura.Tier.Name),
		Parent = box,
	}, 30)
	Ui.paintAura(name, aura)
	task.delay(6, function()
		box:Destroy()
	end)
end

return Hud
