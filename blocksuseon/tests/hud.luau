-- 화면 UI 를 Lune 의 Roblox 인스턴스로 실제로 만들어 본다.   실행: lune run tests/hud
--
-- Lune 은 속성 이름·타입을 Roblox 반영 DB 로 검사하므로, 잘못된 속성이 있으면 여기서 터진다.
-- 이벤트·트윈·입력 서비스는 Lune 에 없어서 가짜로 넣는다.

local roblox = require("@lune/roblox") :: any
local task = require("@lune/task")
local Harness = require("./harness")

-- 가짜 신호 ------------------------------------------------------------------------

-- 인스턴스별로 연결된 콜백을 기억해 두었다가 fire 로 부를 수 있다
local listeners: { [any]: { [string]: { (...any) -> () } } } = setmetatable({}, { __mode = "k" }) :: any

local function fakeSignal(inst: any, name: string)
	return {
		Connect = function(_, callback)
			listeners[inst] = listeners[inst] or {}
			listeners[inst][name] = listeners[inst][name] or {}
			table.insert(listeners[inst][name], callback)
			return { Disconnect = function() end }
		end,
	}
end

local function fire(inst: any, name: string, ...: any)
	for _, callback in (listeners[inst] or {})[name] or {} do
		callback(...)
	end
end

local EVENTS = {
	Activated = true,
	MouseButton1Down = true,
	MouseButton1Up = true,
	MouseLeave = true,
	MouseEnter = true,
	Changed = true,
}

-- Lune 인스턴스를 감싸 이벤트 접근만 가짜로 돌려준다
local wrap, unwrap
local proxies = setmetatable({}, { __mode = "k" })

function unwrap(value)
	if type(value) == "table" and rawget(value, "__inst") then
		return rawget(value, "__inst")
	end
	return value
end

function wrap(inst)
	if typeof(inst) ~= "Instance" then
		return inst
	end
	local existing = proxies[inst]
	if existing then
		return existing
	end
	local proxy = setmetatable({ __inst = inst }, {
		__index = function(_, key)
			if EVENTS[key] then
				return fakeSignal(inst, key)
			end
			if key == "GetPropertyChangedSignal" then
				return function(_, property)
					return fakeSignal(inst, "Changed:" .. property)
				end
			end
			if key == "GetAttributeChangedSignal" then
				return function(_, attribute)
					return fakeSignal(inst, "Attribute:" .. attribute)
				end
			end
			local value = inst[key]
			if type(value) == "function" then
				return function(_, ...)
					local args = table.pack(...)
					for i = 1, args.n do
						args[i] = unwrap(args[i])
					end
					local results = table.pack(value(inst, table.unpack(args, 1, args.n)))
					for i = 1, results.n do
						if type(results[i]) == "table" then
							for k, v in results[i] do
								results[i][k] = wrap(v)
							end
						else
							results[i] = wrap(results[i])
						end
					end
					return table.unpack(results, 1, results.n)
				end
			end
			return wrap(value)
		end,
		__newindex = function(_, key, value)
			inst[key] = unwrap(value)
		end,
	})
	proxies[inst] = proxy
	return proxy
end

-- 가짜 game ------------------------------------------------------------------------

local real = roblox.Instance.new("DataModel")
local playerGui = roblox.Instance.new("Folder")
playerGui.Name = "PlayerGui"
local sharedFolder = Harness.new({}).folder("src/shared")

local tweensPlayed = 0
local heartbeatKey = {}
local tagged: { [string]: { any } } = {} -- 가짜 CollectionService 태그 (태그 → 인스턴스 목록)
local purchases: { number } = {} -- 로벅스 상품 창을 띄운 상품 id
local chatMessages: { string } = {}
local fakeChannel = {
	Parent = true,
	IsA = function(_, className)
		return className == "TextChannel"
	end,
	DisplaySystemMessage = function(_, message)
		table.insert(chatMessages, message)
	end,
}
local services = {
	MarketplaceService = {
		PromptProductPurchase = function(_, _player, productId)
			table.insert(purchases, productId)
		end,
	},
	PolicyService = {
		GetPolicyInfoForPlayerAsync = function()
			return { ArePaidRandomItemsRestricted = false }
		end,
	},
	CollectionService = {
		GetTagged = function(_, tag)
			return tagged[tag] or {}
		end,
		GetInstanceAddedSignal = function()
			return fakeSignal(heartbeatKey, "TagAdded")
		end,
	},
	TextChatService = {
		ChatVersion = roblox.Enum.ChatVersion.TextChatService,
		WaitForChild = function()
			return {
				WaitForChild = function()
					return fakeChannel
				end,
			}
		end,
	},
	StarterGui = {
		SetCore = function()
			error("예전 채팅으로 가면 안 된다")
		end,
	},
	Players = {
		LocalPlayer = {
			WaitForChild = function()
				return wrap(playerGui)
			end,
		},
	},
	TweenService = {
		Create = function(_, target, _info, goal)
			-- 목표 속성이 진짜 있는지 확인하려고 바로 대입해 본다
			local inst = unwrap(target)
			for key, value in goal do
				inst[key] = value
			end
			-- NumberValue 처럼 값이 바뀌면 Changed 를 쏜다 (트윈이 끝난 상태를 바로 흉내 낸다)
			if goal.Value ~= nil then
				fire(inst, "Changed", goal.Value)
			end
			return {
				Play = function()
					tweensPlayed += 1
				end,
				Cancel = function() end,
			}
		end,
	},
	UserInputService = {
		KeyboardEnabled = true,
		TouchEnabled = false,
		InputEnded = fakeSignal(heartbeatKey, "InputEnded"),
	},
	RunService = {
		Heartbeat = fakeSignal(heartbeatKey, "Heartbeat"),
		RenderStepped = fakeSignal(heartbeatKey, "Heartbeat"),
		PreSimulation = fakeSignal(heartbeatKey, "PreSimulation"),
		BindToRenderStep = function() end,
	},
	ContentProvider = { PreloadAsync = function() end },
	Debris = { AddItem = function() end },
	-- 글자 크기 재기: Roblox 글꼴 폭을 대충 흉내 낸다
	TextService = {
		GetTextSize = function(_, text, size, _font, frame)
			local width = utf8.len(text) * size * 0.6
			local lines = math.max(1, math.ceil(width / frame.X))
			return roblox.Vector2.new(math.min(width, frame.X), lines * size)
		end,
	},
	Workspace = {
		CurrentCamera = nil,
		GetAttribute = function()
			return 0
		end,
		GetServerTimeNow = function()
			return 500 -- 밤
		end,
	},
	Lighting = wrap(real:GetService("Lighting")),
	ReplicatedStorage = {
		WaitForChild = function(_, name)
			assert(name == "Shared", "Shared 만 찾는다")
			return sharedFolder
		end,
		FindFirstChild = function()
			return nil
		end,
	},
}

