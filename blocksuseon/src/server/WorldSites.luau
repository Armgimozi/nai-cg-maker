-- 옥반 세계의 자리 목록: 과업 자리, 전송진, 영맥, 볼거리, 영초 범위, 비급 자리, 다리.
-- World.luau 가 이 값대로 놓고, 땅마다의 World*.luau 는 이 둘레를 꾸민다. 땅 모양은 Shared.Land.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")
local Land = require(Shared.Land)

local Sites = {}

-- 다리·징검돌 (World 가 블록으로 놓는다) { ax, az, bx, bz, 윗면 높이 }
Sites.BRIDGES = {
	{ -108, 0, -82, 0, 0.9 }, -- 벽계 다리 (지금 다리 그대로)
	{ -75, -381, -108, -408, 0.2 }, -- 비류대 길 징검돌
	{ -40, -515, -40, -592, 1.2 }, -- 경심정 구곡교 (실제로는 지그재그)
}

local L = {}
local function add(kind: string, id: string, name: string, x: number, z: number, extra: { [string]: any }?)
	local s = { kind = kind, id = id, name = name, x = x, z = z }
	for k, v in extra or {} do
		s[k] = v
	end
	table.insert(L, s)
	return s
end

-- 과업 자리 (Tasks.luau 의 id)
add("site", "plaza", "송계 광장 영맥", 0, 0)
add("site", "furnace", "연단로", -12, -22)
add("site", "elder_1", "늙은 약초꾼", -26, 8)
add("site", "elder_2", "늙은 대장장이", 42, 14)
add("site", "elder_3", "늙은 뱃사공", -82, 20)
add("site", "el_water", "수 오행처: 명경호 물가 바위", 62, -548)
add("site", "el_wood", "목 오행처: 만년목", Land.TREE.x, Land.TREE.z)
add("site", "el_fire", "화 오행처: 홍로성 용광로", 300, 500)
add("site", "el_earth", "토 오행처: 황구 토단", Land.EARTH.x, Land.EARTH.z)
add("site", "el_metal", "금 오행처: 백금굴", Land.MINE.x, Land.MINE.z)
add("site", "star_north", "북쪽 성대 (북진대)", Land.STARS.north.x, Land.STARS.north.z)
add("site", "star_east", "동쪽 성대 (조양대)", Land.STARS.east.x, Land.STARS.east.z)
add("site", "star_south", "남쪽 성대 (남명대)", Land.STARS.south.x, Land.STARS.south.z)
add("site", "star_west", "서쪽 성대 (낙조대)", Land.STARS.west.x, Land.STARS.west.z)
add("site", "up", "위: 관운봉 꼭대기", Land.PEAK.x, Land.PEAK.z)
add("site", "down", "아래: 벽담 너럭바위", -70, 180, { radius = 14 })
add("site", "altar", "칠성단 (관성대)", Land.MESA.x, Land.MESA.z)
for i, angle in { 90, 45, 0, 315, 135, 180, 225, 270 } do
	local a = math.rad(angle)
	add("site", "tri_" .. i, "팔괘 기둥", Land.MESA.x + math.cos(a) * 31, Land.MESA.z + math.sin(a) * 31)
end

-- 전송진 (차례대로)
add("wp", "wp_home", "송계 마을", 60, -60)
add("wp", "wp_grove", "청송림", -300, -70)
add("wp", "wp_ungok", "운곡 마을", -490, 0)
add("wp", "wp_summit", "관운봉 꼭대기", -885, -385)
add("wp", "wp_west", "낙조대", -1175, 22)
add("wp", "wp_lake", "명경호", 95, -560)
add("wp", "wp_north", "북진대", 24, -1176)
add("wp", "wp_camp", "마령채", 650, -770)
add("wp", "wp_cape", "망선대", 1172, -1172)
add("wp", "wp_east", "조양대", 1178, 18)
add("wp", "wp_city", "홍로성", 300, 610)
add("wp", "wp_south", "남명대", 22, 1178)
add("wp", "wp_port", "백사포", -420, 1548)
add("wp", "wp_mesa", "관성대", -625, 625)
add("wp", "wp_ruins", "침사국 옛터", -1120, 1020)
add("wp", "wp_sky", "청허경", 1310, -1340, { sky = true }) -- 극품 영맥(섬 가운데 쪽)과 40 남짓 떨어진 서남쪽 (운제가 닿는 쪽)

