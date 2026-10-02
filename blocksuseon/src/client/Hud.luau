-- 화면 UI. 선협풍: 칠기 현판과 금테, 옥 버튼, 붓글씨·명조 글자.
-- 그림은 art/assets.html 에서 그려 올린 것(Art), 글자는 BitmapText 로 찍는다.
-- 알림은 채팅창 시스템 메시지(Chat)로 보낸다.

local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Insights = require(Shared.Insights)
local MartialRanks = require(Shared.MartialRanks)
local Format = require(Shared.Format)
local Art = require(script.Parent.Art)
local BitmapText = require(script.Parent.BitmapText)
local Chat = require(script.Parent.Chat)

export type Actions = {
	meditate: () -> (),
	breakthrough: () -> (),
	buyInsight: (id: string) -> (),
}

local IMG = Art.images

local C = {
	cream = Color3.fromRGB(239, 226, 192),
	dim = Color3.fromRGB(178, 166, 138),
	jade = Color3.fromRGB(150, 222, 192),
	red = Color3.fromRGB(240, 140, 120),
	gold = Color3.fromRGB(240, 212, 140),
	keyBack = Color3.fromRGB(226, 196, 122),
	keyText = Color3.fromRGB(58, 42, 16),
}
local GOLD_TEXT = ColorSequence.new({
	ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 246, 214)),
	ColorSequenceKeypoint.new(0.55, Color3.fromRGB(226, 188, 110)),
	ColorSequenceKeypoint.new(1, Color3.fromRGB(178, 136, 66)),
})
local RED_TEXT = ColorSequence.new(Color3.fromRGB(255, 220, 180), Color3.fromRGB(218, 86, 62))

local Hud = {}

local player = Players.LocalPlayer
local keyboard = UserInputService.KeyboardEnabled
local touchOnly = UserInputService.TouchEnabled and not keyboard
local actions: Actions
local scales: { UIScale } = {}
local ui: { [string]: any } = {}
local orbs: { [string]: { [string]: any } } = {}
local insightRows: { [string]: { [string]: any } } = {}
local pulses: { [Instance]: Tween } = {}
local cinematicToken = 0
local lastState: { [string]: any }? = nil

-- 도우미 ---------------------------------------------------------------------------

local function new(className: string, props: { [string]: any }?, children: { Instance }?): any
	local inst = Instance.new(className)
	local parent = nil
	for key, value in props or {} do
		if key == "Parent" then
			parent = value
		else
			(inst :: any)[key] = value
		end
	end
	for _, child in children or {} do
		child.Parent = inst
	end
	if parent then
		inst.Parent = parent
	end
	return inst
end

-- Art 그림 하나. 9-slice 그림이면 Slice 로 늘인다.
local function image(name: string, props: { [string]: any }, className: string?): any
	local def = IMG[name]
	local base: { [string]: any } = {
		BackgroundTransparency = 1,
		Image = def.id,
	}
	if def.slice and props.ScaleType == nil then
		base.ScaleType = Enum.ScaleType.Slice
		base.SliceCenter = def.slice
	end
	if className == "ImageButton" then
		base.AutoButtonColor = false
	end
	for key, value in props do
		base[key] = value
	end
	return new(className or "ImageLabel", base)
end

local function setImage(target: ImageLabel | ImageButton, name: string)
	local def = IMG[name]
	target.Image = def.id
	if def.slice then
		target.SliceCenter = def.slice
	end
end

local function text(font: string, size: number, props: { [string]: any }?)
	local options = { font = font, size = size }
	for key, value in props or {} do
		options[key] = value
	end
	return BitmapText.new(options :: any)
end

-- 가운데 정렬 등 줄 배치용 틀
local function row(props: { [string]: any }, align: Enum.HorizontalAlignment?, padding: number?): Frame
	local frame = new("Frame", props)
	frame.BackgroundTransparency = 1
	new("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		HorizontalAlignment = align or Enum.HorizontalAlignment.Center,
		VerticalAlignment = Enum.VerticalAlignment.Bottom,
		SortOrder = Enum.SortOrder.LayoutOrder,
		Padding = UDim.new(0, padding or 6),
		Parent = frame,
	})
	return frame
end

local function tween(target: Instance, info: TweenInfo, goal: { [string]: any })
	TweenService:Create(target, info, goal):Play()
end

