-- HUD 를 Lune 의 Roblox 인스턴스로 짓는 가짜 환경. tests/hud.luau 와 tools/gui_snapshot.luau 가 함께 쓴다.
--
--     local HudEnv = require("./hud_env")
--     local env = HudEnv.new({ viewport = Vector2.new(1920, 1080) })
--     local Hud = env.loader.require(env.clientFolder.Hud)
--
-- Lune 은 속성 이름·타입을 Roblox 반영 DB 로 검사하므로, 잘못된 속성이 있으면 여기서 터진다.
-- 이벤트·트윈·입력 서비스는 Lune 에 없어서 가짜로 넣는다.

local roblox = require("@lune/roblox") :: any
local task = require("@lune/task")
local Harness = require("./harness")

local HudEnv = {}

export type Options = {
	keyboard: boolean?, -- UserInputService.KeyboardEnabled (기본 true)
	touch: boolean?, -- UserInputService.TouchEnabled (기본 false)
	-- 주면 Workspace.CurrentCamera 에 그 ViewportSize 를 가진 가짜 카메라를 둔다.
	-- 없으면 CurrentCamera 는 nil 이고, Hud 는 화면을 1280×720 으로 본다
	viewport: any?,
	displayName: string?, -- Players.LocalPlayer.DisplayName
}

function HudEnv.new(options: Options?)
	local opts: { [string]: any } = options or {}

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

	local counts = { tweens = 0 } -- 재생한 트윈 수
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

	-- 화면 크기를 주면 가짜 카메라. Hud 는 ViewportSize 로 창 크기(UIScale)를 정한다
	local camera = nil
	if opts.viewport then
		local cameraKey = {}
		camera = {
			ViewportSize = opts.viewport,
			CFrame = roblox.CFrame.new(),
			GetPropertyChangedSignal = function(_, property)
				return fakeSignal(cameraKey, "Changed:" .. property)
			end,
		}
	end

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
				DisplayName = opts.displayName,
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
						counts.tweens += 1
					end,
					Cancel = function() end,
				}
			end,
		},
		UserInputService = {
			KeyboardEnabled = if opts.keyboard == nil then true else opts.keyboard,
			TouchEnabled = opts.touch == true,
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
			CurrentCamera = camera,
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

	local globals = Harness.robloxGlobals(real)
	globals.game = game
	globals.Instance = {
		new = function(className)
			return wrap(roblox.Instance.new(className))
		end,
	}
	globals.TweenInfo = {
		new = function(...)
			return { ... }
		end,
	}
	globals.typeof = function(value)
		-- 감싼 인스턴스도 인스턴스로 본다
		if type(value) == "table" and rawget(value, "__inst") then
			return "Instance"
		end
		return typeof(value)
	end
	globals.task = task

	local loader = Harness.new(globals)
	-- Hud 가 require 하는 shared 모듈도 같은 로더로 불러야 하므로 shared 폴더를 로더 것으로 바꾼다
	sharedFolder = loader.folder("src/shared")

	return {
		roblox = roblox,
		real = real, -- 진짜 DataModel (Lighting, Workspace 에 인스턴스를 둘 때)
		playerGui = playerGui, -- 진짜 Folder. Hud 의 ScreenGui 들이 여기 붙는다
		services = services,
		game = game,
		globals = globals,
		camera = camera,
		loader = loader,
		sharedFolder = sharedFolder,
		clientFolder = loader.folder("src/client"),
		fire = fire, -- fire(인스턴스, "Activated") 로 연결된 콜백을 부른다
		wrap = wrap,
		unwrap = unwrap,
		tagged = tagged,
		purchases = purchases,
		chatMessages = chatMessages,
		heartbeatKey = heartbeatKey, -- fire(heartbeatKey, "Heartbeat", dt)
		counts = counts,
	}
end

return HudEnv
