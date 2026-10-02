-- 화면 UI: 경지·영력 패널, 무공 패널, 행동 버튼, 깨달음 창, 알림, 연출.

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

local THEME = {
	panel = Color3.fromRGB(18, 20, 28),
	button = Color3.fromRGB(42, 46, 60),
	buttonOn = Color3.fromRGB(32, 112, 120),
	buttonReady = Color3.fromRGB(160, 112, 36),
	buttonTrib = Color3.fromRGB(150, 50, 44),
	gold = Color3.fromRGB(255, 214, 140),
	text = Color3.fromRGB(236, 236, 242),
	dim = Color3.fromRGB(160, 166, 184),
	qiA = Color3.fromRGB(110, 235, 230),
	qiB = Color3.fromRGB(90, 140, 255),
	martial = Color3.fromRGB(255, 160, 110),
	info = Color3.fromRGB(236, 236, 242),
	good = Color3.fromRGB(150, 240, 170),
	bad = Color3.fromRGB(255, 130, 120),
	tribulation = Color3.fromRGB(255, 120, 90),
	world = Color3.fromRGB(255, 214, 140),
}

local MAX_TOASTS = 6
local TOAST_TIME = 6

local Hud = {}

local player = Players.LocalPlayer
local actions: Actions
local scales: { UIScale } = {}
local refs: { [string]: any } = {}
local insightRows: { [string]: { [string]: any } } = {}
local toastOrder = 0
local cinematicToken = 0
local lastState: { [string]: any }? = nil

-- 인스턴스 생성 도우미 ------------------------------------------------------------

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

local function corner(radius: number): UICorner
	return new("UICorner", { CornerRadius = UDim.new(0, radius) })
end

local function stroke(color: Color3, transparency: number): UIStroke
	return new("UIStroke", { Color = color, Transparency = transparency, Thickness = 1 })
end

local function label(props: { [string]: any }): TextLabel
	local defaults = {
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamMedium,
		TextColor3 = THEME.text,
		TextSize = 16,
		TextXAlignment = Enum.TextXAlignment.Left,
		RichText = true,
	}
	for key, value in props do
		defaults[key] = value
	end
	return new("TextLabel", defaults)
end

local function button(props: { [string]: any }): TextButton
	local defaults = {
		AutoButtonColor = true,
		BackgroundColor3 = THEME.button,
		Font = Enum.Font.GothamBold,
		TextColor3 = THEME.text,
		TextSize = 17,
	}
	for key, value in props do
		defaults[key] = value
	end
	return new("TextButton", defaults, { corner(10), stroke(Color3.new(1, 1, 1), 0.85) })
end

-- 패널마다 붙여서 작은 화면에서 기준점(AnchorPoint) 쪽으로 줄어들게 한다
local function scaled(frame: GuiObject): GuiObject
	local scale = new("UIScale", { Parent = frame })
	table.insert(scales, scale)
	return frame
end

local function rescale()
	local camera = Workspace.CurrentCamera
	local size = if camera then camera.ViewportSize else Vector2.new(1280, 720)
	local value = math.clamp(math.min(size.X / 1280, size.Y / 720), 0.55, 1)
	for _, scale in scales do
		scale.Scale = value
	end
end

local function rgbHex(color: Color3): string
	return string.format(
		"#%02X%02X%02X",
		math.floor(color.R * 255),
		math.floor(color.G * 255),
		math.floor(color.B * 255)
	)
end

-- 만들기 -----------------------------------------------------------------------

