-- 플레이스 파일 만들기.   실행: lune run tools/bake_place   (blocksuseon 폴더에서)
--
-- 1) Rojo 로 스크립트만 든 플레이스를 빌드하고
-- 2) 그 안에 옥반 맵(World.build)을 지어 넣고
-- 3) 땅 모양(Shared.Land)대로 지형을 구워(SmoothGrid) 넣어
-- 4) BlockSuseon.rbxl 로 저장한다.
-- 맵과 지형이 플레이스에 들어 있으므로 Studio 에서 바로 보고 고칠 수 있다.

local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local Harness = require("../tests/harness")
local SmoothGrid = require("./SmoothGrid")

local SCRIPTS_PLACE = "build/scripts.rbxl"
local OUTPUT = "BlockSuseon.rbxl"

fs.writeDir("build")

local result = process.exec("rojo", { "build", "default.project.json", "--output", SCRIPTS_PLACE })
if not result.ok then
	error("rojo build 실패:\n" .. result.stderr)
end

local game = roblox.deserializePlace(fs.readFile(SCRIPTS_PLACE))
local loader = Harness.new(Harness.robloxGlobals(game))
local World = loader.require(loader.folder("src/server").World)
local Land = loader.require(loader.folder("src/shared").Land)

local workspace = game:GetService("Workspace")
local existing = workspace:FindFirstChild(World.MODEL_NAME)
if existing then
	existing:Destroy()
end
World.build(workspace, game:GetService("Lighting"))

-- 지형 굽기 ---------------------------------------------------------------------------

local started = os.clock()
local terrain = workspace:FindFirstChildOfClass("Terrain")
if not terrain then
	terrain = roblox.Instance.new("Terrain")
	terrain.Parent = workspace
end

local SLOT = SmoothGrid.SLOT
local CHUNK = 128 -- SmoothGrid 덩어리 한 변 (32칸)
local chunks: { SmoothGrid.Chunk } = {}
local cellsSolid = 0
-- 덩어리에서 원점에 가장 가까운 점까지 거리 (천애 바깥 덩어리는 비어 있어 건너뛴다)
local function nearest(x0: number, z0: number): number
	local nx = math.clamp(0, x0, x0 + CHUNK)
	local nz = math.clamp(0, z0, z0 + CHUNK)
	return math.sqrt((nx - 0) ^ 2 + (nz - 0) ^ 2)
end
for x0 = Land.MIN_X, Land.MAX_X - CHUNK, CHUNK do
	for z0 = Land.MIN_Z, Land.MAX_Z - CHUNK, CHUNK do
		if Land.EDGE and nearest(x0, z0) > Land.EDGE then
			continue
		end
		local columns = table.create(32 * 32)
		local top = Land.BOTTOM
		for a = 0, 31 do
			for c = 0, 31 do
				local column = Land.column(x0 + a * 4 + 2, z0 + c * 4 + 2)
				columns[a * 32 + c + 1] = column
				top = math.max(top, column.top)
			end
		end
		local ny = math.ceil((top - Land.BOTTOM) / 4) + 1
		-- 세로로 덩어리 여럿에 걸친다 (칸 y 를 32 로 나눈 몫이 덩어리 cy)
		local firstCell = Land.BOTTOM // 4
		local chunkX, chunkZ = x0 // CHUNK, z0 // CHUNK
		local byCy: { [number]: SmoothGrid.Chunk } = {}
		for a = 0, 31 do
			for c = 0, 31 do
				Land.cells(columns[a * 32 + c + 1], Land.BOTTOM, ny, function(b: number, name: string, o: number)
					local cellY = firstCell + b
					local cy = cellY // 32
					local chunk = byCy[cy]
					if not chunk then
						chunk = {
							cx = chunkX,
							cy = cy,
							cz = chunkZ,
							mat = buffer.create(SmoothGrid.CELLS),
							occ = buffer.create(SmoothGrid.CELLS),
						}
						byCy[cy] = chunk
						table.insert(chunks, chunk)
					end
					local slot = SLOT[name]
					assert(slot, "SmoothGrid 에 없는 재질: " .. name)
					local index = SmoothGrid.index(a, cellY - cy * 32, c)
					buffer.writeu8(chunk.mat, index, slot)
					buffer.writeu8(chunk.occ, index, SmoothGrid.occByte(o))
					if slot ~= SLOT.Water then
						cellsSolid += 1
					end
				end)
			end
		end
	end
end
terrain.SmoothGrid = SmoothGrid.encode(chunks)
terrain.PhysicsGrid = SmoothGrid.physicsGrid(chunks)
Land.decorate(terrain)
-- 풀 흔들림(Decoration)은 스크립트로 못 바꾸는 속성이라 여기서 켠다
terrain.Decoration = true
terrain.GrassLength = 0.6
print(
	string.format(
		"지형 %d덩어리 · 고체 칸 %d · SmoothGrid %dKB · %.1f초",
		#chunks,
		cellsSolid,
		#terrain.SmoothGrid // 1024,
		os.clock() - started
	)
)

fs.writeFile(OUTPUT, roblox.serializePlace(game))
print(`{OUTPUT} 저장 ({#fs.readFile(OUTPUT)} 바이트)`)
