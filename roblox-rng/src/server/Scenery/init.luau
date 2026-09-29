-- 주변 풍경: 공원을 바다 위 휴양 섬으로 만듭니다. 서버 시작 때 한 번만 만듭니다.
--   지형(Workspace.Terrain): 구불구불한 해안선의 섬(공원 자리는 y = 0 으로 평평, 부지 뒤 숲띠는 낮은 잔디 언덕)
--     + 물속으로 완만하게 내려가는 모래사장(얕은 곳은 청록 물빛) + 물가 바위 + 수평선까지 바다 + 먼 작은 섬
--     모양은 Scenery/Island(순수 계산). 섬·작은 섬은 복셀 표 한 번씩(WriteVoxelChannels, 안 되면 WriteVoxels),
--     먼 바다는 큰 FillBlock 몇 번. 부지·길·산책로·광장 밑은 풀잎 장식이 없는 재질로 칠함(얇은 파트를 풀잎이 뚫지 않게)
--   파트: 산책로(돌길 고리 둘 + 정원 오솔길 + 원형 광장), 보이지 않는 물가 벽, 장식(정원 8곳·숲띠·모래사장·바다).
--     배치는 Scenery/Plan(고정 시드), 모양은 Scenery/Props. 결과는 Workspace.Scenery 폴더(구역별 하위 폴더).
-- 비상 바닥: default.project.json 의 FallbackGround(반지름 225 원기둥, 윗면 y -0.5 = 지형 윗면 바로 밑)가 있어서
-- 지형을 못 만들어도(또는 만드는 동안에도) 스폰·부지·길 밑은 허공이 아닙니다. 지형을 다 만들면 치웁니다.

local Workspace = game:GetService("Workspace")

local Island = require(script.Island)
local Plan = require(script.Plan)
local Props = require(script.Props)

local Scenery = {}

Scenery.Plan = Plan
Scenery.Island = Island

local FALLBACK_NAME = "FallbackGround" -- default.project.json 의 비상 바닥 파트
local WALL_THICKNESS = 2
local ROUTE_HEIGHT = Plan.Tuning.ROUTE_HEIGHT
local RING_STAGGER = 0.05 -- 이웃 고리 판끼리 윗면 높이 차(겹치는 모서리가 깜빡이지 않게, 걸을 때는 안 느껴짐)

-- 산책로 재질별 색(밝고 따뜻하게)
local ROUTE_COLORS: { [string]: Color3 } = {
	Cobblestone = Color3.fromRGB(206, 190, 162),
	Brick = Color3.fromRGB(210, 144, 114),
	Pebble = Color3.fromRGB(226, 212, 184),
	Slate = Color3.fromRGB(160, 162, 160),
	WoodPlanks = Color3.fromRGB(196, 138, 82),
	Pavement = Color3.fromRGB(222, 208, 180),
}

-- 광장 바닥 무늬: World 의 광장(반지름 45, 윗면 y = 1, 포석) 가운데(스폰 둘레)에 박은 나침반 장미.
-- 여덟 갈래 뾰족한 별(갈래마다 밝은 반쪽 + 짙은 반쪽 = 납작하게 눕힌 쐐기 둘) + 가운데 둥근 메달(스폰 받침을 둘러쌈).
-- 북쪽(지구본 쪽, -Z) 갈래는 빨강. 모든 조각은 광장 속에 반쯤 묻힌 두께 0.2 판이라 걸어서 못 느낌
local PLAZA_TOP = 1 -- World.luau 의 PLAZA_TOP
local COMPASS = {
	Cardinal = { Length = 16.5, Half = 3.4, Top = PLAZA_TOP + 0.1 }, -- 동서남북(북쪽 끝은 지구본 받침(z -17) 바로 앞)
	Diagonal = { Length = 10.5, Half = 2.6, Top = PLAZA_TOP + 0.06 }, -- 사이 네 갈래(동서남북 밑에 깔림)
	North = { Color3.fromRGB(255, 150, 128), Color3.fromRGB(226, 74, 64) },
	Main = { Color3.fromRGB(128, 186, 236), Color3.fromRGB(52, 78, 136) },
	Minor = { Color3.fromRGB(246, 204, 104), Color3.fromRGB(212, 146, 58) },
	Medallion = { -- 금색 테두리 + 남색 가운데(흰 대리석 스폰 받침이 올라앉음)
		{ R = 8.9, Top = PLAZA_TOP + 0.14, Color = Color3.fromRGB(246, 204, 104), Material = "Marble" },
		{ R = 7.9, Top = PLAZA_TOP + 0.18, Color = Color3.fromRGB(52, 78, 136), Material = "Granite" },
	},
}