local function buildStatus(gui: ScreenGui)
	local panel = scaled(new("Frame", {
		Name = "Status",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 8),
		Size = UDim2.fromOffset(460, 110),
		BackgroundColor3 = THEME.panel,
		BackgroundTransparency = 0.2,
		Parent = gui,
	}, { corner(12), stroke(THEME.gold, 0.7) }))

	refs.realm = label({
		Position = UDim2.fromOffset(14, 8),
		Size = UDim2.new(1, -150, 0, 34),
		Font = Enum.Font.GothamBold,
		TextSize = 28,
		TextColor3 = THEME.gold,
		Text = "…",
		Parent = panel,
	})
	refs.enlightenment = label({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -14, 0, 14),
		Size = UDim2.fromOffset(140, 24),
		TextXAlignment = Enum.TextXAlignment.Right,
		TextColor3 = THEME.text,
		Text = "",
		Parent = panel,
	})

	local bar = new("Frame", {
		Position = UDim2.fromOffset(14, 48),
		Size = UDim2.new(1, -28, 0, 22),
		BackgroundColor3 = Color3.fromRGB(8, 10, 16),
		Parent = panel,
	}, { corner(6) })
	refs.qiFill = new("Frame", {
		Size = UDim2.fromScale(0, 1),
		BackgroundColor3 = Color3.new(1, 1, 1),
		Parent = bar,
	}, {
		corner(6),
		new("UIGradient", { Color = ColorSequence.new(THEME.qiA, THEME.qiB) }),
	})
	refs.qiText = label({
		Size = UDim2.fromScale(1, 1),
		TextXAlignment = Enum.TextXAlignment.Center,
		TextSize = 14,
		Font = Enum.Font.GothamBold,
		TextStrokeTransparency = 0.5,
		Text = "",
		ZIndex = 2,
		Parent = bar,
	})

	refs.info = label({
		Position = UDim2.fromOffset(14, 78),
		Size = UDim2.new(1, -28, 0, 22),
		TextSize = 14,
		TextColor3 = THEME.dim,
		Text = "",
		Parent = panel,
	})

	refs.tribulation = label({
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 1, 10),
		Size = UDim2.fromOffset(460, 30),
		TextXAlignment = Enum.TextXAlignment.Center,
		Font = Enum.Font.GothamBold,
		TextSize = 20,
		TextColor3 = THEME.tribulation,
		TextStrokeTransparency = 0.3,
		Visible = false,
		Text = "",
		Parent = panel,
	})
end

local function buildMartial(gui: ScreenGui)
	local panel = scaled(new("Frame", {
		Name = "Martial",
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 10, 0.42, 0),
		Size = UDim2.fromOffset(230, 72),
		BackgroundColor3 = THEME.panel,
		BackgroundTransparency = 0.25,
		Parent = gui,
	}, { corner(10), stroke(THEME.martial, 0.75) }))

	refs.martialRank = label({
		Position = UDim2.fromOffset(12, 6),
		Size = UDim2.new(1, -24, 0, 22),
		Font = Enum.Font.GothamBold,
		TextSize = 17,
		TextColor3 = THEME.martial,
		Text = "",
		Parent = panel,
	})
	local bar = new("Frame", {
		Position = UDim2.fromOffset(12, 32),
		Size = UDim2.new(1, -24, 0, 8),
		BackgroundColor3 = Color3.fromRGB(8, 10, 16),
		Parent = panel,
	}, { corner(4) })
	refs.martialFill = new("Frame", {
		Size = UDim2.fromScale(0, 1),
		BackgroundColor3 = THEME.martial,
		Parent = bar,
	}, { corner(4) })
	refs.martialInfo = label({
		Position = UDim2.fromOffset(12, 44),
		Size = UDim2.new(1, -24, 0, 20),
		TextSize = 13,
		TextColor3 = THEME.dim,
		Text = "",
		Parent = panel,
	})
end

local function buildActions(gui: ScreenGui)
	local bar = scaled(new("Frame", {
		Name = "Actions",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -14),
		Size = UDim2.fromOffset(450, 58),
		BackgroundTransparency = 1,
		Parent = gui,
	}, {
		new("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			Padding = UDim.new(0, 10),
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	}))

	refs.meditate = button({ LayoutOrder = 1, Size = UDim2.new(0, 150, 1, 0), Text = "운기조식", Parent = bar })
	refs.breakthrough = button({ LayoutOrder = 2, Size = UDim2.new(0, 140, 1, 0), Text = "돌파", Parent = bar })
	refs.insightButton = button({ LayoutOrder = 3, Size = UDim2.new(0, 140, 1, 0), Text = "깨달음", Parent = bar })

	refs.meditate.Activated:Connect(function()
		actions.meditate()
	end)
	refs.breakthrough.Activated:Connect(function()
		actions.breakthrough()
	end)
	refs.insightButton.Activated:Connect(function()
		Hud.togglePanel()
	end)
