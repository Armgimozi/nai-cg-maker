-- 주변 풍경: 맵이 휑하지 않고 맵 끝(허공)이 안 보이게 섬 둘레를 채웁니다. 서버 시작 때 한 번만 만듭니다.
--   가장자리 두 가지(Config.SCENERY_EDGE):
--     "Ocean"     모래사장(등대·부두·파라솔·야자수) + 물가 거품 + 얕은 물 + 중간 물빛 띠 + 수평선까지 먼바다
--                 + 먼 작은 섬·돛단배
--     "Mountains" 수평선까지 들판 + 숲 가장자리 + 나무 덩어리 + 엇갈린 초록 언덕 두 줄 + 눈 덮인 뾰족 산 두 겹
--                 + 풀 언덕에 박힌 두 단 폭포 절벽·물웅덩이·개울
--   공통: 산책로 고리 둘(안쪽 r 84, 부지 뒤 r 208) + 틈 정원 오솔길, 쐐기 틈 8곳의 주제 정원,
--         부지 뒤 숲띠, 꽃밭·덤불·바위·잔디 언덕·잔디 무늬, 가로등·벤치
-- 배치는 Scenery/Plan(순수 계산, 고정 시드), 모양은 Scenery/Props. 결과는 Workspace.Scenery 폴더(구역별 하위 폴더).
-- 바닥 섬(원기둥, 반지름 ParkLayout.ISLAND_RADIUS)은 default.project.json 의 Baseplate 라서
-- 여기서 오류가 나도 스폰 바닥은 항상 있습니다.

local Workspace = game:GetService("Workspace")

local Plan = require(script.Plan)
local Props = require(script.Props)

local Scenery = {}

Scenery.Plan = Plan

local WALL_THICKNESS = 2
local WALL_BOTTOM = -5
local ROUTE_HEIGHT = Plan.Tuning.ROUTE_HEIGHT
local ROUTE_MATERIAL = Enum.Material.Concrete -- ParkService 길과 같게

local SAND = Color3.fromRGB(240, 222, 170)
local FOAM = Color3.fromRGB(250, 252, 255)
local SHALLOW = Color3.fromRGB(96, 214, 222)
local MID = Color3.fromRGB(62, 170, 216)
local DEEP = Color3.fromRGB(40, 128, 204)
local STREAM = Color3.fromRGB(74, 172, 230)

local built: Folder? = nil

-- 구역별 하위 폴더(없으면 만듦) + 파트 수 셀 구역 지정
local function zoneFolder(root: Folder, name: string): Folder
	Props.setZone(name)
	local existing = root:FindFirstChild(name)
	if existing and existing:IsA("Folder") then
		return existing
	end
	local folder = Instance.new("Folder")
	folder.Name = name
	folder.Parent = root
	return folder
end

-- 반지름 radius 원을 따라 segments 개의 곧은 판을 세움(원 바깥쪽 모서리까지 틈 없게 조금 길게).
-- radius = 판 가운데 선(판 폭 depth 는 반지름 방향)
local function ringOfBlocks(
	parent: Instance,
	name: string,
	radius: number,
	segments: number,
	depth: number,
	height: number,
	centerY: number,
	color: Color3,
	material: Enum.Material,
	solid: boolean
): { BasePart }
	local list = {}
	local length = 2 * (radius + depth / 2) * math.tan(math.pi / segments) + 0.05
	for k = 0, segments - 1 do
		local angle = (k + 0.5) / segments * math.pi * 2
		local direction = Vector3.new(math.cos(angle), 0, math.sin(angle))
		local center = direction * radius + Vector3.new(0, centerY, 0)
		table.insert(
			list,
			Props.block(
				parent,
				name,
				Vector3.new(length, height, depth),
				CFrame.lookAt(center, center + direction),
				color,
				material,
				solid
			)
		)
	end
	return list
end

-- 보이지 않는 벽(가장자리에서 더 못 나가게). 벽 안쪽 면이 반지름 wall.Radius
local function buildWall(parent: Instance, wall)
	local walls = ringOfBlocks(
		parent,
		"EdgeWall",
		wall.Radius + WALL_THICKNESS / 2,
		wall.Segments,
		WALL_THICKNESS,
		wall.Height,
		WALL_BOTTOM + wall.Height / 2,
		Color3.new(1, 1, 1),
		Enum.Material.SmoothPlastic,
		true
	)
	for _, part in walls do
		part.Transparency = 1
	end
end

