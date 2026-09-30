-- world.luau hook: 맵 위에 "내 공원"을 하나 더 배정하고 진짜 클라이언트 IncomeFx(수입 보이기)를 돌려서, 목업 수입 화면
-- (mockup/src/app.js 의 income_preview · income_preview_p)과 같은 상태·같은 화면 크기의 공원 장면을 만듦.
-- 렌더러는 BillboardGui(전시 이름표·동전 퐁)를 그리지 않으므로, 돌려주는 표(extra)에 목업이 얹어 그릴 값을 넣음:
--   이름표(칸 위 BillboardGui: 화면 자리·스터드당 px·이름·별·수입 글자·등급 색), 지금 떠 있는 동전 퐁(IncomeFx 빌보드: 화면 자리·
--   크기·글자·투명도·배율), 날아갈 동전 출발점(화면에 보이는 내 명소, 수입 큰 순서), 초당 수입 합(= 이름표 합 = HUD).
-- 입구 간판(SurfaceGui: 이름 + 큰 [동전] "+X/s")은 렌더러가 그대로 그림.
--
-- 보통은 mockup/edit_backdrops.sh income_pc income_phone667 이 부름:
--   HOOK=tools/world_preview/income_hook.luau HOOK_ARGS="income=pc" VIEWS=hook PREVIEW_SIZE=1280x720 \
--     tools/world_preview/preview.sh <출력 폴더> - income_pc
-- income=pc | phone667 (아래 SCENARIOS). 상태는 목업 STATE(자동 배치 12칸, 입장료 Lv 4)와 같음.

local GUI_INSET = 58 -- 로블록스 기본 상단바(목업 GUI_INSET 과 같음)

type Scenario = {
	Viewport: Vector2,
	Touch: boolean,
	Eye: Vector3, -- 카메라 자리(부지 좌표: 중앙 바닥 원점, -Z = 입구)
	Target: Vector3,
	Fov: number,
	Seconds: number, -- IncomeFx 를 돌릴 시간(퐁이 여러 단계로 떠 있게)
}

local SCENARIOS: { [string]: Scenario } = {
	-- PC: 입구 앞 왼쪽 위에서 공원 안을 비스듬히 봄 — 왼쪽에 입구 간판(초당 수입 합), 오른쪽에 전시 명소와 이름표
	pc = {
		Viewport = Vector2.new(1280, 720),
		Touch = false,
		Eye = Vector3.new(-26, 24, -64),
		Target = Vector3.new(10, 0, -14),
		Fov = 70,
		Seconds = 3.4,
	},
	-- 휴대폰 667×375: 같은 자리(화면 비율이 같아 같은 구도, HUD 만 배율 0.55)
	phone667 = {
		Viewport = Vector2.new(667, 375),
		Touch = true,
		Eye = Vector3.new(-26, 24, -64),
		Target = Vector3.new(10, 0, -14),
		Fov = 70,
		Seconds = 3.4,
	},
}

local function vec(v: Vector3): { number }
	return { v.X, v.Y, v.Z }
end

