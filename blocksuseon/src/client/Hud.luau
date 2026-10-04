-- 화면 UI. 선협풍: 칠기 현판과 금테, 옥 버튼, 붓글씨·명조 글자.
-- 그림은 art/assets.html 에서 그려 올린 것(Art), 글자는 BitmapText 로 찍는다.
-- 알림은 화면 위 가운데에 칠기 띠로 띄운다(Notice).

local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")
local MarketplaceService = game:GetService("MarketplaceService")
local PolicyService = game:GetService("PolicyService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Skills = require(Shared.Skills)
local Progression = require(Shared.Progression)
local Format = require(Shared.Format)
local Roots = require(Shared.Roots)
local Clock = require(Shared.Clock)
local Tasks = require(Shared.Tasks)
local Places = require(Shared.Places)
local Races = require(Shared.Races)
local Currency = require(Shared.Currency)
local Combat = require(Shared.Combat)
local Guards = require(Shared.Guards)
local Ui = require(script.Parent.Ui)
local Notice = require(script.Parent.Notice)
local PlaceBanner = require(script.Parent.PlaceBanner)
local TravelMenu = require(script.Parent.TravelMenu)
local CombatHud = require(script.Parent.CombatHud)
local Choice = require(script.Parent.Choice)
local Naegwan = require(script.Parent.Naegwan)
local ShopWindow = require(script.Parent.ShopWindow)

export type Actions = {
	meditate: () -> (),
	breakthrough: () -> (),
	useSlot: (slot: number) -> (),
	equip: (id: string, on: boolean) -> (),
	assign: (slot: number, id: string) -> (),
	startTask: (id: string) -> (),
	skipTask: (id: string) -> (),
	choose: (key: string, value: any) -> (),
	eat: (item: string) -> (),
	trialResult: (payload: { [string]: any }) -> (),
	trialCancel: () -> (),
	travel: (id: string) -> (),
	buy: (wareId: string) -> (),
	upgrade: (index: number) -> (),
	craft: (kind: string, grade: number) -> (),
	equipGuard: (kind: string) -> (), -- "" 은 내려놓기
}

local IMG = Ui.IMG
local C = Ui.C
local GOLD_TEXT = Ui.GOLD_TEXT
local RED_TEXT = Ui.RED_TEXT

local Hud = {}

local player = Players.LocalPlayer
local keyboard = UserInputService.KeyboardEnabled
local touchOnly = UserInputService.TouchEnabled and not keyboard
local actions: Actions
local scales: { UIScale } = {}
local ui: { [string]: any } = {}
local orbs: { [string]: { [string]: any } } = {}
local skillRows: { [string]: { [string]: any } } = {}
local hotbar: { { [string]: any } } = {}
local keyPills: { { [string]: any } } = {}
local bindingSlot: number? = nil
local passiveSlots: { { [string]: any } } = {}
local cooldownEnd: { [string]: number } = {}
local cooldownTotal: { [string]: number } = {}
local pulses: { [Instance]: Tween } = {}
local cinematicToken = 0
local lastState: { [string]: any }? = nil
local taskLines: { { [string]: any } } = {}
local pouchRows: { [string]: { [string]: any } } = {}
local weaponRows: { { [string]: any } } = {}
local guardRows: { [string]: { [string]: any } } = {}
local announcedTasks: { [string]: boolean } = {}
local autoOpened: { [string]: boolean } = {}
local skipArmed: { [string]: number } = {}
local lastStones: number? = nil
local stonePulse = 0
local MAX_TASK_LINES = 4

-- 도우미 ---------------------------------------------------------------------------

local new, image, setImage, text, row, tween = Ui.new, Ui.image, Ui.setImage, Ui.text, Ui.row, Ui.tween

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

-- 왼쪽 요약: 경지 현판, 영력, 장착한 공법
local function buildStatus(gui: ScreenGui)
	local status = scaled(new("Frame", {
		Name = "Status",
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.new(0, 14, 0.5, 10),
		Size = UDim2.fromOffset(350, 380),
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

	ui.passiveLabel = text("body", 15, { color = C.dim, text = "공법" })
	ui.passiveLabel.frame.Position = UDim2.fromOffset(20, 152)
	ui.passiveLabel.frame.Parent = status
	for index = 1, #Skills.SLOT_REALMS do
		local slot = image("slot", {
			Position = UDim2.fromOffset(66 + (index - 1) * 38, 148),
			Size = UDim2.fromOffset(32, 32),
			Parent = status,
		})
		local icon = image("skillBreath", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.74, 0.74),
			Visible = false,
			Parent = slot,
		})
		passiveSlots[index] = { slot = slot, icon = icon }
	end

	-- 영석: 늘 보이는 지닌 돈 (공법 칸 오른쪽). 누르면 어디서 얻고 어디에 쓰는지 알려 준다
	local stoneButton = new("TextButton", {
		Name = "Stones",
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.fromOffset(322, 150),
		Size = UDim2.fromOffset(140, 28),
		BackgroundTransparency = 1,
		Text = "",
		Parent = status,
	})
	local stoneRow = row({
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.fromScale(1, 0.5),
		Size = UDim2.fromScale(1, 1),
		Parent = stoneButton,
	}, Enum.HorizontalAlignment.Right, 6)
	stoneRow:FindFirstChildOfClass("UIListLayout").VerticalAlignment = Enum.VerticalAlignment.Center
	ui.stoneScale = new("UIScale", { Parent = stoneRow })
	image("gem", { LayoutOrder = 1, Size = UDim2.fromOffset(20, 20), Parent = stoneRow })
	ui.stoneText = text("body", 18, { color = C.gold, name = "StoneText", parent = stoneRow })
	ui.stoneText.frame.LayoutOrder = 2
	stoneButton.Activated:Connect(function()
		Hud.toast(
			"영석은 위험한 땅의 영석 광맥에서 캔다. 만물상, 대장간, 전송진 삯에 쓴다.",
			"info"
		)
	end)

	-- 낮밤
	ui.clockText = text("body", 15, { color = C.dim })
	ui.clockText.frame.Position = UDim2.fromOffset(20, 188)
	ui.clockText.frame.Parent = status

	-- 과업
	for index = 1, MAX_TASK_LINES do
		local y = 216 + (index - 1) * 32
		local line = new("Frame", {
			Position = UDim2.fromOffset(18, y),
			Size = UDim2.fromOffset(330, 30),
			BackgroundTransparency = 1,
			Visible = false,
			Parent = status,
		})
		local bullet = image("gem", {
			Position = UDim2.fromOffset(0, 8),
			Size = UDim2.fromOffset(14, 14),
			Parent = line,
		})
		local labelRow = row({
			Position = UDim2.fromOffset(20, 0),
			Size = UDim2.fromOffset(200, 28),
			Parent = line,
		}, Enum.HorizontalAlignment.Left, 8)
		local label = text("title", 18, { color = C.cream, parent = labelRow })
		label.frame.LayoutOrder = 1
		local progress = text("body", 13, { color = C.dim, parent = labelRow })
		progress.frame.LayoutOrder = 2
		-- 줄을 누르면 할 일을 화면 알림으로 다시 알려 준다
		local hintButton = new("TextButton", {
			Size = UDim2.new(1, -130, 1, 0),
			BackgroundTransparency = 1,
			Text = "",
			Parent = line,
		})
		local entry = { line = line, bullet = bullet, label = label, progress = progress }
		hintButton.Activated:Connect(function()
			if entry.hint then
				Hud.toast(string.format("%s: %s", entry.labelText or "", entry.hint), "info")
			end
		end)
		local main, mainText = Ui.pill("내관", 60, 26, 13, line, function()
			if entry.onMain then
				entry.onMain()
			end
		end)
		main.AnchorPoint = Vector2.new(1, 0)
		main.Position = UDim2.new(1, -66, 0, 2)
		local alt, altText = Ui.pill("건너뛰기", 62, 26, 12, line, function()
			if entry.onAlt then
				entry.onAlt()
			end
		end)
		alt.AnchorPoint = Vector2.new(1, 0)
		alt.Position = UDim2.new(1, 0, 0, 2)
		setImage(alt, "pillStone")
		entry.main, entry.mainText, entry.alt, entry.altText = main, mainText, alt, altText
		taskLines[index] = entry
	end

	-- 주머니
	ui.pouchText = text("body", 15, { color = C.cream })
	ui.pouchText.frame.Position = UDim2.fromOffset(20, 350)
	ui.pouchText.frame.Parent = status
	local eatButton, eatText = Ui.pill("영초 먹기", 84, 26, 13, status, function()
		actions.eat("herb")
	end)
	eatButton.AnchorPoint = Vector2.new(1, 0)
	eatButton.Position = UDim2.fromOffset(348, 348)
	ui.eatButton, ui.eatText = eatButton, eatText
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

-- 오른쪽 아래: 운기조식(큰 버튼), 돌파, 상태창
local function buildActions(gui: ScreenGui)
	local cluster = scaled(new("Frame", {
		Name = "Actions",
		AnchorPoint = Vector2.new(1, 1),
		Position = if touchOnly then UDim2.new(1, -16, 1, -190) else UDim2.new(1, -20, 1, -10),
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
	orb(cluster, "status", 64, "iconStatus", "C", function()
		Hud.toggleStatus()
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

-- 아래 가운데: 술법 단축칸 (기본 Q·E·Z·X, 상태창에서 바꾼다).
-- 맨 아래에는 Roblox 도구 칸(공격 법구, 숫자 키 1~9)이 있으므로 그 위에 둔다
local function buildHotbar(gui: ScreenGui)
	local bar = scaled(new("Frame", {
		Name = "Hotbar",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -84),
		Size = UDim2.fromOffset(Progression.HOTBAR_SIZE * 76, 92),
		BackgroundTransparency = 1,
		Parent = gui,
	}, {
		new("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			SortOrder = Enum.SortOrder.LayoutOrder,
			Padding = UDim.new(0, 10),
		}),
	}))

	for slot = 1, Progression.HOTBAR_SIZE do
		local holder = new("Frame", {
			LayoutOrder = slot,
			Size = UDim2.fromOffset(66, 92),
			BackgroundTransparency = 1,
			Parent = bar,
		})
		local button = image("slot", { Size = UDim2.fromOffset(66, 66), Parent = holder }, "ImageButton")
		local press = new("UIScale", { Parent = button })
		local icon = image("skillDash", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.74, 0.74),
			Visible = false,
			Parent = button,
		})
		-- 쿨타임: 아래에서부터 줄어드는 그늘과 남은 초
		local shade = new("Frame", {
			AnchorPoint = Vector2.new(0, 1),
			Position = UDim2.new(0, 5, 1, -5),
			Size = UDim2.new(1, -10, 0, 0),
			BackgroundColor3 = Color3.new(0, 0, 0),
			BackgroundTransparency = 0.4,
			BorderSizePixel = 0,
			Parent = button,
		}, { new("UICorner", { CornerRadius = UDim.new(0, 9) }) })
		local timeRow = row({ Size = UDim2.new(1, 0, 1, -8), Parent = button })
		local timeText = text("body", 22, { color = C.cream, parent = timeRow })
		local keyText = nil
		if keyboard then
			local badge = new("Frame", {
				Position = UDim2.fromOffset(3, 3),
				Size = UDim2.fromOffset(18, 18),
				BackgroundColor3 = C.keyBack,
				Parent = button,
			}, { new("UICorner", { CornerRadius = UDim.new(0, 5) }) })
			local keyRow = row({ Size = UDim2.fromScale(1, 1), Parent = badge })
			keyText = text("body", 12, { color = C.keyText, parent = keyRow })
		end
		local labelRow = row({
			Position = UDim2.fromOffset(-30, 66),
			Size = UDim2.new(1, 60, 0, 24),
			Parent = holder,
		})
		local label = text("title", 17, { color = C.dim, text = "빈 칸", parent = labelRow })

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
			local id = lastState and lastState.hotbar[slot]
			if id and id ~= "" then
				actions.useSlot(slot)
			else
				-- 빈 칸을 누르면 술법을 넣을 수 있는 상태창을 연다
				Hud.toggleStatus(true)
			end
		end)
		hotbar[slot] = { icon = icon, shade = shade, timeText = timeText, keyText = keyText, label = label }
	end
end

-- 가운데: 상태창 (C)
local STAT_KEYS = { "체력", "영력", "흡수", "영근", "종족", "영석", "천겁", "영초", "비급" }
local STAT_GAP = 30

local function buildStatusWindow(gui: ScreenGui)
	local panel = scaled(image("panel", {
		Name = "StatusWindow",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(700, 560),
		SliceScale = 0.8,
		Visible = false,
		Active = true,
		Parent = gui,
	}))
	ui.panel = panel

	local titleRow = row({ Position = UDim2.fromOffset(0, 22), Size = UDim2.new(1, 0, 0, 56), Parent = panel })
	text("title", 40, { gradient = GOLD_TEXT, text = "상태창", parent = titleRow })
	image("divider", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 80),
		Size = UDim2.fromOffset(600, 25),
		Parent = panel,
	})
	local close = image("iconClose", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -24, 0, 24),
		Size = UDim2.fromOffset(34, 34),
		Parent = panel,
	}, "ImageButton")
	close.Activated:Connect(function()
		Hud.toggleStatus(false)
	end)

	-- 왼쪽: 이름, 경지, 능력치
	local left = new("Frame", {
		Position = UDim2.fromOffset(44, 118),
		Size = UDim2.fromOffset(250, 410),
		BackgroundTransparency = 1,
		Parent = panel,
	})
	-- 이름은 아무 글자나 올 수 있어서 글자판 대신 Roblox 글꼴로 쓴다
	new("TextLabel", {
		Size = UDim2.new(1, 0, 0, 22),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamMedium,
		TextSize = 16,
		TextColor3 = C.dim,
		TextXAlignment = Enum.TextXAlignment.Left,
		Text = player.DisplayName,
		Parent = left,
	})
	ui.swRealm = text("title", 32, { gradient = GOLD_TEXT })
	ui.swRealm.frame.Position = UDim2.fromOffset(-6, 24)
	ui.swRealm.frame.Parent = left
	ui.swTier = text("body", 15, { color = C.dim })
	ui.swTier.frame.Position = UDim2.fromOffset(-4, 68)
	ui.swTier.frame.Parent = left

	ui.swStats = {}
	for index, key in STAT_KEYS do
		local y = 106 + (index - 1) * STAT_GAP
		local name = text("body", 16, { color = C.dim, text = key })
		name.frame.Position = UDim2.fromOffset(-4, y)
		name.frame.Parent = left
		local value = text("body", 16, { color = C.cream })
		value.frame.AnchorPoint = Vector2.new(1, 0)
		value.frame.Position = UDim2.new(1, 4, 0, y)
		value.frame.Parent = left
		new("Frame", {
			Position = UDim2.fromOffset(0, y + STAT_GAP - 3),
			Size = UDim2.new(1, 0, 0, 1),
			BackgroundColor3 = C.gold,
			BackgroundTransparency = 0.85,
			BorderSizePixel = 0,
			Parent = left,
		})
		ui.swStats[key] = value
	end
	-- 종족 효과와 다시 뽑기 (로벅스)
	local effects, setEffects = Ui.paragraph("body", 13, 250, 2, C.jade, left)
	effects.Position = UDim2.fromOffset(-2, 106 + #STAT_KEYS * STAT_GAP)
	ui.setRaceEffects = setEffects
	local reroll = Ui.pill(
		string.format("다시 뽑기 %d 로벅스", Races.REROLL_PRICE),
		132,
		26,
		13,
		left,
		function()
			if Races.REROLL_PRODUCT_ID == 0 then
				Hud.toast("종족 다시 뽑기는 아직 준비 중이다.", "info")
				return
			end
			MarketplaceService:PromptProductPurchase(player, Races.REROLL_PRODUCT_ID)
		end
	)
	reroll.AnchorPoint = Vector2.new(1, 0)
	reroll.Position = UDim2.new(1, 4, 0, -2)
	-- 유료 뽑기는 사기 전에 확률을 보여 준다 (Roblox 규칙)
	local odds = Ui.pill("확률 보기", 78, 26, 13, left, function()
		ui.oddsPanel.Visible = not ui.oddsPanel.Visible
	end)
	odds.AnchorPoint = Vector2.new(1, 0)
	odds.Position = UDim2.new(1, -134, 0, -2)
	-- 유료 랜덤 아이템을 못 사는 곳의 사람에게는 다시 뽑기를 숨긴다
	task.spawn(function()
		local ok, info = pcall(function()
			return PolicyService:GetPolicyInfoForPlayerAsync(player)
		end)
		if ok and info and info.ArePaidRandomItemsRestricted then
			reroll.Visible = false
		end
	end)

	-- 확률 창
	local oddsPanel = image("panel", {
		Name = "Odds",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(420, 460),
		SliceScale = 0.7,
		Visible = false,
		ZIndex = 6,
		Parent = panel,
	})
	local oddsTitle = row({ Position = UDim2.fromOffset(0, 18), Size = UDim2.new(1, 0, 0, 40), Parent = oddsPanel })
	text("title", 28, { gradient = GOLD_TEXT, text = "종족 확률", parent = oddsTitle })
	local oddsClose = image("iconClose", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -18, 0, 18),
		Size = UDim2.fromOffset(28, 28),
		Parent = oddsPanel,
	}, "ImageButton")
	oddsClose.Activated:Connect(function()
		oddsPanel.Visible = false
	end)
	ui.oddsIntro = text("body", 13, { color = C.dim })
	ui.oddsIntro.frame.Position = UDim2.fromOffset(34, 64)
	ui.oddsIntro.frame.Parent = oddsPanel
	ui.oddsRows = {}
	for index, race in Races.list do
		local y = 90 + (index - 1) * 44
		local name = text("body", 16, { color = C.cream, text = race.name })
		name.frame.Position = UDim2.fromOffset(34, y)
		name.frame.Parent = oddsPanel
		local percent = text("body", 16, { color = C.gold })
		percent.frame.AnchorPoint = Vector2.new(1, 0)
		percent.frame.Position = UDim2.new(1, -34, 0, y)
		percent.frame.Parent = oddsPanel
		local summary = text("body", 12, { color = C.dim, text = Races.effects(race.id) })
		summary.frame.Position = UDim2.fromOffset(34, y + 21)
		summary.frame.Parent = oddsPanel
		ui.oddsRows[race.id] = { name = name, percent = percent }
	end
	ui.oddsPanel = oddsPanel

	new("Frame", {
		Position = UDim2.fromOffset(318, 116),
		Size = UDim2.fromOffset(1, 410),
		BackgroundColor3 = C.gold,
		BackgroundTransparency = 0.75,
		BorderSizePixel = 0,
		Parent = panel,
	})

	-- 오른쪽: 술법·공법 목록
	local list = new("ScrollingFrame", {
		Position = UDim2.fromOffset(338, 112),
		Size = UDim2.fromOffset(330, 420),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 4,
		ScrollBarImageColor3 = C.gold,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = panel,
	}, { new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder }) })

	local order = 0
	local function header(title: string)
		order += 1
		local holder = new("Frame", {
			LayoutOrder = order,
			Size = UDim2.new(1, -8, 0, 42),
			BackgroundTransparency = 1,
			Parent = list,
		})
		local r = row({ Size = UDim2.fromScale(1, 1), Parent = holder }, Enum.HorizontalAlignment.Left, 10)
		local t = text("title", 26, { gradient = GOLD_TEXT, text = title, parent = r })
		t.frame.LayoutOrder = 1
		local extra = text("body", 15, { color = C.dim, parent = r })
		extra.frame.LayoutOrder = 2
		return extra
	end

	local function skillRow(def)
		order += 1
		local item = new("Frame", {
			LayoutOrder = order,
			Size = UDim2.new(1, -8, 0, 66),
			BackgroundTransparency = 1,
			Parent = list,
		})
		local frame =
			image("slot", { Position = UDim2.fromOffset(0, 6), Size = UDim2.fromOffset(50, 50), Parent = item })
		local icon = image(def.icon, {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(0.72, 0.72),
			Parent = frame,
		})
		local name = text("title", 21, { color = C.cream, text = def.name })
		name.frame.Position = UDim2.fromOffset(58, 2)
		name.frame.Parent = item
		local summary = text("body", 13, { color = C.dim })
		summary.frame.Position = UDim2.fromOffset(58, 34)
		summary.frame.Parent = item

		local entry = { icon = icon, name = name, summary = summary }
		if def.kind == "passive" then
			local button = image("pillJade", {
				AnchorPoint = Vector2.new(1, 0),
				Position = UDim2.new(1, 0, 0, 4),
				Size = UDim2.fromOffset(64, 30),
				SliceScale = 0.55,
				Parent = item,
			}, "ImageButton")
			local buttonRow = row({ Size = UDim2.new(1, 0, 1, -2), Parent = button })
			entry.button = button
			entry.buttonText = text("body", 14, { color = C.cream, parent = buttonRow })
			button.Activated:Connect(function()
				local equipped = lastState ~= nil and table.find(lastState.equipped, def.id) ~= nil
				actions.equip(def.id, not equipped)
			end)
		else
			-- 단축칸마다 작은 버튼: 누르면 그 칸에 넣는다 (이미 그 칸이면 뺀다)
			local slotRow = row({
				AnchorPoint = Vector2.new(1, 0),
				Position = UDim2.new(1, 0, 0, 6),
				Size = UDim2.fromOffset(Progression.HOTBAR_SIZE * 31, 26),
				Parent = item,
			}, Enum.HorizontalAlignment.Right, 3)
			entry.slotButtons = {}
			for slot = 1, Progression.HOTBAR_SIZE do
				local pill = image("pillStone", {
					LayoutOrder = slot,
					Size = UDim2.fromOffset(28, 24),
					SliceScale = 0.4,
					Parent = slotRow,
				}, "ImageButton")
				local pillRow = row({ Size = UDim2.new(1, 0, 1, -2), Parent = pill })
				local pillText = text("body", 13, { color = C.cream, parent = pillRow })
				pill.Activated:Connect(function()
					local current = lastState and lastState.hotbar[slot]
					actions.assign(slot, if current == def.id then "" else def.id)
				end)
				entry.slotButtons[slot] = { pill = pill, text = pillText }
			end
			entry.slotRow = slotRow
		end
		skillRows[def.id] = entry
	end

	ui.keyHint = header("단축키")
	order += 1
	local keyLine = new("Frame", {
		LayoutOrder = order,
		Size = UDim2.new(1, -8, 0, 44),
		BackgroundTransparency = 1,
		Parent = list,
	})
	local keyRow = row({ Size = UDim2.fromScale(1, 1), Parent = keyLine }, Enum.HorizontalAlignment.Left, 8)
	for slot = 1, Progression.HOTBAR_SIZE do
		local pill = image("pillJade", {
			LayoutOrder = slot,
			Size = UDim2.fromOffset(58, 36),
			SliceScale = 0.55,
			Parent = keyRow,
		}, "ImageButton")
		local pillRow = row({ Size = UDim2.new(1, 0, 1, -2), Parent = pill })
		local pillText = text("body", 17, { color = C.cream, parent = pillRow })
		pill.Activated:Connect(function()
			Hud.startBinding(slot)
		end)
		keyPills[slot] = { pill = pill, text = pillText }
	end

	header("술법")
	for _, def in Skills.actives do
		skillRow(def)
	end
	ui.swSlots = header("공법")
	for _, def in Skills.passives do
		skillRow(def)
	end

	-- 법구: 공격 법구(숫자 키 도구 칸)와 방어 법구(하나만 지닌다, 겉모습 없이 효과만)
	local function note(name: string, message: string, lines: number)
		order += 1
		local holder = new("Frame", {
			Name = name,
			LayoutOrder = order,
			Size = UDim2.new(1, -8, 0, lines * 21 + 6),
			BackgroundTransparency = 1,
			Parent = list,
		})
		local paragraph, set = Ui.paragraph("body", 13, 314, lines, C.dim, holder)
		paragraph.Position = UDim2.fromOffset(2, 2)
		set(message)
		return holder
	end

	-- 공격 법구는 Roblox 도구 칸에 들어간다 (키보드는 숫자 키, 터치는 아래 칸을 누른다)
	header("공격 법구"):set(if keyboard then "숫자 키로 든다" else "아래 도구 칸에서 든다")
	for index = 1, Combat.MAX_WEAPONS do
		order += 1
		local item = new("Frame", {
			Name = "Weapon" .. index,
			LayoutOrder = order,
			Size = UDim2.new(1, -8, 0, 58),
			BackgroundTransparency = 1,
			Visible = false,
			Parent = list,
		})
		local name = text("title", 21, { color = C.cream, name = "Name" })
		name.frame.Position = UDim2.fromOffset(4, 2)
		name.frame.Parent = item
		local summary = text("body", 13, { color = C.dim, name = "Sub" })
		summary.frame.Position = UDim2.fromOffset(6, 33)
		summary.frame.Parent = item
		-- 드는 키 (도구 칸 번호)
		local badge = new("Frame", {
			Name = "Key",
			AnchorPoint = Vector2.new(1, 0),
			Position = UDim2.new(1, -4, 0, 8),
			Size = UDim2.fromOffset(24, 24),
			BackgroundColor3 = C.keyBack,
			Parent = item,
		}, { new("UICorner", { CornerRadius = UDim.new(0, 6) }) })
		local badgeRow = row({ Size = UDim2.fromScale(1, 1), Parent = badge })
		text("body", 14, { color = C.keyText, text = tostring(index), parent = badgeRow })
		weaponRows[index] = { frame = item, name = name, summary = summary }
	end
	ui.weaponEmpty = note("WeaponEmpty", "지닌 공격 법구가 없다. 만물상에서 산다.", 1)

	ui.guardCount = header("방어 법구")
	note("GuardRule", "방어 법구는 부위와 상관없이 하나만 지닐 수 있다.", 1)
	for _, id in Guards.ORDER do
		order += 1
		local item = new("Frame", {
			Name = "Guard_" .. id,
			LayoutOrder = order,
			Size = UDim2.new(1, -8, 0, 62),
			BackgroundTransparency = 1,
			Visible = false,
			Parent = list,
		})
		local nameRow = row({
			Position = UDim2.fromOffset(4, 2),
			Size = UDim2.new(1, -96, 0, 30),
			Parent = item,
		}, Enum.HorizontalAlignment.Left, 8)
		local name = text("title", 21, { color = C.cream, name = "Name", parent = nameRow })
		name.frame.LayoutOrder = 1
		local worn = text("body", 14, { color = C.jade, text = "지님", name = "Worn", parent = nameRow })
		worn.frame.LayoutOrder = 2
		local effects = text("body", 13, { color = C.dim, name = "Sub" })
		effects.frame.Position = UDim2.fromOffset(6, 34)
		effects.frame.Parent = item
		-- 지닌 것은 내려놓기, 나머지는 지니기 (서버가 하나만 남긴다)
		local button, caption = Ui.pill("지니기", 80, 30, 14, item, function()
			local wearing = lastState ~= nil and lastState.guard == id
			actions.equipGuard(if wearing then "" else id)
		end)
		button.Name = "Button"
		button.AnchorPoint = Vector2.new(1, 0)
		button.Position = UDim2.new(1, 0, 0, 4)
		guardRows[id] = { frame = item, name = name, worn = worn, effects = effects, button = button, text = caption }
	end
	ui.guardEmpty = note(
		"GuardEmpty",
		"아직 방어 법구가 없다. 요수를 쓰러뜨리거나, 대장간에서 만들거나, 만물상에서 산다.",
		2
	)

	header("주머니")
	for _, id in Balance.ITEM_ORDER do
		order += 1
		local item = new("Frame", {
			LayoutOrder = order,
			Size = UDim2.new(1, -8, 0, 40),
			BackgroundTransparency = 1,
			Parent = list,
		})
		local name = text("title", 20, { color = C.cream, text = Balance.ITEMS[id].name })
		name.frame.Position = UDim2.fromOffset(4, 4)
		name.frame.Parent = item
		local count = text("body", 15, { color = C.dim })
		count.frame.Position = UDim2.fromOffset(130, 10)
		count.frame.Parent = item
		local button = nil
		if id ~= "pill" then
			button = Ui.pill("먹기", 64, 30, 14, item, function()
				actions.eat(id)
			end)
			button.AnchorPoint = Vector2.new(1, 0)
			button.Position = UDim2.new(1, 0, 0, 4)
		end
		pouchRows[id] = { frame = item, count = count, button = button }
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
	-- CanvasGroup 은 기기에 따라 그룹 투명도가 무시돼 연출이 안 사라질 수 있어서 쓰지 않는다.
	-- 대신 fade 값 하나를 트윈하고, 바뀔 때마다 붓질·글자 투명도에 그대로 옮긴다.
	local stage = new("Frame", {
		Name = "Stage",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.44),
		Size = UDim2.fromOffset(1000, 300),
		BackgroundTransparency = 1,
		Visible = false,
		Parent = gui,
	})
	ui.cineStage = stage
	ui.cineScale = new("UIScale", { Parent = stage })
	ui.cineSwash = image("swash", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(920, 230),
		ImageTransparency = 1,
		Parent = stage,
	})
	local titleRow = row({ Position = UDim2.fromOffset(0, 74), Size = UDim2.new(1, 0, 0, 100), Parent = stage })
	ui.cineTitle = text("title", 68, { gradient = GOLD_TEXT, parent = titleRow })
	local subRow = row({ Position = UDim2.fromOffset(0, 172), Size = UDim2.new(1, 0, 0, 34), Parent = stage })
	ui.cineSub = text("body", 20, { color = C.cream, parent = subRow })

	local fade = new("NumberValue", { Value = 1 })
	fade.Changed:Connect(function(value: number)
		ui.cineSwash.ImageTransparency = value
		ui.cineTitle:setTransparency(value)
		ui.cineSub:setTransparency(value)
		stage.Visible = value < 0.995
	end)
	ui.cineFade = fade
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
	buildHotbar(gui)
	buildStatusWindow(gui)
	local notices = Notice.build(gui)
	table.insert(scales, notices:FindFirstChildOfClass("UIScale"))
	Choice.build(gui, function(key, value)
		actions.choose(key, value)
	end)
	Naegwan.build(gui, function(payload)
		actions.trialResult(payload)
	end, function()
		actions.trialCancel()
	end)
	TravelMenu.build(gui, function(id)
		actions.travel(id)
	end)
	ShopWindow.build(gui, {
		buy = function(wareId)
			actions.buy(wareId)
		end,
		upgrade = function(index)
			actions.upgrade(index)
		end,
		craft = function(kind, grade)
			actions.craft(kind, grade)
		end,
	})
	local banner = PlaceBanner.build(gui)
	local combat = CombatHud.build(gui)
	table.insert(scales, combat:FindFirstChildOfClass("UIScale"))
	table.insert(scales, (gui:FindFirstChild("MyHealth") :: any):FindFirstChildOfClass("UIScale"))
	table.insert(scales, (gui:FindFirstChild("Choice") :: any):FindFirstChildOfClass("UIScale"))
	table.insert(scales, (gui:FindFirstChild("Naegwan") :: any):FindFirstChildOfClass("UIScale"))
	table.insert(scales, (gui:FindFirstChild("TravelMenu") :: any):FindFirstChildOfClass("UIScale"))
	table.insert(scales, (gui:FindFirstChild("ShopWindow") :: any):FindFirstChildOfClass("UIScale"))
	table.insert(scales, banner:FindFirstChildOfClass("UIScale"))
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

