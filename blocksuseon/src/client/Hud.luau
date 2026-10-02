-- 화면 UI.
-- 수묵·인장 느낌: 상자 대신 글자와 가는 먹선, 버튼은 붉은 인장, 깨달음 창은 한지 족자 한 폭.

local Players = game:GetService("Players")
local Lighting = game:GetService("Lighting")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Insights = require(Shared.Insights)
local MartialRanks = require(Shared.MartialRanks)
local Format = require(Shared.Format)

export type Actions = {
	meditate: () -> (),
	breakthrough: () -> (),
	buyInsight: (id: string) -> (),
}

local C = {
	paper = Color3.fromRGB(236, 228, 210),
	paperShade = Color3.fromRGB(214, 203, 180),
	ink = Color3.fromRGB(30, 27, 24),
	inkSoft = Color3.fromRGB(110, 100, 88),
	white = Color3.fromRGB(246, 242, 232),
	seal = Color3.fromRGB(170, 52, 42),
	sealDim = Color3.fromRGB(96, 82, 76),
	jade = Color3.fromRGB(110, 196, 166),
	jadeDeep = Color3.fromRGB(46, 120, 100),
	gold = Color3.fromRGB(226, 188, 108),
	red = Color3.fromRGB(238, 122, 106),
}

local FEED_COLORS = {
	info = C.white,
	good = C.jade,
	bad = C.red,
	tribulation = C.red,
	world = C.gold,
}
local FEED_MAX = 4
local FEED_TIME = 4.5

local SEALS = {
	{ key = "meditate", glyph = "運", caption = "운기조식", hotkey = "R" },
	{ key = "breakthrough", glyph = "破", caption = "돌파", hotkey = "B" },
	{ key = "insight", glyph = "悟", caption = "깨달음", hotkey = "T" },
}

local Hud = {}

local player = Players.LocalPlayer
local keyboard = UserInputService.KeyboardEnabled
local actions: Actions
local scales: { UIScale } = {}
local ui: { [string]: any } = {}
local seals: { [string]: { [string]: any } } = {}
local insightRows: { [string]: { [string]: any } } = {}
local pulses: { [Instance]: Tween } = {}
local feedOrder = 0
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

local function hex(color: Color3): string
	return string.format(
		"#%02X%02X%02X",
		math.floor(color.R * 255 + 0.5),
		math.floor(color.G * 255 + 0.5),
		math.floor(color.B * 255 + 0.5)
	)
end

local function corner(px: number): UICorner
	return new("UICorner", { CornerRadius = UDim.new(0, px) })
end

local function border(color: Color3, thickness: number, transparency: number): UIStroke
	return new("UIStroke", {
		Color = color,
		Thickness = thickness,
		Transparency = transparency,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
	})
end

-- 3D 화면 위에 바로 얹는 글자. 먹선을 둘러 어디서나 읽히게 한다.
local function text(props: { [string]: any }): TextLabel
	local base: { [string]: any } = {
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamMedium,
		TextColor3 = C.white,
		TextStrokeColor3 = C.ink,
		TextStrokeTransparency = 0.45,
		TextSize = 15,
		RichText = true,
		Text = "",
	}
	for key, value in props do
		base[key] = value
	end
	return new("TextLabel", base)
end

-- 종이 위의 먹 글씨
local function inkText(props: { [string]: any }): TextLabel
	props.TextColor3 = props.TextColor3 or C.ink
	props.TextStrokeTransparency = 1
	return text(props)
end

local function tween(target: Instance, info: TweenInfo, goal: { [string]: any })
	TweenService:Create(target, info, goal):Play()
end