return function(ctx: any): any
	local Mock, Harness, shared, server, opts = ctx.Mock, ctx.Harness, ctx.shared, ctx.server, ctx.opts
	local name = opts.income or "pc"
	local scenario = SCENARIOS[name]
	assert(scenario, "income= 는 pc | phone667: " .. tostring(opts.income))
	-- 시점 고르기용: eye=x,y,z target=x,y,z (부지 좌표)로 장면 카메라를 바꿔 볼 수 있음
	local function parseVec(text: string?): Vector3?
		local x, y, z = (text or ""):match("^([%-%d%.]+),([%-%d%.]+),([%-%d%.]+)$")
		return if x then Vector3.new(tonumber(x) :: number, tonumber(y) :: number, tonumber(z) :: number) else nil
	end
	scenario = table.clone(scenario)
	scenario.Eye = parseVec(opts.eye) or scenario.Eye
	scenario.Target = parseVec(opts.target) or scenario.Target

	local installClient =
		compile(readfile("tools/client_smoke/client_mock.luau"), "tools/client_smoke/client_mock.luau")()
	local C = installClient(Mock, Harness, {
		Viewport = scenario.Viewport,
		Inset = GUI_INSET,
		Touch = scenario.Touch,
		UserId = 4242,
	})

	local PlayerState = Harness.require(shared.PlayerState)
	local Landmarks = Harness.require(shared.Landmarks)
	local ParkService = Harness.require(server.ParkService)

	-- 목업 STATE 와 같은 상태(edit_hook.luau baseState 와 같음)
	local data = PlayerState.new()
	data.Rolls = 3214
	data.Coins = 4832
	for id, count in
		{
			clocktower = 1020,
			lighthouse = 690,
			windmill = 410,
			fountain = 300,
			arc = 170,
			bigben = 98,
			sungnyemun = 71,
			pisa = 44,
			liberty = 31,
			namsan = 18,
			eiffel = 9,
			colosseum = 6,
			tajmahal = 3,
			angkor = 2,
			sphinx = 12,
			pyramid = 4,
			greatwall = 4,
			alexandria = 1,
			machupicchu = 1,
			harbourbridge = 520,
			skytower = 60,
			apostles = 7,
		}
	do
		assert(Landmarks.ById[id], "명소 Id " .. id)
		data.Inventory[id] = count
		data.Discovered[id] = true
	end
	data.Featured = "alexandria"
	data.Upgrades.Globe, data.Upgrades.Agency, data.Upgrades.Park, data.Upgrades.Ticket = 4, 10, 2, 4
	data.Settings.AutoFeature = true

	-- 서버: 내 부지 ----------------------------------------------------------------------------------
	local serverPlayer = { Name = "Me", DisplayName = "나", UserId = 4242 }
	ParkService.assign(serverPlayer)
	ParkService.update(serverPlayer, data)
	local plot
	for _, model in workspace.Parks:GetChildren() do
		if model:GetAttribute("OwnerUserId") == 4242 then
			plot = model
		end
	end
	assert(plot, "내 부지")
	local origin: CFrame = plot:GetAttribute("Origin")
	C.root.CFrame = origin * CFrame.new(0, 3.6, -52) -- 입구 앞(그림에는 안 그림)
	C.root.Transparency = 1

	local camera = workspace.CurrentCamera
	camera.FieldOfView = scenario.Fov
	camera.CFrame = CFrame.lookAt(origin:PointToWorldSpace(scenario.Eye), origin:PointToWorldSpace(scenario.Target))

	-- 클라이언트: 진짜 IncomeFx(퐁 빌보드를 돌려 씀). 날아가는 동전은 목업이 HUD 코인 알약 자리에 맞춰 그림 -----------------
	local Ui = Harness.require(C.client.Ui)
	local IncomeFx = Harness.require(C.client.IncomeFx)
	IncomeFx.init(C.playerGui, {
		CoinTarget = function()
			return nil -- 날리기는 목업이(HUD 는 목업이 그림)
		end,
		Bump = function() end,
		Editing = function()
			return false
		end,
		Covered = function()
			return false
		end,
	})
	IncomeFx.setPlot(plot)
	Mock.runScheduler(Mock.clock() + 0.5)
	-- (가짜 환경의 Random.new() 는 늘 같은 수열이라 퐁 자리·차례도 늘 같음). 퐁이 여럿 떠 있는 순간에서 멈춤
	for _ = 1, math.floor(scenario.Seconds * 30) do
		C.frame(1 / 30)
	end
	for _ = 1, 6 * 30 do
		if IncomeFx.stats().Pops >= 5 then
			break
		end
		C.frame(1 / 30)
	end

	local cf = camera.CFrame
	local t = math.tan(math.rad(camera.FieldOfView) / 2)
	local function screenOf(point: Vector3): { number }?
		local p, depth = C.toScreen(point)
		if depth <= 0 then
			return nil
		end
		return { p.X, p.Y, depth }
	end
	local function pxPerStud(depth: number): number
		return scenario.Viewport.Y / (2 * t * depth)
	end

	-- 전시 이름표(칸 위 BillboardGui, 스터드 크기): 모든 부지, 카메라에서 MaxDistance 안이면 보임
	local labels = {}
	local total = PlayerState.incomePerSecond(data)
	for _, park in workspace.Parks:GetChildren() do
		local slots = park:FindFirstChild("Slots")
		for _, container in if slots then slots:GetChildren() else {} do
			local landmark = Landmarks.ById[container:GetAttribute("Look") or ""]
			local billboard = container:FindFirstChildWhichIsA("BillboardGui", true)
			if landmark and billboard and billboard.Enabled ~= false then
				local anchor = billboard.Adornee or billboard.Parent
				local point = if anchor.ClassName == "Attachment"
					then anchor.Parent.CFrame * anchor.Position
					else anchor.Position
				local distance = (point - cf.Position).Magnitude
				local screen = screenOf(point)
				local amount = billboard:FindFirstChild("Amount", true)
				local face = billboard:FindFirstChild("Income", true)
				if screen and distance <= (billboard.MaxDistance or math.huge) then
					table.insert(labels, {
						Mine = park == plot,
						Slot = container:GetAttribute("Slot"),
						Id = landmark.Id,
						Name = landmark.Name,
						Tier = landmark.Tier.Rank,
						Color = { landmark.Tier.Color.R, landmark.Tier.Color.G, landmark.Tier.Color.B },
						Stars = container:GetAttribute("Stars"),
						Income = container:GetAttribute("Income"),
						Amount = amount and amount.Text,
						AmountBox = if amount then { amount.Position.X.Scale, amount.Size.X.Scale } else nil,
						PillWidth = face and face.Size.X.Scale, -- 이름표 폭 비율
						Distance = distance,
						Screen = screen,
						PxPerStud = pxPerStud(screen[3]),
						Size = { billboard.Size.X.Scale, billboard.Size.Y.Scale },
					})
				end
			end
		end
	end
	table.sort(labels, function(a, b)
		return a.Distance > b.Distance -- 먼 것부터(가까운 이름표가 위에)
	end)

	-- 지금 떠 있는 동전 퐁(IncomeFx 빌보드)
	local pops = {}
	for _, gui in workspace:FindFirstChild("IncomeFx"):GetChildren() do
		if gui.ClassName == "BillboardGui" and gui.Enabled then
			local adornee = gui.Adornee
			local point = adornee.Position + gui.StudsOffsetWorldSpace
			local screen = screenOf(point)
			local text = gui:FindFirstChild("Amount", true)
			local scale = gui:FindFirstChild("Body"):FindFirstChildOfClass("UIScale")
			if screen then
				table.insert(pops, {
					Screen = screen,
					W = gui.Size.X.Offset,
					H = gui.Size.Y.Offset,
					Text = text.Text,
					TextSize = text.TextSize,
					Alpha = text.TextTransparency,
					Scale = if scale then scale.Scale else 1,
				})
			end
		end
	end

	-- 날아갈 동전 출발점: 화면에 보이는 내 명소(모형 60% 높이), 수입 큰 순서 — IncomeFx.flySources 와 같은 식
	local sources = {}
	for _, container in plot.Slots:GetChildren() do
		local income = container:GetAttribute("Income")
		local pedestal = container:FindFirstChild("Pedestal")
		if type(income) == "number" and income > 0 and pedestal then
			local top = container:GetAttribute("Top") or 4
			local point = pedestal.Position + Vector3.new(0, pedestal.Size.Y / 2 + top * 0.6, 0)
			local screen = screenOf(point)
			if
				screen
				and screen[1] >= 0
				and screen[1] <= scenario.Viewport.X
				and screen[2] >= 0
				and screen[2] <= scenario.Viewport.Y
			then
				table.insert(sources, { X = screen[1], Y = screen[2] - GUI_INSET, Income = income })
			end
		end
	end
	table.sort(sources, function(a, b)
		return a.Income > b.Income
	end)

	local stats = IncomeFx.stats()
	ctx.note(
		string.format(
			"수입 보이기(%s): 부지 %s, 이름표 %d개, 퐁 %d개(지금까지 %d), 출발점 %d곳, 초당 수입 %.1f",
			name,
			plot.Name,
			#labels,
			#pops,
			stats.PopsSpawned,
			#sources,
			total
		)
	)
	return {
		Scenario = name,
		Camera = {
			Position = vec(cf.Position),
			Look = vec(cf.LookVector),
			Up = vec(cf.UpVector),
			Fov = camera.FieldOfView,
		},
		Screen = { W = scenario.Viewport.X, H = scenario.Viewport.Y, Inset = GUI_INSET, Scale = Ui.scale() },
		Plot = plot.Name,
		Income = total,
		Labels = labels,
		Pops = pops,
		Sources = sources,
	}
end