-- 산책로: 고리 + 틈 정원 오솔길
local function buildWalkways(parent: Instance, plan: Plan.Result)
	for _, ring in plan.Rings do
		ringOfBlocks(
			parent,
			"Walkway",
			ring.Radius,
			ring.Segments,
			ring.Width,
			ROUTE_HEIGHT,
			ring.Top - ROUTE_HEIGHT / 2,
			Props.PATH,
			ROUTE_MATERIAL,
			true
		)
	end
	for _, trail in plan.Trails do
		Props.segment(parent, "GardenTrail", trail, ROUTE_HEIGHT, Props.PATH, ROUTE_MATERIAL, true)
	end
end

-- 바다: 모래사장(걸을 수 있음) + 거품 띠 + 얕은 물 + 먼바다 판(수평선까지)
local function buildOcean(parent: Instance)
	local O = Plan.Tuning.OCEAN
	Props.disc(parent, "Beach", Vector3.new(0, O.BeachTop - 4, 0), 4, O.BeachRadius * 2, SAND, Enum.Material.Sand, true)
	Props.disc(parent, "Foam", Vector3.new(0, O.FoamTop - 0.3, 0), 0.3, O.FoamRadius * 2, FOAM)
	Props.disc(parent, "ShallowWater", Vector3.new(0, O.ShallowTop - 0.4, 0), 0.4, O.ShallowRadius * 2, SHALLOW)
	Props.disc(parent, "MidWater", Vector3.new(0, O.MidTop - 0.2, 0), 0.2, O.MidRadius * 2, MID)
	local tile = O.OceanTile
	for i = -O.OceanTiles, O.OceanTiles do
		for j = -O.OceanTiles, O.OceanTiles do
			Props.block(
				parent,
				"Ocean",
				Vector3.new(tile, 2, tile),
				CFrame.new(i * tile, O.DeepTop - 1, j * tile),
				DEEP
			)
		end
	end
end

-- 산맥 쪽 들판(섬보다 살짝 낮은 풀 판을 수평선까지 깔아서 멀리서도 끝이 안 보이게)
local function buildField(parent: Instance)
	local M = Plan.Tuning.MOUNTAINS
	local tile = M.FieldTile
	for i = -M.FieldTiles, M.FieldTiles do
		for j = -M.FieldTiles, M.FieldTiles do
			Props.block(
				parent,
				"Field",
				Vector3.new(tile, 2, tile),
				CFrame.new(i * tile, M.FieldTop - 1, j * tile),
				Props.GRASS,
				Enum.Material.Grass,
				true
			)
		end
	end
end

-- 파트 수 요약 문자열("구역 n, ...") + 합계
local function summary(counts: { [string]: number }): (string, number)
	local names = {}
	local total = 0
	for name, count in counts do
		table.insert(names, name)
		total += count
	end
	table.sort(names)
	local parts = {}
	for _, name in names do
		table.insert(parts, name .. " " .. counts[name])
	end
	return table.concat(parts, ", "), total
end

-- 풍경을 만들어 Workspace.Scenery 에 둠(두 번째 호출부터는 그대로 돌려줌).
-- variant: "Ocean" | "Mountains"(모르는 값이면 Ocean). 반환: 폴더, 구역별 파트 수
function Scenery.build(variant: string?): (Folder, { [string]: number })
	if built then
		return built, Props.counts()
	end
	if variant ~= nil and Plan.variant(variant) ~= variant then
		warn("[Scenery] 모르는 가장자리 풍경 '" .. tostring(variant) .. "' → " .. Plan.DEFAULT_VARIANT)
	end
	local plan = Plan.make(variant)
	Props.resetCounts()

	local root = Instance.new("Folder")
	root.Name = "Scenery"

	local ground = zoneFolder(root, "Ground")
	if plan.Variant == "Ocean" then
		buildOcean(ground)
	else
		buildField(ground)
	end
	buildWall(zoneFolder(root, "Walls"), plan.Wall)
	buildWalkways(zoneFolder(root, "Walkways"), plan)

	for _, item in plan.Items do
		if not Props.build(zoneFolder(root, item.Zone), item) then
			warn("[Scenery] 모르는 장식 종류: " .. item.Kind)
		end
	end

	if #plan.Peaks > 0 or #plan.Stream > 0 then
		local mountains = zoneFolder(root, "Mountains")
		for _, peak in plan.Peaks do
			for _, triangle in peak.Triangles do
				Props.peakFace(mountains, triangle)
			end
		end
		for _, segment in plan.Stream do
			Props.segment(mountains, "Stream", segment, 0.3, STREAM, Enum.Material.SmoothPlastic, false)
		end
	end

	root.Parent = Workspace
	built = root
	local counts = Props.counts()
	local text, total = summary(counts)
	print(string.format("[Scenery] %s: 파트 %d개 (%s)", plan.Variant, total, text))
	return root, counts
end

return Scenery