end

local function buildInsightPanel(gui: ScreenGui)
	local panel = scaled(new("Frame", {
		Name = "Insights",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(520, 470),
		BackgroundColor3 = THEME.panel,
		BackgroundTransparency = 0.08,
		Visible = false,
		Parent = gui,
	}, { corner(14), stroke(THEME.gold, 0.5) }))
	refs.panel = panel

	refs.panelTitle = label({
		Position = UDim2.fromOffset(18, 12),
		Size = UDim2.new(1, -120, 0, 30),
		Font = Enum.Font.GothamBold,
		TextSize = 22,
		TextColor3 = THEME.gold,
		Text = "깨달음",
		Parent = panel,
	})
	label({
		Position = UDim2.fromOffset(18, 42),
		Size = UDim2.new(1, -36, 0, 18),
		TextSize = 13,
		TextColor3 = THEME.dim,
		Text = "경지가 오르고 천겁을 넘을 때마다 깨달음을 얻는다.",
		Parent = panel,
	})
	local close = button({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -12, 0, 12),
		Size = UDim2.fromOffset(72, 32),
		TextSize = 15,
		Text = "닫기",
		Parent = panel,
	})
	close.Activated:Connect(function()
		Hud.togglePanel(false)
	end)

	local list = new("ScrollingFrame", {
		Position = UDim2.fromOffset(12, 68),
		Size = UDim2.new(1, -24, 1, -80),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 6,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = panel,
	}, {
		new("UIListLayout", { Padding = UDim.new(0, 8), SortOrder = Enum.SortOrder.LayoutOrder }),
	})

	for index, def in Insights.list do
		local row = new("Frame", {
			LayoutOrder = index,
			Size = UDim2.new(1, -10, 0, 96),
			BackgroundColor3 = THEME.button,
			BackgroundTransparency = 0.25,
			Parent = list,
		}, { corner(10) })
		local title = label({
			Position = UDim2.fromOffset(12, 6),
			Size = UDim2.new(1, -140, 0, 24),
			Font = Enum.Font.GothamBold,
			TextSize = 17,
			Parent = row,
		})
		local current = label({
			Position = UDim2.fromOffset(12, 32),
			Size = UDim2.new(1, -140, 0, 18),
			TextSize = 13,
			TextColor3 = THEME.text,
			TextTruncate = Enum.TextTruncate.AtEnd,
			Parent = row,
		})
		local nextLine = label({
			Position = UDim2.fromOffset(12, 52),
			Size = UDim2.new(1, -140, 0, 18),
			TextSize = 13,
			TextColor3 = THEME.gold,
			TextTruncate = Enum.TextTruncate.AtEnd,
			Parent = row,
		})
		label({
			Position = UDim2.fromOffset(12, 72),
			Size = UDim2.new(1, -140, 0, 16),
			TextSize = 12,
			Font = Enum.Font.Gotham,
			TextColor3 = THEME.dim,
			TextTruncate = Enum.TextTruncate.AtEnd,
			Text = def.flavor,
			Parent = row,
		})
		local buy = button({
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, -10, 0.5, 0),
			Size = UDim2.fromOffset(112, 60),
			TextSize = 15,
			Text = "",
			Parent = row,
		})
		buy.Activated:Connect(function()
			actions.buyInsight(def.id)
		end)
		insightRows[def.id] = { title = title, current = current, nextLine = nextLine, buy = buy }
	end
end

local function buildToasts(gui: ScreenGui)
	refs.toasts = scaled(new("Frame", {
		Name = "Toasts",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -10, 0, 8),
		Size = UDim2.fromOffset(330, 400),
		BackgroundTransparency = 1,
		Parent = gui,
	}, {
		new("UIListLayout", {
			Padding = UDim.new(0, 6),
			SortOrder = Enum.SortOrder.LayoutOrder,
			HorizontalAlignment = Enum.HorizontalAlignment.Right,
		}),
	}))
end