local function pulse(target: Instance, on: boolean, goal: { [string]: any }, rest: { [string]: any })
	local running = pulses[target]
	if on and running then
		return
	end
	if running then
		running:Cancel()
		pulses[target] = nil
	end
	if on then
		local t = TweenService:Create(
			target,
			TweenInfo.new(1.1, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
			goal
		)
		pulses[target] = t
		t:Play()
	else
		for key, value in rest do
			(target :: any)[key] = value
		end
	end
end

local function scaled(frame: GuiObject): GuiObject
	table.insert(scales, new("UIScale", { Parent = frame }))
	return frame
end

local function rescale()
	local camera = Workspace.CurrentCamera
	local size = if camera then camera.ViewportSize else Vector2.new(1280, 720)
	local value = math.clamp(math.min(size.X / 1280, size.Y / 720), 0.6, 1)
	for _, scale in scales do
		scale.Scale = value
	end
end

-- 만들기 ---------------------------------------------------------------------------

-- 왼쪽 상태창: 경지 현판, 영력, 무공, 깨달음
local function buildStatus(gui: ScreenGui)
	local status = scaled(new("Frame", {
		Name = "Status",
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 14, 0.5, -20),
		Size = UDim2.fromOffset(350, 214),
		BackgroundTransparency = 1,
		Parent = gui,
	}))

	image("mist", { Position = UDim2.fromOffset(-80, -60), Size = UDim2.fromOffset(540, 330), Parent = status })

	local plaque = image("plaque", {
		Size = UDim2.fromOffset(340, 74),
		ScaleType = Enum.ScaleType.Stretch,
		Parent = status,
	})
	local realmRow = row({ Size = UDim2.new(1, 0, 1, -14), Parent = plaque }, nil, 8)
	ui.realmName = text("title", 36, { gradient = GOLD_TEXT, parent = realmRow })
	ui.realmSub = text("title", 24, { color = C.cream, parent = realmRow })
	ui.realmName.frame.LayoutOrder = 1
	ui.realmSub.frame.LayoutOrder = 2

	local track = image("barTrack", {
		Position = UDim2.fromOffset(24, 82),
		Size = UDim2.fromOffset(292, 18),
		SliceScale = 0.6,
		Parent = status,
	})
	ui.qiFill = image("barJade", {
		Position = UDim2.fromOffset(3, 3),
		Size = UDim2.fromOffset(0, 12),
		SliceScale = 0.55,
		Parent = track,
	})

	ui.qiText = text("body", 16, { color = C.cream })
	ui.qiText.frame.Position = UDim2.fromOffset(20, 101)
	ui.qiText.frame.Parent = status
	ui.rateText = text("body", 16, { color = C.jade })
	ui.rateText.frame.AnchorPoint = Vector2.new(1, 0)
	ui.rateText.frame.Position = UDim2.fromOffset(322, 101)
	ui.rateText.frame.Parent = status
	ui.veinText = text("body", 15, { color = C.jade })
	ui.veinText.frame.Position = UDim2.fromOffset(20, 123)
	ui.veinText.frame.Parent = status

	image("iconDummy", { Position = UDim2.fromOffset(20, 152), Size = UDim2.fromOffset(26, 26), Parent = status })
	ui.martialText = text("body", 16, { color = C.cream })
	ui.martialText.frame.Position = UDim2.fromOffset(46, 151)
	ui.martialText.frame.Parent = status
	local mini = image("barTrack", {
		Position = UDim2.fromOffset(176, 160),
		Size = UDim2.fromOffset(140, 10),
		SliceScale = 0.35,
		Parent = status,
	})
	ui.martialFill = image("barGold", {
		Position = UDim2.fromOffset(2, 2),
		Size = UDim2.fromOffset(0, 6),
		SliceScale = 0.3,
		Parent = mini,
	})

	image("gem", { Position = UDim2.fromOffset(24, 186), Size = UDim2.fromOffset(18, 18), Parent = status })
	ui.pointsText = text("body", 16, { color = C.cream })
	ui.pointsText.frame.Position = UDim2.fromOffset(46, 182)
	ui.pointsText.frame.Parent = status
end