-- 지금 있는 곳, 영맥, 취령진을 한 줄에
local currentPlace: Places.Region? = nil
local function refreshPlaceLine(state)
	local places = {}
	if currentPlace then
		table.insert(places, currentPlace.name)
	end
	if state.veinId then
		local vein = Balance.VEINS[state.veinId]
		table.insert(places, string.format("%s 위 (흡수 ×%s)", vein.name, tostring(vein.mult)))
	end
	if state.inFormation then
		table.insert(places, string.format("취령진 안 (×%d)", Skills.EFFECT.formationMult))
	end
	ui.veinText:set(table.concat(places, ", "))
	ui.veinText:setColor(if state.veinId or state.inFormation then C.jade else C.dim)
end

-- 땅이 바뀌면 그 땅 이름을 화면에 띄운다 (맵에는 이름표를 띄우지 않는다).
-- 경계를 따라 걸을 때 깜박이지 않게 새 땅에 1초 넘게 있어야 바뀐 것으로 치고, 같은 땅 이름은 1분 안에 다시 띄우지 않는다.
-- 경지 연출이 화면을 덮는 동안에는 기다렸다가 걷힌 뒤에 띄운다
local cinematicUntil = 0
local candidate: Places.Region? = nil
local candidateSince = 0
local bannerShown: { [string]: number } = {}
local function refreshPlace()
	if os.clock() < cinematicUntil then
		return
	end
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") then
		return
	end
	local region = Places.regionAt(root.Position.X, root.Position.Z, root.Position.Y)
	if region == currentPlace then
		candidate = nil
		return
	end
	local now = os.clock()
	if region ~= candidate then
		candidate, candidateSince = region, now
		-- 처음 들어올 때(아직 아무 땅도 아닐 때)는 바로 정한다
		if currentPlace ~= nil then
			return
		end
	elseif now - candidateSince < 1 then
		return
	end
	candidate = nil
	currentPlace = region
	if now - (bannerShown[region.id] or -math.huge) > 60 then
		bannerShown[region.id] = now
		PlaceBanner.show(region.name, region.sub)
	end
	if lastState then
		refreshPlaceLine(lastState)
	end