-- 숨 쉬듯 반복하는 트윈. 끄면 rest 값으로 되돌린다.
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
			TweenInfo.new(0.9, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
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

-- 작은 화면에서는 각 묶음이 자기 기준점(AnchorPoint) 쪽으로 줄어든다
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

-- "結丹期" → "結"
local function firstChar(s: string?): string?
	if not s or s == "" then
		return nil
	end
	local second = utf8.offset(s, 2)
	return if second then string.sub(s, 1, second - 1) else s
end

-- 인장 하나: 붉은 바탕, 안쪽 가는 테, 가운데 한 글자
local function stamp(
	parent: Instance,
	size: number,
	glyph: string,
	glyphSize: number,
	className: string?
): (GuiObject, TextLabel)
	local frame = new(className or "Frame", {
		Size = UDim2.fromOffset(size, size),
		BackgroundColor3 = C.seal,
		BorderSizePixel = 0,
		Parent = parent,
	}, { corner(math.max(3, math.floor(size / 12))) })
	if frame:IsA("TextButton") then
		frame.AutoButtonColor = false
		frame.Text = ""
	end
	new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.new(1, -math.floor(size / 7), 1, -math.floor(size / 7)),
		BackgroundTransparency = 1,
		Parent = frame,
	}, { corner(math.max(2, math.floor(size / 18))), border(C.paper, 1.5, 0.4) })
	local label = text({
		Size = UDim2.fromScale(1, 1),
		Font = Enum.Font.GothamBold,
		TextSize = glyphSize,
		TextColor3 = C.paper,
		TextStrokeTransparency = 1,
		RichText = false,
		Text = glyph,
		Parent = frame,
	})
	return frame, label
end

-- 만들기 ---------------------------------------------------------------------------

-- 위 가운데: 경지 이름, 영력 먹선, 상태 한 줄, 천겁
local function buildTop(gui: ScreenGui)
	local top = scaled(new("Frame", {
		Name = "Realm",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 6),
		Size = UDim2.fromOffset(420, 132),
		BackgroundTransparency = 1,
		Parent = gui,
	}))

	ui.realm = text({
		Size = UDim2.new(1, 0, 0, 38),
		Font = Enum.Font.GothamBold,
		TextSize = 30,
		TextStrokeTransparency = 0.3,
		Parent = top,
	})

	local track = new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 44),
		Size = UDim2.fromOffset(300, 4),
		BackgroundColor3 = C.ink,
		BackgroundTransparency = 0.35,
		BorderSizePixel = 0,
		Parent = top,
	})
	ui.qiFill = new("Frame", {
		Size = UDim2.fromScale(0, 1),
		BackgroundColor3 = C.jade,
		BorderSizePixel = 0,
		Parent = track,
	})
	-- 병목 표시: 줄 끝의 마름모
	ui.qiCap = new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(1, 0.5),
		Size = UDim2.fromOffset(9, 9),
		Rotation = 45,
		BackgroundColor3 = C.paper,
		BorderSizePixel = 0,
		Visible = false,
		Parent = track,
	})

	ui.qiText = text({
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 52),
		Size = UDim2.fromOffset(360, 18),
		TextSize = 13,
		TextStrokeTransparency = 0.5,
		Parent = top,
	})
	ui.status = text({
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 70),
		Size = UDim2.fromOffset(400, 18),
		TextSize = 13,
		TextColor3 = C.jade,
		Parent = top,
	})
	ui.tribulation = text({
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 94),
		Size = UDim2.fromOffset(420, 34),
		Font = Enum.Font.GothamBold,
		TextSize = 24,
		TextColor3 = C.red,
		TextStrokeTransparency = 0.2,
		Visible = false,
		Parent = top,
	})
end

