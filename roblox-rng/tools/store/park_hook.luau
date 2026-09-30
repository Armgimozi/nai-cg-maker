-- 스토어 썸네일 4(나만의 관광 공원) world.luau hook: stage_hook(다른 부지 채우기) + 내 부지에서 진짜 ParkEdit(3D 배치 모드).
--   * 다른 샘플 플레이어 부지는 stage_hook 의 fillParks 로 가득(진짜 ParkService.update 전시)
--   * 내 부지(UserId 4242): 무대 JSON 의 myPark 대로 명소를 직접 배치(빈 칸 하나 남김) → 진짜 ParkEdit.enter →
--     보관함 카드를 눌러 명소를 집고 빈 칸 위를 가리킴(반투명 복사본 + 빛나는 판 = 게임 화면 그대로)
--   * 배치 모드는 부지 간판을 숨기지만(hideSign) 썸네일에서는 수입 간판을 보여 주려고 다시 켬(간판 글자·수입은 진짜 값)
-- 무대 JSON(stage=<경로>, stage_hook 과 같은 파일) 에 더하는 것:
--   "myPark": { "level": 10, "display": { [칸 번호]: 명소 Id ... }, "storage": [명소 Id ...](보관함에만),
--               "pick": 집을 명소 Id(보관함), "target": 가리킬 칸 번호, "frames": 60, "name": "You", "counts": 1 }
--   counts = 전시 명소마다 보유 개수(없으면 칸마다 1~5). 1 = 처음 발견(☆0) = 등급 기본 수입
--   name = 내 간판 이름(영어 — 스토어 그림에는 한글을 넣지 않음)
-- 돌려주는 표(덤프 extra): 부지 Origin(CFrame 12값), 칸 가운데(월드), 칸 명소 Id, 들고 있는 명소, 간판 위치, 초당 수입,
--   칸마다 그 명소의 초당 수입(PlayerState.landmarkIncome — 썸네일 말풍선 "+N/s" 는 이 값을 그대로 씀)
-- 보통은 tools/store/thumbs.py(thumb_park)가 부름. Roblox API 호출·업로드 없음(가짜 환경).

local GUI_INSET = 58

local function vec(v: Vector3): { number }
	return { v.X, v.Y, v.Z }
end

local function cframeList(cf: CFrame): { number }
	local out = {}
	for _, v in { cf:GetComponents() } do
		table.insert(out, v)
	end
	return out
end

