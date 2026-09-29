--!strict
-- 공원 부지·길 배치의 기준(순수 계산: Instance/Vector3 없이 숫자만). ParkService 와 Scenery 가 같이 씁니다.
--
-- 좌표: 광장 중심이 원점, 땅 윗면 y = 0. 방향 각도 a 는 (cos a, 0, sin a) 쪽(스폰 정면 -Z = 270도).
-- 부지 좌표계(ParkService 의 plot.CFrame): 부지 중앙이 원점, +Z(Dir) = 광장에서 멀어지는 쪽,
--   -Z = 입구(광장 쪽), +X(Right) = CFrame.lookAt(부지 중심, 원점) 의 RightVector.
-- 여기 숫자를 바꾸면 부지 위치가 바뀝니다(ParkService 가 그대로 씀). 장식(Scenery)은 blocked 로 비켜 갑니다.

local ParkLayout = {}

ParkLayout.PLOT_COUNT = 8 -- 서버 최대 인원과 같게 (Creator Hub 에서 서버 크기 8)
ParkLayout.RING_RADIUS = 115 -- 광장 중심에서 부지 입구(광장 쪽 가장자리)까지
ParkLayout.FIRST_ANGLE = 247.5 -- 첫 부지 방향(도). 스폰 정면(270도) 근처
ParkLayout.PLAZA_EDGE = 44 -- 길이 시작되는 곳(광장 둘레 계단 아래에서부터)

ParkLayout.PLOT_WIDTH = 76
ParkLayout.PLOT_DEPTH = 80
ParkLayout.BORDER = 1.5 -- 부지 둘레 색 띠 폭
ParkLayout.PATH_WIDTH = 10 -- 광장 → 입구 길 폭

-- 장식이 비켜야 할 곳 ---------------------------------------------------------
-- 광장(반지름 45) + 둘레 계단(3) + 둘레 나무(World: 반지름 56, 잎 지름 7.5) 바깥까지. 스폰·지구본도 이 안
ParkLayout.PLAZA_CLEAR = 62
-- 입구 앞 간판 자리: 주인 간판 아치(판자 28 + 기둥, 밑으로 7.5 스터드) / 빈 부지 말뚝(길 옆 x = 9)
ParkLayout.SIGN_HALF_WIDTH = 16.5
ParkLayout.SIGN_DEPTH = 8.5 -- 입구(둘레 띠 앞 가장자리)에서 광장 쪽으로
ParkLayout.PLOT_MARGIN = 3 -- 부지(+둘레 띠) 둘레 여유
ParkLayout.PATH_MARGIN = 2 -- 길 양옆 여유
ParkLayout.SIGN_MARGIN = 1

-- 섬(바닥) 반지름. default.project.json 의 Workspace.Baseplate(원기둥) 지름의 절반과 같아야 함(테스트가 확인)
ParkLayout.ISLAND_RADIUS = 250

export type Layout = { Angle: number, Radius: number, Path: boolean }

-- 부지 하나의 바닥 사각형(둘레 띠 포함)과 입구 길
export type Footprint = {
	Index: number,
	Angle: number, -- 라디안
	CenterX: number, -- 부지 중앙(바닥)
	CenterZ: number,
	DirX: number, -- 부지 +Z = 광장 중심 → 부지 방향(단위 벡터)
	DirZ: number,
	RightX: number, -- 부지 +X
	RightZ: number,
	HalfWidth: number, -- 둘레 띠 포함 반폭(부지 X)
	HalfDepth: number, -- 둘레 띠 포함 반깊이(부지 Z)
	PathFrom: number, -- 길: 광장 중심에서 부지 방향으로 PathFrom ~ PathTo, 폭 PATH_WIDTH
	PathTo: number,
}

-- 부지 순서 = 배정 순서(가장 작은 빈 번호부터). 모두 한 고리(RING_RADIUS)에 있고 광장에서 길이 이어짐
ParkLayout.LAYOUT = {} :: { Layout }
for i = 0, ParkLayout.PLOT_COUNT - 1 do
	table.insert(ParkLayout.LAYOUT, {
		Angle = math.rad(ParkLayout.FIRST_ANGLE + 360 / ParkLayout.PLOT_COUNT * i),
		Radius = ParkLayout.RING_RADIUS,
		Path = true,
	})
end

