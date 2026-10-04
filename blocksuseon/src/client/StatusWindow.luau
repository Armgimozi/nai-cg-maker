-- 상태창 (C). 왼쪽에 늘 보이는 인물 칸(이름, 경지, 능력치, 종족과 다시 뽑기·확률),
-- 오른쪽에 갈래: 술법(단축칸 넣기·키 바꾸기), 공법(장착), 법구(공격·방어), 주머니.
-- 마지막으로 본 갈래를 기억한다. 화면 아래 단축칸의 빈 칸을 누르면 술법 갈래가 그 칸을 고른 채 열린다.
-- 크기는 1040×540 (Hud 의 UIScale 로 줄인다: 폰 가로 844×390 은 0.6 배라 위쪽 막대 아래 332px 안에 든다).

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local PolicyService = game:GetService("PolicyService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Format = require(Shared.Format)
local Roots = require(Shared.Roots)
local Races = require(Shared.Races)
local Currency = require(Shared.Currency)
local Ui = require(script.Parent.Ui)
local BitmapText = require(script.Parent.BitmapText)
local Kit = require(script.Parent.StatusKit)
local SkillsTab = require(script.Parent.SkillsTab)
local BeopguTab = require(script.Parent.BeopguTab)
local PouchTab = require(script.Parent.PouchTab)

local C = Ui.C
local new, image, setImage, text, row, tween = Ui.new, Ui.image, Ui.setImage, Ui.text, Ui.row, Ui.tween

local StatusWindow = {}

StatusWindow.W, StatusWindow.H = 1040, 540
local SIDE = 34 -- 창 가장자리에서 안쪽 칸까지
local LEFT_W = 262 -- 인물 칸
local BODY_Y = 84
local CONTENT_X = SIDE + LEFT_W + 18
local CONTENT_Y = BODY_Y + 48
StatusWindow.LEFT_INNER = LEFT_W - 28

StatusWindow.TABS = {
	{ key = "skills", label = "술법" },
	{ key = "passives", label = "공법" },
	{ key = "gear", label = "법구" },
	{ key = "pouch", label = "주머니" },
}

local STAT_KEYS = { "체력", "영력", "흡수", "영근", "종족", "영석", "천겁", "영초", "비급" }
local STAT_Y, STAT_GAP = 118, 24

local player = Players.LocalPlayer
local ui: { [string]: any } = {}
local tabs: { [string]: { [string]: any } } = {}
local current = "skills"
local lastState: { [string]: any }? = nil

local function draw()
	local state = lastState
	if not state or not ui.panel then
		return
	end
	local step = Realms.get(state.step)
	-- 긴 경지 이름("연기기 1성 칠십이지살")은 작은 글자로 찍어 칸에 맞춘다
	local label = Realms.label(state.step)
	local small = BitmapText.measure("title", 30, label).X > StatusWindow.LEFT_INNER + 4
	ui.realm.frame.Visible = not small
	ui.realmSmall.frame.Visible = small
	ui.realm:set(if small then "" else label)
	ui.realmSmall:set(if small then label else "")
	ui.tier:set(step.realm.tier)
	local ratio = if state.req > 0 then math.clamp(state.qi / state.req, 0, 1) else 1
	setImage(ui.qiFill, if ratio >= 1 then "barGold" else "barJade")
	ui.qiFill.Visible = ratio > 0.03
	tween(ui.qiFill, TweenInfo.new(0.3, Enum.EasingStyle.Linear), {
		Size = UDim2.fromOffset(math.floor((StatusWindow.LEFT_INNER - 6) * ratio), 10),
	})

	local stats = state.stats or {}
	local values = {
		["체력"] = tostring(state.maxHealth),
		["영력"] = string.format("%s / %s", Format.qi(state.qi), Format.qi(state.req)),
		["흡수"] = string.format("%s / 초", Format.rate(state.gain)),
		["영근"] = if state.root then (string.gsub(Roots.describe(state.root), "[(),]", "")) else "아직 모름",
		["종족"] = if state.race then Races.get(state.race).name else "-",
		["영석"] = string.format("%s개", Currency.format(state.stones or 0)),
		["천겁"] = string.format("%d회 넘음", stats.tribulations or 0),
		["영초"] = string.format("%d개", stats.herbs or 0),
		["비급"] = string.format("%d권", stats.manuals or 0),
	}
	for key, label in ui.stats do
		label:set(values[key] or "-")
	end
	ui.setRaceEffects(if state.race then Races.effects(state.race) else "")
	-- 다시 뽑으면 지금 종족은 나오지 않는다: 그만큼 나눠 보인다
	for id, entry in ui.oddsRows do
		local isMine = id == state.race
		entry.percent:set(if isMine then "지금 종족" else string.format("%.1f%%", Races.chance(id, state.race)))
		entry.name:setColor(if isMine then C.gold else C.cream)
	end

	for _, def in StatusWindow.TABS do
		local entry = tabs[def.key]
		local on = def.key == current
		entry.frame.Visible = on
		setImage(entry.button, if on then "pillJade" else "pillStone")
		entry.caption:setColor(if on then C.cream else C.dim)
		entry.tab.update(state)
	end
end

-- 갈래 이름: 열쇠(skills…), 글자(술법…), 또는 번호(1~4)
local function resolveTab(tab: string | number): string?
	local index = tonumber(tab)
	if index and StatusWindow.TABS[index] then
		return StatusWindow.TABS[index].key
	end
	for _, def in StatusWindow.TABS do
		if def.key == tab or def.label == tab then
			return def.key
		end
	end
	return nil
end

function StatusWindow.build(gui: ScreenGui, ctx: Kit.Context): ImageLabel
	local tabCtx = table.clone(ctx)
	tabCtx.refresh = draw

	local panel = image("panel", {
		Name = "StatusWindow",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(StatusWindow.W, StatusWindow.H),
		SliceScale = 0.8,
		Visible = false,
		Active = true,
		Parent = gui,
	})
	new("UIScale", { Parent = panel })
	ui.panel = panel
	-- 판 그림은 살짝 비친다. 창이 커서 뒤의 HUD(단축칸, 왼쪽 요약)가 비쳐 어지럽지 않게 같은 판을 한 겹 더 깐다
	image("panel", {
		Name = "Backing",
		Size = UDim2.fromScale(1, 1),
		SliceScale = 0.8,
		Parent = panel,
	})

	local titleRow = row({ Position = UDim2.fromOffset(0, 14), Size = UDim2.new(1, 0, 0, 48), Parent = panel })
	text("title", 36, { gradient = Ui.GOLD_TEXT, text = "상태창", parent = titleRow })
	image("divider", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 58),
		Size = UDim2.fromOffset(420, 20),
		Parent = panel,
	})
	local close = image("iconClose", {
		Name = "Close",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -24, 0, 22),
		Size = UDim2.fromOffset(32, 32),
		Parent = panel,
	}, "ImageButton")
	close.Activated:Connect(function()
		StatusWindow.setOpen(false)
	end)
	if ctx.keyboard then
		local closeHint = text("body", 14, { color = C.dim, text = "C, Esc 로 나간다", name = "CloseHint" })
		closeHint.frame.AnchorPoint = Vector2.new(1, 0)
		closeHint.frame.Position = UDim2.new(1, -64, 0, 28)
		closeHint.frame.Parent = panel
	end

	-- 인물 칸 ---------------------------------------------------------------------
	local left, _ = Kit.card(panel, {
		Name = "Character",
		Position = UDim2.fromOffset(SIDE, BODY_Y),
		Size = UDim2.fromOffset(LEFT_W, StatusWindow.H - BODY_Y - 28),
		BackgroundTransparency = 0.6,
	})
	local inner = StatusWindow.LEFT_INNER
	-- 이름은 아무 글자나 올 수 있어서 글자판 대신 Roblox 글꼴로 쓴다
	new("TextLabel", {
		Name = "PlayerName",
		Position = UDim2.fromOffset(14, 10),
		Size = UDim2.fromOffset(inner, 20),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamMedium,
		TextSize = 15,
		TextColor3 = C.dim,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextTruncate = Enum.TextTruncate.AtEnd,
		Text = player.DisplayName or "",
		Parent = left,
	})
	ui.realm = text("title", 30, { gradient = Ui.GOLD_TEXT, name = "Realm" })
	ui.realm.frame.Position = UDim2.fromOffset(10, 30)
	ui.realm.frame.Parent = left
	ui.realmSmall = text("title", 24, { gradient = Ui.GOLD_TEXT, name = "RealmSmall" })
	ui.realmSmall.frame.Position = UDim2.fromOffset(11, 35)
	ui.realmSmall.frame.Parent = left
	ui.tier = text("body", 15, { color = C.dim, name = "Tier" })
	ui.tier.frame.Position = UDim2.fromOffset(12, 68)
	ui.tier.frame.Parent = left
	local track = image("barTrack", {
		Position = UDim2.fromOffset(14, 94),
		Size = UDim2.fromOffset(inner, 16),
		SliceScale = 0.55,
		Parent = left,
	})
	ui.qiFill = image("barJade", {
		Position = UDim2.fromOffset(3, 3),
		Size = UDim2.fromOffset(0, 10),
		SliceScale = 0.5,
		Parent = track,
	})

	ui.stats = {}
	for index, key in STAT_KEYS do
		local y = STAT_Y + (index - 1) * STAT_GAP
		local name = text("body", 15, { color = C.dim, text = key })
		name.frame.Position = UDim2.fromOffset(11, y)
		name.frame.Parent = left
		local value = text("body", 16, { color = C.cream, name = "Value" })
		value.frame.AnchorPoint = Vector2.new(1, 0)
		value.frame.Position = UDim2.new(1, -10, 0, y - 1)
		value.frame.Parent = left
		new("Frame", {
			Position = UDim2.fromOffset(14, y + STAT_GAP - 3),
			Size = UDim2.fromOffset(inner, 1),
			BackgroundColor3 = C.gold,
			BackgroundTransparency = 0.86,
			BorderSizePixel = 0,
			Parent = left,
		})
		ui.stats[key] = value
	end
	-- 종족 효과와 다시 뽑기 (로벅스)
	local effects, setEffects = Ui.paragraph("body", 14, inner, 2, C.jade, left)
	effects.Name = "RaceEffects"
	effects.Position = UDim2.fromOffset(12, STAT_Y + #STAT_KEYS * STAT_GAP + 4)
	ui.setRaceEffects = setEffects
	local buttons = row({
		Name = "RaceButtons",
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 14, 1, -12),
		Size = UDim2.fromOffset(inner, 30),
		Parent = left,
	}, Enum.HorizontalAlignment.Left, 6)
	-- 유료 뽑기는 사기 전에 확률을 보여 준다 (Roblox 규칙)
	local odds = Ui.pill("확률 보기", 86, 30, 14, buttons, function()
		ui.oddsPanel.Visible = not ui.oddsPanel.Visible
		ui.shade.Visible = ui.oddsPanel.Visible
	end)
	odds.Name = "Odds"
	odds.LayoutOrder = 1
	setImage(odds, "pillStone")
	local reroll = Ui.pill(
		string.format("다시 뽑기 %d 로벅스", Races.REROLL_PRICE),
		inner - 92,
		30,
		14,
		buttons,
		function()
			if Races.REROLL_PRODUCT_ID == 0 then
				ctx.toast("종족 다시 뽑기는 아직 준비 중이다.", "info")
				return
			end
			MarketplaceService:PromptProductPurchase(player, Races.REROLL_PRODUCT_ID)
		end
	)
	reroll.Name = "Reroll"
	reroll.LayoutOrder = 2
	ui.reroll = reroll
	-- 유료 랜덤 아이템을 못 사는 곳의 사람에게는 다시 뽑기를 숨긴다
	task.spawn(function()
		local ok, info = pcall(function()
			return PolicyService:GetPolicyInfoForPlayerAsync(player)
		end)
		if ok and info and info.ArePaidRandomItemsRestricted then
			reroll.Visible = false
		end
	end)

	-- 갈래 -------------------------------------------------------------------------
	local tabRow = row({
		Name = "Tabs",
		Position = UDim2.fromOffset(CONTENT_X, BODY_Y),
		Size = UDim2.fromOffset(Kit.W, 36),
		Parent = panel,
	}, Enum.HorizontalAlignment.Left, 8)
	new("Frame", {
		Position = UDim2.fromOffset(CONTENT_X, BODY_Y + 41),
		Size = UDim2.fromOffset(Kit.W, 1),
		BackgroundColor3 = C.gold,
		BackgroundTransparency = 0.8,
		BorderSizePixel = 0,
		Parent = panel,
	})
	local builders = {
		skills = SkillsTab.buildActive,
		passives = SkillsTab.buildPassive,
		gear = BeopguTab.build,
		pouch = PouchTab.build,
	}
	for index, def in StatusWindow.TABS do
		local button, caption = Ui.pill(def.label, 116, 36, 17, tabRow, function()
			StatusWindow.setTab(def.key)
		end)
		button.Name = "Tab_" .. def.key
		button.LayoutOrder = index
		local frame = new("Frame", {
			Name = "Page_" .. def.key,
			Position = UDim2.fromOffset(CONTENT_X, CONTENT_Y),
			Size = UDim2.fromOffset(Kit.W + Kit.GUTTER, Kit.H),
			BackgroundTransparency = 1,
			Visible = false,
			Parent = panel,
		})
		tabs[def.key] = { button = button, caption = caption, frame = frame, tab = builders[def.key](frame, tabCtx) }
	end

	-- 확률 창 (다시 뽑기 전에): 갈래 자리를 덮고, 인물 칸의 다시 뽑기 단추는 보이게 둔다 -------------------
	local contentW = Kit.W + Kit.GUTTER
	local shade = new("TextButton", {
		Name = "OddsShade",
		Position = UDim2.fromOffset(CONTENT_X - 8, BODY_Y - 6),
		Size = UDim2.fromOffset(contentW + 16, StatusWindow.H - BODY_Y - 22),
		BackgroundColor3 = C.ink,
		BackgroundTransparency = 0.35,
		BorderSizePixel = 0,
		AutoButtonColor = false,
		Text = "",
		Visible = false,
		ZIndex = 5,
		Parent = panel,
	}, { new("UICorner", { CornerRadius = UDim.new(0, 10) }) })
	local oddsH = 136 + #Races.list * 40
	local oddsPanel = image("panel", {
		Name = "OddsPanel",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset(CONTENT_X + contentW / 2, StatusWindow.H / 2),
		Size = UDim2.fromOffset(440, oddsH),
		SliceScale = 0.7,
		Visible = false,
		Active = true,
		ZIndex = 6,
		Parent = panel,
	})
	image("panel", { Name = "Backing", Size = UDim2.fromScale(1, 1), SliceScale = 0.7, Parent = oddsPanel })
	local oddsTitle = row({ Position = UDim2.fromOffset(0, 14), Size = UDim2.new(1, 0, 0, 40), Parent = oddsPanel })
	text("title", 28, { gradient = Ui.GOLD_TEXT, text = "종족 확률", parent = oddsTitle })
	local oddsClose = image("iconClose", {
		Name = "OddsClose",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -18, 0, 16),
		Size = UDim2.fromOffset(28, 28),
		Parent = oddsPanel,
	}, "ImageButton")
	local intro = text("body", 14, {
		color = C.dim,
		text = "다시 뽑으면 지금 종족을 뺀 나머지에서 이 확률로 나온다.",
	})
	intro.frame.Position = UDim2.fromOffset(36, 58)
	intro.frame.Parent = oddsPanel
	ui.oddsRows = {}
	for index, race in Races.list do
		local y = 90 + (index - 1) * 40
		local name = text("body", 16, { color = C.cream, text = race.name })
		name.frame.Position = UDim2.fromOffset(40, y)
		name.frame.Parent = oddsPanel
		local percent = text("body", 16, { color = C.gold })
		percent.frame.AnchorPoint = Vector2.new(1, 0)
		percent.frame.Position = UDim2.new(1, -40, 0, y)
		percent.frame.Parent = oddsPanel
		local summary = text("body", 14, { color = C.dim, text = Races.effects(race.id) })
		summary.frame.Position = UDim2.fromOffset(40, y + 19)
		summary.frame.Parent = oddsPanel
		ui.oddsRows[race.id] = { name = name, percent = percent }
	end
	ui.oddsPanel = oddsPanel
	-- 확률 창과 그늘은 함께 열고 닫는다 (그늘을 눌러도 닫힌다)
	oddsPanel:GetPropertyChangedSignal("Visible"):Connect(function()
		shade.Visible = oddsPanel.Visible
	end)
	local function closeOdds()
		oddsPanel.Visible = false
		shade.Visible = false
	end
	oddsClose.Activated:Connect(closeOdds)
	shade.Activated:Connect(closeOdds)
	ui.shade = shade

	return panel