-- 둥근 옥 버튼 하나
local function orb(parent: Instance, key: string, size: number, icon: string, hotkey: string, onClick: () -> ())
	local holder = new("Frame", {
		Name = key,
		Size = UDim2.fromOffset(size, size + 30),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	local halo = image("halo", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset(size / 2, size / 2),
		Size = UDim2.fromOffset(size * 1.5, size * 1.5),
		ImageTransparency = 1,
		Parent = holder,
	})
	local haloScale = new("UIScale", { Parent = halo })
	local button = image("orbJade", {
		Size = UDim2.fromOffset(size, size),
		Parent = holder,
	}, "ImageButton")
	local press = new("UIScale", { Parent = button })
	local iconLabel = image(icon, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.62, 0.62),
		Parent = button,
	})
	local labelRow = row({
		Position = UDim2.fromOffset(-40, size - 2),
		Size = UDim2.new(1, 80, 0, 30),
		Parent = holder,
	})
	local label = text("title", if size >= 90 then 22 else 19, { gradient = GOLD_TEXT, parent = labelRow })

	if keyboard then
		local badge = new("Frame", {
			AnchorPoint = Vector2.new(1, 0),
			Position = UDim2.new(1, -2, 0, 2),
			Size = UDim2.fromOffset(20, 20),
			BackgroundColor3 = C.keyBack,
			Parent = button,
		}, { new("UICorner", { CornerRadius = UDim.new(0, 5) }) })
		local keyRow = row({ Size = UDim2.fromScale(1, 1), Parent = badge })
		text("body", 13, { color = C.keyText, text = hotkey, parent = keyRow })
	end

	local gem = image("gem", {
		Position = UDim2.fromOffset(2, 2),
		Size = UDim2.fromOffset(18, 18),
		Visible = false,
		Parent = button,
	})

	button.MouseButton1Down:Connect(function()
		press.Scale = 0.93
	end)
	button.MouseButton1Up:Connect(function()
		press.Scale = 1
	end)
	button.MouseLeave:Connect(function()
		press.Scale = 1
	end)
	button.Activated:Connect(function()
		press.Scale = 1
		onClick()
	end)

	orbs[key] = {
		holder = holder,
		button = button,
		icon = iconLabel,
		label = label,
		halo = halo,
		haloScale = haloScale,
		gem = gem,
	}
	return holder
end

-- 오른쪽 아래: 운기조식(큰 버튼), 돌파, 깨달음
local function buildActions(gui: ScreenGui)
	local cluster = scaled(new("Frame", {
		Name = "Actions",
		AnchorPoint = Vector2.new(1, 1),
		Position = UDim2.new(1, if touchOnly then -170 else -20, 1, -10),
		Size = UDim2.fromOffset(300, 240),
		BackgroundTransparency = 1,
		Parent = gui,
	}))
	orb(cluster, "meditate", 108, "iconLotus", "R", function()
		actions.meditate()
	end).Position =
		UDim2.fromOffset(180, 100)
	orb(cluster, "breakthrough", 84, "iconSword", "B", function()
		actions.breakthrough()
	end).Position =
		UDim2.fromOffset(72, 120)
	orb(cluster, "insight", 64, "iconScroll", "T", function()
		Hud.togglePanel()
	end).Position =
		UDim2.fromOffset(232, 0)
end

-- 위 가운데: 천겁 알림 현판
local function buildTribulation(gui: ScreenGui)
	local banner = scaled(image("plaque", {
		Name = "Tribulation",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 10),
		Size = UDim2.fromOffset(320, 70),
		ScaleType = Enum.ScaleType.Stretch,
		ImageColor3 = Color3.fromRGB(255, 190, 170),
		Visible = false,
		Parent = gui,
	}))
	ui.tribulation = banner
	local bannerRow = row({ Size = UDim2.new(1, 0, 1, -14), Parent = banner }, nil, 10)
	ui.tribName = text("title", 32, { gradient = RED_TEXT, parent = bannerRow })
	ui.tribWave = text("body", 18, { color = C.cream, parent = bannerRow })
	ui.tribName.frame.LayoutOrder = 1
	ui.tribWave.frame.LayoutOrder = 2
end