-- 아래 가운데: 인장 버튼 세 개
local function buildSeals(gui: ScreenGui)
	local bar = scaled(new("Frame", {
		Name = "Seals",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -12),
		Size = UDim2.fromOffset(260, 88),
		BackgroundTransparency = 1,
		Parent = gui,
	}, {
		new("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			SortOrder = Enum.SortOrder.LayoutOrder,
			Padding = UDim.new(0, 18),
		}),
	}))

	for index, def in SEALS do
		local holder = new("Frame", {
			LayoutOrder = index,
			Size = UDim2.fromOffset(62, 88),
			BackgroundTransparency = 1,
			Parent = bar,
		})
		local button, glyph = stamp(holder, 58, def.glyph, 30, "TextButton")
		button.AnchorPoint = Vector2.new(0.5, 0)
		button.Position = UDim2.fromScale(0.5, 0)
		local press = new("UIScale", { Parent = button })
		local glow = border(C.gold, 2.5, 1)
		glow.Parent = button

		text({
			AnchorPoint = Vector2.new(1, 0),
			Position = UDim2.new(1, -6, 0, 4),
			Size = UDim2.fromOffset(12, 12),
			TextSize = 10,
			TextColor3 = C.paper,
			TextTransparency = 0.4,
			TextStrokeTransparency = 1,
			RichText = false,
			Text = def.hotkey,
			Visible = keyboard,
			Parent = button,
		})
		local badge = new("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromOffset(4, 4),
			Size = UDim2.fromOffset(10, 10),
			BackgroundColor3 = C.jade,
			BorderSizePixel = 0,
			Visible = false,
			Parent = button,
		}, { corner(5), border(C.ink, 1, 0.3) })
		local caption = text({
			AnchorPoint = Vector2.new(0.5, 0),
			Position = UDim2.new(0.5, 0, 0, 63),
			Size = UDim2.fromOffset(110, 18),
			TextSize = 13,
			Text = def.caption,
			Parent = holder,
		})

		button.MouseButton1Down:Connect(function()
			press.Scale = 0.92
		end)
		button.MouseButton1Up:Connect(function()
			press.Scale = 1
		end)
		button.MouseLeave:Connect(function()
			press.Scale = 1
		end)
		button.Activated:Connect(function()
			press.Scale = 1
			if def.key == "meditate" then
				actions.meditate()
			elseif def.key == "breakthrough" then
				actions.breakthrough()
			else
				Hud.togglePanel()
			end
		end)

		seals[def.key] = { button = button, glyph = glyph, caption = caption, glow = glow, badge = badge }
	end
end

-- 왼쪽: 무공
local function buildMartial(gui: ScreenGui)
	local box = scaled(new("Frame", {
		Name = "Martial",
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 16, 0.56, 0),
		Size = UDim2.fromOffset(200, 50),
		BackgroundTransparency = 1,
		Parent = gui,
	}))
	stamp(box, 24, "武", 14)
	ui.martialRank = text({
		Position = UDim2.fromOffset(32, 0),
		Size = UDim2.new(1, -32, 0, 24),
		TextXAlignment = Enum.TextXAlignment.Left,
		Font = Enum.Font.GothamBold,
		TextSize = 17,
		Parent = box,
	})
	local track = new("Frame", {
		Position = UDim2.fromOffset(0, 31),
		Size = UDim2.fromOffset(150, 2),
		BackgroundColor3 = C.ink,
		BackgroundTransparency = 0.35,
		BorderSizePixel = 0,
		Parent = box,
	})
	ui.martialFill = new("Frame", {
		Size = UDim2.fromScale(0, 1),
		BackgroundColor3 = C.paper,
		BorderSizePixel = 0,
		Parent = track,
	})
	ui.martialInfo = text({
		Position = UDim2.fromOffset(0, 36),
		Size = UDim2.new(1, 0, 0, 14),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextSize = 12,
		TextTransparency = 0.15,
		Parent = box,
	})
end

-- 아래 가운데, 인장 위: 알림 몇 줄
local function buildFeed(gui: ScreenGui)
	ui.feed = scaled(new("Frame", {
		Name = "Feed",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -110),
		Size = UDim2.fromOffset(600, 100),
		BackgroundTransparency = 1,
		Parent = gui,
	}, {
		new("UIListLayout", {
			VerticalAlignment = Enum.VerticalAlignment.Bottom,
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			SortOrder = Enum.SortOrder.LayoutOrder,
			Padding = UDim.new(0, 2),
		}),
	}))
end