end

-- 화면에 맞춘 배율: Hud 배율을 넘지 않고, 화면(위쪽 막대 아래)에 창이 다 드는 만큼
function StatusWindow.fit(viewport: Vector2, hudScale: number)
	local scale = ui.panel and ui.panel:FindFirstChildOfClass("UIScale")
	if not scale then
		return
	end
	local inset = 58 -- Roblox 위쪽 막대 (알 수 없으면 가장 큰 값)
	pcall(function()
		inset = (game:GetService("GuiService"):GetGuiInset()).Y
	end)
	scale.Scale = math.min(hudScale, (viewport.X - 16) / StatusWindow.W, (viewport.Y - inset - 8) / StatusWindow.H)
end

function StatusWindow.update(state: { [string]: any })
	lastState = state
	draw()
end

function StatusWindow.isOpen(): boolean
	return ui.panel ~= nil and ui.panel.Visible
end

-- 열고 닫기 (open 이 nil 이면 뒤집는다). 닫으면 고르던 것과 확률 창을 접는다
-- 창이 열려 있는 동안 Roblox 도구 칸을 숨긴다 (휴대폰에서 창 아래쪽을 가린다)
local function showBackpack(visible: boolean)
	pcall(function()
		game:GetService("StarterGui"):SetCoreGuiEnabled(Enum.CoreGuiType.Backpack, visible)
	end)
