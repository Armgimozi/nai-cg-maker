-- 옥반(玉盤)의 땅 이름과 요수 위험도. 들어설 때 화면에 이름을 띄우고(client/Hud, PlaceBanner),
-- 요수·광맥이 위험도를 본다(server/MobService, Ores). 자리 좌표는 Shared.Land 의 땅 모양을 따른다.
-- 위에서부터 차례로 보고 처음 맞는 땅을 고른다 (좁은 땅을 넓은 땅보다 앞에).
-- tier: 요수 위험도의 바닥값. 송계에서 거리로 정한 값(Places.ring)과 큰 쪽을 쓴다.
--       0 이면 요수가 들어오지 않는 곳(마을), nil 이면 거리로만.
-- regionAt 은 플레이어마다 자주 부르므로 원·네모를 먼저, 노이즈(blob)·선(polyDist)을 보는 넓은 땅을 뒤에 둔다
-- (Lune 에서 한 번에 10µs 안팎).
local Land = require(script.Parent.Land)

export type Region = {
	id: string,
	name: string,
	sub: string?,
	tier: number?,
	minY: number?, -- 이 높이 아래면 아니다 (하늘섬, 꼭대기)
	x: number?,
	z: number?,
	r: number?,
	x1: number?,
	x2: number?,
	z1: number?,
	z2: number?,
	test: ((x: number, z: number) -> boolean)?,
}

local Places = {}
Places.WAYPOINT_RADIUS = 14
Places.HOME_WAYPOINT = "wp_home" -- 처음부터 열려 있는 진 (송계 마을)

-- 송계에서 거리로 정하는 위험도 고리
Places.RINGS = { 170, 560, 900, 1250, 1600 } -- 이 반지름 안이면 0, 1, 2, 3, 4, 바깥은 5
function Places.ring(x: number, z: number): number
	local r = math.sqrt(x * x + z * z)
	for tier, radius in Places.RINGS do
		if r < radius then
			return tier - 1
		end
	end
	return 5
end

local function within(p, d: number)
	return function(x: number, z: number): boolean
		return Land.polyDist(x, z, p, d) < d
	end
end
local function inBlob(b, t: number)
	return function(x: number, z: number): boolean
		return Land.blob(x, z, b) > t
	end
end

local peak = Land.PEAK
local vol = Land.VOLCANO