local game = {
	GetService = function(_, name)
		return assert(services[name], "가짜 서비스 없음: " .. name)
	end,
}

local env = Harness.robloxGlobals(real)
env.game = game
env.Instance = {
	new = function(className)
		return wrap(roblox.Instance.new(className))
	end,
}
env.TweenInfo = {
	new = function(...)
		return { ... }
	end,
}
env.typeof = function(value)
	-- 감싼 인스턴스도 인스턴스로 본다
	if type(value) == "table" and rawget(value, "__inst") then
		return "Instance"
	end
	return typeof(value)
end
env.task = task

-- 실제로 만들고 갱신해 본다 ----------------------------------------------------------

local loader = Harness.new(env)
-- Hud 가 require 하는 shared 모듈도 같은 로더로 불러야 하므로 shared 폴더를 로더 것으로 바꾼다
sharedFolder = loader.folder("src/shared")
local Hud = loader.require(loader.folder("src/client").Hud)

local noop = function() end
local sent: { [string]: any } = {}
local function record(name: string)
	return function(...)
		sent[name] = { ... }
	end
end
Hud.build({
	meditate = noop,
	breakthrough = noop,
	useSlot = noop,
	equip = noop,
	assign = noop,
	startTask = record("startTask"),
	skipTask = record("skipTask"),
	choose = record("choose"),
	eat = record("eat"),
	trialResult = record("trialResult"),
	trialCancel = record("trialCancel"),
	travel = record("travel"),
	buy = record("buy"),
	upgrade = record("upgrade"),
})

local function state(overrides)
	local s = {
		step = 5,
		qi = 120,
		req = 300,
		gain = 4.5,
		meditating = false,
		veinId = nil,
		needsBreak = false,
		ready = false,
		tasksDone = false,
		entry = nil,
		tasks = {},
		root = nil,
		choice = {},
		items = {},
		inTrial = false,
		skills = {},
		equipped = {},
		hotbar = { "", "", "", "" },
		keys = { "Q", "E", "Z", "X" },
		slots = 1,
		stats = { tribulations = 0, herbs = 0, manuals = 0 },
		inFormation = false,
		maxHealth = 125,
		tribulation = nil,
		canSave = true,
		stones = 30,
		weapons = { { kind = "sword", grade = 1 } },
	}
	for k, v in overrides or {} do
		s[k] = v
	end
	return s
end

local Tasks0 = loader.require(sharedFolder.Tasks)
local Progression0 = loader.require(sharedFolder.Progression)
local Roots0 = loader.require(sharedFolder.Roots)
local function tasksFor(step: number, root)
	local data = Progression0.newData()
	data.step = step
	data.root = root
	return Tasks0.snapshot(data)
end

local cases = {
	{ "기본", state() },
	{ "범인 과업", state({ step = 1, tasks = tasksFor(1, nil) }) },
	{
		"단수기 과업",
		state({
			step = 2,
			root = Roots0.make({ "wood", "fire" }),
			tasks = tasksFor(2, Roots0.make({ "wood", "fire" })),
			items = { herb = 3, lingzhi = 1 },
		}),
	},
	{
		"돌파 준비 끝",
		state({
			step = 16,
			qi = 999,
			req = 999,
			ready = true,
			tasksDone = true,
			entry = { kind = "trial", title = "무극영운" },
		}),
	},
	{ "과업 남음", state({ step = 3, qi = 999, req = 999, tasksDone = false }) },
	{ "운기 중 + 영맥", state({ meditating = true, veinId = "low" }) },
	{
		"병목 천겁",
		state({
			step = 48,
			qi = 999,
			req = 999,
			ready = true,
			entry = { kind = "tribulation", title = "천겁 맞기" },
		}),
	},
	{
		"천겁 모이는 중",
		state({ step = 44, qi = 999, req = 999, tribulation = { name = "천겁", wave = 0, waves = 9 } }),
	},
	{
		"천겁 진행",
		state({ step = 44, qi = 999, req = 999, tribulation = { name = "천겁", wave = 3, waves = 9 } }),
	},
	{ "천겁 끝", state({ step = 45 }) },
	{
		"술법·공법 익힘",
		state({
			skills = { gyeongsin = true, yeongan = true, tonap = true, baekcho = true },
			equipped = { "tonap" },
			hotbar = { "gyeongsin", "", "yeongan", "" },
			keys = { "Q", "T", "Z", "X" },
		}),
	},
	{
		"공법 칸 가득",
		state({
			step = 45,
			slots = 3,
			skills = { tonap = true, baekcho = true, geumgang = true, piroe = true },
			equipped = { "tonap", "baekcho", "geumgang" },
			inFormation = true,
			veinId = "high",
		}),
	},
	{ "최고 경지", state({ step = 56, qi = 1e12, req = 1e12 }) },
}
for _, case in cases do
	local ok, err = pcall(Hud.update, case[2])
	if not ok then
		error(`갱신 실패 [{case[1]}]: {err}`)
	end