end

function StatusWindow.setOpen(open: boolean?): boolean
	local panel = ui.panel
	if not panel then
		return false
	end
	local visible = if open == nil then not panel.Visible else open
	if panel.Visible ~= visible then
		showBackpack(not visible)
	end
	panel.Visible = visible
	if not visible then
		ui.oddsPanel.Visible = false
		ui.shade.Visible = false
		for _, entry in tabs do
			entry.tab.reset()
		end
	end
	draw()
	return visible
end

function StatusWindow.setTab(tab: string | number)
	local key = resolveTab(tab)
	if not key then
		return
	end
	if key ~= current then
		for _, entry in tabs do
			entry.tab.reset()
		end
	end
	current = key
	draw()
end

function StatusWindow.currentTab(): string
	return current
end

-- 술법 갈래로 바꾸고 그 단축칸을 고른다 (화면 아래 빈 단축칸을 눌렀을 때)
function StatusWindow.pickSlot(slot: number)
	StatusWindow.setTab("skills")
	tabs.skills.tab.pickSlot(slot)
	draw()
end

-- 열려 있을 때 프레임마다: 단축칸 쿨타임, 손에 든 법구
function StatusWindow.tick()
	if not StatusWindow.isOpen() then
		return
	end
	local entry = tabs[current]
	if entry and entry.tab.tick then
		entry.tab.tick()
	end
end

return StatusWindow
