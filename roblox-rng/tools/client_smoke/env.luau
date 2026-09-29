-- 클라이언트 스모크 테스트 공용 환경: 가짜 Roblox(tools/roblox_mock.luau)에 클라이언트 쪽 흉내를 더하고
-- 진짜 ParkService(서버)로 내 부지를 만든 뒤 입력·화면 도우미를 돌려줌. Studio 없이 3D 배치 모드를 돌려 보는 용도.
--
-- 사용법(roblox-rng 폴더에서): luaurun tools/client_smoke/parkedit.luau / luaurun tools/client_smoke/init.luau
--   local E = compile(readfile("tools/client_smoke/env.luau"), "tools/client_smoke/env.luau")()
--
-- 더한 흉내(가짜 환경에 없거나 부르지 않는 것만):
--   Parent 바꾸기 -> 부모의 ChildAdded/ChildRemoved 발생(서버가 칸 모델을 다시 만드는 것을 클라이언트가 봄)
--   GUI Absolute*/CanvasPosition 기본값, LocalTransparencyModifier 기본값, Sound:Play, 마우스/터치 GUI 이벤트
--   UserInputService(입력 이벤트, GetMouseLocation), GuiService:GetGuiInset(상단바 36), TweenService(Play = 바로 끝 값)
--   카메라 ViewportSize 1280×720 · ViewportPointToRay, LocalPlayer + 캐릭터(HumanoidRootPart, Humanoid.Died)
--   하네스 노드(src/client)의 WaitForChild
-- 실제 로블록스와 다른 점: 화면 배치(AbsolutePosition 등)는 계산하지 않음, 렌더링·물리·스트리밍 없음,
--   task.wait 는 가짜 시계(E.Mock.runScheduler 로 진행), os.clock 은 진짜 시계(날아가는 연출 0.3초는 E.waitReal 로 기다림)

local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()
local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()
local Signal = Mock.Signal

local E: any = {}
local failures = 0
function E.check(cond: any, label: string)
	if cond then
		print("  ok   " .. label)
	else
		failures += 1
		print("  FAIL " .. label)
	end
end
function E.finish(): boolean
	E.check(#Mock.errors == 0, "task 오류 없음 (" .. #Mock.errors .. ")")
	for _, message in Mock.errors do
		print(message)
	end
	print(string.format("\n%d failed", failures))
	return failures == 0
end

-- 1) 가짜 환경 보강 ------------------------------------------------------------------
local IMT = getmetatable(workspace)
local oldNewIndex = IMT.__newindex
IMT.__newindex = function(self, k, v)
	if k == "Parent" then
		local old = self.__props.Parent
		oldNewIndex(self, k, v)
		if old ~= v then
			if old and rawget(old.__props, "ChildRemoved") then
				old.__props.ChildRemoved:Fire(self)
			end
			if v and rawget(v.__props, "ChildAdded") then
				v.__props.ChildAdded:Fire(self)
			end
		end
		return
	end
	oldNewIndex(self, k, v)
end
local oldIndex = IMT.__index
local EXTRA_EVENTS = {
	MouseButton1Up = true,
	MouseEnter = true,
	MouseLeave = true,
	MouseButton2Click = true,
	InputBegan = true,
	InputEnded = true,
	InputChanged = true,
	Died = true,
	CharacterAdded = true,
	CharacterRemoving = true,
	OnClientEvent = true,
	PromptGamePassPurchaseFinished = true,
	PromptProductPurchaseFinished = true,
}
IMT.__index = function(self, k)
	local v = oldIndex(self, k)
	if v == nil then
		if k == "AbsolutePosition" or k == "CanvasPosition" then
			return Vector2.new(0, 0)
		elseif k == "AbsoluteSize" or k == "AbsoluteWindowSize" then
			return Vector2.new(600, 100)
		elseif k == "LocalTransparencyModifier" then
			return 0
		elseif k == "Play" or k == "Stop" or k == "Pause" then
			return function() end
		elseif EXTRA_EVENTS[k] then
			local signal = Signal.new()
			self.__props[k] = signal
			return signal
		end
	end
	return v
end

local UIS = game:GetService("UserInputService")
for _, name in { "InputBegan", "InputChanged", "InputEnded", "LastInputTypeChanged" } do
	UIS.__props[name] = Signal.new()
end
UIS.__props.MouseEnabled = true
UIS.__props.TouchEnabled = false
UIS.__props.KeyboardEnabled = true
local mouse = Vector2.new(640, 360)
UIS.__props.GetMouseLocation = function()
	return mouse