local function buildCinematic()
	local gui = new("ScreenGui", {
		Name = "BlockSuseonCinematic",
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		DisplayOrder = 10,
		Parent = player:WaitForChild("PlayerGui"),
	})
	refs.cineBack = new("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.new(0, 0, 0),
		BackgroundTransparency = 1,
		Active = false,
		Parent = gui,
	})
	refs.cineTitle = label({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.42),
		Size = UDim2.new(0.9, 0, 0, 70),
		TextXAlignment = Enum.TextXAlignment.Center,
		Font = Enum.Font.GothamBlack,
		TextSize = 56,
		TextColor3 = THEME.gold,
		TextTransparency = 1,
		TextStrokeTransparency = 1,
		TextStrokeColor3 = Color3.fromRGB(60, 30, 0),
		Text = "",
		Parent = gui,
	})
	refs.cineSub = label({
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.fromScale(0.5, 0.42),
		Size = UDim2.new(0.9, 0, 0, 30),
		TextXAlignment = Enum.TextXAlignment.Center,
		Font = Enum.Font.GothamMedium,
		TextSize = 20,
		TextColor3 = THEME.text,
		TextTransparency = 1,
		TextStrokeTransparency = 1,
		Text = "",
		Parent = gui,
	})
	refs.cineSub.Position = UDim2.new(0.5, 0, 0.42, 44)
	refs.cineScale = new("UIScale", { Parent = refs.cineTitle })
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
	buildMartial(gui)
	buildActions(gui)
	buildInsightPanel(gui)
	buildToasts(gui)
	buildCinematic()

	-- 3D 공간 색보정: 천겁이 내릴 때 어둡게
	refs.tint = new("ColorCorrectionEffect", { Name = "천겁색보정", Parent = Lighting })

	rescale()
	local camera = Workspace.CurrentCamera
	if camera then
		camera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)
	end
end

-- 갱신 -------------------------------------------------------------------------

local function keyHint(key: string): string
	if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled then
		return ""
	end
	return string.format(' <font size="12" color="%s">[%s]</font>', rgbHex(THEME.dim), key)
end

local function setTribulationMood(active: boolean)
	local goal = if active
		then { Brightness = -0.08, Contrast = 0.15, Saturation = -0.45, TintColor = Color3.fromRGB(190, 195, 255) }
		else { Brightness = 0, Contrast = 0, Saturation = 0, TintColor = Color3.new(1, 1, 1) }
	TweenService:Create(refs.tint, TweenInfo.new(1.2), goal):Play()
end

local function updateStatus(state)
	local step = Realms.get(state.step)
	local tierText = if step.realm.tier ~= step.realm.name
		then string.format('  <font size="15" color="%s">%s</font>', rgbHex(THEME.dim), step.realm.tier)
		else ""
	refs.realm.Text = Realms.label(state.step) .. tierText
	refs.enlightenment.Text =
		string.format('깨달음 <font color="%s"><b>%d</b></font>', rgbHex(THEME.gold), state.enlightenment)

	local ratio = if state.req > 0 then math.clamp(state.qi / state.req, 0, 1) else 1
	TweenService:Create(refs.qiFill, TweenInfo.new(0.45, Enum.EasingStyle.Linear), { Size = UDim2.fromScale(ratio, 1) })
		:Play()

	local atMax = state.step >= Realms.maxStep
	local bottleneck = Realms.nextIsMajor(state.step)
	local full = ratio >= 1 and (bottleneck or atMax)
	if atMax and full then
		refs.qiText.Text = "최고 경지 — 지금 갈 수 있는 끝"
	elseif full then
		refs.qiText.Text = string.format("병목 — %s 돌파 가능", Realms.get(state.step + 1).realm.name)
	else
		refs.qiText.Text = string.format("영력 %s / %s", Format.qi(state.qi), Format.qi(state.req))
	end

	local parts = {}
	if state.meditating then
		table.insert(
			parts,
			string.format(
				'<font color="%s">운기조식 중</font> · +%s/초',
				rgbHex(THEME.qiA),
				Format.rate(state.gain)
			)
		)
	else
		table.insert(parts, "제자리에서 운기조식해 영기를 모으라" .. keyHint("R"))
	end
	if state.veinId then
		local vein = Balance.VEINS[state.veinId]
		table.insert(
			parts,
			string.format('<font color="%s">%s x%s</font>', rgbHex(THEME.qiA), vein.name, tostring(vein.mult))
		)
	elseif state.veinBlocked then
		local vein = Balance.VEINS[state.veinBlocked]
		table.insert(
			parts,
			string.format(
				'<font color="%s">%s: %s 이상만 감당한다</font>',
				rgbHex(THEME.bad),
				vein.name,
				Realms.byId[vein.minRealm].name
			)
		)
	end
	refs.info.Text = table.concat(parts, "  ·  ")

	local trib = state.tribulation
	refs.tribulation.Visible = trib ~= nil
	if trib then
		refs.tribulation.Text = if trib.wave == 0
			then string.format("[%s] 겁운이 모여든다…", trib.name)
			else string.format("[%s] 뇌격 %d / %d — 붉은 원을 피하라", trib.name, trib.wave, trib.waves)
	end
	local wasTrib = lastState ~= nil and lastState.tribulation ~= nil
	if (trib ~= nil) ~= wasTrib then
		setTribulationMood(trib ~= nil)
	end