-- 영맥
add("vein", "low@plaza", "하품: 송계 광장", 0, 0, { radius = 12 })
add("vein", "low@camp", "하품: 마령채", 600, -820)
add("vein", "low@oasis", "하품: 녹주", -1030, 668)
add("vein", "low@port", "하품: 백사포 해신당", -470, 1530)
add("vein", "mid@grove", "중품: 청송림 영천굴", -380, 110)
add("vein", "mid@ungok", "중품: 운곡 석종굴", -585, 30)
add("vein", "mid@lake", "중품: 경심정", Land.ISLET.x, Land.ISLET.z, { radius = 14 })
add("vein", "mid@hermit", "중품: 청음암", Land.HERMIT.x, Land.HERMIT.z)
add("vein", "mid@temple", "중품: 무명사 옛터", Land.TEMPLE.x, Land.TEMPLE.z)
add("vein", "high@summit", "상품: 관운봉 꼭대기", Land.PEAK.x + 14, Land.PEAK.z - 14) -- '위' 자리와 20 떨어지게
add("vein", "high@tarn", "상품: 빙경담", Land.TARN.x, Land.TARN.z)
add("vein", "high@volcano", "상품: 주염산 화구 둘레", 0, 0, { volcano = true, radius = 6 }) -- 화구 길 끝 좁은 턱
add("vein", "high@ruins", "상품: 침사국 옛터", Land.RUINS.x, Land.RUINS.z)
add("vein", "top@sky", "극품: 청허경", Land.SKY.x - 20, Land.SKY.z + 20, { sky = true })

-- 그 밖의 볼거리
add("poi", "falls_top", "비류폭 위 (비류대)", -290, -722)
add("poi", "stones", "팔방석진", Land.STONES.x, Land.STONES.z)
add("poi", "tower", "무택 고탑", Land.TOWER.x, Land.TOWER.z)
add("poi", "oasis", "녹주", Land.OASIS.x + 30, Land.OASIS.z)
add("poi", "salt", "한해 소금벌", Land.SALT.x, Land.SALT.z)
add("poi", "glacier_mouth", "설하 빙하 끝", -330, -1660)
add("poi", "swords", "검총(劍塚): 옛 싸움터", -260, 1120)
add("poi", "stair_base", "운제 첫 계단 (망선대)", 1201, -1201)

-- 화구 둘레 상품 영맥: 화구 길 끝
do
	local sp = Land.VOLCANO_TRAIL
	local p = sp.pts[sp.n]
	local a = math.rad(sp.a0 + sp.dir * sp.n)
	for _, s in L do
		if s.volcano then
			s.x, s.z = sp.cx + math.cos(a) * p[1], sp.cz + math.sin(a) * p[1]
		end
	end
end

Sites.LIST = L

-- 종류별로 (id 로도 찾는다)
Sites.TASK, Sites.WAYPOINTS, Sites.VEINS, Sites.POI = {}, {}, {}, {}
Sites.byId = {}
for _, s in L do
	local list = if s.kind == "site"
		then Sites.TASK
		elseif s.kind == "wp" then Sites.WAYPOINTS
		elseif s.kind == "vein" then Sites.VEINS
		else Sites.POI
	table.insert(list, s)
	Sites.byId[s.id] = s
	if s.kind == "vein" then
		s.grade = string.match(s.id, "^(%a+)@")
	end
end

