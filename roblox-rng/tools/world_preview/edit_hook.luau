-- world.luau hook: 맵 위에 "내 공원"을 하나 더 배정하고 진짜 클라이언트 ParkEdit(3D 배치 모드)를 돌려서, 목업 6번대
-- (mockup/src/app.js 의 screen6 · 6c · 6p)와 같은 상태·같은 화면 크기의 배치 모드 장면을 만듦. 덤프에는 ParkEdit 가
-- 이 화면에서만 만든 것(빛나는 판·들고 있는 반투명 복사본·강조 Highlight, 숨긴 원래 명소)이 그대로 들어가고,
-- 돌려주는 표(extra)에는 배치 모드 카메라와 목업이 HUD 를 얹을 때 쓰는 값(이름표 화면 자리, 띠 자리, 칸 배치)이 들어감.
--
-- 보통은 mockup/edit_backdrops.sh 가 부름:
--   HOOK=tools/world_preview/edit_hook.luau HOOK_ARGS="edit=pc" VIEWS=hook PREVIEW_SIZE=1280x720 \
--     tools/world_preview/preview.sh <출력 폴더> - edit_pc
-- edit=pc | phone844 | phone667 (아래 SCENARIOS). 상태는 목업의 PARK_STATE / REBORN_STATE 와 같게 만듦
-- (목업 검사 항목이 extra.Slots · extra.Storage 를 목업 계산과 비교함).

local GUI_INSET = 58 -- 로블록스 기본 상단바(목업 GUI_INSET 과 같음)

type Scenario = {
	Viewport: Vector2,
	Touch: boolean,
	State: string, -- "park" | "reborn"
	Pick: string?, -- "slot1" = 1번 칸 명소를 눌러 집음, "storage" = 보관함 첫 "더 좋은" 카드를 톡
	Target: number?, -- 가리키는 칸(마우스 / 누르고 있는 손가락)
	Frames: number?, -- 가리킨 뒤 돌릴 프레임 수(1/60초) — 복사본이 따라가 붙고 조금 돎
}

local SCENARIOS: { [string]: Scenario } = {
	-- screen6: PC, 1번 칸(입구 정면) 명소를 집어 5번 칸(명소 있음 = 자리 바꿈) 위를 가리킴
	pc = { Viewport = Vector2.new(1280, 720), Touch = false, State = "park", Pick = "slot1", Target = 5, Frames = 34 },
	-- screen6c: 휴대폰 844×390, 환생 직후(빈 보관함), 아무것도 안 듦
	phone844 = { Viewport = Vector2.new(844, 390), Touch = true, State = "reborn" },
	-- screen6p: 휴대폰 667×375, 보관함 카드를 톡 눌러 집고 손가락을 3번 칸 위에 대고 있음
	phone667 = {
		Viewport = Vector2.new(667, 375),
		Touch = true,
		State = "park",
		Pick = "storage",
		Target = 3,
		Frames = 34,
	},
}

local function vec(v: Vector3): { number }
	return { v.X, v.Y, v.Z }
end