end

Hud.toggleStatus()
Hud.toggleStatus(false)

-- 전송진 창: 열린 진만 고를 수 있고, 고르면 서버에 보낸다
Hud.update(state({
	waypoints = {
		{ id = "wp_home", name = "송계 마을", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = false },
	},
}))
-- 맵의 전송진(WorldSites 의 16 곳)이 모두 창에 들어가고, 이름이 칸 안에 들며, 창이 화면(1280×720 기준) 안에 든다
do
	local fs = require("@lune/fs")
	local many = {}
	for id, name in string.gmatch(fs.readFile("src/server/WorldSites.luau"), 'add%("wp", "([%w_]+)", "([^"]+)"') do
		table.insert(many, { id = id, name = name, open = true })
	end
	assert(#many == 16, `WorldSites 의 전송진 {#many}곳 (16)`)
	Hud.update(state({ waypoints = many }))
	Hud.openTravel(many[2].id)
	local menu = playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("TravelMenu")
	local shown, cellWidth = 0, nil
	for _, item in menu:GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			shown += 1
		elseif item:IsA("UIGridLayout") then
			cellWidth = item.CellSize.X.Offset
		end
	end
	assert(shown == #many, `전송진 {shown}개만 보인다 ({#many})`)
	local BitmapTextForMenu = loader.require(loader.folder("src/client").BitmapText)
	for _, point in many do
		local width = BitmapTextForMenu.measure("title", 19, point.name).X
		assert(width < cellWidth - 12, `{point.name} 이 칸({cellWidth})보다 넓다 ({width})`)
	end
	assert(BitmapTextForMenu.measure("title", 19, "가 보지 못한 곳").X < cellWidth - 12, "가 보지 못한 곳")
	assert(menu.Size.X.Offset <= 1280 - 80 and menu.Size.Y.Offset <= 720 - 80, `전송진 창이 크다 ({menu.Size})`)
	-- 진이 더 늘어도 스물까지는 들어간다
	local more = table.clone(many)
	for i = #many + 1, 20 do
		table.insert(more, { id = "wp_more" .. i, name = "청허경", open = true })
	end
	Hud.update(state({ waypoints = more }))
	Hud.openTravel(many[2].id)
	shown = 0
	for _, item in menu:GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			shown += 1
		end
	end
	assert(shown == 20, `전송진 {shown}개만 보인다 (20)`)
	Hud.closeTravel()
end
Hud.update(state({
	waypoints = {
		{ id = "wp_home", name = "송계 마을", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = false },
	},
}))
Hud.openTravel("wp_home")
assert(Hud.travelOpen(), "전송진 창이 열리지 않았다")
do
	local menu = playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("TravelMenu")
	local buttons = {}
	for _, item in menu:GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			buttons[item.LayoutOrder] = item
		end
	end
	assert(buttons[1] and buttons[2] and buttons[3] and not buttons[4], "진 셋만 보여야 한다")
	fire(buttons[3], "Activated")
	assert(sent.travel == nil and Hud.travelOpen(), "닫힌 진은 고를 수 없다")
	fire(buttons[1], "Activated")
	assert(sent.travel == nil, "지금 선 진은 고를 수 없다")
	fire(buttons[2], "Activated")
	assert(sent.travel and sent.travel[1] == "wp_two", "고른 진을 보내야 한다")
	assert(not Hud.travelOpen(), "고르면 창이 닫힌다")
end

-- 영석 ------------------------------------------------------------------------------

-- BitmapText 틀에 찍힌 글자를 다시 읽는다 (빈칸은 그림이 없어서 빠진다)
local ArtGlyphs = loader.require(loader.folder("src/client").Art)
local glyphChars: { [string]: string } = {}
for _, font in ArtGlyphs.fonts do
	for ch, glyph in font.glyphs do
		glyphChars[`{font.pages[glyph[1]]}:{glyph[2]}:{glyph[3]}`] = ch
	end
end
local function readText(frame): string
	assert(frame, "글자 틀이 없다")
	local labels = {}
	for _, child in frame:GetChildren() do
		if child:IsA("ImageLabel") then
			table.insert(labels, child)
		end
	end
	table.sort(labels, function(a, b)
		return a.Position.X.Offset < b.Position.X.Offset
	end)
	local out = {}
	for _, label in labels do
		table.insert(out, glyphChars[`{label.Image}:{label.ImageRectOffset.X}:{label.ImageRectOffset.Y}`] or "?")
	end
	return table.concat(out)
end
-- 글자판에 있는 글자만 찍히므로, 기대하는 글에서도 빈칸과 글자판에 없는 글자는 빼고 견준다
-- (새 글자가 들어가 글자판을 다시 굽기 전에도 통과하게)
local function shows(frame, fontName: string, expected: string): boolean
	local out = {}
	for _, code in utf8.codes(expected) do
		local ch = utf8.char(code)
		local glyph = ArtGlyphs.fonts[fontName].glyphs[ch]
		if glyph and glyph[4] > 0 then
			table.insert(out, ch)
		end
	end
	return readText(frame) == table.concat(out)
end
local function find(root, name: string)
	for _, item in root:GetDescendants() do
		if item.Name == name then
			return item
		end
	end
	return nil
end
local UiForTest = loader.require(loader.folder("src/client").Ui)

do
	local hudGui = playerGui:FindFirstChild("BlockSuseonHud")
	-- 늘 보이는 영석 칸: 쉼표로 끊어 보이고, 늘면 잠깐 옥빛이 된다
	Hud.update(state({ stones = 1250 }))
	local counter = find(hudGui:FindFirstChild("Status"), "StoneText")
	assert(shows(counter, "body", "1,250"), `영석 칸 {readText(counter)} (1,250)`)
	-- 앞 상태(30)보다 늘어서 잠깐 빛났다가 금빛으로 돌아온다
	task.wait(1)
	local first = counter:FindFirstChildOfClass("ImageLabel")
	assert(first.ImageColor3 == UiForTest.C.gold, "영석 칸은 금빛이다")
	Hud.update(state({ stones = 1265 }))
	assert(shows(counter, "body", "1,265"), "영석이 늘면 숫자를 바꾼다")
	first = counter:FindFirstChildOfClass("ImageLabel")
	assert(first.ImageColor3 == UiForTest.C.jade, "영석이 늘면 잠깐 빛난다")
	-- 상태창 능력치에도 보인다
	local statShown = false
	for _, item in hudGui:FindFirstChild("StatusWindow"):GetDescendants() do
		if item.Name == "Text" and shows(item, "body", "1,265개") then
			statShown = true
		end
	end
	assert(statShown, "상태창에 영석이 없다")

	-- 만물상: 물건, 무기, 영석 사기
	Hud.update(state({
		stones = 100,
		items = { herb = 3 },
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
	}))
	Hud.openShop("market")
	assert(Hud.shopOpen(), "상점 창이 열리지 않았다")
	local shop = hudGui:FindFirstChild("ShopWindow")
	local function shown(): { [number]: any }
		local out = {}
		for _, item in shop:GetDescendants() do
			if item.Name == "Row" and item.Visible then
				out[item.LayoutOrder] = item
			end
		end
		return out
	end
	local function count(list): number
		local n = 0
		for _ in list do
			n += 1
		end
		return n
	end
	local function buttonOf(rowFrame)
		return find(rowFrame, "Button")
	end
	local pillStone = ArtGlyphs.images.pillStone.id
	local Combat = loader.require(sharedFolder.Combat)
	local function weaponName(kind: string, grade: number): string
		return Combat.weaponName({ kind = kind, grade = grade })
	end
	assert(shows(find(shop, "Stones"), "body", "100"), "상점 창 머리에 지닌 영석이 보여야 한다")
	local rows = shown()
	assert(count(rows) == 4, `물건 {count(rows)}줄 (4)`)
	assert(shows(find(rows[1], "Name"), "title", "영초"), "첫 물건은 영초")
	assert(shows(find(rows[1], "Sub"), "body", "1개, 주머니에 3개"), readText(find(rows[1], "Sub")))
	assert(shows(find(rows[1], "Price"), "body", "15"), "영초 값")
	fire(buttonOf(rows[1]), "Activated")
	assert(sent.buy and sent.buy[1] == "herb1", "사기를 누르면 서버에 보낸다")
	sent.buy = nil
	-- 모자라면 버튼을 흐리게 하고 보내지 않는다
	assert(buttonOf(rows[2]).Image == pillStone, "못 사는 물건은 흐려야 한다")
	fire(buttonOf(rows[2]), "Activated")
	assert(sent.buy == nil, "영석이 모자라면 보내지 않는다")

	fire(find(shop, "Tab2"), "Activated")
	rows = shown()
	assert(count(rows) == 3, `무기 {count(rows)}줄 (3)`)
	assert(shows(find(rows[1], "Name"), "title", weaponName("saber", 1)), readText(find(rows[1], "Name")))
	assert(shows(find(rows[1], "Sub"), "body", Combat.KINDS.saber.summary), "무기 설명")
	assert(shows(find(buttonOf(rows[1]), "Text"), "body", "지님"), "지닌 종류는 지님")
	fire(buttonOf(rows[1]), "Activated")
	assert(sent.buy == nil, "지닌 종류는 다시 사지 않는다")
	fire(buttonOf(rows[2]), "Activated")
	assert(sent.buy and sent.buy[1] == "spear", "창을 산다")
	sent.buy = nil

	fire(find(shop, "Tab3"), "Activated")
	rows = shown()
	assert(count(rows) == 3, `영석 묶음 {count(rows)}줄 (3)`)
	assert(shows(find(rows[1], "Name"), "title", "영석 한 줌"), "묶음 이름")
	assert(shows(find(rows[1], "Sub"), "body", "영석 120개"), "묶음 영석")
	assert(shows(find(buttonOf(rows[1]), "Text"), "body", "25 로벅스"), "묶음 값")
	fire(buttonOf(rows[2]), "Activated")
	local Currency = loader.require(sharedFolder.Currency)
	assert(purchases[1] == Currency.PACKS[2].productId, "로벅스 상품 창을 띄워야 한다")

	-- 열려 있는 동안 상태가 오면 다시 그린다
	fire(find(shop, "Tab2"), "Activated")
	Hud.update(state({ stones = 10, weapons = { { kind = "sword", grade = 1 } } }))
	assert(shows(find(shop, "Stones"), "body", "10"), "상태가 오면 머리 영석을 바꾼다")
	rows = shown()
	assert(shows(find(buttonOf(rows[1]), "Text"), "body", "사기"), "지니지 않은 종류는 사기")
	assert(buttonOf(rows[1]).Image == pillStone, "모자라면 흐려진다")

	-- 대장간: 지닌 무기마다 다음 등급과 값. 최고 등급은 버튼이 없다
	Hud.update(state({
		stones = 100,
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
	}))
	Hud.openShop("smith")
	assert(Hud.shopOpen(), "대장간 창이 열리지 않았다")
	assert(not find(shop, "Tab1").Parent.Visible, "대장간에는 갈래가 없다")
	rows = shown()
	assert(count(rows) == 3, `대장간 {count(rows)}줄 (3)`)
	assert(shows(find(rows[1], "Name"), "title", weaponName("sword", 1)), "첫 무기")
	assert(
		shows(
			find(rows[1], "Sub"),
			"body",
			string.format("%s 등급, 강화하면 %s", Combat.GRADES[1].prefix, weaponName("sword", 2))
		),
		readText(find(rows[1], "Sub"))
	)
	assert(shows(find(rows[1], "Price"), "body", "120"), "목→철 값")
	assert(shows(find(rows[3], "Name"), "title", weaponName("fan", 5)), "부채 최고 등급")
	assert(shows(find(rows[3], "Price"), "body", "최고 등급"), "최고 등급은 값 대신")
	assert(not buttonOf(rows[3]).Visible, "최고 등급은 강화 버튼이 없다")
	fire(buttonOf(rows[1]), "Activated")
	assert(sent.upgrade == nil, "영석이 모자라면 강화를 보내지 않는다")
	Hud.update(state({
		stones = 500,
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
	}))
	fire(buttonOf(rows[2]), "Activated")
	assert(sent.upgrade and sent.upgrade[1] == 2, "그 칸 무기를 강화한다")
	-- 상태창을 열면 상점 창은 닫힌다
	Hud.toggleStatus(true)
	assert(not Hud.shopOpen(), "상태창을 열면 상점 창을 닫는다")
	Hud.toggleStatus(false)

	-- 전송진 삯: 선 진과 갈 진 바닥 사이 거리로 센다. 송계 마을(Places.HOME_WAYPOINT)로는 공짜
	local function pad(id: string, x: number, z: number)
		local part = roblox.Instance.new("Part")
		part.Position = roblox.Vector3.new(x, 0, z)
		part:SetAttribute("WaypointId", id)
		return wrap(part)
	end
	tagged.Waypoint = { pad("wp_home", 0, 0), pad("wp_two", 600, 0), pad("wp_three", 0, 5000) }
	local points = {
		{ id = "wp_home", name = "송계 마을", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = true },
	}
	Hud.update(state({ stones = 5, waypoints = points }))
	Hud.openTravel("wp_two")
	local menu = hudGui:FindFirstChild("TravelMenu")
	local function entries()
		local out = {}
		for _, item in menu:GetDescendants() do
			if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
				out[item.LayoutOrder] = item
			end
		end
		return out
	end
	local buttons = entries()
	assert(shows(find(menu, "Stones"), "body", "5"), "전송진 창에 지닌 영석")
	assert(shows(find(buttons[1], "Fee"), "body", "공짜"), "송계 마을로 가는 길은 공짜")
	assert(not find(buttons[2], "Fee").Visible, "지금 선 진에는 삯이 없다")
	local far = Currency.travelFee(math.sqrt(600 ^ 2 + 5000 ^ 2), false)
	assert(shows(find(buttons[3], "Fee"), "body", "영석 " .. far), readText(find(buttons[3], "Fee")))
	sent.travel = nil
	fire(buttons[3], "Activated")
	assert(sent.travel == nil, "삯이 모자라면 보내지 않는다")
	assert(Hud.travelOpen(), "삯이 모자라면 창을 닫지 않는다")
	fire(buttons[1], "Activated")
	assert(sent.travel[1] == "wp_home", "공짜 길은 바로 간다")
	Hud.openTravel("wp_home")
	buttons = entries()
	local near = Currency.travelFee(600, false)
	assert(shows(find(buttons[2], "Fee"), "body", "영석 " .. near), "가까운 진 삯")
	fire(buttons[2], "Activated")
	assert(sent.travel[1] == "wp_two", "삯이 넉넉하면 간다")
	tagged.Waypoint = nil
end

-- 싸움: 대상 창과 맞은 느낌
do
	local mob = roblox.Instance.new("Model")
	mob:SetAttribute("Hp", 40)
	mob:SetAttribute("MaxHp", 60)
	mob:SetAttribute("Tier", 1)
	mob.Parent = real:GetService("Workspace")
	Hud.combat({ kind = "hit", mob = wrap(mob), name = "잿빛이리", tier = 1, hp = 40, maxHp = 60 })
	local frame = playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("Target")
	assert(frame and frame.Visible, "대상 창이 떠야 한다")
	Hud.combat({ kind = "hurt", amount = 8, name = "잿빛이리", mob = wrap(mob) })
	Hud.combat({ kind = "blocked", name = "잿빛이리" })
	Hud.combat({ kind = "hit", mob = wrap(mob), name = "잿빛이리", tier = 1, hp = 0, maxHp = 60, killed = true })
	assert(not frame.Visible, "쓰러뜨리면 대상 창이 닫힌다")
end

-- 땅 이름 띄우기
loader.require(loader.folder("src/client").PlaceBanner).show("청송림", "다리 건너 영초가 돋는 솔숲")

-- 현판: 판자 겉면에 붓글씨 글자를 붙인다 (가로, 세로)
do
	local Plaques = loader.require(loader.folder("src/client").Plaques)
	for _, case in
		{ { "송계", false, roblox.Vector3.new(8, 3, 0.6) }, { "관성대", true, roblox.Vector3.new(3, 10, 1.2) } }
	do
		local board = roblox.Instance.new("Part")
		board.Size = case[3]
		board:SetAttribute("Text", case[1])
		board:SetAttribute("Vertical", case[2])
		board:SetAttribute("Faces", "Front,Back")
		Plaques.decorate(wrap(board))
		local guis = 0
		for _, child in board:GetChildren() do
			if child:IsA("SurfaceGui") then
				guis += 1
				local glyphs = 0
				for _, item in child:GetDescendants() do
					if item:IsA("ImageLabel") then
						glyphs += 1
					end
				end
				assert(glyphs == utf8.len(case[1]), `현판 글자 수 {glyphs} ({case[1]})`)
			end
		end
		assert(guis == 2, "앞뒤 두 면에 새겨야 한다")
		Plaques.decorate(wrap(board))
		assert(#board:GetChildren() == 2, "두 번 새기면 안 된다")
	end
end

-- 내관 창: 박자와 균형
Hud.openTrial({
	id = 1,
	mode = "rhythm",
	seed = 9,
	params = { beats = 2, interval = 0.9, band = 1 },
	title = "음양지의",
	hint = "박자에 맞춰 누른다.",
})
for _ = 1, 30 do
	fire(heartbeatKey, "Heartbeat", 0.05)
end
Hud.openTrial({ close = true })
Hud.openTrial({
	id = 2,
	mode = "balance",
	seed = 3,
	params = { bars = 3, target = 1, band = 1.3, turbulence = 1 },
	title = "혼원지의",
})
for _ = 1, 10 do
	fire(heartbeatKey, "Heartbeat", 0.05)
end
Hud.openTrial({ close = true })
for id, case in
	{
		{ "sequence", { nodes = 9, lengths = { 3, 3 }, style = "dots" } },
		{ "sequence", { nodes = 9, lengths = { 4 }, style = "cheongang" } },
		{ "ring", { hits = 3, band = 1 } },
		{ "arrange", { band = 1 } },
		{ "strands", { count = 9, time = 17, speed = 1, band = 1 } },
		{
			"order",
			{ items = { "금단이 맺힌 날", "영근이 깨어난 날", "송계 마을에 처음 온 날" } },
		},
	}
do
	Hud.openTrial({ id = 10 + id, mode = case[1], seed = 42, params = case[2], title = "내관" })
	for _ = 1, 20 do
		fire(heartbeatKey, "Heartbeat", 0.05)
	end
	Hud.openTrial({ close = true })
end
-- 술법 쿨타임이 단축칸에 그려지는지
-- 단축키 바꾸기 모드
Hud.startBinding(2)
assert(Hud.bindingSlot() == 2, "단축키 바꾸기 모드가 아니다")
Hud.stopBinding()
assert(Hud.bindingSlot() == nil, "단축키 바꾸기 모드가 안 끝났다")
Hud.skillUsed({ id = "gyeongsin", cooldown = 5 })
fire(heartbeatKey, "Heartbeat", 0.016)
assert(Hud.cooldownReady("gyeongsin") == false, "쿨타임 중인데 바로 쓸 수 있다")
for i = 1, 6 do
	Hud.toast("알림 " .. i, if i % 2 == 0 then "good" else "bad")
end
Hud.cinematic({ kind = "intro", realm = "범인", returning = false })
Hud.cinematic({ kind = "ascend", step = 45, realm = "결단기 초기", blurb = "금단을 맺는다." })
Hud.cinematic({ kind = "ascend", step = 49, realm = "원영기 초기", blurb = "" })
Hud.cinematic({ kind = "down" })

-- 미뤄 둔 연출(task.delay)까지 돌게 잠깐 기다린다
task.wait(4)

local hud = playerGui:FindFirstChild("BlockSuseonHud")
assert(hud, "HUD ScreenGui 가 없다")
-- 알림은 화면 위 가운데 띠로 뜬다. 한 번에 넷까지, 넘치면 줄을 세운다 (버리지 않는다)
local Art = loader.require(loader.folder("src/client").Art)
local Notice = loader.require(loader.folder("src/client").Notice)
local notices = hud:FindFirstChild("Notices")
assert(notices, "화면 알림 틀이 없다")
assert(#chatMessages == 0, "알림을 채팅으로 보내면 안 된다")
-- 앞의 상태 검사에서 열린 고르기 창을 닫고 보통 자리로
loader.require(loader.folder("src/client").Choice).close()
Notice.setCompact(false)
Notice.clear()
task.wait(0.5)
for i = 1, 6 do
	Hud.toast("몰린 알림 " .. i, "good")
end
assert(Notice.count() == 4, `화면 알림 {Notice.count()}개 (넷)`)
assert(Notice.pendingCount() == 2, "넘친 알림은 기다린다")
Hud.toast("몰린 알림 6", "good")
assert(Notice.pendingCount() == 2, "기다리는 알림과 같으면 겹쳐 쌓지 않는다")
Hud.toast("몰린 알림 1", "good")
assert(Notice.count() == 4 and Notice.pendingCount() == 2, "떠 있는 알림과 같으면 시간만 늘린다")
Notice.clear()
task.wait(0.5)

-- 연출 중에는 멈췄다가 걷힌 뒤 띄운다
Notice.hold(0.6)
Hud.toast("연출 뒤 알림", "info")
assert(Notice.count() == 0 and Notice.pendingCount() == 1, "연출 중에는 띄우지 않는다")
task.wait(0.8)
assert(Notice.count() == 1 and Notice.pendingCount() == 0, "연출이 끝나면 띄운다")
Notice.clear()
task.wait(0.5)

-- 창이 열려 있으면 맨 위로 올리고 둘만
Notice.setCompact(true)
for i = 1, 3 do
	Hud.toast("창 열림 알림 " .. i, "info")
end
assert(Notice.count() == 2, "창이 열려 있으면 둘만 띄운다")
Notice.setCompact(false)
assert(Notice.count() == 3, "창을 닫으면 기다리던 것을 띄운다")
Notice.clear()
task.wait(0.5)

-- 글자판에 없는 글자가 있으면 그 알림만 Roblox 글꼴로
Hud.toast("Ωmega님이 결단기에 올랐다.", "world")
Hud.toast("영력이 가득 찼다. 남은 과업을 마치면 오른다.", "info")
local fallbacks = 0
for _, item in notices:GetDescendants() do
	if item:IsA("TextLabel") then
		assert(
			string.find(item.Text, "Ωmega", 1, true),
			"글자판으로 찍을 수 있는 알림이 Roblox 글꼴로 갔다"
		)
		fallbacks += 1
	end
end
assert(fallbacks == 1, "글자판에 없는 글자가 있으면 Roblox 글꼴로 찍어야 한다")
-- 도움말처럼 긴 알림도 글자판으로
local Commands = loader.require(sharedFolder.Commands)
for _, line in Commands.HELP do
	for _, code in utf8.codes("[검수] " .. line) do
		local ch = utf8.char(code)
		assert(ch == " " or Art.fonts.body.glyphs[ch], "도움말 글자가 글자판에 없다: " .. ch)
	end
end
local cinematicGui = playerGui:FindFirstChild("BlockSuseonCinematic")
assert(cinematicGui, "연출 ScreenGui 가 없다")
-- 연출이 끝나면 화면에서 사라져야 한다 (지난번에 계속 남아 있던 문제)
task.wait(1.5)
local stage = cinematicGui:FindFirstChild("Stage")
assert(stage, "연출 Stage 가 없다")
assert(stage.Visible == false, "연출이 끝났는데 화면에 남아 있다")
for _, child in cinematicGui:GetChildren() do
	if child:IsA("Frame") and child.Name ~= "Stage" then
		assert(child.BackgroundTransparency == 1, "연출 배경이 어둡게 남아 있다")
	end
end

task.wait(10)
assert(Notice.count() == 0 and Notice.pendingCount() == 0, "알림이 사라지지 않았다")

local count = 0
for _, _ in hud:GetDescendants() do
	count += 1
end
print(`HUD 통과 · 인스턴스 {count}개 · 트윈 {tweensPlayed}회 · 상태 {#cases}가지`)

-- 화면에 나올 수 있는 글자가 모두 글자판에 있는지 -----------------------------------------
local Realms = loader.require(sharedFolder.Realms)
local Skills = loader.require(sharedFolder.Skills)
local missing = {}
local function need(fontName: string, text: string)
	for _, code in utf8.codes(text) do
		local ch = utf8.char(code)
		if not Art.fonts[fontName].glyphs[ch] then
			missing[`{fontName}:{ch}`] = text
		end
	end
end
for step = 1, Realms.maxStep do
	local s = Realms.get(step)
	need("title", Realms.label(step))
	need("title", s.realm.name)
	need("title", s.sub)
	need("body", s.realm.blurb)
	if s.realm.tribulation then
		need("title", s.realm.tribulation.name)
	end
end
for _, def in Skills.list do
	need("title", def.name)
	need("body", def.summary)
	need("body", string.format("%s부터 익힐 수 있다", Realms.byId[def.minRealm].name))
end
local Tasks = loader.require(sharedFolder.Tasks)
local Roots = loader.require(sharedFolder.Roots)
local Progression = loader.require(sharedFolder.Progression)
local Clock = loader.require(sharedFolder.Clock)
Tasks.LIVE_UNTIL = Realms.maxStep
for step = 1, Realms.maxStep do
	for _, combo in { { "wood" }, { "wood", "fire", "earth", "metal", "water" } } do
		local data = Progression.newData()
		data.step = step
		data.root = Roots.make(combo)
		for _, choice in { { chilsu = "baek", element = combo[1] }, {} } do
			data.choice = choice
			for _, job in Tasks.list(data) do
				need("title", job.label)
				need("body", job.hint)
			end
		end
	end
	if Realms.get(step).realm.entry then
		need("title", Realms.get(step).realm.entry.title)
		need("body", "B 로 " .. Realms.get(step).realm.entry.title)
	end
end
for _, element in Roots.ELEMENTS do
	need("title", Roots.ELEMENT[element].name .. " 속성")
	need("body", Roots.ELEMENT[element].place .. "에서 닦는다")
end
for _, kind in Roots.KIND do
	need("title", kind.name)
	need("body", kind.summary)
end
for _, def in Tasks.CHILSU do
	need("title", def.name)
	need("body", def.summary)
end
for _, name in Clock.PHASE_NAME do
	need("body", name)
end
local Trials = loader.require(sharedFolder.Trials)
for _, memory in Trials.MEMORIES do
	need("body", memory)
end
need("body", Trials.BIRTH)
for _, def in Tasks.DOSIM do
	need("title", def.name)
	need("body", def.summary)
end
for mansion = 1, 4 do
	for _, name in Tasks.mansionStars(mansion) do
		need("title", name)
	end
	need("title", Tasks.MANSIONS[mansion].name)
end
need("title", "천지인")
-- 종족 (상태창)
local RacesForGlyphs = loader.require(sharedFolder.Races)
for _, race in RacesForGlyphs.list do
	need("body", race.name)
	need("body", race.summary)
	need("body", RacesForGlyphs.effects(race.id))
end
need("body", "종족 다시 뽑기 49 로벅스")
-- 땅 이름 (들어설 때 화면에 띄운다)
for _, region in loader.require(sharedFolder.Places).REGIONS do
	need("title", region.name)
	need("body", region.name)
	if region.sub then
		need("body", region.sub)
	end
end
need("body", "별씨 12")
for _, name in Trials.CHEONGANG do
	need("title", name)
end
for i, name in Trials.GUGUNG do
	need("body", name)
	need("title", tostring(i))
end
for _, def in Tasks.CHILSU do
	need("body", string.format("%s 시운, 3분 12초 남았다 %s 시운까지 40초", def.name, def.name))
end
need("body", "주머니  영초 3  천년영지 1  홍령삼 1  축기단 1 주머니 비었다 끝 12 / 30초")
-- 서버가 보내는 알림 문구 (화면에 글자판으로 찍는다).
-- 맵 짓는 World*.luau 의 글은 부품 이름과 현판 글(붓글씨, tests/run 이 본다)이라 빼고, 전송진 이름만 창에 나온다
local fs = require("@lune/fs")
for id, name in string.gmatch(fs.readFile("src/server/WorldSites.luau"), 'add%("wp", "([%w_]+)", "([^"]+)"') do
	need("title", name)
end
for _, file in fs.readDir("src/server") do
	if string.match(file, "^World") then
		continue
	end
	local source = fs.readFile("src/server/" .. file)
	source = string.gsub(source, "%-%-[^\n]*", "")
	for literal in string.gmatch(source, '"([^"\n]*)"') do
		if string.find(literal, "[\234-\237]") then
			need("body", (string.gsub(literal, "%%[%a%.%d]+", "")))
		end
	end
end
-- 영석: 영석 칸, 상점·대장간 창, 전송진 삯
local CurrencyForGlyphs = loader.require(sharedFolder.Currency)
local CombatForGlyphs = loader.require(sharedFolder.Combat)
local BalanceForGlyphs = loader.require(sharedFolder.Balance)
need("body", "1,250 1,265개 영석 25 공짜")
need("title", "만물상 대장간")
for _, ware in CurrencyForGlyphs.WARES do
	if ware.item then
		need("title", BalanceForGlyphs.ITEMS[ware.item].name)
	end
end
for _, pack in CurrencyForGlyphs.PACKS do
	need("title", pack.name)
	need("body", string.format("영석 %s개 %d 로벅스", CurrencyForGlyphs.format(pack.stones), pack.robux))
end
for _, kind in CombatForGlyphs.KIND_ORDER do
	need("body", CombatForGlyphs.KINDS[kind].summary)
	for grade = 1, #CombatForGlyphs.GRADES do
		local weapon = { kind = kind, grade = grade }
		need("title", CombatForGlyphs.weaponName(weapon))
		need("body", CombatForGlyphs.weaponName(weapon) .. " " .. CombatForGlyphs.GRADES[grade].prefix .. " 등급")
	end
end
for _, file in { "src/client/ShopWindow.luau", "src/client/TravelMenu.luau", "src/client/Hud.luau" } do
	local source = string.gsub(fs.readFile(file), "%-%-[^\n]*", "")
	for literal in string.gmatch(source, '"([^"\n]*)"') do
		if string.find(literal, "[\234-\237]") then
			need("body", (string.gsub(literal, "%%[%a%.%d]+", "")))
		end
	end
end
for key, text in missing do
	print(`  글자판에 없음 {key} ← "{text}"`)
end
assert(next(missing) == nil, "글자판에 없는 글자가 있다 — tools/fetch_fonts.py 부터 다시")
print("글자판 검사 통과")