-- 영맥 못 반지름 (자리에 radius 가 없을 때)
Sites.VEIN_RADIUS = { low = 10, mid = 10, high = 8, top = 12 }
for _, s in Sites.VEINS do
	s.radius = s.radius or Sites.VEIN_RADIUS[s.grade]
end

-- 오행처 빛깔 (영근 속성)
Sites.ELEMENT_COLORS = {
	el_wood = Color3.fromRGB(110, 200, 120),
	el_fire = Color3.fromRGB(240, 120, 80),
	el_earth = Color3.fromRGB(210, 170, 100),
	el_metal = Color3.fromRGB(235, 235, 240),
	el_water = Color3.fromRGB(90, 140, 230),
}

-- 사방 성대: 새길 글과 빛깔
Sites.STAR_ALTARS = {
	{ id = "star_east", name = "조양대", carve = "동방 청룡", color = Color3.fromRGB(80, 200, 170) },
	{ id = "star_west", name = "낙조대", carve = "서방 백호", color = Color3.fromRGB(235, 235, 240) },
	{ id = "star_south", name = "남명대", carve = "남방 주작", color = Color3.fromRGB(230, 90, 70) },
	{ id = "star_north", name = "북진대", carve = "북방 현무", color = Color3.fromRGB(90, 100, 170) },
}

-- 영초가 돋는 범위 { 이름, 가운데 x, z, 너비 x, z, 귀한 영초 배율, weight: 고를 때 넓이에 곱하는 값 }
-- 청송림은 범인이 처음 영초를 캐러 가는 숲이라 넓이보다 자주 고른다
Sites.HERB_ZONES = {
	{ name = "청송림", x = -280, z = 0, sx = 330, sz = 660, rare = 1, weight = 3 },
	{ name = "태고림", x = 1110, z = -130, sx = 900, sz = 900, rare = 1.5 },
	{ name = "청음죽림", x = 580, z = 300, sx = 360, sz = 360, rare = 1.2 },
	{ name = "무택", x = 130, z = 1270, sx = 400, sz = 400, rare = 1.5 },
	{ name = "녹주", x = -1050, z = 650, sx = 80, sz = 80, rare = 2 },
	{ name = "비류대", x = -450, z = -760, sx = 360, sz = 280, rare = 1.3 },
	{ name = "청허경", x = Land.SKY.x, z = Land.SKY.z, sx = 240, sz = 240, rare = 3, sky = true },
}

-- 비급이 나타날 수 있는 자리 { x, z } (마을 둘레 몇 곳, 나머지는 땅마다)
Sites.MANUALS = {
	-- 송계 둘레
	{ 0, 80 },
	{ -62, -58 },
	{ 96, 10 },
	{ 70, 140 },
	-- 청송림
	{ -200, -200 },
	{ -420, -20 },
	{ -250, 220 },
	{ -360, 180 },
	-- 백령과 서쪽
	{ -688, -122 }, -- (가파른 비탈을 피해 옮겼다)
	{ -561, -204 }, -- 관운잔도 위
	{ -992, -660 },
	{ -600, 120 },
	{ -1250, 60 },
	-- 북쪽 (명경호, 설원, 초원)
	{ 160, -700 },
	{ -200, -1100 },
	{ 300, -1100 },
	{ 700, -900 },
	-- 동쪽 (태고림, 죽림)
	{ 900, -200 },
	{ 1150, -450 },
	{ 620, 260 },
	-- 남쪽 (홍로성, 주염산, 무택)
	{ 420, 640 },
	{ 703, 766 }, -- 주염산 길 위
	{ 80, 1100 },
	{ 300, 1250 },
	-- 남서 (황구, 한해)
	{ -360, 520 },
	{ -800, 900 },
	{ -1100, 820 },
	{ -500, 1450 },
	-- 하늘섬
	{ Land.SKY.x + 40, Land.SKY.z - 30, sky = true },
}

return Sites
