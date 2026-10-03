--!native
local fs = require("@lune/fs")
local process = require("@lune/process")
local Harness = require("../tests/harness")
local loader = Harness.new({})
local Land = loader.require(loader.folder("src/shared").Land)
-- 4 스터드마다 한 점
local N = (Land.MAX_X - Land.MIN_X) // 4
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
}
local t0 = os.clock()
local H = table.create(N * N)
local cols = table.create(N * N)
for i = 0, N - 1 do
	for k = 0, N - 1 do
		local c = Land.column(Land.MIN_X + i * 4 + 2, Land.MIN_Z + k * 4 + 2)
		cols[i * N + k + 1] = c
		H[i * N + k + 1] = c.ground
	end
end
print(string.format("columns %.2fs", os.clock() - t0))
local img = buffer.create(N * N * 3)
for i = 0, N - 1 do
	for k = 0, N - 1 do
		local c = cols[i * N + k + 1]
		local h = c.ground
		local hx = H[math.min(i + 1, N - 1) * N + k + 1] - h
		local hz = H[i * N + math.min(k + 1, N - 1) + 1] - h
		local shade = math.clamp(0.8 - (hx * 0.6 + hz * 0.4) * 0.1, 0.35, 1.2)
		local rgb = COLORS[c.surface] or { 255, 0, 255 }
		if c.islandTop then
			rgb = { 60, 170, 60 }
			shade = 1.15
		elseif c.water and c.water > h then
			rgb = { 40, 100, 140 }
			shade = 1
		end
		local o = (k * N + i) * 3
		for j = 1, 3 do
			buffer.writeu8(img, o + j - 1, math.clamp(math.floor(rgb[j] * shade), 0, 255))
		end
	end
end
local out = "build/"
fs.writeFile(out .. "map.ppm", string.format("P6\n%d %d\n255\n", N, N) .. buffer.tostring(img))
process.exec("convert", { out .. "map.ppm", out .. "map.png" })
print("ok")