end
local INSET = Vector2.new(0, 36)
game:GetService("GuiService").__props.GetGuiInset = function()
	return INSET, Vector2.new(0, 0)
end
local TweenService = game:GetService("TweenService")
local cameraTweens: { { From: any, To: any } } = {} -- 카메라 트윈 기록(시작 자리 = 만들 때 카메라 자리)
TweenService.__props.Create = function(_self, instance, _info, goals)
	local completed = Signal.new()
	if instance == workspace.CurrentCamera and goals.CFrame then
		table.insert(cameraTweens, { From = instance.CFrame, To = goals.CFrame })
	end
	return {
		Completed = completed,
		Play = function()
			for key, value in goals do
				instance[key] = value
			end
			completed:Fire("Completed")
		end,
		Cancel = function() end,
		Pause = function() end,
		Destroy = function() end,
	}
end

-- 가짜 환경의 GetTagged 는 서비스 자신(CollectionService.HasTag 를 덮어쓴 표)까지 훑다가 멈춤 -> 태그 모형 없음으로
game:GetService("CollectionService").__props.GetTagged = function()
	return {}
end

local camera = workspace.CurrentCamera
camera.ViewportSize = Vector2.new(1280, 720)
camera.CameraType = Enum.CameraType.Custom
local function tanHalf()
	return math.tan(math.rad(camera.FieldOfView) / 2)
end
camera.__props.ViewportPointToRay = function(self, x, y)
	local cf = self.CFrame
	local size = self.ViewportSize
	local nx = x / size.X * 2 - 1
	local ny = 1 - y / size.Y * 2
	local t = tanHalf()
	local dir = (cf.LookVector + cf.RightVector * (nx * t * size.X / size.Y) + cf.UpVector * (ny * t)).Unit
	return { Origin = cf.Position, Direction = dir }
end
local function toScreen(point: Vector3): Vector2
	local v = camera.CFrame:PointToObjectSpace(point)
	local depth = -v.Z
	local size = camera.ViewportSize
	local t = tanHalf()
	local nx = v.X / (depth * t * size.X / size.Y)
	local ny = v.Y / (depth * t)
	return Vector2.new((nx + 1) / 2 * size.X, (1 - ny) / 2 * size.Y)
end

local Players = game:GetService("Players")
local player = Instance.new("Player")
player.Name = "Me"
player.DisplayName = "나"
player.UserId = 4242
local playerGui = Instance.new("PlayerGui")
playerGui.Name = "PlayerGui"
playerGui.Parent = player
Players.__props.LocalPlayer = player

local character = Instance.new("Model")
character.Name = "Me"
local root = Instance.new("Part")
root.Name = "HumanoidRootPart"
root.Size = Vector3.new(2, 2, 1)
root.CanQuery = false
root.Parent = character
local humanoid = Instance.new("Humanoid")
humanoid.Name = "Humanoid"
humanoid.__props.Died = Signal.new()
humanoid.Parent = character
character.Parent = workspace
player.Character = character

-- 하네스 노드(src/client)에 WaitForChild
local shared = Harness.folder("src/shared")
local server = Harness.folder("src/server")
local client = Harness.folder("src/client")
local nodeMeta = getmetatable(client)
local oldNodeIndex = nodeMeta.__index
nodeMeta.__index = function(self, key)
	if key == "WaitForChild" then
		return function(this, name)
			return this[name]
		end
	end
	return oldNodeIndex(self, key)
end
Mock.link(Mock.ReplicatedStorage, "Shared", shared)

-- 서버: 내 부지 + 명소 16개(공원 확장 Lv 3 = 15칸 열림, 자동 배치) -------------------------------
local PlayerState = Harness.require(shared.PlayerState)
local Landmarks = Harness.require(shared.Landmarks)
local ParkGrid = Harness.require(shared.ParkGrid)
local ParkService = Harness.require(server.ParkService)

local serverPlayer = { Name = "Me", DisplayName = "나", UserId = 4242 }
local data = PlayerState.new()
data.Upgrades.Park = 3
local owned = 0
for _, landmark in Landmarks.RarestFirst do
	if owned >= 16 then
		break
	end
	owned += 1
	data.Inventory[landmark.Id] = 5
	data.Discovered[landmark.Id] = true
end
local built, buildError = Mock.run(function()
	ParkService.init()
	ParkService.assign(serverPlayer)
	ParkService.update(serverPlayer, data)
end)
assert(built, buildError)
local plot
for _, model in workspace.Parks:GetChildren() do
	if model:GetAttribute("OwnerUserId") == player.UserId then
		plot = model
	end
