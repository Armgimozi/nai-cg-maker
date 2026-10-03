--!native
-- 옥반을 위에서 본 지도 → build/map.png (4 스터드마다 한 점). 지형 빛깔은 Land.COLORS,
-- 그 위에 WorldSites 의 자리를 찍는다: 전송진(흰 네모), 과업 자리(노랑, 오행처는 속성 빛깔), 영맥(하늘색).
--   lune run tools/render_map
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox") :: any
local Harness = require("../tests/harness")
local game = roblox.Instance.new("DataModel")
Harness.mount(game)
local loader = Harness.new(Harness.robloxGlobals(game))
local Land = loader.require(loader.folder("src/shared").Land)
local Sites = loader.require(loader.folder("src/server").WorldSites)
local N = (Land.MAX_X - Land.MIN_X) // 4
local COLORS = Land.COLORS
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
-- 자리 찍기 (가운데 x z, 반지름 px, 빛깔)
local function dot(x: number, z: number, r: number, rgb: { number })
	local ci, ck = (x - Land.MIN_X) / 4, (z - Land.MIN_Z) / 4
	for i = math.floor(ci - r - 1), math.ceil(ci + r + 1) do
		for k = math.floor(ck - r - 1), math.ceil(ck + r + 1) do
			if i >= 0 and i < N and k >= 0 and k < N then
				local d = math.max(math.abs(i - ci), math.abs(k - ck))
				local color = if d <= r then rgb elseif d <= r + 1 then { 20, 20, 24 } else nil
				if color then
					local o = (k * N + i) * 3
					for j = 1, 3 do
						buffer.writeu8(img, o + j - 1, color[j])
					end
				end
			end
		end
	end
end
local function rgbOf(c: Color3): { number }
	return { math.floor(c.R * 255), math.floor(c.G * 255), math.floor(c.B * 255) }
end
for _, s in Sites.VEINS do
	dot(s.x, s.z, 1.5, { 120, 230, 255 })
end
for _, s in Sites.TASK do
	local color = Sites.ELEMENT_COLORS[s.id]
	dot(s.x, s.z, 1.5, if color then rgbOf(color) else { 250, 210, 70 })
end
for _, s in Sites.WAYPOINTS do
	dot(s.x, s.z, 2.5, { 255, 255, 255 })
end

local out = "build/"
fs.writeFile(out .. "map.ppm", string.format("P6\n%d %d\n255\n", N, N) .. buffer.tostring(img))
process.exec("convert", { out .. "map.ppm", out .. "map.png" })
print("ok")
