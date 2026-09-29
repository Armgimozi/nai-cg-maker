-- 클라이언트 스모크 테스트 공용 환경: 가짜 Roblox(tools/roblox_mock.luau)에 클라이언트 쪽 흉내를 더하고
-- 진짜 ParkService(서버)로 내 부지를 만든 뒤 입력·화면 도우미를 돌려줌. Studio 없이 3D 배치 모드를 돌려 보는 용도.
--
-- 사용법(roblox-rng 폴더에서): luaurun tools/client_smoke/parkedit.luau / luaurun tools/client_smoke/init.luau
--   local E = compile(readfile("tools/client_smoke/env.luau"), "tools/client_smoke/env.luau")()
--
-- 클라이언트 흉내(입력·카메라·LocalPlayer·ChildAdded 등)는 client_mock.luau — 여기서는 1280×720, 상단바 36.
-- task.wait 는 가짜 시계(E.Mock.runScheduler 로 진행), os.clock 은 진짜 시계(날아가는 연출 0.3초는 E.waitReal 로 기다림)

local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()
local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()
local Signal = Mock.Signal
local installClient = compile(readfile("tools/client_smoke/client_mock.luau"), "tools/client_smoke/client_mock.luau")()
local C = installClient(Mock, Harness, { Viewport = Vector2.new(1280, 720), Inset = 36 })

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

local UIS, camera, INSET = C.UIS, C.camera, C.INSET
local player, playerGui, character, root, humanoid = C.player, C.playerGui, C.character, C.root, C.humanoid
local toScreen, input, frame, waitReal = C.toScreen, C.input, C.frame, C.waitReal
local mouseTo, click, drag, rightClick, key = C.mouseTo, C.click, C.drag, C.rightClick, C.key
local touchDrag, tap, face = C.touchDrag, C.tap, C.face
local cameraTweens = C.cameraTweens

local shared = Harness.folder("src/shared")
local server = Harness.folder("src/server")
local client = C.client
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
-- 날아가는 연출(0.3초)이 끝나고 제자리를 맞출 때까지
local function settle()
	waitReal(0.36)
	frame()
	frame()
end
-- 칸 가운데(받침대 윗면 위 height)의 화면 자리(뷰포트 px)
local function slotScreen(slot: number, height: number?): Vector2
	local x, z = ParkGrid.slotOffset(slot)
	return (toScreen(origin:PointToWorldSpace(Vector3.new(x, ParkGrid.BASE_TOP + (height or 0.6), z))))
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
E.mouse = C.mouse
return E
