-- 화면 UI 를 Lune 의 Roblox 인스턴스로 실제로 만들어 본다.   실행: lune run tests/hud
--
-- Lune 은 속성 이름·타입을 Roblox 반영 DB 로 검사하므로, 잘못된 속성이 있으면 여기서 터진다.
-- 이벤트·트윈·입력 서비스는 Lune 에 없어서 가짜로 넣는다.

local roblox = require("@lune/roblox") :: any
local task = require("@lune/task")
local Harness = require("./harness")

-- 가짜 신호 ------------------------------------------------------------------------

local function fakeSignal()
	return {
		Connect = function()
			return { Disconnect = function() end }
		end,
	}
end

local EVENTS = {
	Activated = true,
	MouseButton1Down = true,
	MouseButton1Up = true,
	MouseLeave = true,
	MouseEnter = true,
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
				return fakeSignal()
			end
			if key == "GetPropertyChangedSignal" then
				return function()
					return fakeSignal()
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
local services = {
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
			for key, value in goal do
				unwrap(target)[key] = value
			end
			return {
				Play = function()
					tweensPlayed += 1
				end,
				Cancel = function() end,
			}
		end,
	},
	UserInputService = { KeyboardEnabled = true, TouchEnabled = false },
	Workspace = { CurrentCamera = nil },
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
Hud.build({ meditate = noop, breakthrough = noop, buyInsight = noop })

local function state(overrides)
	local s = {
		step = 5,
		qi = 120,
		req = 300,
		gain = 4.5,
		meditating = false,
		veinId = nil,
		veinBlocked = nil,
		breakChance = nil,
		enlightenment = 0,
		insights = {},
		martialExp = 0,
		maxHealth = 125,
		tribulation = nil,
		canSave = true,
	}
	for k, v in overrides or {} do
		s[k] = v
	end
	return s
end

local cases = {
	{ "기본", state() },
	{ "운기 중 + 영맥", state({ meditating = true, veinId = "low" }) },
	{ "영맥 경지 부족", state({ veinBlocked = "mid" }) },
	{ "병목 돌파", state({ step = 16, qi = 999, req = 999, breakChance = 0.8 }) },
	{ "병목 천겁", state({ step = 44, qi = 999, req = 999 }) },
	{
		"천겁 모이는 중",
		state({ step = 44, qi = 999, req = 999, tribulation = { name = "천겁", wave = 0, waves = 9 } }),
	},
	{
		"천겁 진행",
		state({ step = 44, qi = 999, req = 999, tribulation = { name = "천겁", wave = 3, waves = 9 } }),
	},
	{ "천겁 끝", state({ step = 45 }) },
	{ "깨달음 살 수 있음", state({ enlightenment = 50, insights = { gongbeop = 3 } }) },
	{ "깨달음 완성", state({ enlightenment = 5, insights = { geobun = 10 } }) },
	{ "무공 최고", state({ martialExp = 1e6 }) },
	{ "최고 경지", state({ step = 81, qi = 1e12, req = 1e12 }) },
}
for _, case in cases do
	local ok, err = pcall(Hud.update, case[2])
	if not ok then
		error(`갱신 실패 [{case[1]}]: {err}`)
	end
end

Hud.togglePanel()
Hud.togglePanel(false)
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
local feed = hud:FindFirstChild("Feed")
local lines = 0
for _, child in feed:GetChildren() do
	if child:IsA("TextLabel") then
		lines += 1
	end
end
assert(lines <= 4, `알림이 {lines}줄 남았다 (최대 4)`)
assert(playerGui:FindFirstChild("BlockSuseonCinematic"), "연출 ScreenGui 가 없다")

local count = 0
for _, _ in hud:GetDescendants() do
	count += 1
end
print(`HUD 통과 · 인스턴스 {count}개 · 트윈 {tweensPlayed}회 · 상태 {#cases}가지`)