end

local function updateActions(state)
	local meditate = refs.meditate :: TextButton
	meditate.RichText = true
	meditate.Text = (if state.meditating then "운기조식 중…" else "운기조식") .. keyHint("R")
	meditate.BackgroundColor3 = if state.meditating then THEME.buttonOn else THEME.button

	local breakthrough = refs.breakthrough :: TextButton
	breakthrough.RichText = true
	local ready = Realms.nextIsMajor(state.step) and state.qi >= state.req and state.tribulation == nil
	local text = "돌파"
	local color = THEME.button
	if ready then
		local target = Realms.get(state.step + 1).realm
		if target.tribulation then
			text = "천겁 맞기"
			color = THEME.buttonTrib
		else
			text = string.format("돌파 %s", Format.percent(state.breakChance or 0))
			color = THEME.buttonReady
		end
	end
	breakthrough.Text = text .. keyHint("B")
	breakthrough.BackgroundColor3 = color

	local insight = refs.insightButton :: TextButton
	insight.RichText = true
	insight.Text = string.format("깨달음 %d", state.enlightenment) .. keyHint("T")
end

local function updateMartial(state)
	local index = MartialRanks.indexFor(state.martialExp)
	local rank = MartialRanks.list[index]
	local nextRank = MartialRanks.list[index + 1]
	refs.martialRank.Text = "무공 · "
		.. rank.name
		.. (if rank.hanja then string.format(' <font size="13">%s</font>', rank.hanja) else "")
	if nextRank then
		local ratio = (state.martialExp - rank.exp) / (nextRank.exp - rank.exp)
		refs.martialFill.Size = UDim2.fromScale(math.clamp(ratio, 0, 1), 1)
		refs.martialInfo.Text = string.format(
			"다음 %s %d/%d · 체력 %d",
			nextRank.name,
			math.floor(state.martialExp),
			nextRank.exp,
			state.maxHealth
		)
	else
		refs.martialFill.Size = UDim2.fromScale(1, 1)
		refs.martialInfo.Text = string.format("무공의 끝 · 체력 %d", state.maxHealth)
	end
end

local function updateInsights(state)
	refs.panelTitle.Text =
		string.format('깨달음 <font color="%s">%d</font>', rgbHex(THEME.text), state.enlightenment)
	for id, row in insightRows do
		local def = Insights.byId[id]
		local level = state.insights[id] or 0
		row.title.Text = string.format(
			'%s <font size="13" color="%s">%s</font>  <font size="14" color="%s">Lv.%d/%d</font>',
			def.name,
			rgbHex(THEME.dim),
			def.hanja or "",
			rgbHex(THEME.gold),
			level,
			def.maxLevel
		)
		row.current.Text = "현재  " .. def.describe(level)
		local buy = row.buy :: TextButton
		if level >= def.maxLevel then
			row.nextLine.Text = "끝까지 깨달았다"
			buy.Text = "완성"
			buy.BackgroundColor3 = THEME.button
			buy.AutoButtonColor = false
		else
			local cost = Insights.cost(id, level)
			local affordable = state.enlightenment >= cost
			row.nextLine.Text = "다음  " .. def.describe(level + 1)
			buy.Text = string.format("깨닫기\n%d", cost)
			buy.BackgroundColor3 = if affordable then THEME.buttonReady else THEME.button
			buy.AutoButtonColor = affordable
		end
	end