-- 가운데: 깨달음 창
local function buildPanel(gui: ScreenGui)
	local panel = scaled(image("panel", {
		Name = "Insights",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(480, 540),
		SliceScale = 0.8,
		Visible = false,
		Active = true,
		Parent = gui,
	}))
	ui.panel = panel

	local titleRow = row({ Position = UDim2.fromOffset(0, 22), Size = UDim2.new(1, 0, 0, 56), Parent = panel })
	text("title", 40, { gradient = GOLD_TEXT, text = "깨달음", parent = titleRow })
	image("divider", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 80),
		Size = UDim2.fromOffset(400, 25),
		Parent = panel,
	})
	local pointsRow = row({ Position = UDim2.fromOffset(0, 104), Size = UDim2.new(1, 0, 0, 26), Parent = panel })
	ui.panelPoints = text("body", 16, { color = C.dim, parent = pointsRow })

	local close = image("iconClose", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -24, 0, 24),
		Size = UDim2.fromOffset(34, 34),
		Parent = panel,
	}, "ImageButton")
	close.Activated:Connect(function()
		Hud.togglePanel(false)
	end)

	local list = new("ScrollingFrame", {
		Position = UDim2.fromOffset(34, 140),
		Size = UDim2.new(1, -62, 1, -170),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 4,
		ScrollBarImageColor3 = C.gold,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = panel,
	}, { new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder }) })

	for index, def in Insights.list do
		local item = new("Frame", {
			LayoutOrder = index,
			Size = UDim2.new(1, -8, 0, 76),
			BackgroundTransparency = 1,
			Parent = list,
		})
		local nameRow = row(
			{ Position = UDim2.fromOffset(0, 4), Size = UDim2.new(1, -110, 0, 36), Parent = item },
			Enum.HorizontalAlignment.Left,
			10
		)
		local name = text("title", 25, { color = C.cream, text = def.name, parent = nameRow })
		name.frame.LayoutOrder = 1
		local level = text("body", 14, { color = C.gold, parent = nameRow })
		level.frame.LayoutOrder = 2

		local effectRow = row(
			{ Position = UDim2.fromOffset(0, 40), Size = UDim2.new(1, -110, 0, 26), Parent = item },
			Enum.HorizontalAlignment.Left,
			6
		)
		local stat = text("body", 15, { color = C.dim, text = def.stat, parent = effectRow })
		local current = text("body", 15, { color = C.cream, parent = effectRow })
		local arrow = text("body", 15, { color = C.dim, text = "→", parent = effectRow })
		local nextValue = text("body", 15, { color = C.jade, parent = effectRow })
		for i, t in { stat, current, arrow, nextValue } do
			t.frame.LayoutOrder = i
		end

		local buy = image("pillJade", {
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, -4, 0.5, -2),
			Size = UDim2.fromOffset(96, 42),
			SliceScale = 0.8,
			Parent = item,
		}, "ImageButton")
		local buyRow = row({ Size = UDim2.new(1, 0, 1, -4), Parent = buy }, nil, 4)
		local buyGem = image("gem", { Size = UDim2.fromOffset(16, 16), LayoutOrder = 1, Parent = buyRow })
		local cost = text("body", 18, { color = C.cream, parent = buyRow })
		cost.frame.LayoutOrder = 2
		buy.Activated:Connect(function()
			actions.buyInsight(def.id)
		end)

		new("Frame", {
			AnchorPoint = Vector2.new(0, 1),
			Position = UDim2.fromScale(0, 1),
			Size = UDim2.new(1, 0, 0, 1),
			BackgroundColor3 = C.gold,
			BackgroundTransparency = 0.78,
			BorderSizePixel = 0,
			Parent = item,
		})

		insightRows[def.id] = {
			level = level,
			current = current,
			arrow = arrow,
			nextValue = nextValue,
			buy = buy,
			buyGem = buyGem,
			cost = cost,
		}
	end
end

local function buildCinematic()
	local gui = new("ScreenGui", {
		Name = "BlockSuseonCinematic",
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		DisplayOrder = 10,
		Parent = player:WaitForChild("PlayerGui"),
	})
	ui.cineBack = new("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.fromRGB(8, 9, 13),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Parent = gui,
	})
	local group = new("CanvasGroup", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.44),
		Size = UDim2.fromOffset(1000, 300),
		BackgroundTransparency = 1,
		GroupTransparency = 1,
		Parent = gui,
	})
	ui.cineGroup = group
	ui.cineScale = new("UIScale", { Parent = group })
	image("swash", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(920, 230),
		Parent = group,
	})
	local titleRow = row({ Position = UDim2.fromOffset(0, 74), Size = UDim2.new(1, 0, 0, 100), Parent = group })
	ui.cineTitle = text("title", 68, { gradient = GOLD_TEXT, parent = titleRow })
	local subRow = row({ Position = UDim2.fromOffset(0, 172), Size = UDim2.new(1, 0, 0, 34), Parent = group })
	ui.cineSub = text("body", 20, { color = C.cream, parent = subRow })
end

function Hud.build(newActions: Actions)
	actions = newActions
	local gui = new("ScreenGui", {
		Name = "BlockSuseonHud",
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = player:WaitForChild("PlayerGui"),
	})
	buildStatus(gui)
	buildActions(gui)
	buildTribulation(gui)
	buildPanel(gui)
	buildCinematic()

	-- 천겁이 내릴 때 화면을 어둡게
	ui.tint = new("ColorCorrectionEffect", { Name = "천겁색보정", Parent = Lighting })

	rescale()
	local camera = Workspace.CurrentCamera
	if camera then
		camera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)
	end