Places.REGIONS = {
	-- 하늘
	{
		id = "sky",
		tier = 5,
		name = "청허경",
		sub = "바다 위에 뜬 섬, 우화문이 있는 곳",
		x = Land.SKY.x,
		z = Land.SKY.z,
		r = 210,
		minY = 250,
	},
	-- 사람 사는 곳 (요수가 들어오지 않는다)
	{ id = "home", tier = 0, name = "송계 마을", sub = "솔숲 개울가의 작은 마을", x = 0, z = 0, r = 150 },
	{
		id = "city",
		tier = 0,
		name = "홍로성",
		sub = "불을 다루는 장인들의 성",
		x1 = 205,
		x2 = 395,
		z1 = 445,
		z2 = 635,
	},
	{
		id = "ungok",
		tier = 0,
		name = "운곡 마을",
		sub = "백령 기슭 구름골 마을",
		x = Land.VILLAGE_W.x,
		z = Land.VILLAGE_W.z,
		r = 100,
	},
	{
		id = "camp",
		tier = 0,
		name = "마령채",
		sub = "백초원 유목민의 목책 마을",
		x = Land.CAMP.x,
		z = Land.CAMP.z,
		r = 90,
	},
	{
		id = "port",
		tier = 0,
		name = "백사포",
		sub = "흰 모래 포구, 고깃배가 드나드는 곳",
		x = Land.PORT.x,
		z = Land.PORT.z,
		r = 90,
	},
	{
		id = "hermit",
		tier = 0,
		name = "청음암",
		sub = "대숲 속 작은 암자",
		x = Land.HERMIT.x,
		z = Land.HERMIT.z,
		r = 45,
	},
	-- 과업 자리가 있는 곳
	{
		id = "summit",
		tier = 4,
		name = "관운봉 꼭대기",
		sub = "구름을 꿰뚫는 봉우리",
		x = peak.x,
		z = peak.z,
		r = 70,
		minY = 420,
	},
	{
		id = "west_altar",
		tier = 3,
		name = "낙조대",
		sub = "해 지는 바다를 굽어보는 서쪽 성대",
		x = Land.STARS.west.x,
		z = Land.STARS.west.z,
		r = 90,
	},
	{
		id = "north_altar",
		tier = 3,
		name = "북진대",
		sub = "북극성을 우러르는 설원의 성대",
		x = Land.STARS.north.x,
		z = Land.STARS.north.z,
		r = 60,
	},
	{
		id = "east_altar",
		tier = 3,
		name = "조양대",
		sub = "아침 해를 맞는 동쪽 성대",
		x = Land.STARS.east.x,
		z = Land.STARS.east.z,
		r = 60,
	},
	{
		id = "south_altar",
		tier = 3,
		name = "남명대",
		sub = "안개 늪 가운데 남쪽 성대",
		x = Land.STARS.south.x,
		z = Land.STARS.south.z,
		r = 60,
	},
	{
		id = "mesa",
		tier = 3,
		name = "관성대",
		sub = "별을 보던 탁상 바위, 칠성단과 팔괘 기둥",
		x = Land.MESA.x,
		z = Land.MESA.z,
		r = 115,
	}, -- 기슭 전송진(106)까지
	{
		id = "pool",
		tier = 1,
		name = "벽담",
		sub = "벽계 폭포 아래 푸른 못",
		x = Land.POOL.x,
		z = Land.POOL.z,
		r = 50,
	},
	{
		id = "tree",
		tier = 1,
		name = "만년목",
		sub = "만 년을 살았다는 큰 나무",
		x = Land.TREE.x,
		z = Land.TREE.z,
		r = 45,
	},
	{
		id = "earth",
		tier = 1,
		name = "황구 토단",
		sub = "누런 흙을 쌓아 올린 옛 제단",
		x = Land.EARTH.x,
		z = Land.EARTH.z,
		r = 45,
	},
	{
		id = "mine",
		tier = 1,
		name = "백금굴",
		sub = "백금이 나는 바위 언덕의 굴",
		x = Land.KNOLL.x + 22,
		z = Land.KNOLL.z,
		r = 55,
	},
	-- 볼거리
	{
		id = "falls",
		tier = 2,
		name = "비류폭",
		sub = "명경호로 떨어지는 백 길 폭포",
		x = -255,
		z = -718,
		r = 60,
	},
	{
		id = "table",
		tier = 3,
		name = "비류대",
		sub = "폭포가 시작되는 높은 대지",
		test = inBlob(Land.TABLE, 0.5),
	},
	{
		id = "lake",
		tier = 2,
		name = "명경호",
		sub = "하늘이 그대로 비치는 거울 호수",
		x = Land.LAKE.x,
		z = Land.LAKE.z,
		r = 220,
	},
	{
		id = "tarn",
		tier = 4,
		name = "빙경담",
		sub = "빙하 위 얼어붙은 못",
		x = Land.TARN.x,
		z = Land.TARN.z,
		r = 60,
	},
	{
		id = "glacier",
		tier = 4,
		name = "설하",
		sub = "응봉에서 바다까지 흘러내린 얼음 강",
		test = within(Land.GLACIER, 110),
	},
	{
		id = "crater",
		tier = 4,
		name = "주염산 화구",
		sub = "끓는 불이 고인 산꼭대기",
		x = vol.x,
		z = vol.z,
		r = vol.crater + 25,
	},
	{
		id = "volcano",
		tier = 3,
		name = "주염산",
		sub = "불이 꺼지지 않는 붉은 산",
		x = vol.x,
		z = vol.z,
		r = vol.radius + 10,
	},
	{
		id = "ruins",
		tier = 4,
		name = "침사국 옛터",
		sub = "모래에 가라앉은 옛 나라",
		x = Land.RUINS.x,
		z = Land.RUINS.z,
		r = 120,
	},
	{
		id = "salt",
		tier = 4,
		name = "소금벌",
		sub = "옛 바다가 남긴 흰 소금밭",
		x = Land.SALT.x,
		z = Land.SALT.z,
		r = 160,
	},
	{
		id = "oasis",
		tier = 2,
		name = "녹주",
		sub = "마른 바다 한가운데의 샘",
		x = Land.OASIS.x,
		z = Land.OASIS.z,
		r = 60,
	},
	{
		id = "swords",
		tier = 3,
		name = "검총",
		sub = "칼이 무덤처럼 꽂힌 옛 싸움터",
		x = -260,
		z = 1120,
		r = 90,
	},
	{
		id = "canyon",
		tier = 2,
		name = "단애곡",
		sub = "붉은 벼랑이 이어진 마른 골짜기",
		test = within(Land.CANYON, 40),
	},
	{
		id = "temple",
		tier = 3,
		name = "무명사 옛터",
		sub = "이름이 지워진 숲속 절터",
		x = Land.TEMPLE.x,
		z = Land.TEMPLE.z,
		r = 70,
	},
	{
		id = "stones",
		tier = 3,
		name = "팔방석진",
		sub = "여덟 선돌이 둘러선 들판의 진",
		x = Land.STONES.x,
		z = Land.STONES.z,
		r = 60,
	},
	{
		id = "cape",
		tier = 4,
		name = "망선대",
		sub = "신선을 기다리던 바위 곶, 운제가 시작되는 곳",
		x = Land.CAPE.x,
		z = Land.CAPE.z,
		r = 130,
	},
	{
		id = "tower",
		tier = 4,
		name = "무택 고탑",
		sub = "늪에 반쯤 잠긴 옛 탑",
		x = Land.TOWER.x,
		z = Land.TOWER.z,
		r = 40,
	},
	{
		id = "gorge",
		tier = 2,
		name = "벽계협",
		sub = "벽계가 무택으로 흘러가는 협곡",
		test = function(x, z)
			return z > 126 and Land.polyDist(x, z, Land.GORGE, 40) < 40
		end,
	},
	{
		id = "pass",
		tier = 2,
		name = "송풍령",
		sub = "솔바람이 넘는 고개",
		test = within(Land.BENCHES.pass, 60),
	},
	-- 넓은 땅
	{
		id = "mountain",
		tier = 3,
		name = "백령",
		sub = "서쪽을 가로막은 흰 산줄기",
		test = function(x, z)
			if (x - peak.x) ^ 2 + (z - peak.z) ^ 2 < (peak.radius * 0.9) ^ 2 then
				return true
			end
			for _, other in Land.PEAKS do
				if (x - other[1]) ^ 2 + (z - other[2]) ^ 2 < (other[4] * 0.8) ^ 2 then
					return true
				end
			end
			return Land.polyDist(x, z, Land.SPINE, 120) < 110
		end,
	},
	{
		id = "snowfield",
		tier = 3,
		name = "백랑설원",
		sub = "흰 물결처럼 눈이 쌓인 북쪽 벌판",
		test = inBlob(Land.SNOW, 0.5),
	},
	{ id = "marsh", tier = 3, name = "무택", sub = "안개가 걷히지 않는 늪", test = inBlob(Land.MARSH, 0.5) },
	{
		id = "bamboo",
		tier = 2,
		name = "청음죽림",
		sub = "바람이 대숲을 울리는 곳",
		test = inBlob(Land.BAMBOO, 0.5),
	},
	{
		id = "grove",
		tier = 1,
		name = "청송림",
		sub = "다리 건너 영초가 돋는 솔숲",
		x1 = -470,
		x2 = -110,
		z1 = -340,
		z2 = 330,
	},
	{ id = "loess", name = "황구", sub = "누런 흙 언덕이 굽이치는 땅", test = inBlob(Land.LOESS, 0.5) }, -- 거리로 (1~2)
	{
		id = "desert",
		name = "한해",
		sub = "물 대신 모래가 출렁이는 마른 바다",
		test = inBlob(Land.DESERT, 0.5),
	}, -- 거리로 (2~5)
	{ id = "forest", name = "태고림", sub = "해를 가리는 오래된 숲", test = inBlob(Land.FOREST, 0.5) }, -- 거리로 (2~5)
	{ id = "steppe", name = "백초원", sub = "온갖 풀이 바람에 눕는 들", test = inBlob(Land.STEPPE, 0.5) }, -- 거리로 (2~5)
	-- 바다
	{
		id = "isle_moon",
		tier = 5,
		name = "월아도",
		sub = "초승달 모양 섬, 옛 천문대 터",
		x = Land.ISLES.crescent.x,
		z = Land.ISLES.crescent.z,
		r = 140,
	},
	{
		id = "isle_mist",
		tier = 5,
		name = "연파군도",
		sub = "물안개 속 작은 섬들",
		x = 1960,
		z = 380,
		r = 220,
	},
	{
		id = "isle_whale",
		tier = 5,
		name = "경도",
		sub = "고래 등 같은 바위섬",
		x = Land.ISLES.whale.x,
		z = Land.ISLES.whale.z,
		r = 190,
	},
	{
		id = "rim",
		tier = 5,
		name = "천애",
		sub = "바다가 운해로 쏟아지는 세상 끝",
		test = function(x, z)
			return x * x + z * z > (Land.EDGE - 120) ^ 2
		end,
	},
	{
		id = "sea",
		name = "환해",
		sub = "땅을 두른 바다",
		test = function(x, z)
			return Land.shoreDist(x, z) > 0
		end,
	}, -- 거리로 (4~5)
	{ id = "fields", name = "송계 들판", sub = "논밭과 들길" }, -- 나머지 (거리로)
} :: { Region }

Places.byId = {} :: { [string]: Region }
for _, region: Region in Places.REGIONS do
	Places.byId[region.id] = region
end

local function inside(region, x: number, z: number, y: number?): boolean
	if region.minY and (y == nil or y < region.minY) then
		return false
	end
	if region.test then
		return region.test(x, z)
	elseif region.r then
		local dx, dz = x - region.x, z - region.z
		return dx * dx + dz * dz <= region.r * region.r
	elseif region.x1 then
		return x >= region.x1 and x <= region.x2 and z >= region.z1 and z <= region.z2
	end
	return true
end

function Places.regionAt(x: number, z: number, y: number?): Region
	for _, region in Places.REGIONS do
		if inside(region, x, z, y) then
			return region
		end
	end
	return Places.REGIONS[#Places.REGIONS]
end

-- 이 자리의 요수 위험도
function Places.tierAt(x: number, z: number, y: number?): number
	local region = Places.regionAt(x, z, y)
	if region.tier == 0 then
		return 0
	end
	return math.max(region.tier or 0, Places.ring(x, z))
end

return Places
