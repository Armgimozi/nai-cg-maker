-- 지형을 게임 서버에서 직접 짓는다 (WriteVoxels).
--
-- 보통은 tools/bake_place.luau 가 같은 땅 모양(Shared.Land)으로 지형을 플레이스 파일에 미리 구워 둔다.
-- 엔진이 구운 지형을 못 읽었거나(지형 칸이 0), 맵을 서버가 새로 지을 때만 여기서 짓는다.
-- 마을 가까운 곳부터 짓고, 한 프레임에 오래 붙잡지 않게 나눠 짓는다.

local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")

local Land = require(Shared.Land)

local TerrainGen = {}

local CHUNK = 64 -- 한 번에 쓰는 기둥 묶음 한 변(스터드)
local BUDGET = 0.008 -- 한 프레임에 쓰는 시간(초)

local function material(name: string): Enum.Material
	return (Enum.Material :: any)[name] or Enum.Material.Grass
end

-- 지형이 이미 있는가 (구운 지형을 엔진이 읽었는가)
function TerrainGen.present(): boolean
	local terrain = Workspace.Terrain
	local ok, count = pcall(function()
		return terrain:CountCells()
	end)
	return ok and type(count) == "number" and count > 0
end

-- 기둥 묶음 하나를 쓴다. x0, z0 는 4 의 배수
local function writeChunk(terrain: Terrain, x0: number, z0: number)
	local cells = CHUNK // 4
	local columns = table.create(cells * cells)
	local top = Land.BOTTOM
	for a = 0, cells - 1 do
		for c = 0, cells - 1 do
			local column = Land.column(x0 + a * 4 + 2, z0 + c * 4 + 2)
			columns[a * cells + c + 1] = column
			top = math.max(top, column.top)
		end
	end
	local ny = math.ceil((top - Land.BOTTOM) / 4) + 1
	local materials = table.create(cells)
	local occupancy = table.create(cells)
	for a = 1, cells do
		local matX, occX = table.create(ny), table.create(ny)
		for b = 1, ny do
			matX[b] = table.create(cells, Enum.Material.Air)
			occX[b] = table.create(cells, 0)
		end
		materials[a], occupancy[a] = matX, occX
	end
	for a = 0, cells - 1 do
		for c = 0, cells - 1 do
			local column = columns[a * cells + c + 1]
			Land.cells(column, Land.BOTTOM, ny, function(b: number, name: string, occ: number)
				materials[a + 1][b + 1][c + 1] = material(name)
				occupancy[a + 1][b + 1][c + 1] = occ
			end)
		end
	end
	local region =
		Region3.new(Vector3.new(x0, Land.BOTTOM, z0), Vector3.new(x0 + CHUNK, Land.BOTTOM + ny * 4, z0 + CHUNK))
	terrain:WriteVoxels(region, 4, materials, occupancy)
end

-- 지형을 짓는다. 마을 둘레를 다 지으면 Workspace 속성 TerrainHubReady, 다 지으면 TerrainReady 를 켠다
local HUB_RADIUS = 320
function TerrainGen.build(center: Vector3?)
	local terrain = Workspace.Terrain
	Land.decorate(terrain)
	local origin = center or Vector3.zero
	local chunks = {}
	for x0 = Land.MIN_X, Land.MAX_X - CHUNK, CHUNK do
		for z0 = Land.MIN_Z, Land.MAX_Z - CHUNK, CHUNK do
			local dx, dz = x0 + CHUNK / 2 - origin.X, z0 + CHUNK / 2 - origin.Z
			table.insert(chunks, { x0 = x0, z0 = z0, d = dx * dx + dz * dz })
		end
	end
	table.sort(chunks, function(a, b)
		return a.d < b.d
	end)
	local started = os.clock()
	for _, chunk in chunks do
		if chunk.d > HUB_RADIUS * HUB_RADIUS and not Workspace:GetAttribute("TerrainHubReady") then
			Workspace:SetAttribute("TerrainHubReady", true)
		end
		writeChunk(terrain, chunk.x0, chunk.z0)
		if os.clock() - started > BUDGET then
			task.wait()
			started = os.clock()
		end
	end
	Workspace:SetAttribute("TerrainHubReady", true)
	Workspace:SetAttribute("TerrainReady", true)
end

-- 마을 둘레 지형이 있을 때까지 기다린다 (캐릭터를 내보내기 전)
function TerrainGen.waitForHub()
	while not Workspace:GetAttribute("TerrainHubReady") do
		Workspace:GetAttributeChangedSignal("TerrainHubReady"):Wait()
	end
end

return TerrainGen