end

-- 갱신 ---------------------------------------------------------------------------

local function setTribulationMood(active: boolean)
	local goal = if active
		then { Brightness = -0.08, Contrast = 0.15, Saturation = -0.45, TintColor = Color3.fromRGB(190, 195, 255) }
		else { Brightness = 0, Contrast = 0, Saturation = 0, TintColor = Color3.new(1, 1, 1) }
	tween(ui.tint, TweenInfo.new(1.2), goal)
end

local function updateStatus(state)
	local step = Realms.get(state.step)
	ui.realmName:set(step.realm.name)
	ui.realmSub:set(step.sub)
	ui.realmSub.frame.Visible = step.sub ~= ""

	local ratio = if state.req > 0 then math.clamp(state.qi / state.req, 0, 1) else 1
	local atMax = state.step >= Realms.maxStep
	local bottleneck = Realms.nextIsMajor(state.step)
	local full = ratio >= 1 and (bottleneck or atMax)
	setImage(ui.qiFill, if full then "barGold" else "barJade")
	ui.qiFill.Visible = ratio > 0.04
	tween(ui.qiFill, TweenInfo.new(0.45, Enum.EasingStyle.Linear), { Size = UDim2.fromOffset(286 * ratio, 12) })

	if atMax and full then
		ui.qiText:set("최고 경지")
		ui.qiText:setColor(C.gold)
		ui.rateText:set("")
	elseif full then
		local target = Realms.get(state.step + 1).realm
		ui.qiText:set("영력이 가득 찼다")
		ui.qiText:setColor(C.gold)
		ui.rateText:set(
			if target.tribulation
				then "천겁을 넘어야 한다"
				else string.format("돌파 확률 %s", Format.percent(state.breakChance or 0))
		)
		ui.rateText:setColor(C.gold)
	else
		ui.qiText:set(string.format("영력 %s / %s", Format.qi(state.qi), Format.qi(state.req)))
		ui.qiText:setColor(C.cream)
		ui.rateText:set(if state.meditating then string.format("+%s / 초", Format.rate(state.gain)) else "")
		ui.rateText:setColor(C.jade)
	end

	if state.veinId then
		local vein = Balance.VEINS[state.veinId]
		ui.veinText:set(string.format("%s 위 (흡수 ×%s)", vein.name, tostring(vein.mult)))
		ui.veinText:setColor(C.jade)
	elseif state.veinBlocked then
		local vein = Balance.VEINS[state.veinBlocked]
		ui.veinText:set(string.format("%s %s 이상만 쓸 수 있다", vein.name, Realms.byId[vein.minRealm].name))
		ui.veinText:setColor(C.red)
	else
		ui.veinText:set("")
	end

	local index = MartialRanks.indexFor(state.martialExp)
	local rank = MartialRanks.list[index]
	local nextRank = MartialRanks.list[index + 1]
	ui.martialText:set("무공 " .. rank.name)
	local martialRatio = if nextRank then (state.martialExp - rank.exp) / (nextRank.exp - rank.exp) else 1
	ui.martialFill.Size = UDim2.fromOffset(136 * math.clamp(martialRatio, 0, 1), 6)
	ui.martialFill.Visible = martialRatio > 0.05

	ui.pointsText:set(string.format("깨달음 %d", state.enlightenment))

	local trib = state.tribulation
	ui.tribulation.Visible = trib ~= nil
	if trib then
		ui.tribName:set(trib.name)
		ui.tribWave:set(
			if trib.wave == 0 then "겁운이 모인다" else string.format("%d / %d", trib.wave, trib.waves)
		)
	end
	local wasTrib = lastState ~= nil and lastState.tribulation ~= nil
	if (trib ~= nil) ~= wasTrib then
		setTribulationMood(trib ~= nil)
	end
end

local function setOrb(key: string, look: "jade" | "stone" | "gold", label: string, glow: boolean)
	local o = orbs[key]
	setImage(o.button, if look == "gold" then "orbGold" elseif look == "stone" then "orbStone" else "orbJade")
	o.icon.ImageColor3 = if look == "stone" then Color3.fromRGB(150, 146, 138) else Color3.new(1, 1, 1)
	o.label:set(label)
	pulse(o.halo, glow, { ImageTransparency = 0.05 }, { ImageTransparency = 1 })
	pulse(o.haloScale, glow, { Scale = 1.08 }, { Scale = 1 })
