-- 맵의 땅 이름. 플레이어가 어느 땅에 있는지 화면에 알려 주는 데 쓴다 (맵에 이름표를 띄우지 않는다).
-- 땅은 위에서 본 타원이다. 여러 땅에 걸치면 더 좁은 땅을 고른다 (마을 안의 광장처럼).
-- 순수 데이터와 계산만 있다 (Roblox 전역을 쓰지 않는다).

export type Region = {
	id: string,
	name: string,
	sub: string?, -- 들어설 때 이름 아래 작게
	x: number,
	z: number,
	rx: number, -- 동서 반지름
	rz: number, -- 남북 반지름
	minY: number?, -- 이 높이 아래면 이 땅이 아니다 (떠 있는 섬 등)
}

local Places = {}

-- 전송진 위에 섰다고 치는 거리 (수평, 스터드). 서버(Travel)와 화면(전송진 창 닫기)이 같이 쓴다
Places.WAYPOINT_RADIUS = 14

Places.REGIONS = {
	{ id = "yeonguk", name = "연국", sub = "영맥 웅덩이가 있는 마을", x = 0, z = 0, rx = 96, rz = 96 },
	{
		id = "forest",
		name = "영초숲",
		sub = "영초와 천년영지가 돋는 숲",
		x = -190,
		z = 0,
		rx = 96,
		rz = 180,
	},
	{ id = "creek", name = "개울", sub = "땅의 기운이 고이는 물가", x = -95, z = 0, rx = 14, rz = 380 },
	{
		id = "mountain",
		name = "영산",
		sub = "비탈을 따라 감아 오르는 산",
		x = 0,
		z = -250,
		rx = 96,
		rz = 96,
	},
	{ id = "altar", name = "천겁대", sub = "칠성단과 팔괘 기둥", x = 200, z = -160, rx = 44, rz = 44 },
	{ id = "star_east", name = "동쪽 성대", sub = "청룡 일곱 별", x = 330, z = 20, rx = 16, rz = 16 },
	{ id = "star_west", name = "서쪽 성대", sub = "백호 일곱 별", x = -330, z = 0, rx = 16, rz = 16 },
	{ id = "star_south", name = "남쪽 성대", sub = "주작 일곱 별", x = 0, z = 330, rx = 16, rz = 16 },
	{ id = "star_north", name = "북쪽 성대", sub = "현무 일곱 별", x = 0, z = -362, rx = 16, rz = 16 },
} :: { Region }

Places.byId = {} :: { [string]: Region }
for _, region in Places.REGIONS do
	Places.byId[region.id] = region
end

local function inside(region: Region, x: number, z: number, y: number?): boolean
	if region.minY and y and y < region.minY then
		return false
	end
	local dx, dz = (x - region.x) / region.rx, (z - region.z) / region.rz
	return dx * dx + dz * dz <= 1
end

-- 이 자리의 땅. 아무 땅도 아니면 nil (들판)
function Places.regionAt(x: number, z: number, y: number?): Region?
	local best: Region? = nil
	local bestArea = math.huge
	for _, region in Places.REGIONS do
		if inside(region, x, z, y) then
			local area = region.rx * region.rz
			if area < bestArea then
				best, bestArea = region, area
			end
		end
	end
	return best
end

return Places