end
assert(plot, "내 부지")
local origin: CFrame = plot:GetAttribute("Origin")

-- 도우미 ----------------------------------------------------------------------------------------
local RunService = game:GetService("RunService")
local function frame(dt: number?)
	RunService.RenderStepped:Fire(dt or 1 / 60)
end
local function waitReal(seconds: number)
	local start = os.clock()
	while os.clock() - start < seconds do
	end
end
-- 날아가는 연출(0.3초)이 끝나고 제자리를 맞출 때까지
local function settle()
	waitReal(0.36)
	frame()
	frame()
end
-- 칸 가운데(받침대 윗면 위 height)의 화면 자리(뷰포트 px)
local function slotScreen(slot: number, height: number?): Vector2
	local x, z = ParkGrid.slotOffset(slot)
	return toScreen(origin:PointToWorldSpace(Vector3.new(x, ParkGrid.BASE_TOP + (height or 0.6), z)))
end
-- InputObject 흉내(Position 은 GUI 좌표 = 뷰포트 - 상단바)
local function input(kind: string, position: Vector2?, key: string?)
	local at = position or mouse
	return {
		UserInputType = "UserInputType." .. kind,
		KeyCode = "KeyCode." .. (key or "Unknown"),
		Position = Vector3.new(at.X - INSET.X, at.Y - INSET.Y, 0),
	}
end
local function mouseTo(at: Vector2)
	mouse = at
	UIS.InputChanged:Fire(input("MouseMovement", at), false)
	frame()
end
local function click(at: Vector2)
	mouseTo(at)
	UIS.InputBegan:Fire(input("MouseButton1", at), false)
	frame()
	UIS.InputEnded:Fire(input("MouseButton1", at), false)
	frame()
end
local function drag(from: Vector2, to: Vector2)
	mouseTo(from)
	UIS.InputBegan:Fire(input("MouseButton1", from), false)
	frame()
	mouseTo((from + to) / 2)
	mouseTo(to)
	UIS.InputEnded:Fire(input("MouseButton1", to), false)
	frame()
end
local function rightClick()
	UIS.InputBegan:Fire(input("MouseButton2", mouse), false)
	UIS.InputEnded:Fire(input("MouseButton2", mouse), false)
	frame()
end
local function key(name: string)
	UIS.InputBegan:Fire(input("Keyboard", nil, name), false)
	frame()
end
local function touchDrag(from: Vector2, to: Vector2)
	local t = input("Touch", from)
	UIS.InputBegan:Fire(t, false)
	frame()
	t.Position = Vector3.new((from.X + to.X) / 2 - INSET.X, (from.Y + to.Y) / 2 - INSET.Y, 0)
	UIS.InputChanged:Fire(t, false)
	frame()
	t.Position = Vector3.new(to.X - INSET.X, to.Y - INSET.Y, 0)
	UIS.InputChanged:Fire(t, false)
	frame()
	UIS.InputEnded:Fire(t, false)
	frame()
end
local function tap(at: Vector2)
	local t = input("Touch", at)
	UIS.InputBegan:Fire(t, false)
	frame()
	UIS.InputEnded:Fire(t, false)
	frame()
end
-- 버튼(Ui.chunkyButton 은 Root 안 Face 가 눌리는 곳)
local function face(button: any): any
	return button:FindFirstChild("Face", true) or button
end

E.Harness, E.Mock, E.Signal = Harness, Mock, Signal
E.UIS, E.camera, E.INSET = UIS, camera, INSET
E.player, E.playerGui, E.character, E.root, E.humanoid = player, playerGui, character, root, humanoid
E.shared, E.server, E.client = shared, server, client
E.PlayerState, E.Landmarks, E.ParkGrid, E.ParkService = PlayerState, Landmarks, ParkGrid, ParkService
E.serverPlayer, E.data, E.plot, E.origin = serverPlayer, data, plot, origin
E.slotsFolder = plot:FindFirstChild("Slots")
E.toScreen, E.slotScreen, E.input, E.frame, E.waitReal, E.settle = toScreen, slotScreen, input, frame, waitReal, settle
E.mouseTo, E.click, E.drag, E.rightClick, E.key = mouseTo, click, drag, rightClick, key
E.touchDrag, E.tap, E.face = touchDrag, tap, face
E.cameraTweens = cameraTweens
function E.mouse(): Vector2
	return mouse
end
return E