end

function Hud.update(state)
	updateStatus(state)
	updateActions(state)
	updateMartial(state)
	updateInsights(state)
	lastState = state
end

function Hud.togglePanel(open: boolean?)
	local panel = refs.panel :: Frame
	if open == nil then
		open = not panel.Visible
	end
	panel.Visible = open :: boolean
end

-- 알림 -------------------------------------------------------------------------

function Hud.toast(text: string, kind: string?)
	toastOrder += 1
	local color = THEME[kind or "info"] or THEME.text
	local frame = new("Frame", {
		LayoutOrder = toastOrder,
		Size = UDim2.new(1, 0, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		BackgroundColor3 = THEME.panel,
		BackgroundTransparency = 0.2,
		Parent = refs.toasts,
	}, {
		corner(8),
		new("UIPadding", {
			PaddingTop = UDim.new(0, 6),
			PaddingBottom = UDim.new(0, 6),
			PaddingLeft = UDim.new(0, 10),
			PaddingRight = UDim.new(0, 10),
		}),
	})
	local text_ = label({
		Size = UDim2.new(1, 0, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		TextWrapped = true,
		TextSize = 15,
		TextColor3 = color,
		RichText = false,
		Text = text,
		Parent = frame,
	})

	local frames = {}
	for _, child in refs.toasts:GetChildren() do
		if child:IsA("Frame") then
			table.insert(frames, child)
		end
	end
	table.sort(frames, function(a, b)
		return a.LayoutOrder < b.LayoutOrder
	end)
	for i = 1, #frames - MAX_TOASTS do
		frames[i]:Destroy()
	end

	task.delay(TOAST_TIME, function()
		if frame.Parent then
			local info = TweenInfo.new(0.6)
			TweenService:Create(frame, info, { BackgroundTransparency = 1 }):Play()
			TweenService:Create(text_, info, { TextTransparency = 1 }):Play()
			task.wait(0.6)
			frame:Destroy()
		end
	end)
end

-- 연출 -------------------------------------------------------------------------

local function showCinematic(title: string, subtitle: string, dark: boolean, hold: number)
	cinematicToken += 1
	local token = cinematicToken
	refs.cineTitle.Text = title
	refs.cineSub.Text = subtitle
	refs.cineScale.Scale = 0.85

	local fadeIn = TweenInfo.new(0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	TweenService:Create(refs.cineBack, fadeIn, { BackgroundTransparency = if dark then 0.15 else 1 }):Play()
	TweenService:Create(refs.cineTitle, fadeIn, { TextTransparency = 0, TextStrokeTransparency = 0.3 }):Play()
	TweenService:Create(refs.cineSub, fadeIn, { TextTransparency = 0, TextStrokeTransparency = 0.6 }):Play()
	TweenService
		:Create(
			refs.cineScale,
			TweenInfo.new(hold + 0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
			{ Scale = 1 }
		)
		:Play()

	task.delay(hold, function()
		if token ~= cinematicToken then
			return
		end
		local fadeOut = TweenInfo.new(0.9)
		TweenService:Create(refs.cineBack, fadeOut, { BackgroundTransparency = 1 }):Play()
		TweenService:Create(refs.cineTitle, fadeOut, { TextTransparency = 1, TextStrokeTransparency = 1 }):Play()
		TweenService:Create(refs.cineSub, fadeOut, { TextTransparency = 1, TextStrokeTransparency = 1 }):Play()
	end)
end

function Hud.cinematic(payload: { [string]: any })
	if payload.kind == "intro" then
		local subtitle = if payload.returning
			then string.format("다시 연국(連國)으로 · %s", payload.realm)
			else "연국(連國) — 영기를 받아들여 선(仙)의 길에 올라라"
		showCinematic("블록수선전", subtitle, true, 3)
	elseif payload.kind == "ascend" then
		showCinematic(payload.realm, payload.blurb or "", false, 2.6)
	elseif payload.kind == "down" then
		showCinematic("쓰러졌다", "잠시 후 마을에서 깨어난다.", true, 3)
	end
end

return Hud