-- 깨달음 창: 한지 족자
local function buildPanel(gui: ScreenGui)
	local sheet = scaled(new("Frame", {
		Name = "Insights",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(440, 480),
		BackgroundColor3 = C.paper,
		BorderSizePixel = 0,
		Visible = false,
		Parent = gui,
	}, { border(C.ink, 1.5, 0.2) }))
	ui.panel = sheet

	-- 족자 위아래 축
	for _, y in { 0, 1 } do
		new("Frame", {
			AnchorPoint = Vector2.new(0.5, y),
			Position = UDim2.new(0.5, 0, y, if y == 0 then -6 else 6),
			Size = UDim2.new(1, 28, 0, 10),
			BackgroundColor3 = C.ink,
			BorderSizePixel = 0,
			Parent = sheet,
		}, { corner(3) })
	end

	local seal = stamp(sheet, 44, "悟", 26)
	seal.Position = UDim2.fromOffset(26, 28)
	ui.panelTitle = inkText({
		Position = UDim2.fromOffset(84, 28),
		Size = UDim2.new(1, -150, 0, 26),
		TextXAlignment = Enum.TextXAlignment.Left,
		Font = Enum.Font.GothamBold,
		TextSize = 22,
		Text = "깨달음",
		Parent = sheet,
	})
	ui.panelPoints = inkText({
		Position = UDim2.fromOffset(84, 54),
		Size = UDim2.new(1, -150, 0, 18),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextSize = 13,
		TextColor3 = C.inkSoft,
		Parent = sheet,
	})

	local close = new("TextButton", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -18, 0, 24),
		Size = UDim2.fromOffset(32, 32),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamMedium,
		TextSize = 26,
		TextColor3 = C.ink,
		Text = "×",
		Parent = sheet,
	})
	close.Activated:Connect(function()
		Hud.togglePanel(false)
	end)

	new("Frame", {
		Position = UDim2.fromOffset(26, 88),
		Size = UDim2.new(1, -52, 0, 1),
		BackgroundColor3 = C.ink,
		BackgroundTransparency = 0.6,
		BorderSizePixel = 0,
		Parent = sheet,
	})

	local list = new("ScrollingFrame", {
		Position = UDim2.fromOffset(26, 96),
		Size = UDim2.new(1, -46, 1, -116),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 3,
		ScrollBarImageColor3 = C.ink,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = sheet,
	}, {
		new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder }),
	})

	for index, def in Insights.list do
		local row = new("Frame", {
			LayoutOrder = index,
			Size = UDim2.new(1, -8, 0, 62),
			BackgroundTransparency = 1,
			Parent = list,
		})
		local name = inkText({
			Position = UDim2.fromOffset(0, 9),
			Size = UDim2.new(1, -92, 0, 22),
			TextXAlignment = Enum.TextXAlignment.Left,
			Font = Enum.Font.GothamBold,
			TextSize = 17,
			Parent = row,
		})
		local effect = inkText({
			Position = UDim2.fromOffset(0, 33),
			Size = UDim2.new(1, -92, 0, 18),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextSize = 13,
			TextColor3 = C.inkSoft,
			Parent = row,
		})
		local buy = new("TextButton", {
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.fromScale(1, 0.5),
			Size = UDim2.fromOffset(76, 38),
			BackgroundColor3 = C.seal,
			AutoButtonColor = false,
			BorderSizePixel = 0,
			Font = Enum.Font.GothamBold,
			TextSize = 16,
			TextColor3 = C.paper,
			RichText = true,
			Text = "",
			Parent = row,
		}, { corner(4) })
		new("Frame", {
			AnchorPoint = Vector2.new(0, 1),
			Position = UDim2.fromScale(0, 1),
			Size = UDim2.new(1, 0, 0, 1),
			BackgroundColor3 = C.ink,
			BackgroundTransparency = 0.82,
			BorderSizePixel = 0,
			Parent = row,
		})
		buy.Activated:Connect(function()
			actions.buyInsight(def.id)
		end)
		insightRows[def.id] = { name = name, effect = effect, buy = buy }
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
		BackgroundColor3 = C.ink,
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Parent = gui,
	})
	-- 제목 뒤에 크게 깔리는 한자
	ui.cineHanja = text({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.45),
		Size = UDim2.new(1, 0, 0, 170),
		Font = Enum.Font.GothamBold,
		TextSize = 150,
		TextColor3 = C.paper,
		TextTransparency = 1,
		TextStrokeTransparency = 1,
		RichText = false,
		Parent = gui,
	})
	ui.cineTitle = text({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.45),
		Size = UDim2.new(1, 0, 0, 64),
		Font = Enum.Font.GothamBlack,
		TextSize = 50,
		TextTransparency = 1,
		TextStrokeTransparency = 1,
		RichText = false,
		Parent = gui,
	})
	ui.cineTitleScale = new("UIScale", { Parent = ui.cineTitle })
	ui.cineSub = text({
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0.45, 40),
		Size = UDim2.new(1, 0, 0, 26),
		TextSize = 18,
		TextTransparency = 1,
		TextStrokeTransparency = 1,
		RichText = false,
		Parent = gui,
	})
	local seal, glyph = stamp(gui, 58, "", 32)
	seal.AnchorPoint = Vector2.new(0.5, 0.5)
	seal.Position = UDim2.new(0.5, 0, 0.45, -84)
	ui.cineSeal = seal
	ui.cineSealGlyph = glyph
	ui.cineSealScale = new("UIScale", { Parent = seal })
	seal.Visible = false
