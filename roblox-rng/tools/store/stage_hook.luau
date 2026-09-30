-- 스토어 그림용 world.luau hook: 진짜 맵 위에 "무대"를 올립니다(Workspace/Store 폴더).
--   * 명소 모형: 게임의 진짜 Models.create(명소, 크기) 로 만들어 원하는 자리·방향으로(크게 키워도 모양은 게임 그대로)
--   * 파트: 바위·수정 조각·블록 아바타 같은 무대 소품(목록은 tools/store/thumbs.py 가 계산해서 넘김)
--   * 공원 채우기: 샘플 플레이어들의 공원 확장 레벨·보관함을 채워 진짜 ParkService.update 로 전시(모든 부지가 북적이게)
-- 사용법(보통은 tools/store/thumbs.py 가 부름):
--   HOOK=tools/store/stage_hook.luau HOOK_ARGS="stage=<무대 JSON 경로>" tools/world_preview/preview.sh ...
-- 무대 JSON = {
--   "models": [ { "folder": "Hero", "id": "worldtree", "size": 30, "cf": [x,y,z, r00,r01,r02, r10,r11,r12, r20,r21,r22] } ],
--   "parts":  [ { "folder": "Rocks", "shape": "Block|Ball|Cylinder|Wedge|CornerWedge", "size": [x,y,z], "cf": [...12],
--                 "color": [r,g,b](0~255), "mat": "Slate", "t": 0, "shadow": true } ],
--   "fillParks": { "level": 10, "count": 40 },   (선택)
--   "lighting": { "ClockTime": 15 }              (선택) Lighting 속성 덮어쓰기
-- }
-- 돌려주는 표(덤프 extra)는 없음 — 카메라는 thumbs.py 가 render_layers.js 에 직접 넘김.

local function cframeOf(list: { number }): CFrame
	return CFrame.new(
		list[1],
		list[2],
		list[3],
		list[4],
		list[5],
		list[6],
		list[7],
		list[8],
		list[9],
		list[10],
		list[11],
		list[12]
	)
end

return function(ctx: any): any
	local Mock, Harness, shared, server, opts = ctx.Mock, ctx.Harness, ctx.shared, ctx.server, ctx.opts
	local path = opts.stage
	assert(path, "stage=<무대 JSON 경로> 가 필요합니다")
	local text = readfile(path)
	assert(text, "무대 JSON 을 읽지 못했습니다: " .. tostring(path))
	local stage = Mock.json.decode(text)

	local Landmarks = Harness.require(shared.Landmarks)
	local Models = Harness.require(shared.Models)

	local root = Instance.new("Folder")
	root.Name = "Store"
	root.Parent = Mock.Workspace
	local folders: { [string]: any } = {}
	local function folder(name: string): any
		if not folders[name] then
			local f = Instance.new("Folder")
			f.Name = name
			f.Parent = root
			folders[name] = f
		end
		return folders[name]
	end

	for _, spec in stage.models or {} do
		local landmark = if spec.id == "Globe" then Landmarks.Globe else Landmarks.ById[spec.id] -- Globe = 광장 지구본
		assert(landmark, "없는 명소 id: " .. tostring(spec.id))
		local model = Models.create(landmark, spec.size or 10)
		model:PivotTo(cframeOf(spec.cf))
		model.Parent = folder(spec.folder or "Hero")
	end

	local CLASS = { Wedge = "WedgePart", CornerWedge = "CornerWedgePart" }
	for i, spec in stage.parts or {} do
		local part = Instance.new(CLASS[spec.shape] or "Part")
		part.Name = spec.name or ("P" .. i)
		if not CLASS[spec.shape] and spec.shape and spec.shape ~= "Block" then
			part.Shape = Enum.PartType[spec.shape]
		end
		part.Size = Vector3.new(spec.size[1], spec.size[2], spec.size[3])
		part.CFrame = cframeOf(spec.cf)
		part.Color = Color3.fromRGB(spec.color[1], spec.color[2], spec.color[3])
		part.Material = Enum.Material[spec.mat or "SmoothPlastic"]
		part.Transparency = spec.t or 0
		part.CastShadow = spec.shadow ~= false
		part.Anchored = true
		part.CanCollide = false
		part.TopSurface = Enum.SurfaceType.Smooth
		part.BottomSurface = Enum.SurfaceType.Smooth
		part.Parent = folder(spec.folder or "Props")
	end

	local fill = stage.fillParks
	if fill then
		local PlayerState = Harness.require(shared.PlayerState)
		local ParkService = Harness.require(server.ParkService)
		local list = Landmarks.List
		for i, sample in ctx.samples do
			local data = sample.Data
			data.Upgrades.Park = math.max(data.Upgrades.Park or 0, (fill.level or 10) - (i - 1) % 3)
			-- 부지마다 다른 명소: 목록을 플레이어마다 다른 간격으로 훑음(흔한 것 위주 + 가끔 희귀한 것)
			local count = fill.count or 40
			for k = 1, count do
				local index = (i * 17 + k * (7 + 2 * i)) % #list + 1
				local landmark = list[index]
				data.Inventory[landmark.Id] = 1 + (index * 7) % 40
				data.Discovered[landmark.Id] = true
			end
			local ok, err = Mock.run(function()
				ParkService.update(sample.Player, data)
			end)
			if not ok then
				ctx.note("공원 채우기 실패(" .. i .. "): " .. tostring(err))
			end
			local _, unlocked = PlayerState.parkSlots(data)
			ctx.note(string.format("공원 %d: 전시 칸 %d", i, unlocked))
		end
		Mock.runScheduler(Mock.clock() + 5)
	end

	for key, value in stage.lighting or {} do
		Mock.Lighting[key] = value
	end
	return nil
end