return function(ctx: any): any
	local Mock, Harness, shared, server, opts = ctx.Mock, ctx.Harness, ctx.shared, ctx.server, ctx.opts
	local name = opts.edit or "pc"
	local scenario = SCENARIOS[name]
	assert(scenario, "edit= 는 pc | phone844 | phone667: " .. tostring(opts.edit))

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
	local ParkGrid = Harness.require(shared.ParkGrid)
	local ParkService = Harness.require(server.ParkService)

	-- 목업 STATE / PARK_STATE / REBORN_STATE 와 같은 상태 ------------------------------------------
	local function baseState()
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
		return data
	end
	local data
	if scenario.State == "park" then
		-- 6번: 자동 배치에서 시작해 플린더스 스트리트 역을 1번 칸에, 알렉산드리아 등대를 2번 칸에(직접 배치)
		local autoSecond = (PlayerState.parkSlots(baseState()))[2]
		data = baseState()
		data.Inventory.flindersst = 35
		data.Discovered.flindersst = true
		data.Settings.AutoPark = true
		assert(PlayerState.setDisplay(data, 1, "flindersst"), "1번 칸")
		assert(PlayerState.setDisplay(data, 2, "alexandria", autoSecond), "2번 칸")
	else
		-- 6-3번: 환생 직후 — 보유 명소·업그레이드 없음, 자동 배치
		data = PlayerState.new()
		data.Rebirths = 1
		data.Rolls = 3214
		data.Settings.AutoFeature = true
		data.Settings.AutoPark = true
	end

	-- 서버: 내 부지(비어 있는 가장 작은 번호) -------------------------------------------------------
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
	-- 캐릭터: 부지 입구 안쪽(그림에는 안 그림 — 가짜 캐릭터는 상자 하나라서)
	C.root.CFrame = origin * CFrame.new(0, 3.6, -37)
	C.root.Transparency = 1

	-- 클라이언트: ParkEdit ------------------------------------------------------------------------
	local ParkEdit = Harness.require(C.client.ParkEdit)
	local Ui = Harness.require(C.client.Ui)
	local gui = Instance.new("ScreenGui")
	gui.Name = "LandmarkRNG"
	gui.AbsoluteSize = Vector2.new(scenario.Viewport.X, scenario.Viewport.Y - GUI_INSET)
	gui.Parent = C.playerGui
	local revision = 0
	local toasts: { string } = {}
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
		Toast = function(text)
			table.insert(toasts, text)
		end,
		Changed = function() end,
	})
	pushState()
	ParkEdit.setPlot(plot)
	Mock.runScheduler(Mock.clock() + 1)
	ParkEdit.enter(nil)
	Mock.runScheduler(Mock.clock() + 0.1)
	assert(ParkEdit.isEditing(), "배치 모드에 들어가지 못했습니다")

	-- 띠 자리(ParkEdit.layoutBar 가 정한 Position/Size + 자동 배율) -> 쟁반 Absolute*(overBar 판정)
	local bar = gui:FindFirstChild("ParkEditBar")
	local tray = bar:FindFirstChild("Tray")
	local scale = Ui.scale()
	local barWidth = bar.Size.X.Offset * scale
	local barHeight = bar.Size.Y.Offset * scale
	local barLeft = bar.Position.X.Offset - barWidth / 2
	local barTop = bar.Position.Y.Offset - barHeight
	tray.__props.AbsolutePosition = Vector2.new(barLeft, barTop)
	tray.__props.AbsoluteSize = Vector2.new(barWidth, barHeight)

	local function slotScreen(slot: number, height: number?): Vector2
		local x, z = ParkGrid.slotOffset(slot)
		return (C.toScreen(origin:PointToWorldSpace(Vector3.new(x, ParkGrid.BASE_TOP + (height or 0.6), z))))
	end

	local snapshot = PlayerState.snapshot(data, revision)
	local picked: string? = nil
	local from = 0
	if scenario.Pick == "slot1" then
		picked = (PlayerState.parkSlots(data))[1]
		from = 1
		C.click(slotScreen(1, 2))
	elseif scenario.Pick == "storage" then
		picked = PlayerState.betterHidden(snapshot)[1] or ParkGrid.storage(snapshot)[1]
		local card = tray:FindFirstChild("Storage"):FindFirstChild(picked)
		assert(card, "보관함 카드 " .. tostring(picked))
		card.Activated:Fire()
		C.frame()
	end
	if scenario.Target then
		local at = slotScreen(scenario.Target)
		if scenario.Touch then
			C.touchDrag(at + Vector2.new(24, 30), at, true) -- 손가락을 대고 끌어서 칸 위에 멈춤(떼지 않음)
		else
			C.mouseTo(at)
		end
	end
	for _ = 1, scenario.Frames or 4 do
		C.frame(1 / 60)
	end

	-- 목업이 HUD 를 얹을 때 쓰는 값 ----------------------------------------------------------------
	local camera = workspace.CurrentCamera
	local cf = camera.CFrame
	local function screenOf(point: Vector3): { number }?
		local p, depth = C.toScreen(point)
		if depth <= 0 then
			return nil
		end
		return { p.X, p.Y, depth }
	end
	-- 화면 이름표(ParkEdit setTag: ScreenGui 좌표, 아래 가운데가 기준)
	local tagInfo: any = nil
	local tagFrame = gui:FindFirstChild("ParkEditTag")
	if tagFrame and tagFrame.Visible then
		local chip = tagFrame:FindFirstChild("Name")
		local text = chip and chip:FindFirstChild("Label", true)
		local tagId: string? = nil
		for _, landmark in Landmarks.List do
			if text and landmark.Name == text.Text then
				tagId = landmark.Id
			end
		end
		tagInfo = { Id = tagId, X = tagFrame.Position.X.Offset, Y = tagFrame.Position.Y.Offset }
	end
	local heldInfo = if picked then { Id = picked, From = from } else nil
	-- 전시 이름표(칸 위 BillboardGui, 스터드 크기): 카메라에서 MaxDistance 안이면 보임
	local labels = {}
	local t = math.tan(math.rad(camera.FieldOfView) / 2)
	for _, container in plot.Slots:GetChildren() do
		for _, d in container:GetDescendants() do
			if d.ClassName == "BillboardGui" and d.Enabled ~= false then
				local anchor = d.Adornee or d.Parent
				local point = if anchor.ClassName == "Attachment"
					then anchor.Parent.CFrame * anchor.Position
					else anchor.Position
				local distance = (point - cf.Position).Magnitude
				local screen = screenOf(point)
				if screen then
					table.insert(labels, {
						Slot = container:GetAttribute("Slot"),
						Distance = distance,
						Visible = distance <= (d.MaxDistance or math.huge),
						Screen = screen,
						PxPerStud = scenario.Viewport.Y / (2 * t * screen[3]),
					})
				end
			end
		end
	end
	local slots, unlocked = PlayerState.parkSlots(data)
	local slotList = {}
	for slot = 1, unlocked do
		slotList[slot] = slots[slot] or ""
	end
	local slotScreens = {}
	for slot = 1, PlayerState.MAX_SLOTS do
		local p = slotScreen(slot)
		slotScreens[slot] = { p.X, p.Y }
	end
	ctx.note(
		string.format(
			"배치 모드(%s): 부지 %s, 카메라 %s, 들고 있음 %s, 알림 %s",
			name,
			plot.Name,
			tostring(cf.Position),
			tostring(picked),
			table.concat(toasts, ",")
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
		-- 부지 좌표(ParkGrid: 중앙 바닥 원점, -Z = 입구)의 카메라 자리 — 목업의 topView 계산과 비교
		LocalEye = vec(origin:PointToObjectSpace(cf.Position)),
		Screen = { W = scenario.Viewport.X, H = scenario.Viewport.Y, Inset = GUI_INSET, Scale = scale },
		Bar = { Left = barLeft, Top = barTop, Width = barWidth, Height = barHeight },
		Plot = plot.Name,
		Held = heldInfo,
		Tag = tagInfo,
		Target = scenario.Target,
		Labels = labels,
		SlotScreens = slotScreens,
		Slots = slotList,
		Unlocked = unlocked,
		Storage = ParkGrid.storage(PlayerState.snapshot(data, revision)),
		Toasts = toasts,
	}
end
