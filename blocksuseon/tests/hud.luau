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
	CollectionService = {
		GetTagged = function()
			return {}
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
	RunService = { Heartbeat = fakeSignal(heartbeatKey, "Heartbeat") },
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
env.typeof = typeof
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
		{ id = "wp_yeonguk", name = "연국", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = false },
	},
}))
-- 맵의 전송진이 모두 창에 들어간다
do
	local many = {}
	for i = 1, 13 do
		table.insert(many, { id = "wp_" .. i, name = "연국", open = true })
	end
	Hud.update(state({ waypoints = many }))
	Hud.openTravel("wp_1")
	local shown = 0
	for _, item in playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("TravelMenu"):GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			shown += 1
		end
	end
	assert(shown == 13, `전송진 {shown}개만 보인다 (13)`)
	Hud.closeTravel()
end
Hud.update(state({
	waypoints = {
		{ id = "wp_yeonguk", name = "연국", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = false },
	},
}))
Hud.openTravel("wp_yeonguk")
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

-- 땅 이름 띄우기
loader.require(loader.folder("src/client").PlaceBanner).show("영초숲", "영초와 천년영지가 돋는 숲")

-- 현판: 판자 겉면에 붓글씨 글자를 붙인다 (가로, 세로)
do
	local Plaques = loader.require(loader.folder("src/client").Plaques)
	for _, case in
		{ { "연국", false, roblox.Vector3.new(8, 3, 0.6) }, { "천겁대", true, roblox.Vector3.new(3, 10, 1.2) } }
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
		{ "order", { items = { "금단이 맺힌 날", "영근이 깨어난 날", "연국에 처음 온 날" } } },
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
-- 서버가 보내는 알림 문구 (화면에 글자판으로 찍는다)
local fs = require("@lune/fs")
for _, file in fs.readDir("src/server") do
	local source = fs.readFile("src/server/" .. file)
	source = string.gsub(source, "%-%-[^\n]*", "")
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
