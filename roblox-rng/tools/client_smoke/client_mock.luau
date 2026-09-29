-- 가짜 Roblox(tools/roblox_mock.luau)에 클라이언트 쪽 흉내를 더함: 입력·카메라 광선·LocalPlayer·ChildAdded 등.
-- env.luau(스모크 테스트)와 tools/world_preview/edit_hook.luau(배치 모드 미리보기 렌더)가 같이 씀.
--
--   local install = compile(readfile("tools/client_smoke/client_mock.luau"), "tools/client_smoke/client_mock.luau")()
--   local C = install(Mock, Harness, { Viewport = Vector2.new(1280, 720), Inset = 36, Touch = false })
--
-- 더한 흉내(가짜 환경에 없거나 부르지 않는 것만):
--   Parent 바꾸기 -> 부모의 ChildAdded/ChildRemoved 발생(서버가 칸 모델을 다시 만드는 것을 클라이언트가 봄)
--   GUI Absolute*/CanvasPosition 기본값, LocalTransparencyModifier 기본값, Sound:Play, 마우스/터치 GUI 이벤트
--   UserInputService(입력 이벤트, GetMouseLocation), GuiService:GetGuiInset(상단바), TweenService(Play = 바로 끝 값)
--   카메라 ViewportSize · ViewportPointToRay, LocalPlayer + 캐릭터(HumanoidRootPart, Humanoid.Died)
--   하네스 노드(src/client)의 WaitForChild
-- 실제 로블록스와 다른 점: 화면 배치(AbsolutePosition 등)는 계산하지 않음, 렌더링·물리·스트리밍 없음,
--   task.wait 는 가짜 시계(Mock.runScheduler 로 진행), os.clock 은 진짜 시계(날아가는 연출 0.3초는 C.waitReal 로 기다림)

export type Options = {
	Viewport: Vector2?, -- 카메라 ViewportSize (기본 1280×720)
	Inset: number?, -- 상단바 높이(GuiService:GetGuiInset, 기본 36)
	Touch: boolean?, -- 터치 전용 기기(TouchEnabled, 키보드·마우스 없음)
	UserId: number?, -- LocalPlayer.UserId (기본 4242)
}

return function(Mock: any, Harness: any, options: Options?): any
	local opts: Options = options or {}
	local Signal = Mock.Signal
	local C: any = {}

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

	local touch = opts.Touch == true
	local UIS = game:GetService("UserInputService")
	for _, name in { "InputBegan", "InputChanged", "InputEnded", "LastInputTypeChanged" } do
		UIS.__props[name] = Signal.new()
	end
	UIS.__props.MouseEnabled = not touch
	UIS.__props.TouchEnabled = touch
	UIS.__props.KeyboardEnabled = not touch
	local viewport = opts.Viewport or Vector2.new(1280, 720)
	local mouse = viewport / 2
	UIS.__props.GetMouseLocation = function()
		return mouse
	end
	local INSET = Vector2.new(0, opts.Inset or 36)
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
	camera.ViewportSize = viewport
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
	-- 월드 점 -> 뷰포트 px(카메라 앞이 아니면 depth <= 0)
	local function toScreen(point: Vector3): (Vector2, number)
		local v = camera.CFrame:PointToObjectSpace(point)
		local depth = -v.Z
		local size = camera.ViewportSize
		local t = tanHalf()
		local nx = v.X / (depth * t * size.X / size.Y)
		local ny = v.Y / (depth * t)
		return Vector2.new((nx + 1) / 2 * size.X, (1 - ny) / 2 * size.Y), depth
	end
	-- Camera:WorldToViewportPoint -> (Vector3(x, y, 깊이), 화면 안인지)
	camera.__props.WorldToViewportPoint = function(_self, point: Vector3)
		local p, depth = toScreen(point)
		local size = camera.ViewportSize
		local inside = depth > 0 and p.X >= 0 and p.Y >= 0 and p.X <= size.X and p.Y <= size.Y
		return Vector3.new(p.X, p.Y, depth), inside
	end

	local Players = game:GetService("Players")
	local player = Instance.new("Player")
	player.Name = "Me"
	player.DisplayName = "나"
	player.UserId = opts.UserId or 4242
	local playerGui = Instance.new("PlayerGui")
	playerGui.Name = "PlayerGui"
	playerGui.Parent = player
	Players.__props.LocalPlayer = player

	local character = Instance.new("Model")
	character.Name = "Me"
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Size = Vector3.new(2, 2, 1)
	root.CanCollide = false
	root.CanQuery = false
	root.Parent = character
	local humanoid = Instance.new("Humanoid")
	humanoid.Name = "Humanoid"
	humanoid.__props.Died = Signal.new()
	humanoid.Parent = character
	character.Parent = workspace
	player.Character = character

	-- 하네스 노드(src/client)에 WaitForChild
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

	-- 입력 도우미 ------------------------------------------------------------------------
	local RunService = game:GetService("RunService")
	local function frame(dt: number?)
		RunService.RenderStepped:Fire(dt or 1 / 60)
	end
	local function waitReal(seconds: number)
		local start = os.clock()
		while os.clock() - start < seconds do
		end
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
	-- 터치 끌기. hold = true 면 손을 떼지 않고 멈춤(반환한 InputObject 로 나중에 InputEnded)
	local function touchDrag(from: Vector2, to: Vector2, hold: boolean?)
		local t = input("Touch", from)
		UIS.InputBegan:Fire(t, false)
		frame()
		t.Position = Vector3.new((from.X + to.X) / 2 - INSET.X, (from.Y + to.Y) / 2 - INSET.Y, 0)
		UIS.InputChanged:Fire(t, false)
		frame()
		t.Position = Vector3.new(to.X - INSET.X, to.Y - INSET.Y, 0)
		UIS.InputChanged:Fire(t, false)
		frame()
		if not hold then
			UIS.InputEnded:Fire(t, false)
			frame()
		end
		return t
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

	C.Signal = Signal
	C.UIS, C.camera, C.INSET = UIS, camera, INSET
	C.player, C.playerGui, C.character, C.root, C.humanoid = player, playerGui, character, root, humanoid
	C.client = client
	C.toScreen, C.input, C.frame, C.waitReal = toScreen, input, frame, waitReal
	C.mouseTo, C.click, C.drag, C.rightClick, C.key = mouseTo, click, drag, rightClick, key
	C.touchDrag, C.tap, C.face = touchDrag, tap, face
	C.cameraTweens = cameraTweens
	function C.mouse(): Vector2
		return mouse
	end
	return C
end