end

local function updateStatus(state)
	local step = Realms.get(state.step)
	ui.realmName:set(step.realm.name)
	ui.realmSub:set(step.sub)
	ui.realmSub.frame.Visible = step.sub ~= ""

	local ratio = if state.req > 0 then math.clamp(state.qi / state.req, 0, 1) else 1
	local atMax = state.step >= Realms.maxStep
	local full = ratio >= 1
	setImage(ui.qiFill, if full and (state.ready or atMax) then "barGold" else "barJade")
	ui.qiFill.Visible = ratio > 0.04
	tween(ui.qiFill, TweenInfo.new(0.45, Enum.EasingStyle.Linear), { Size = UDim2.fromOffset(286 * ratio, 12) })

	if atMax and full then
		ui.qiText:set("경지의 끝")
		ui.qiText:setColor(C.gold)
		ui.rateText:set("")
	elseif full then
		ui.qiText:set("영력이 가득 찼다")
		ui.qiText:setColor(C.gold)
		if state.ready then
			local title = if state.entry and state.entry.title then state.entry.title else "돌파"
			ui.rateText:set(string.format("B 로 %s", title))
			ui.rateText:setColor(C.gold)
		elseif not state.tasksDone then
			ui.rateText:set("과업이 남았다")
			ui.rateText:setColor(C.red)
		else
			ui.rateText:set("")
		end
	else
		ui.qiText:set(string.format("영력 %s / %s", Format.qi(state.qi), Format.qi(state.req)))
		ui.qiText:setColor(C.cream)
		ui.rateText:set(if state.meditating then string.format("+%s / 초", Format.rate(state.gain)) else "")
		ui.rateText:setColor(C.jade)
	end

	refreshPlaceLine(state)

	for index, slot in passiveSlots do
		slot.slot.Visible = index <= state.slots
		local id = state.equipped[index]
		slot.icon.Visible = id ~= nil
		if id then
			slot.icon.Image = IMG[Skills.byId[id].icon].id
		end
	end

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

	if state.tribulation then
		setOrb("breakthrough", "stone", "천겁 중", false)
	elseif state.ready then
		local title = if state.entry and state.entry.title then state.entry.title else "돌파"
		setOrb("breakthrough", "gold", title, true)
	else
		setOrb("breakthrough", "stone", "돌파", false)
	end

	setOrb("status", "jade", "상태창", false)