return function(ctx: any): any
	local Mock, Harness, shared, server, opts = ctx.Mock, ctx.Harness, ctx.shared, ctx.server, ctx.opts

	-- 1) 다른 부지 채우기(무대 모형·파트도 같이)
	local stageHook = compile(readfile("tools/store/stage_hook.luau"), "tools/store/stage_hook.luau")()
	stageHook(ctx)
	local stage = Mock.json.decode(readfile(opts.stage))
	local spec = stage.myPark
	assert(spec, "무대 JSON 에 myPark 가 없습니다")

	local installClient =
		compile(readfile("tools/client_smoke/client_mock.luau"), "tools/client_smoke/client_mock.luau")()
	local C = installClient(Mock, Harness, {
		Viewport = Vector2.new(1280, 720),
		Inset = GUI_INSET,
		Touch = false,
		UserId = 4242,
	})

	local PlayerState = Harness.require(shared.PlayerState)
	local Landmarks = Harness.require(shared.Landmarks)
	local ParkGrid = Harness.require(shared.ParkGrid)
	local ParkService = Harness.require(server.ParkService)

	-- 2) 내 상태: 직접 배치(칸 번호 -> 명소) + 보관함
	local data = PlayerState.new()
	data.Rolls = 5000
	data.Coins = 25000
	data.Upgrades.Park = spec.level or 10
	data.Settings.AutoPark = false
	data.Display = {}
	local function own(id: string, count: number)
		assert(Landmarks.ById[id], "없는 명소 id: " .. id)
		data.Inventory[id] = count
		data.Discovered[id] = true
	end
	for key, id in spec.display or {} do
		local slot = tonumber(key)
		-- counts = 보유 개수(1 이면 처음 발견 ☆0 = 명소 수입이 등급 기본값 Config.TIER_INCOME 그대로)
		own(id, spec.counts or (1 + (slot * 7) % 5))
		data.Display[slot] = id
	end
	for i, id in spec.storage or {} do
		own(id, 1 + i % 3)
	end

	local serverPlayer = { Name = "Me", DisplayName = spec.name or "You", UserId = 4242 }
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
	C.root.CFrame = origin * CFrame.new(0, 3.6, -45)
	C.root.Transparency = 1

	-- 3) 클라이언트 ParkEdit: 배치 모드 → 보관함 카드 톡 → 빈 칸 위를 가리킴
	local ParkEdit = Harness.require(C.client.ParkEdit)
	local gui = Instance.new("ScreenGui")
	gui.Name = "LandmarkRNG"
	gui.AbsoluteSize = Vector2.new(1280, 720 - GUI_INSET)
	gui.Parent = C.playerGui
	local revision = 0
	local function pushState()
		revision += 1
		ParkEdit.render(PlayerState.snapshot(data, revision))
	end
	ParkEdit.init(gui, {
		SetDisplay = function(slot, id, expected, from)
			local done, reason = PlayerState.setDisplay(data, slot, id, expected, from)
			if done then
				ParkService.update(serverPlayer, data)
			end
			pushState()
			return done, reason == "stale"
		end,
		SetAutoPark = function(on)
			local done = PlayerState.setSetting(data, "AutoPark", on)
			ParkService.update(serverPlayer, data)
			pushState()
			return done
		end,
		GoToPark = function()
			return true
		end,
		Toast = function() end,
		Changed = function() end,
	})
	pushState()
	ParkEdit.setPlot(plot)
	Mock.runScheduler(Mock.clock() + 1)
	ParkEdit.enter(nil)
	Mock.runScheduler(Mock.clock() + 0.1)
	assert(ParkEdit.isEditing(), "배치 모드에 들어가지 못했습니다")

	local bar = gui:FindFirstChild("ParkEditBar")
	local tray = bar:FindFirstChild("Tray")
	local picked = spec.pick
	if picked then
		local card = tray:FindFirstChild("Storage"):FindFirstChild(picked)
		assert(card, "보관함 카드 " .. tostring(picked))
		card.Activated:Fire()
		C.frame()
	end
	-- 빈 칸 위를 가리킴: 위에서 보기 카메라에서 앞줄 명소가 칸을 가리면 광선이 그 명소에 맞으므로, 칸 안 여러 점을
	-- 차례로 가리켜 들고 있는 명소(반투명 복사본)가 정말 그 칸 위로 가는 점을 씀(아니면 멈춤 — 그림이 틀리지 않게)
	local frames = spec.frames or 60
	if spec.target then
		local x, z = ParkGrid.slotOffset(spec.target)
		local goal = origin:PointToWorldSpace(Vector3.new(x, 0, z))
		local function ghostOnTarget(): boolean
			local folder = workspace:FindFirstChild("ParkEditLocal")
			local ghost = folder and folder:FindFirstChild(picked)
			if not ghost then
				return false
			end
			local p = ghost:GetPivot().Position
			return Vector2.new(p.X - goal.X, p.Z - goal.Z).Magnitude < 1.5
		end
		local ok = false
		for _, offset in { { 0, 0 }, { 0, -4 }, { 0, -5.5 }, { -3, -5 }, { 3, -5 }, { 0, 4 } } do
			local at =
				C.toScreen(origin:PointToWorldSpace(Vector3.new(x + offset[1], ParkGrid.BASE_TOP + 0.6, z + offset[2])))
			C.mouseTo(at)
			for _ = 1, frames do
				C.frame(1 / 60)
			end
			if ghostOnTarget() then
				ok = true
				break
			end
		end
		assert(ok, "들고 있는 명소가 칸 " .. tostring(spec.target) .. " 위로 가지 않았습니다")
	else
		for _ = 1, frames do
			C.frame(1 / 60)
		end
	end

	-- 4) 간판 다시 보이기(배치 모드는 숨김) — 썸네일에서 수입 간판을 보여 줌
	local sign = plot:FindFirstChild("Sign")
	local signPos = nil
	if sign then
		for _, d in sign:GetDescendants() do
			if d:IsA("BasePart") then
				d.LocalTransparencyModifier = 0
			elseif d:IsA("SurfaceGui") then
				d.Enabled = true
			end
		end
		local ok, cf = pcall(function()
			return sign:GetPivot()
		end)
		if ok then
			signPos = vec(cf.Position)
		end
	end

	local slots, unlocked = PlayerState.parkSlots(data)
	local slotWorld, slotIds = {}, {}
	for slot = 1, unlocked do
		local x, z = ParkGrid.slotOffset(slot)
		slotWorld[slot] = vec(origin:PointToWorldSpace(Vector3.new(x, ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT, z)))
		slotIds[slot] = slots[slot] or ""
	end
	local income = PlayerState.incomePerSecond(data)
	-- 칸마다 그 명소가 내는 초당 수입(게임 식 그대로): 명소 수입 × (입장료·환생·게임패스 배율 = 전체 수입 / 명소 합)
	local baseSum = 0
	for _, id in PlayerState.park(data) do
		baseSum += PlayerState.landmarkIncome(Landmarks.ById[id], data.Inventory[id])
	end
	local mult = if baseSum > 0 then income / baseSum else 1
	local slotIncome = {}
	for slot = 1, unlocked do
		local id = slots[slot]
		slotIncome[slot] = if id then PlayerState.landmarkIncome(Landmarks.ById[id], data.Inventory[id]) * mult else 0
	end
	-- 그려지는 간판 글자는 영어만(내 간판까지 만든 뒤 한 번 더)
	ctx.englishOnly()
	ctx.note(
		string.format(
			"내 부지 %s: 열린 칸 %d, 들고 있음 %s, 초당 수입 %s",
			plot.Name,
			unlocked,
			tostring(picked),
			tostring(income)
		)
	)
	return {
		Origin = cframeList(origin),
		Plot = plot.Name,
		SlotWorld = slotWorld,
		Slots = slotIds,
		Unlocked = unlocked,
		Held = picked,
		Target = spec.target,
		Sign = signPos,
		Income = income,
		SlotIncome = slotIncome,
	}
end
