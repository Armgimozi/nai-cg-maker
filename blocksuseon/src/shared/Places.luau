-- 맵의 땅 이름. 플레이어가 어느 땅에 있는지 화면에 알려 주는 데 쓴다 (맵에 이름표를 띄우지 않는다).
-- 위에서부터 차례로 보고 처음 맞는 땅을 고른다 (좁은 땅을 넓은 땅보다 앞에 둔다).
-- 높이(y)를 넘기면 등선향처럼 떠 있는 땅과 그 아래 땅을 가른다.

local Land = require(script.Parent.Land)

export type Region = {
	id: string,
	name: string,
	sub: string?, -- 들어설 때 이름 아래 작게
	-- 모양: 원(x, z, r), 네모(x1, x2, z1, z2), 또는 test
	x: number?,
	z: number?,
	r: number?,
	x1: number?,
	x2: number?,
	z1: number?,
	z2: number?,
	minY: number?, -- 이 높이보다 위에 있어야 이 땅
	tier: number, -- 요수 위험도 (0 이면 요수가 들어오지 않는 곳)
	test: ((x: number, z: number) -> boolean)?,
}

local Places = {}

-- 전송진 위에 섰다고 치는 거리 (수평, 스터드). 서버(Travel)와 화면(전송진 창 닫기)이 같이 쓴다
Places.WAYPOINT_RADIUS = 14
-- 처음부터 열려 있는 집 전송진 (여기로 가는 삯은 공짜)
Places.HOME_WAYPOINT = "wp_yeonguk"

local peak = Land.PEAK

Places.REGIONS = {
	{
		id = "deungseon",
		tier = 5,
		name = "등선향",
		sub = "답천사막 위에 뜬 섬, 승천문이 있는 곳",
		x = Land.ISLAND.x,
		z = Land.ISLAND.z,
		r = 175,
		minY = 200,
	},
	{ id = "yeonguk", tier = 0, name = "연국", sub = "연산 아래 작은 마을", x = 0, z = 0, r = 140 },
	{
		id = "cheonsaek",
		tier = 0,
		name = "천색성",
		sub = "벽라국 장인들의 성",
		x1 = 330,
		x2 = 510,
		z1 = -90,
		z2 = 70,
	},
	{
		id = "volcano",
		tier = 3,
		name = "화구산",
		sub = "불이 꺼지지 않는 산",
		x = Land.VOLCANO.x,
		z = Land.VOLCANO.z,
		r = 235,
	},
	{
		id = "dapcheondae",
		tier = 4,
		name = "답천대",
		sub = "하늘을 밟는 바위",
		x = Land.MESA.x,
		z = Land.MESA.z,
		r = 105,
	},
	{
		id = "ruins",
		tier = 4,
		name = "중령성국 폐허",
		sub = "용맥을 빼앗기고 모래에 묻힌 나라",
		x = Land.RUINS.x,
		z = Land.RUINS.z,
		r = 120,
	},
	{
		id = "seoak",
		tier = 0,
		name = "서악 마을",
		sub = "쇄천봉 기슭의 마을",
		x = Land.SEOAK.x,
		z = Land.SEOAK.z,
		r = 100,
	},
	{
		id = "summit",
		tier = 4,
		name = "쇄천봉 꼭대기",
		sub = "구름보다 높은 곳",
		x = peak.x,
		z = peak.z,
		r = 70,
	},
	{
		id = "swaecheon",
		tier = 3,
		name = "쇄천봉",
		sub = "하늘을 부순다는 서쪽의 큰 산",
		test = function(x, z)
			if (x - peak.x) ^ 2 + (z - peak.z) ^ 2 < (peak.radius * 0.85) ^ 2 then
				return true
			end
			for _, other in Land.PEAKS do
				if (x - other[1]) ^ 2 + (z - other[2]) ^ 2 < (other[4] * 0.8) ^ 2 then
					return true
				end
			end
			return false
		end,
	},
	{
		id = "snowfield",
		tier = 4,
		name = "서천 설원",
		sub = "세상 서쪽 끝의 눈벌",
		test = function(x, z)
			return x < -990 and z > -700 and z < 420
		end,
	},
	{
		id = "pool",
		tier = 1,
		name = "용소",
		sub = "폭포가 떨어지는 깊은 못",
		x = Land.POOL.x,
		z = Land.POOL.z,
		r = 50,
	},
	{
		id = "gorge",
		tier = 2,
		name = "연하 협곡",
		sub = "바다로 흘러가는 물길",
		test = function(x, z)
			return z > 126 and Land.polyDist(x, z, Land.GORGE) < 40
		end,
	},
	{
		id = "southisle",
		tier = 3,
		name = "남천도",
		sub = "해룡족 천문대가 있던 섬",
		x = Land.SOUTH_ISLE.x,
		z = Land.SOUTH_ISLE.z,
		r = 100,
	},
	{
		id = "haeryong",
		tier = 2,
		name = "해룡 사당",
		sub = "바다를 굽어보는 곶",
		x = -330,
		z = 730,
		r = 70,
	},
	{
		id = "sea",
		tier = 2,
		name = "남해",
		sub = "끝없는 바다",
		test = function(x, z)
			return z > Land.coastZ(x)
		end,
	},
	{
		id = "steppe",
		tier = 2,
		name = "북방 대초원",
		sub = "바람이 그치지 않는 들",
		test = function(_x, z)
			return z < -560
		end,
	},
	{
		id = "desert",
		tier = 3,
		name = "답천사막",
		sub = "수계 한가운데의 모래바다",
		test = function(x, _z)
			return x > 600
		end,
	},
	{
		id = "byeokra",
		tier = 2,
		name = "벽라국",
		sub = "사막과 맞닿은 메마른 땅",
		test = function(x, _z)
			return x > 220
		end,
	},
	{
		id = "forest",
		tier = 1,
		name = "영초숲",
		sub = "영초와 천년영지가 돋는 숲",
		x1 = -470,
		x2 = -110,
		z1 = -340,
		z2 = 330,
	},
	{ id = "fields", tier = 1, name = "연국 들판", sub = "논밭과 들길" },
} :: { Region }

Places.byId = {} :: { [string]: Region }
for _, region in Places.REGIONS do
	Places.byId[region.id] = region
end

local function inside(region: Region, x: number, z: number, y: number?): boolean
	if region.minY and (y == nil or y < region.minY) then
		return false
	end
	if region.test then
		return region.test(x, z)
	elseif region.r then
		local dx, dz = x - (region.x :: number), z - (region.z :: number)
		return dx * dx + dz * dz <= region.r * region.r
	elseif region.x1 then
		return x >= region.x1
			and x <= (region.x2 :: number)
			and z >= (region.z1 :: number)
			and z <= (region.z2 :: number)
	end
	return true -- 모양이 없는 땅(들판)은 나머지 전부
end

-- 이 자리의 땅
function Places.regionAt(x: number, z: number, y: number?): Region
	for _, region in Places.REGIONS do
		if inside(region, x, z, y) then
			return region
		end
	end
	return Places.REGIONS[#Places.REGIONS]
end

-- 이 자리의 요수 위험도 (0 은 안전한 곳)
function Places.tierAt(x: number, z: number, y: number?): number
	return Places.regionAt(x, z, y).tier
end

return Places