local built: Folder? = nil

local function material(name: string): Enum.Material
	return (Enum.Material :: any)[name]
end

local function rgb(list: { number }): Color3
	return Color3.fromRGB(list[1], list[2], list[3])
end

-- 구역별 하위 폴더(없으면 만듦) + 파트 수 셀 구역 지정
local function zoneFolder(root: Folder, name: string): Folder
	Props.setZone(name)
	local existing = root:FindFirstChild(name)
	if existing and existing:IsA("Folder") then
		return existing
	end
	local folder = Instance.new("Folder")
	folder.Name = name
	folder.Parent = root
	return folder
end

-- 지형 -------------------------------------------------------------------------------

export type TerrainStats = {
	Ok: boolean,
	Method: string, -- "WriteVoxelChannels" | "WriteVoxels" | "failed"
	Voxels: number, -- 복셀 표로 쓴 복셀 수
	Solid: number, -- 그중 땅이 있는 복셀
	Water: number, -- 그중 물이 있는 복셀
	FillBlocks: number, -- 먼 바다 FillBlock 호출 수
	FillVoxels: number, -- FillBlock 이 채운 복셀 수(대략)
	Seconds: number,
}

-- 재질 이름 → Enum.Material(처음 쓸 때 찾아 둠)
local MATERIALS = setmetatable({}, {
	__index = function(self, name)
		local value = material(name)
		rawset(self, name, value)
		return value
	end,
}) :: any

local function setupLook(terrain: Terrain)
	for name, color in Island.COLORS do
		terrain:SetMaterialColor(material(name), rgb(color))
	end
	local W = Island.WATER
	terrain.WaterColor = rgb(W.Color)
	terrain.WaterTransparency = W.Transparency
	terrain.WaterReflectance = W.Reflectance
	terrain.WaterWaveSize = W.WaveSize
	terrain.WaterWaveSpeed = W.WaveSpeed
	-- 풀잎 장식(Terrain.Decoration, Grass 재질에만 나옴)은 스크립트로 못 바꾸는 속성(NotScriptable)이라 여기서 켜지 않고
	-- default.project.json 의 Workspace.Terrain 에서 켬(place 파일에 저장됨)
end