local FOOTPRINTS: { Footprint } = {}
for index, layout in ParkLayout.LAYOUT do
	local dirX, dirZ = math.cos(layout.Angle), math.sin(layout.Angle)
	local centerDistance = layout.Radius + ParkLayout.PLOT_DEPTH / 2
	table.insert(FOOTPRINTS, {
		Index = index,
		Angle = layout.Angle,
		CenterX = dirX * centerDistance,
		CenterZ = dirZ * centerDistance,
		DirX = dirX,
		DirZ = dirZ,
		-- CFrame.lookAt(중심, 원점).RightVector = (-Dir) x (0, 1, 0)
		RightX = dirZ,
		RightZ = -dirX,
		HalfWidth = ParkLayout.PLOT_WIDTH / 2 + ParkLayout.BORDER,
		HalfDepth = ParkLayout.PLOT_DEPTH / 2 + ParkLayout.BORDER,
		PathFrom = ParkLayout.PLAZA_EDGE,
		PathTo = if layout.Path then layout.Radius + 1 else ParkLayout.PLAZA_EDGE,
	})
end

-- 모든 부지의 바닥 사각형(복사본)
function ParkLayout.footprints(): { Footprint }
	local list = {}
	for _, footprint in FOOTPRINTS do
		table.insert(list, table.clone(footprint))
	end
	return list
end

-- 월드 (x, z) → 부지 좌표 (x, z)
function ParkLayout.toLocal(footprint: Footprint, x: number, z: number): (number, number)
	local dx, dz = x - footprint.CenterX, z - footprint.CenterZ
	return dx * footprint.RightX + dz * footprint.RightZ, dx * footprint.DirX + dz * footprint.DirZ
end

-- 이웃 부지 사이 쐐기 모양 잔디 틈의 가운데 방향(라디안). gapAngles()[i] = i 번 부지와 i+1 번 부지 사이
function ParkLayout.gapAngles(): { number }
	local list = {}
	for _, layout in ParkLayout.LAYOUT do
		table.insert(list, layout.Angle + math.pi / ParkLayout.PLOT_COUNT)
	end
	return list
end

-- 틈 가운데 선에서 광장 중심으로부터 rho 만큼 간 곳의 틈 반폭(가운데 선에 수직, 부지 둘레 띠까지). 음수면 틈 없음
function ParkLayout.gapHalfWidth(rho: number): number
	local half = math.pi / ParkLayout.PLOT_COUNT
	return (rho * math.sin(half) - (ParkLayout.PLOT_WIDTH / 2 + ParkLayout.BORDER)) / math.cos(half)
end

-- (x, z) 에 반지름 pad 인 장식을 두면 광장/부지/간판/길을 침범하는지. 침범하면 true 와 이유
-- ("plaza" | "plot" | "sign" | "path")
function ParkLayout.blocked(x: number, z: number, pad: number?): (boolean, string?)
	local p = pad or 0
	if x * x + z * z <= (ParkLayout.PLAZA_CLEAR + p) ^ 2 then
		return true, "plaza"
	end
	for _, footprint in FOOTPRINTS do
		local lx, lz = ParkLayout.toLocal(footprint, x, z)
		local plotPad = p + ParkLayout.PLOT_MARGIN
		if math.abs(lx) <= footprint.HalfWidth + plotPad and math.abs(lz) <= footprint.HalfDepth + plotPad then
			return true, "plot"
		end
		local signPad = p + ParkLayout.SIGN_MARGIN
		if
			math.abs(lx) <= ParkLayout.SIGN_HALF_WIDTH + signPad
			and lz <= -footprint.HalfDepth
			and lz >= -footprint.HalfDepth - ParkLayout.SIGN_DEPTH - signPad
		then
			return true, "sign"
		end
		-- 길은 광장 중심에서 부지 방향으로 곧게 뻗으므로 원점 기준으로 잼
		local along = x * footprint.DirX + z * footprint.DirZ
		local side = x * footprint.RightX + z * footprint.RightZ
		local pathPad = p + ParkLayout.PATH_MARGIN
		if
			footprint.PathTo > footprint.PathFrom
			and math.abs(side) <= ParkLayout.PATH_WIDTH / 2 + pathPad
			and along >= footprint.PathFrom - pathPad
			and along <= footprint.PathTo + pathPad
		then
			return true, "path"
		end
	end
	return false, nil
end

return ParkLayout
