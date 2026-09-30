-- 스토어 그림용 world.luau hook: 진짜 맵 위에 "무대"를 올립니다(Workspace/Store 폴더).
--   * 명소 모형: 게임의 진짜 Models.create(명소, 크기) 로 만들어 원하는 자리·방향으로(크게 키워도 모양은 게임 그대로)
--   * 파트: 바위·수정 조각·블록 아바타 같은 무대 소품(목록은 tools/store/thumbs.py 가 계산해서 넘김)
--   * 공원 채우기: 샘플 플레이어들의 공원 확장 레벨·보관함을 채워 진짜 ParkService.update 로 전시(모든 부지가 북적이게)
-- 사용법(보통은 tools/store/thumbs.py 가 부름):
--   HOOK=tools/store/stage_hook.luau HOOK_ARGS="stage=<무대 JSON 경로>" tools/world_preview/preview.sh ...
-- 무대 JSON = {
--   "models": [ { "folder": "Hero", "id": "worldtree", "size": 30, "cf": [x,y,z, r00,r01,r02, r10,r11,r12, r20,r21,r22],
--                 "dropBase": true, "keep": { "materials": ["WoodPlanks"], "shapes": ["Ball"] } } ],
--        dropBase = 바닥 전시 받침(얇고 넓은 판)은 뺌(선택). keep = 이 재질(과 모양)의 파트만 남김(선택 — 썸네일의
--        "아직 못 찾은 명소" 그림자에서 받침·뒷벽을 빼고 명소 주인공 모양만: 트로이 목마의 나무 말, 네시의 목·등)
--   "parts":  [ { "folder": "Rocks", "shape": "Block|Ball|Cylinder|Wedge|CornerWedge", "size": [x,y,z], "cf": [...12],
--                 "color": [r,g,b](0~255), "mat": "Slate", "t": 0, "shadow": true } ],
--   "fillParks": { "level": 10, "count": 36, "ids": [...], "famous": 20, "maxOneIn": 100000 },   (선택)
--        공원 확장 레벨 · 보관함 명소 수 · 꼭 넣을 명소(플레이어마다 famous 개) · 이보다 희귀한 건 안 넣음
--   "lighting": { "ClockTime": 15 }              (선택) Lighting 속성 덮어쓰기
--   "hologram": "shangrila"                     (선택) 진짜 World.hologram(명소) — 광장 하늘의 거대 홀로그램(게임과 같은
--        자리·크기·재질). 홀로그램 아래 제목(BillboardGui: "속보!" + 한국어 이름)은 스토어 그림에 한글이 들어가지 않게 지움
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

-- 샘플 플레이어 간판 이름(영어 — 로블록스 표시 이름처럼). 부지 간판(SurfaceGui)은 렌더러가 글자까지 그림
local SIGN_NAMES = { "TravelKing", "Explorer", "LuckyLeo", "Nova", "MapMaster", "Wanderer", "Globetrotter", "Mochi" }

-- Enum 값 이름("Material.WoodPlanks" 문자열 또는 EnumItem) → "WoodPlanks"
local function enumName(value: any): string
	if type(value) == "string" then
		return value:match("%.([^%.]+)$") or value
	end
	return value.Name
end

local function hasHangul(text: string): boolean
	for _, code in utf8.codes(text) do
		if
			(code >= 0xAC00 and code <= 0xD7A3)
			or (code >= 0x1100 and code <= 0x11FF)
			or (code >= 0x3130 and code <= 0x318F)
		then
			return true
		end
	end
	return false
end

-- 게임 간판에 쓰는 한국어 글자 → 스토어 그림용 영어(ParkService 의 빈 부지 말뚝 간판)
local ENGLISH = { ["빈 부지"] = "EMPTY PLOT" }

-- 그려지는 글자(켜진 SurfaceGui 안의 글자): 아는 한국어는 영어로 바꾸고, 그래도 한글이 남으면 멈춤.
-- BillboardGui(명소 이름표, 홀로그램 제목 "속보!" 등)는 렌더러가 그리지 않지만, 나중에 그리게 되어도 한글이 새지 않게
-- 스토어 그림 덤프에서는 모두 지움
local function englishOnly(root: any)
	for _, gui in root:GetDescendants() do
		if gui:IsA("BillboardGui") then
			gui:Destroy()
		end
	end
	for _, gui in root:GetDescendants() do
		if gui:IsA("SurfaceGui") and gui.Enabled ~= false then
			for _, label in gui:GetDescendants() do
				local isText = label:IsA("TextLabel") or label:IsA("TextButton") or label:IsA("TextBox")
				local text = if isText then label.Text else nil
				if type(text) == "string" and ENGLISH[text] then
					label.Text = ENGLISH[text]
				elseif type(text) == "string" and hasHangul(text) then
					error("스토어 그림에 한글 글자: " .. label:GetFullName() .. " = " .. text)
				end
			end
		end
	end
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
		if spec.dropBase then
			-- 전시 받침(바닥에 깔린 얇고 넓은 판·원판)은 빼고 명소만: 스토어 그림에서 모형이 땅(빛)에서 바로 솟게
			local size = spec.size or 10
			for _, d in model:GetDescendants() do
				if d:IsA("BasePart") and d ~= model.PrimaryPart then
					local s = d.Size
					local thin = math.min(s.X, s.Y, s.Z) < size * 0.07
					local wide = math.max(s.X, s.Y, s.Z) > size * 0.55
					if thin and wide and d.Position.Y < size * 0.05 then
						d:Destroy()
					end
				end
			end
		end
		if spec.keep then
			local materials, shapes = {}, {}
			for _, name in spec.keep.materials or {} do
				materials[name] = true
			end
			for _, name in spec.keep.shapes or {} do
				shapes[name] = true
			end
			for _, d in model:GetDescendants() do
				if d:IsA("BasePart") and d ~= model.PrimaryPart then
					local shape = if d.ClassName == "Part" then enumName(d.Shape) else "Block"
					local keepMaterial = next(materials) == nil or materials[enumName(d.Material)]
					local keepShape = next(shapes) == nil or shapes[shape]
					if not (keepMaterial and keepShape) then
						d:Destroy()
					end
				end
			end
		end
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
			data.Upgrades.Park = math.max(data.Upgrades.Park or 0, fill.level or 10)
			-- 부지마다 다른 명소: fill.ids(잘 알려진 명소, 앞에서부터 플레이어마다 조금씩 밀어서) + 목록을 플레이어마다
			-- 다른 간격으로 훑어 count 개까지. 자동 전시는 희귀한 순서라 count 가 전시 칸 수(36)면 모두 전시됨
			local count = fill.count or 40
			local owned = 0
			local function give(id: string, amount: number)
				if data.Inventory[id] == nil then
					owned += 1
				end
				data.Inventory[id] = amount
				data.Discovered[id] = true
			end
			local ids = fill.ids or {}
			for k = 1, math.min(#ids, fill.famous or #ids) do
				local id = ids[(k + i * 3 - 1) % #ids + 1]
				if Landmarks.ById[id] and owned < count then
					give(id, 1 + (k * 5 + i) % 30)
				end
			end
			local k = 0
			while owned < count and k < #list * 2 do
				k += 1
				local index = (i * 17 + k * (7 + 2 * i)) % #list + 1
				local landmark = list[index]
				if landmark.OneIn < (fill.maxOneIn or math.huge) and data.Inventory[landmark.Id] == nil then
					give(landmark.Id, 1 + (index * 7) % 40)
				end
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

	if stage.hologram then
		local World = Harness.require(server.World)
		local landmark = Landmarks.ById[stage.hologram]
		assert(landmark, "없는 명소 id: " .. tostring(stage.hologram))
		local ok, err = Mock.run(function()
			World.hologram(landmark)
		end)
		assert(ok, "홀로그램 실패: " .. tostring(err))
	end

	-- 스토어 그림에는 한글을 넣지 않음(전 세계 스토어용): 샘플 플레이어 간판 이름을 영어로 바꿔 다시 전시
	local ParkService = Harness.require(server.ParkService)
	for i, sample in ctx.samples or {} do
		sample.Player.DisplayName = SIGN_NAMES[(i - 1) % #SIGN_NAMES + 1]
		local ok, err = Mock.run(function()
			ParkService.update(sample.Player, sample.Data)
		end)
		if not ok then
			ctx.note("간판 이름 바꾸기 실패(" .. i .. "): " .. tostring(err))
		end
	end
	Mock.runScheduler(Mock.clock() + 1)
	-- park_hook 처럼 뒤에 간판을 더 만드는 hook 은 마지막에 한 번 더 부름
	ctx.englishOnly = function()
		englishOnly(Mock.Workspace)
	end
	ctx.englishOnly()
	return nil
end
