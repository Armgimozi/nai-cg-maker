-- 땅 하나(src/server/World*.luau)만 지어 부품과 거친 지형을 JSON 으로 쏟는다. 그림은 preview.py 로 본다.
--
--   lune run tools/region_preview <모듈> <가운데 x> <가운데 z> <반지름> [지형 칸 크기=8]
--   python3 tools/preview/preview.py build/region_<모듈>.json build/<그림>.png --eye x,y,z --at x,y,z
--
-- 모듈은 Region.build(root, rng) 를 내놓는다 (World.luau 가 부르는 것과 같다). 모듈 이름이 "World" 면 맵 전체를 짓는다.
-- 반지름 안의 부품만 쏟는다. 지형은 Land.column 의 겉면 높이와 재질로 칸마다 기둥 하나, 물은 반투명 판.

local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox") :: any
local serde = require("@lune/serde")
local Harness = require("../tests/harness")
local D = require("./preview/dumplib")

local args = process.args
local moduleName = args[1] or error("모듈 이름을 준다 (예: WorldNorth)")
local cx, cz = tonumber(args[2]) or 0, tonumber(args[3]) or 0
local radius = tonumber(args[4]) or 200
local step = tonumber(args[5]) or 8

local game = roblox.Instance.new("DataModel")
Harness.mount(game)
local loader = Harness.new(Harness.robloxGlobals(game))
local server = loader.folder("src/server")
local Land = loader.require(loader.folder("src/shared").Land)
local Kit = loader.require(server.WorldKit)

local workspace = game:GetService("Workspace")
local t0 = os.clock()
local root
if moduleName == "World" then
	root = loader.require(server.World).build(workspace, game:GetService("Lighting"))
else
	root = roblox.Instance.new("Model")
	root.Name = "Preview"
	root.Parent = workspace
	loader.require(server[moduleName]).build(root, Kit.makeRng(20261003))
end
local built = os.clock() - t0

local parts = {}
local count = 0
for _, d in root:GetDescendants() do
	if d:IsA("BasePart") then
		count += 1
		local p = d.CFrame.Position
		if (p.X - cx) ^ 2 + (p.Z - cz) ^ 2 <= radius * radius then
			table.insert(parts, D.partJson(d))
		end
	end
end

-- 거친 지형 (render_map.luau 와 같은 빛깔)
local COLORS = {
	Sand = { 214, 174, 112 },
	Sandstone = { 190, 120, 78 },
	Ground = { 156, 118, 80 },
	Basalt = { 52, 48, 48 },
	CrackedLava = { 232, 90, 40 },
	Snow = { 240, 244, 250 },
	Glacier = { 170, 210, 235 },
	Slate = { 96, 104, 112 },
	LeafyGrass = { 70, 112, 60 },
	Grass = { 98, 140, 74 },
	Mud = { 92, 74, 58 },
	Cobblestone = { 150, 145, 135 },
	Pavement = { 168, 150, 120 },
	Rock = { 112, 108, 104 },
	Ice = { 180, 220, 240 },
	Salt = { 236, 232, 222 },
}
local terrain = 0
for x = cx - radius, cx + radius, step do
	for z = cz - radius, cz + radius, step do
		if (x - cx) ^ 2 + (z - cz) ^ 2 <= radius * radius then
			local column = Land.column(x, z)
			local top = column.ground
			if top and top > Land.BOTTOM then
				local low = top
				for _, o in { { step, 0 }, { -step, 0 }, { 0, step }, { 0, -step } } do
					local g = Land.column(x + o[1], z + o[2]).ground or top
					low = math.min(low, g)
				end
				local h = math.clamp(top - low + 2, 2, 60)
				table.insert(parts, {
					shape = "Block",
					cf = { x, top - h / 2, z, 1, 0, 0, 0, 1, 0, 0, 0, 1 },
					size = { step, h, step },
					color = COLORS[column.surface] or { 255, 0, 255 },
					transparency = 0,
					material = column.surface or "Ground",
					name = "Terrain",
				})
				terrain += 1
			end
			-- 떠 있는 섬
			if column.islandTop and column.islandBottom then
				local h = math.max(2, column.islandTop - column.islandBottom)
				table.insert(parts, {
					shape = "Block",
					cf = { x, column.islandTop - h / 2, z, 1, 0, 0, 0, 1, 0, 0, 0, 1 },
					size = { step, h, step },
					color = { 90, 150, 80 },
					transparency = 0,
					material = "Grass",
					name = "Island",
				})
			end
			if column.water and (column.ground == nil or column.water > column.ground) then
				table.insert(parts, {
					shape = "Block",
					cf = { x, column.water - 0.5, z, 1, 0, 0, 0, 1, 0, 0, 0, 1 },
					size = { step, 1, step },
					color = { 60, 120, 160 },
					transparency = 0.35,
					material = "Water",
					name = "Water",
				})
			end
		end
	end
end

fs.writeDir("build")
local out = string.format("build/region_%s.json", moduleName)
fs.writeFile(out, serde.encode("json", parts))
print(
	string.format(
		"%s: 부품 %d개 (반지름 안 %d개), 지형 기둥 %d개, 짓기 %.2f초 → %s",
		moduleName,
		count,
		#parts - terrain,
		terrain,
		built,
		out
	)
)