end

local function updateOrbs(state)
	if state.meditating then
		setOrb("meditate", "jade", "운기 중", true)
	else
		setOrb("meditate", "jade", "운기조식", false)
	end

	local ready = Realms.nextIsMajor(state.step) and state.qi >= state.req
	if state.tribulation then
		setOrb("breakthrough", "stone", "천겁 중", false)
	elseif ready and Realms.get(state.step + 1).realm.tribulation then
		setOrb("breakthrough", "gold", "천겁 맞기", true)
	elseif ready then
		setOrb("breakthrough", "gold", "돌파", true)
	else
		setOrb("breakthrough", "stone", "돌파", false)
	end

	local affordable = false
	for _, def in Insights.list do
		local level = state.insights[def.id] or 0
		if level < def.maxLevel and state.enlightenment >= Insights.cost(def.id, level) then
			affordable = true
			break
		end
	end
	setOrb("insight", "jade", "깨달음", false)
	orbs.insight.gem.Visible = affordable
end

local function updatePanel(state)
	ui.panelPoints:set(string.format("남은 깨달음 %d", state.enlightenment))
	for id, r in insightRows do
		local def = Insights.byId[id]
		local level = state.insights[id] or 0
		r.level:set(string.format("%d / %d", level, def.maxLevel))
		r.current:set(def.show(level))
		local maxed = level >= def.maxLevel
		r.arrow.frame.Visible = not maxed
		r.nextValue.frame.Visible = not maxed
		r.buy.Visible = not maxed
		if not maxed then
			r.nextValue:set(def.show(level + 1))
			local price = Insights.cost(id, level)
			local canBuy = state.enlightenment >= price
			setImage(r.buy, if canBuy then "pillJade" else "pillStone")
			r.cost:set(tostring(price))
			r.cost:setColor(if canBuy then C.cream else C.dim)
			r.buyGem.ImageTransparency = if canBuy then 0 else 0.5
		end
	end
end

function Hud.update(state)
	updateStatus(state)
	updateOrbs(state)
	updatePanel(state)
	lastState = state
end

function Hud.togglePanel(open: boolean?)
	local panel = ui.panel :: ImageLabel
	panel.Visible = if open == nil then not panel.Visible else open
end

function Hud.toast(message: string, kind: string?)
	Chat.system(message, kind)
end

-- 연출 ---------------------------------------------------------------------------

local function showCinematic(title: string, subtitle: string, dark: boolean, hold: number)
	cinematicToken += 1
	local token = cinematicToken
	ui.cineTitle:set(title)
	ui.cineSub:set(subtitle)
	ui.cineScale.Scale = 0.94

	local fadeIn = TweenInfo.new(0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	tween(ui.cineBack, fadeIn, { BackgroundTransparency = if dark then 0.3 else 1 })
	tween(ui.cineGroup, fadeIn, { GroupTransparency = 0 })
	tween(ui.cineScale, TweenInfo.new(hold + 0.6, Enum.EasingStyle.Quad), { Scale = 1 })

	task.delay(hold, function()
		if token ~= cinematicToken then
			return
		end
		local fadeOut = TweenInfo.new(0.9)
		tween(ui.cineBack, fadeOut, { BackgroundTransparency = 1 })
		tween(ui.cineGroup, fadeOut, { GroupTransparency = 1 })
	end)
end

function Hud.cinematic(payload: { [string]: any })
	if payload.kind == "intro" then
		showCinematic(
			"블록수선전",
			if payload.returning
				then "다시 연국으로 돌아왔다"
				else "연국에서 수선의 길을 시작한다",
			true,
			3
		)
		if not payload.returning then
			task.delay(3.5, function()
				if keyboard then
					Chat.system("R 키로 운기조식, B 키로 돌파, T 키로 깨달음 창을 연다.", "info")
				else
					Chat.system("오른쪽 아래 옥 버튼으로 운기조식하고 돌파한다.", "info")
				end
				Chat.system(
					"광장 가운데 영맥 위에서 운기조식하면 영력이 더 빨리 모인다.",
					"info"
				)
			end)
		end
	elseif payload.kind == "ascend" then
		showCinematic(payload.realm, payload.blurb or "", false, 2.6)
	elseif payload.kind == "down" then
		showCinematic("쓰러졌다", "잠시 후 마을에서 깨어난다", true, 3)
	end
end

return Hud