-- 먼 바다: 바닥 판 + 물(섬·작은 섬 자리는 나중에 복셀 표가 덮어씀)
local function fillOcean(terrain: Terrain, stats: TerrainStats)
	local V = Island.VOXEL
	local floorHeight = Island.SEA_FLOOR - Island.FLOOR_BOTTOM
	local waterHeight = Island.WATER_LEVEL - Island.SEA_FLOOR
	for _, tile in Island.oceanTiles() do
		local floorY = (Island.FLOOR_BOTTOM + Island.SEA_FLOOR) / 2
		local waterY = (Island.SEA_FLOOR + Island.WATER_LEVEL) / 2
		terrain:FillBlock(
			CFrame.new(tile.X, floorY, tile.Z),
			Vector3.new(tile.Size, floorHeight, tile.Size),
			MATERIALS.Mud
		)
		terrain:FillBlock(
			CFrame.new(tile.X, waterY, tile.Z),
			Vector3.new(tile.Size, waterHeight, tile.Size),
			MATERIALS.Water
		)
		stats.FillBlocks += 2
		stats.FillVoxels += (tile.Size // V) ^ 2 * ((floorHeight + waterHeight) // V)
	end
end

-- 복셀 표 한 장 쓰기: WriteVoxelChannels(땅 + 물이 한 복셀에 같이 → 물가가 매끈) 가 안 되면 WriteVoxels
local function writeArea(terrain: Terrain, area: Island.Area, plan: Plan.Result, stats: TerrainStats)
	local V = Island.VOXEL
	local grid = Island.voxels(area.MinX, area.MinZ, area.SizeX, area.SizeZ, {
		Paint = plan.Paint,
		Ponds = plan.Ponds,
		Materials = MATERIALS,
	})
	local lo = Vector3.new(grid.MinX, grid.MinY, grid.MinZ)
	local region = Region3.new(lo, lo + Vector3.new(grid.SizeX, grid.SizeY, grid.SizeZ) * V)
	local ok = stats.Method ~= "WriteVoxels"
		and pcall(function()
			terrain:WriteVoxelChannels(region, V, {
				SolidMaterial = grid.Material,
				SolidOccupancy = grid.Solid,
				LiquidOccupancy = grid.Liquid,
			})
		end)
	if ok then
		stats.Method = "WriteVoxelChannels"
	else
		local materials, occupancies = Island.legacy(grid, MATERIALS.Water, MATERIALS.Air)
		terrain:WriteVoxels(region, V, materials, occupancies)
		stats.Method = "WriteVoxels"
	end
	stats.Voxels += grid.SizeX * grid.SizeY * grid.SizeZ
	stats.Solid += grid.SolidCount
	stats.Water += grid.WaterCount
end

-- 지형 섬 + 바다. 실패해도 오류를 밖으로 던지지 않음(비상 바닥이 있음)
function Scenery.buildTerrain(plan: Plan.Result): TerrainStats
	local stats: TerrainStats = {
		Ok = false,
		Method = "failed",
		Voxels = 0,
		Solid = 0,
		Water = 0,
		FillBlocks = 0,
		FillVoxels = 0,
		Seconds = 0,
	}
	local started = os.clock()
	local ok, err = pcall(function()
		local terrain = Workspace.Terrain
		setupLook(terrain)
		fillOcean(terrain, stats)
		stats.Method = "?"
		for _, area in Island.areas() do
			writeArea(terrain, area, plan, stats)
		end
	end)
	stats.Seconds = os.clock() - started
	stats.Ok = ok
	if ok then
		-- 지형이 생겼으면 비상 바닥은 필요 없음(땅속에 묻혀 있지만 연못 바닥에서는 보이므로 치움)
		local fallback = Workspace:FindFirstChild(FALLBACK_NAME)
		if fallback and fallback:IsA("BasePart") then
			fallback:Destroy()
		end
	else
		stats.Method = "failed"
		warn("[Scenery] 지형 섬을 만들지 못했습니다(비상 바닥은 있음): " .. tostring(err))
	end
	return stats
end

-- 파트 --------------------------------------------------------------------------------

-- 보이지 않는 물가 벽: 닫힌 꺾은선(각도가 커지는 순서 = 안쪽이 왼쪽)을 따라 판을 세움. 판 안쪽 면이 선 위
local function buildWall(parent: Instance, wall)
	local points = wall.Points
	local height = wall.Height
	local y = wall.Bottom + height / 2
	for k, p in points do
		local q = points[k % #points + 1]
		local dx, dz = q[1] - p[1], q[2] - p[2]
		local length = math.sqrt(dx * dx + dz * dz)
		if length > 0.01 then
			-- 오른쪽(바깥) = (dz, -dx) / length
			local ox, oz = dz / length * WALL_THICKNESS / 2, -dx / length * WALL_THICKNESS / 2
			local center = Vector3.new((p[1] + q[1]) / 2 + ox, y, (p[2] + q[2]) / 2 + oz)
			local part = Props.block(
				parent,
				"EdgeWall",
				Vector3.new(WALL_THICKNESS, height, length + 0.6),
				CFrame.lookAt(center, center + Vector3.new(dx, 0, dz)),
				Color3.new(1, 1, 1),
				Enum.Material.SmoothPlastic,
				true
			)
			part.Transparency = 1
			part.CastShadow = false
		end
	end
end

-- 고리 산책로: 가운데 선 꼭짓점(Points) 사이마다 곧은 판 하나. 이음매에서 꺾이는 만큼 판을 반폭 * tan(꺾인 각 / 2)
-- 늘려서 바깥쪽 틈을 덮고, 겹치는 모서리가 깜빡이지 않게 이웃 판끼리 윗면을 RING_STAGGER 씩 번갈아 낮춤
local function buildRing(parent: Instance, ring: Plan.Ring)
	local points = ring.Points
	local n = #points
	local half = ring.Width / 2
	local color = if ring.Color then rgb(ring.Color) else ROUTE_COLORS[ring.Material] or ROUTE_COLORS.Cobblestone
	local function at(k: number): Vector3
		local p = points[(k - 1) % n + 1]
		return Vector3.new(p[1], 0, p[2])
	end
	-- k 번 꼭짓점에서 꺾이는 각의 절반의 tan
	local function bend(k: number): number
		local a = (at(k) - at(k - 1)).Unit
		local b = (at(k + 1) - at(k)).Unit
		local cos = math.clamp(a:Dot(b), -1, 1)
		return math.tan(math.acos(cos) / 2)
	end
	for k = 1, n do
		local a, b = at(k), at(k + 1)
		local direction = (b - a).Unit
		local from = a - direction * (half * bend(k) + 0.05)
		local to = b + direction * (half * bend(k + 1) + 0.05)
		local top = ring.Top - (k % 2) * RING_STAGGER
		local center = (from + to) / 2 + Vector3.new(0, top - ROUTE_HEIGHT / 2, 0)
		local part = Props.block(
			parent,
			"Walkway",
			Vector3.new(ring.Width, ROUTE_HEIGHT, (to - from).Magnitude),
			CFrame.lookAt(center, center + direction),
			color,
			material(ring.Material),
			true
		)
		part.CastShadow = false
	end
end

local function buildWalkways(parent: Instance, plan: Plan.Result)
	for _, ring in plan.Rings do
		buildRing(parent, ring)
	end
	for _, trail in plan.Trails do
		local color = ROUTE_COLORS[trail.Material] or ROUTE_COLORS.Cobblestone
		local part = Props.segment(parent, "GardenTrail", trail, ROUTE_HEIGHT, color, material(trail.Material), true)
		part.CastShadow = false
	end
	for _, disc in plan.Discs do
		local color = ROUTE_COLORS[disc.Material] or ROUTE_COLORS.Cobblestone
		local part = Props.disc(
			parent,
			"GardenPlaza",
			disc.X,
			disc.Z,
			disc.R,
			disc.Top,
			ROUTE_HEIGHT,
			color,
			material(disc.Material),
			true
		)
		part.CastShadow = false
	end
end

-- 나침반 갈래 반쪽: 가운데(0, 0)에서 끝(방향 (ux, uz) 으로 length)까지, 옆으로 half 폭의 직각삼각형.
-- 쐐기(로컬 YZ 단면이 직각삼각형)를 눕힘: 로컬 X = 위(두께), 직각 꼭짓점 = 가운데. side = 1 / -1(어느 쪽 반쪽)
local function compassHalf(
	parent: Instance,
	ux: number,
	uz: number,
	length: number,
	half: number,
	top: number,
	side: number,
	color: Color3,
	mat: Enum.Material
)
	local thickness = 0.2
	local u = Vector3.new(ux, 0, uz)
	local v = Vector3.new(uz, 0, -ux) * side -- 옆(up x v = -u 가 되게 side 에 따라 위아래를 뒤집음)
	local up = Vector3.new(0, side, 0)
	local center = u * (length / 2) + v * (half / 2) + Vector3.new(0, top - thickness / 2, 0)
	local piece = Props.wedge(
		parent,
		"PlazaCompass",
		Vector3.new(thickness, half, length),
		CFrame.fromMatrix(center, up, v),
		color,
		mat,
		true
	)
	piece.CastShadow = false
end

local function buildPlazaInlay(parent: Instance)
	for k = 0, 7 do
		local angle = math.rad(270 + k * 45) -- k = 0 이 북쪽(지구본 쪽, -Z)
		local ux, uz = math.cos(angle), math.sin(angle)
		local spec = if k % 2 == 0 then COMPASS.Cardinal else COMPASS.Diagonal
		local colors = if k == 0 then COMPASS.North elseif k % 2 == 0 then COMPASS.Main else COMPASS.Minor
		compassHalf(parent, ux, uz, spec.Length, spec.Half, spec.Top, 1, colors[1], Enum.Material.Marble)
		compassHalf(parent, ux, uz, spec.Length, spec.Half, spec.Top, -1, colors[2], Enum.Material.Granite)
	end
	for _, ring in COMPASS.Medallion do
		local part =
			Props.disc(parent, "PlazaCompass", 0, 0, ring.R, ring.Top, 0.2, ring.Color, material(ring.Material), true)
		part.CastShadow = false
	end
end

-- 파트 수 요약 문자열("구역 n, ...") + 합계
local function summary(counts: { [string]: number }): (string, number)
	local names = {}
	local total = 0
	for name, count in counts do
		table.insert(names, name)
		total += count
	end
	table.sort(names)
	local parts = {}
	for _, name in names do
		table.insert(parts, name .. " " .. counts[name])
	end
	return table.concat(parts, ", "), total
end

-- 풍경을 만들어 Workspace.Scenery 에 둠(두 번째 호출부터는 그대로 돌려줌). 반환: 폴더, 구역별 파트 수, 지형 결과
function Scenery.build(): (Folder, { [string]: number }, TerrainStats?)
	if built then
		return built, Props.counts(), nil
	end
	local started = os.clock()
	local plan = Plan.make()
	local planSeconds = os.clock() - started
	local terrain = Scenery.buildTerrain(plan)

	started = os.clock()
	Props.resetCounts()
	local root = Instance.new("Folder")
	root.Name = "Scenery"
	buildWall(zoneFolder(root, "Walls"), plan.Wall)
	buildWalkways(zoneFolder(root, "Walkways"), plan)
	buildPlazaInlay(zoneFolder(root, "Walkways"))
	for _, item in plan.Items do
		if not Props.build(zoneFolder(root, item.Zone), item) then
			warn("[Scenery] 모르는 장식 종류: " .. item.Kind)
		end
	end
	root.Parent = Workspace
	built = root

	local counts = Props.counts()
	local text, total = summary(counts)
	print(
		string.format(
			"[Scenery] 파트 %d개 (%s) / 지형 %s: 복셀 표 %d(땅 %d, 물 %d) + FillBlock %d번(약 %d 복셀), %.2f초"
				.. " / 배치 %.2f초, 파트 %.2f초",
			total,
			text,
			terrain.Method,
			terrain.Voxels,
			terrain.Solid,
			terrain.Water,
			terrain.FillBlocks,
			terrain.FillVoxels,
			terrain.Seconds,
			planSeconds,
			os.clock() - started
		)
	)
	for key, count in plan.Skipped do
		print(string.format("[Scenery] 자리가 없어 못 놓음: %s x%d", key, count))
	end
	return root, counts, terrain
end

return Scenery