end

function Hud.build(newActions: Actions)
	actions = newActions
	local gui = new("ScreenGui", {
		Name = "BlockSuseonHud",
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = player:WaitForChild("PlayerGui"),
	})
	buildTop(gui)
	buildMartial(gui)
	buildFeed(gui)
	buildSeals(gui)
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

local function updateTop(state)
	local step = Realms.get(state.step)
	local realm = step.realm
	local sub = if step.sub ~= "" then string.format(' <font size="22">%s</font>', step.sub) else ""
	local hanja = if realm.hanja
		then string.format('  <font size="16" transparency="0.35">%s</font>', realm.hanja)
		else ""
	ui.realm.Text = realm.name .. sub .. hanja

	local ratio = if state.req > 0 then math.clamp(state.qi / state.req, 0, 1) else 1
	tween(ui.qiFill, TweenInfo.new(0.45, Enum.EasingStyle.Linear), { Size = UDim2.fromScale(ratio, 1) })

	local atMax = state.step >= Realms.maxStep
	local bottleneck = Realms.nextIsMajor(state.step)
	local full = ratio >= 1 and (bottleneck or atMax)
	ui.qiFill.BackgroundColor3 = if full then C.gold else C.jade
	ui.qiCap.Visible = bottleneck
	ui.qiCap.BackgroundColor3 = if full then C.seal else C.paper

	if atMax and full then
		ui.qiText.Text = "최고 경지"
	elseif full then
		local target = Realms.get(state.step + 1).realm
		ui.qiText.Text = if target.tribulation
			then string.format('<font color="%s">병목</font>  ·  %s 천겁', hex(C.gold), target.name)
			else string.format(
				'<font color="%s">병목</font>  ·  %s 돌파 %s',
				hex(C.gold),
				target.name,
				Format.percent(state.breakChance or 0)
			)
	else
		ui.qiText.Text = string.format("%s / %s", Format.qi(state.qi), Format.qi(state.req))
	end

	local parts = {}
	if state.meditating then
		table.insert(parts, string.format("운기 +%s/초", Format.rate(state.gain)))
	end
	if state.veinId then
		local vein = Balance.VEINS[state.veinId]
		table.insert(parts, string.format("%s ×%s", vein.name, tostring(vein.mult)))
	elseif state.veinBlocked then
		local vein = Balance.VEINS[state.veinBlocked]
		table.insert(
			parts,
			string.format(
				'<font color="%s">%s · %s부터</font>',
				hex(C.red),
				vein.name,
				Realms.byId[vein.minRealm].name
			)
		)
	end
	ui.status.Text = table.concat(parts, "   ·   ")

	local trib = state.tribulation
	ui.tribulation.Visible = trib ~= nil
	if trib then
		ui.tribulation.Text = if trib.wave == 0
			then string.format('劫  %s  <font size="16">겁운이 모인다</font>', trib.name)
			else string.format('劫  %s  <font size="18">%d / %d</font>', trib.name, trib.wave, trib.waves)
	end
	local wasTrib = lastState ~= nil and lastState.tribulation ~= nil
	if (trib ~= nil) ~= wasTrib then
		setTribulationMood(trib ~= nil)
	end
end

local function setSeal(key: string, color: Color3, glyph: string, caption: string, glowColor: Color3?)
	local seal = seals[key]
	seal.button.BackgroundColor3 = color
	seal.glyph.Text = glyph
	seal.caption.Text = caption
	if glowColor then
		seal.glow.Color = glowColor
	end
	pulse(seal.glow, glowColor ~= nil, { Transparency = 0.05 }, { Transparency = 1 })
end