end

local function updateStatusWindow(state)
	local step = Realms.get(state.step)
	ui.swRealm:set(Realms.label(state.step))
	ui.swTier:set(step.realm.tier)

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
	for key, label in ui.swStats do
		label:set(values[key] or "-")
	end
	ui.setRaceEffects(if state.race then Races.effects(state.race) else "")
	-- 다시 뽑으면 지금 종족은 나오지 않는다: 그만큼 나눠 보인다
	for id, entry in ui.oddsRows do
		local isMine = id == state.race
		entry.percent:set(if isMine then "지금 종족" else string.format("%.1f%%", Races.chance(id, state.race)))
		entry.name:setColor(if isMine then C.gold else C.cream)
	end
	ui.oddsIntro:set("다시 뽑으면 지금 종족을 뺀 나머지에서 이 확률로 나온다.")
	ui.swSlots:set(string.format("장착 %d / %d", #state.equipped, state.slots))
	for id, entry in pouchRows do
		local count = (state.items or {})[id] or 0
		entry.count:set(string.format("%d개", count))
		if entry.button then
			entry.button.Visible = count > 0
		end
	end
	ui.keyHint:set(if bindingSlot then "바꿀 키를 누른다" else "눌러서 키를 바꾼다")
	for slot, pill in keyPills do
		pill.text:set(if bindingSlot == slot then "?" else state.keys[slot])
		setImage(pill.pill, if bindingSlot == slot then "pillStone" else "pillJade")
	end

	for id, entry in skillRows do
		local def = Skills.byId[id]
		local known = state.skills[id] == true
		local equipped = table.find(state.equipped, id) ~= nil
		entry.icon.ImageColor3 = if known then Color3.new(1, 1, 1) else Color3.fromRGB(70, 66, 60)
		entry.name:setColor(if equipped then C.gold elseif known then C.cream else C.dim)
		if known then
			entry.summary:set(def.summary)
			entry.summary:setColor(if equipped then C.jade else C.dim)
		else
			local realmIndex = state.step >= Realms.firstStepById[def.minRealm]
			entry.summary:set(
				if realmIndex
					then "비급을 찾으면 익힐 수 있다"
					else string.format("%s부터 익힐 수 있다", Realms.byId[def.minRealm].name)
			)
			entry.summary:setColor(C.dim)
		end
		if entry.slotRow then
			entry.slotRow.Visible = known
			for slot, button in entry.slotButtons do
				local here = state.hotbar[slot] == id
				setImage(button.pill, if here then "pillJade" else "pillStone")
				button.text:set(state.keys[slot])
				button.text:setColor(if here then C.cream else C.dim)
			end
		end
		if entry.button then
			entry.button.Visible = known
			if known then
				local free = #state.equipped < state.slots
				setImage(entry.button, if equipped or not free then "pillStone" else "pillJade")
				entry.buttonText:set(if equipped then "해제" else "장착")
				entry.buttonText:setColor(if equipped or free then C.cream else C.dim)
			end
		end
	end
end

-- 상태창 법구: 공격 법구 칸마다 이름·등급·키, 방어 법구는 가진 것만 (지닌 것 하나에 "지님")
local function updateGear(state)
	local weapons = state.weapons or {}
	for index, entry in weaponRows do
		local weapon = weapons[index]
		local grade = weapon and Combat.GRADES[weapon.grade]
		entry.frame.Visible = grade ~= nil
		if weapon and grade then
			entry.name:set(Combat.weaponName(weapon))
			entry.summary:set(string.format("%s 등급, %s", grade.prefix, Combat.KINDS[weapon.kind].summary))
		end
	end
	ui.weaponEmpty.Visible = #weapons == 0

	local owned = {}
	for _, guard in state.guards or {} do
		if Guards.isGuard(guard) then
			owned[guard.kind] = guard
		end
	end
	local any = false
	for id, entry in guardRows do
		local guard = owned[id]
		entry.frame.Visible = guard ~= nil
		if not guard then
			continue
		end
		any = true
		local wearing = state.guard == id
		entry.name:set(Guards.name(guard))
		entry.name:setColor(if wearing then C.gold else C.cream)
		entry.worn.frame.Visible = wearing
		entry.effects:set(Guards.effects(guard))
		entry.effects:setColor(if wearing then C.jade else C.dim)
		entry.text:set(if wearing then "내려놓기" else "지니기")
		setImage(entry.button, if wearing then "pillStone" else "pillJade")
	end
	ui.guardEmpty.Visible = not any
	ui.guardCount:set(if state.guard and owned[state.guard] then "지님 1 / 1" else "지님 0 / 1")
end

local function updateHotbar(state)
	for slot, entry in hotbar do
		local id = state.hotbar[slot]
		local def = if id and id ~= "" then Skills.byId[id] else nil
		entry.icon.Visible = def ~= nil
		if def then
			entry.icon.Image = IMG[def.icon].id
			entry.label:set(def.name)
			entry.label:setColor(C.cream)
		else
			entry.label:set("빈 칸")
			entry.label:setColor(C.dim)
		end
		if entry.keyText then
			entry.keyText:set(state.keys[slot])
		end
	end
end

local function taskProgress(job, items): string
	if job.done then
		return "끝"
	elseif job.cost and job.cost.starSeed then
		return string.format("별씨 %d", items.starSeed or 0)
	elseif job.kind == "meditate" and not job.sites then
		return string.format("%d / %d초", math.floor(job.value), job.max)
	elseif job.max > 1 then
		return string.format("%d / %d", math.floor(job.value), job.max)
	end
	return ""
end

local function updateTasks(state)
	local tasks = state.tasks or {}
	local canSkip = Roots.canSkip(state.root)
	for index, entry in taskLines do
		local job = tasks[index]
		entry.line.Visible = job ~= nil
		if not job then
			continue
		end
		entry.hint = job.hint
		entry.labelText = job.label
		entry.label:set(job.label)
		entry.label:setColor(if job.done then C.dim elseif job.open then C.cream else C.dim)
		entry.progress:set(taskProgress(job, state.items or {}))
		entry.progress:setColor(if job.done then C.jade else C.dim)
		entry.bullet.ImageColor3 = if job.done
			then Color3.fromRGB(255, 220, 140)
			elseif job.open then Color3.new(1, 1, 1)
			else Color3.fromRGB(90, 86, 80)

		local main: string? = nil
		entry.onMain, entry.onAlt = nil, nil
		if job.open and not job.done then
			if job.kind == "trial" then
				main = "내관"
				entry.onMain = function()
					actions.startTask(job.id)
				end
			elseif job.kind == "choose" then
				main = "고르기"
				entry.onMain = function()
					TravelMenu.close()
					ShopWindow.close()
					Choice.open(job.key, lastState or state)
				end
			elseif job.kind == "eat" and ((state.items or {})[job.item or "herb"] or 0) > 0 then
				main = "먹기"
				entry.onMain = function()
					actions.eat("herb")
				end
			end
		end
		entry.main.Visible = main ~= nil
		if main then
			entry.mainText:set(main)
		end
		local skippable = job.skippable and canSkip and job.open and not job.done
		entry.alt.Visible = skippable
		if skippable then
			entry.onAlt = function()
				-- 영력이 드는 일이라 두 번 눌러야 건너뛴다
				local armed = skipArmed[job.id]
				if armed and os.clock() - armed < 5 then
					skipArmed[job.id] = nil
					actions.skipTask(job.id)
				else
					skipArmed[job.id] = os.clock()
					Hud.toast(
						"한 번 더 누르면 퍼즐을 건너뛴다. 대신 이 단계에 영력이 2.5배 든다 (선통후각).",
						"info"
					)
				end
			end
		end

		-- 새로 열린 과업은 할 일을 화면 알림으로 알려 준다
		local key = string.format("%d:%s", state.step, job.id)
		if job.open and not job.done and not announcedTasks[key] then
			announcedTasks[key] = true
			Hud.toast(string.format("할 일, %s: %s", job.label, job.hint), "info")
		end
		-- 영근 고르기는 열리자마자 창을 띄운다
		if job.kind == "choose" and job.open and not job.done and not autoOpened[key] then
			autoOpened[key] = true
			task.defer(function()
				if not Choice.isOpen() then
					TravelMenu.close()
					ShopWindow.close()
					Choice.open(job.key, lastState or state)
				end
			end)
		end
	end

	local items = state.items or {}
	local parts = {}
	for _, id in Balance.ITEM_ORDER do
		local count = items[id] or 0
		if count > 0 then
			table.insert(parts, string.format("%s %d", Balance.ITEMS[id].name, count))
		end
	end
	ui.pouchText:set(if #parts > 0 then "주머니  " .. table.concat(parts, "  ") else "주머니 비었다")
	ui.pouchText:setColor(if #parts > 0 then C.cream else C.dim)
	ui.eatButton.Visible = (items.herb or 0) > 0
end

-- 지닌 영석. 늘면 잠깐 커졌다 줄며 옥빛으로 빛난다
local function updateStones(state)
	local stones = state.stones or 0
	ui.stoneText:set(Currency.format(stones))
	if lastStones ~= nil and stones > lastStones then
		stonePulse += 1
		local token = stonePulse
		ui.stoneScale.Scale = 1.35
		tween(ui.stoneScale, TweenInfo.new(0.5, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 })
		ui.stoneText:setColor(C.jade)
		task.delay(0.8, function()
			if token == stonePulse then
				ui.stoneText:setColor(C.gold)
			end
		end)
	end
	lastStones = stones
end

function Hud.update(state)
	updateStatus(state)
	updateStones(state)
	updateTasks(state)
	updateOrbs(state)
	updateStatusWindow(state)
	updateGear(state)
	updateHotbar(state)
	lastState = state
	-- 전송진 창이 열려 있으면 방금 열린 진도 바로 보이게 다시 그린다
	TravelMenu.refresh(state)
	ShopWindow.refresh(state)
end

-- 전송진 위에서 F: 갈 곳 고르기
function Hud.openTravel(fromId: string)
	if lastState and not Naegwan.isOpen() then
		Choice.close()
		ShopWindow.close()
		TravelMenu.open(fromId, lastState)
	end
end

function Hud.closeTravel()
	TravelMenu.close()
end

function Hud.travelOpen(): boolean
	return TravelMenu.isOpen()
end

-- 상점 자리에서 F: 만물상("market") 또는 대장간("smith") 창
function Hud.openShop(kind: string)
	if lastState and not Naegwan.isOpen() then
		Choice.close()
		TravelMenu.close()
		Hud.toggleStatus(false)
		ShopWindow.open(kind, lastState)
	end
end

function Hud.closeShop()
	ShopWindow.close()
end

function Hud.shopOpen(): boolean
	return ShopWindow.isOpen()
end

function Hud.toggleStatus(open: boolean?)
	local panel = ui.panel :: ImageLabel
	panel.Visible = if open == nil then not panel.Visible else open
	-- 상태창을 열면 상점 창은 닫는다 (겹치지 않게)
	if panel.Visible then
		ShopWindow.close()
	end
end

-- 내관 창
function Hud.openTrial(payload: { [string]: any })
	if payload.close then
		Naegwan.close()
		return
	end
	Hud.toggleStatus(false)
	Choice.close()
	TravelMenu.close()
	ShopWindow.close()
	Naegwan.open(payload :: any, lastState and lastState.root)
end

function Hud.combat(payload: { [string]: any })
	CombatHud.event(payload, Hud.toast)
end

function Hud.toast(message: string, kind: string?)
	Notice.show(message, kind)
end

-- 술법 ---------------------------------------------------------------------------

function Hud.knows(id: string): boolean
	return lastState ~= nil and lastState.skills[id] == true
end

function Hud.cooldownReady(id: string): boolean
	return os.clock() >= (cooldownEnd[id] or 0)
end

-- 단축키 바꾸기: 상태창에서 칸을 누르면 다음에 누르는 키를 그 칸에 묶는다
function Hud.startBinding(slot: number)
	bindingSlot = slot
	if lastState then
		Hud.update(lastState)
	end
end

function Hud.bindingSlot(): number?
	return bindingSlot
end

function Hud.stopBinding()
	bindingSlot = nil
	if lastState then
		Hud.update(lastState)
	end
end

-- 서버가 술법을 허락했다: 쿨타임 시작
function Hud.skillUsed(payload: { [string]: any })
	local cooldown = payload.cooldown or 0
	cooldownEnd[payload.id] = os.clock() + cooldown
	cooldownTotal[payload.id] = math.max(cooldown, 0.01)
end

local function clockLine(): string
	local origin = Workspace:GetAttribute(Clock.ATTRIBUTE)
	if type(origin) ~= "number" then
		return ""
	end
	local t = (Workspace:GetServerTimeNow() - origin) % Clock.CYCLE
	local phase = Clock.phase(t)
	-- 칠성제의를 기다리는 중이면 시운을 보여 준다
	local state = lastState
	local chilsu = state and state.choice and state.choice.chilsu
	if state and chilsu then
		for _, job in state.tasks or {} do
			if job.kind == "ritual" and job.open and not job.done then
				local inside, seconds = Clock.sigunState(t, chilsu, Roots.window(state.root))
				local name = Tasks.CHILSU[chilsu].name
				return if inside
					then string.format("%s 시운, %s 남았다", name, Clock.format(seconds))
					else string.format("%s 시운까지 %s", name, Clock.format(seconds))
			end
		end
	end
	if phase == "day" then
		return string.format("낮, 밤까지 %s", Clock.format(Clock.untilPhase(t, "night")))
	elseif phase == "night" then
		return string.format("밤, 날이 밝기까지 %s", Clock.format(Clock.remaining(t) + 30))
	end
	return Clock.PHASE_NAME[phase]
end

local clockElapsed = 1
RunService.Heartbeat:Connect(function(dt)
	clockElapsed += dt
	if clockElapsed >= 0.5 and ui.clockText then
		clockElapsed = 0
		ui.clockText:set(clockLine())
		refreshPlace()
		-- 창이 열려 있거나 땅 이름이 떠 있으면 알림이 가리지 않게 화면 맨 위로 올린다
		Notice.setCompact(
			(ui.panel and ui.panel.Visible)
				or Choice.isOpen()
				or Naegwan.isOpen()
				or TravelMenu.isOpen()
				or ShopWindow.isOpen()
				or PlaceBanner.isShowing()
		)
	end
	local now = os.clock()
	for slot, entry in hotbar do
		local id = if lastState then lastState.hotbar[slot] else nil
		local finish = if id then cooldownEnd[id] else nil
		local remaining = if finish then math.max(0, finish - now) else 0
		entry.shade.Size =
			UDim2.new(1, -10, remaining / ((id and cooldownTotal[id]) or 1), if remaining > 0 then -10 else 0)
		entry.timeText:set(if remaining > 0 then tostring(math.ceil(remaining)) else "")
	end
end)

-- 연출 ---------------------------------------------------------------------------

local function showCinematic(title: string, subtitle: string, dark: boolean, hold: number)
	cinematicToken += 1
	local token = cinematicToken
	ui.cineTitle:set(title)
	ui.cineSub:set(subtitle)
	ui.cineScale.Scale = 0.94

	local fadeIn = TweenInfo.new(0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	tween(ui.cineBack, fadeIn, { BackgroundTransparency = if dark then 0.3 else 1 })
	tween(ui.cineFade, fadeIn, { Value = 0 })
	tween(ui.cineScale, TweenInfo.new(hold + 0.6, Enum.EasingStyle.Quad), { Scale = 1 })

	local fadeOutTime = 0.9
	-- 연출이 화면을 덮는 동안 알림은 잠시 멈췄다가 연출이 걷힌 뒤 띄운다
	Notice.hold(hold + fadeOutTime)
	cinematicUntil = os.clock() + hold + fadeOutTime
	task.delay(hold, function()
		if token ~= cinematicToken then
			return
		end
		local fadeOut = TweenInfo.new(fadeOutTime)
		tween(ui.cineBack, fadeOut, { BackgroundTransparency = 1 })
		tween(ui.cineFade, fadeOut, { Value = 1 })
	end)
	-- 트윈이 어떤 이유로든 끝나지 않아도 화면에 남지 않게 마지막에 확실히 치운다
	task.delay(hold + fadeOutTime + 0.3, function()
		if token ~= cinematicToken then
			return
		end
		ui.cineFade.Value = 1
		ui.cineBack.BackgroundTransparency = 1
	end)
end

function Hud.cinematic(payload: { [string]: any })
	if payload.kind == "intro" then
		showCinematic(
			"블록수선전",
			if payload.returning
				then "다시 송계 마을로 돌아왔다"
				else "송계 마을에서 수선의 길을 시작한다",
			true,
			3
		)
		if not payload.returning then
			task.delay(3.5, function()
				if keyboard then
					Hud.toast(
						"R 키로 운기조식, B 키로 돌파, C 키로 상태창을 연다. 술법은 화면 아래 Q, E, Z, X 칸에 넣어 쓴다.",
						"info"
					)
				else
					Hud.toast(
						"오른쪽 옥 버튼으로 운기조식하고 돌파한다. 아래 칸은 술법이다.",
						"info"
					)
				end
				Hud.toast(
					"광장 가운데 영맥 위에서 운기조식하면 영력이 더 빨리 모인다.",
					"info"
				)
				Hud.toast(
					"맵 곳곳에서 빛나는 비급을 찾으면 술법과 공법을 익힐 수 있다.",
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