local function updateSeals(state)
	if state.meditating then
		setSeal("meditate", C.jadeDeep, "運", "운기 중", C.jade)
	else
		setSeal("meditate", C.seal, "運", "운기조식", nil)
	end

	local ready = Realms.nextIsMajor(state.step) and state.qi >= state.req
	if state.tribulation then
		setSeal("breakthrough", C.sealDim, "劫", "천겁 중", nil)
	elseif state.step >= Realms.maxStep then
		setSeal("breakthrough", C.sealDim, "破", "끝", nil)
	elseif ready and Realms.get(state.step + 1).realm.tribulation then
		setSeal("breakthrough", C.seal, "劫", "천겁 맞기", C.gold)
	elseif ready then
		setSeal("breakthrough", C.seal, "破", "돌파 " .. Format.percent(state.breakChance or 0), C.gold)
	else
		setSeal("breakthrough", C.sealDim, "破", "돌파", nil)
	end

	local affordable = false
	for _, def in Insights.list do
		local level = state.insights[def.id] or 0
		if level < def.maxLevel and state.enlightenment >= Insights.cost(def.id, level) then
			affordable = true
			break
		end
	end
	setSeal("insight", C.seal, "悟", string.format("깨달음 %d", state.enlightenment), nil)
	seals.insight.badge.Visible = affordable
end

local function updateMartial(state)
	local index = MartialRanks.indexFor(state.martialExp)
	local rank = MartialRanks.list[index]
	local nextRank = MartialRanks.list[index + 1]
	ui.martialRank.Text = rank.name
		.. (if rank.hanja then string.format('  <font size="12" transparency="0.4">%s</font>', rank.hanja) else "")
	if nextRank then
		local ratio = (state.martialExp - rank.exp) / (nextRank.exp - rank.exp)
		ui.martialFill.Size = UDim2.fromScale(math.clamp(ratio, 0, 1), 1)
		ui.martialInfo.Text =
			string.format("%s까지 %d / %d", nextRank.name, math.floor(state.martialExp), nextRank.exp)
	else
		ui.martialFill.Size = UDim2.fromScale(1, 1)
		ui.martialInfo.Text = "무공의 끝"
	end
end

local function updatePanel(state)
	ui.panelPoints.Text = string.format("남은 깨달음  %d", state.enlightenment)
	for id, row in insightRows do
		local def = Insights.byId[id]
		local level = state.insights[id] or 0
		row.name.Text = string.format(
			'%s  <font size="13" color="%s">%s</font>   <font size="13" color="%s">%d / %d</font>',
			def.name,
			hex(C.inkSoft),
			def.hanja or "",
			hex(C.seal),
			level,
			def.maxLevel
		)
		local buy = row.buy :: TextButton
		if level >= def.maxLevel then
			row.effect.Text = string.format("%s  %s  · 완성", def.stat, def.show(level))
			buy.Visible = false
		else
			row.effect.Text = string.format(
				'%s  %s  <font color="%s">→ %s</font>',
				def.stat,
				def.show(level),
				hex(C.jadeDeep),
				def.show(level + 1)
			)
			local cost = Insights.cost(id, level)
			local canBuy = state.enlightenment >= cost
			buy.Visible = true
			buy.Text = string.format('<font size="12">悟</font> %d', cost)
			buy.BackgroundColor3 = if canBuy then C.seal else C.paperShade
			buy.TextColor3 = if canBuy then C.paper else C.inkSoft
		end
	end
end

function Hud.update(state)
	updateTop(state)
	updateSeals(state)
	updateMartial(state)
	updatePanel(state)
	lastState = state
end

function Hud.togglePanel(open: boolean?)
	local panel = ui.panel :: Frame
	panel.Visible = if open == nil then not panel.Visible else open
end

-- 알림 ---------------------------------------------------------------------------

function Hud.toast(message: string, kind: string?)
	feedOrder += 1
	local line = text({
		LayoutOrder = feedOrder,
		Size = UDim2.new(1, 0, 0, 22),
		TextSize = 16,
		TextColor3 = FEED_COLORS[kind or "info"] or C.white,
		TextTransparency = 1,
		TextStrokeTransparency = 1,
		RichText = false,
		Text = message,
		Parent = ui.feed,
	})
	tween(line, TweenInfo.new(0.2), { TextTransparency = 0, TextStrokeTransparency = 0.35 })

	local lines = {}
	for _, child in ui.feed:GetChildren() do
		if child:IsA("TextLabel") then
			table.insert(lines, child)
		end
	end
	table.sort(lines, function(a, b)
		return a.LayoutOrder < b.LayoutOrder
	end)
	for i = 1, #lines - FEED_MAX do
		lines[i]:Destroy()
	end

	task.delay(FEED_TIME, function()
		if line.Parent then
			tween(line, TweenInfo.new(0.8), { TextTransparency = 1, TextStrokeTransparency = 1 })
			task.wait(0.8)
			line:Destroy()
		end
	end)
end

-- 연출 ---------------------------------------------------------------------------

type CinematicOptions = { dark: boolean, hold: number, hanja: string?, seal: string? }

local function showCinematic(title: string, subtitle: string, options: CinematicOptions)
	cinematicToken += 1
	local token = cinematicToken

	ui.cineTitle.Text = title
	ui.cineSub.Text = subtitle
	ui.cineHanja.Text = options.hanja or ""
	ui.cineTitleScale.Scale = 0.94

	local fadeIn = TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	tween(ui.cineBack, fadeIn, { BackgroundTransparency = if options.dark then 0.2 else 1 })
	tween(ui.cineHanja, TweenInfo.new(1.4), { TextTransparency = 0.9 })
	tween(ui.cineTitle, fadeIn, { TextTransparency = 0, TextStrokeTransparency = 0.3 })
	tween(ui.cineSub, fadeIn, { TextTransparency = 0.1, TextStrokeTransparency = 0.5 })
	tween(ui.cineTitleScale, TweenInfo.new(options.hold + 0.5, Enum.EasingStyle.Quad), { Scale = 1 })

	-- 인장이 쾅 찍힌다
	local seal = ui.cineSeal :: Frame
	seal.Visible = options.seal ~= nil
	if options.seal then
		ui.cineSealGlyph.Text = options.seal
		ui.cineSealScale.Scale = 1.8
		seal.BackgroundTransparency = 1
		ui.cineSealGlyph.TextTransparency = 1
		task.delay(0.35, function()
			if token ~= cinematicToken then
				return
			end
			local hit = TweenInfo.new(0.2, Enum.EasingStyle.Back, Enum.EasingDirection.Out)
			tween(ui.cineSealScale, hit, { Scale = 1 })
			tween(seal, TweenInfo.new(0.12), { BackgroundTransparency = 0 })
			tween(ui.cineSealGlyph, TweenInfo.new(0.12), { TextTransparency = 0 })
		end)
	end

	task.delay(options.hold, function()
		if token ~= cinematicToken then
			return
		end
		local fadeOut = TweenInfo.new(0.9)
		tween(ui.cineBack, fadeOut, { BackgroundTransparency = 1 })
		tween(ui.cineHanja, fadeOut, { TextTransparency = 1 })
		tween(ui.cineTitle, fadeOut, { TextTransparency = 1, TextStrokeTransparency = 1 })
		tween(ui.cineSub, fadeOut, { TextTransparency = 1, TextStrokeTransparency = 1 })
		tween(seal, fadeOut, { BackgroundTransparency = 1 })
		tween(ui.cineSealGlyph, fadeOut, { TextTransparency = 1 })
	end)
end

function Hud.cinematic(payload: { [string]: any })
	if payload.kind == "intro" then
		local subtitle = if payload.returning then "연국 · " .. payload.realm else "연국(連國)"
		showCinematic("블록수선전", subtitle, { dark = true, hold = 3, hanja = "修仙", seal = "修" })
		if not payload.returning then
			task.delay(3.6, function()
				Hud.toast(
					if keyboard
						then "R 운기조식  ·  B 돌파  ·  T 깨달음"
						else "아래 인장으로 운기조식 · 돌파 · 깨달음",
					"info"
				)
				Hud.toast("광장 가운데 영맥 위에서 운기조식하면 더 빠르다", "info")
			end)
		end
	elseif payload.kind == "ascend" then
		local realm = if payload.step then Realms.get(payload.step).realm else nil
		local hanja = realm and realm.hanja
		showCinematic(payload.realm, payload.blurb or "", {
			dark = false,
			hold = 2.6,
			hanja = hanja,
			seal = firstChar(hanja) or "破",
		})
	elseif payload.kind == "down" then
		showCinematic("쓰러졌다", "잠시 후 마을에서 깨어난다", { dark = true, hold = 3 })
	end
end

return Hud
