-- 맵 미리보기 도구 점검용 작은 장면: 지형 섬 + 물 + 재질별 파트. 게임 코드는 안 씀(도구가 제대로 그리는지만 봄).
-- 사용법(roblox-rng 폴더에서): WORLD=test tools/world_preview/preview.sh <출력 폴더> - test
--   (또는 직접) luaurun tools/world_preview/test_scene.luau → DUMP_BEGIN/DUMP_END 사이 JSON
-- 들어 있는 것
--   * 바다: 게임 풍경과 같은 방식(1024 판 3x3: 진흙 바닥 y -28..-24 + 물 -24..-4)
--   * 섬: WriteVoxelChannels 로 높이 지도(평지 y 0, 모래 비탈 → 물속), 언덕 + 바위 + 눈, 연못(물 윗면 y 0),
--     칠한 재질(Pavement 길, Cobblestone 광장, Brick·WoodPlanks 단, Mud·Ground·LeafyGrass·Basalt·Salt·Limestone·
--     Sandstone·Slate 조각), FillWedge 절벽
--   * 파트: 재질 견본 상자 한 줄(SmoothPlastic ~ Neon), 공·원기둥, 나무, 벤치, 유리
--   * 일부러 틀린 것(겹침 보고서 점검): 떠 있는 상자, 땅에 파묻힌 상자
-- 지형 규칙은 tools/roblox_mock.luau 의 Terrain 주석 참고.

local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()
local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()

local notes: { string } = {}
local function note(text: string)
	table.insert(notes, text)
	print("[test] " .. text)
end

-- 조명(게임과 같게)
local Lighting = Mock.Lighting
Lighting.ClockTime = 14.5
Lighting.Brightness = 2
Lighting.GlobalShadows = true
local atmosphere = Instance.new("Atmosphere")
atmosphere.Density = 0.3
atmosphere.Haze = 1.5
atmosphere.Parent = Lighting

Mock.origin = "Scenery"
local Terrain = workspace.Terrain
Terrain.WaterColor = Color3.fromRGB(28, 128, 150)
Terrain.WaterTransparency = 0.6
Terrain.WaterReflectance = 1
Terrain.WaterWaveSize = 0.15
Terrain.Decoration = true
Terrain:SetMaterialColor(Enum.Material.Grass, Color3.fromRGB(104, 168, 72))
Terrain:SetMaterialColor(Enum.Material.LeafyGrass, Color3.fromRGB(84, 150, 64))
Terrain:SetMaterialColor(Enum.Material.Sand, Color3.fromRGB(228, 206, 150))
Terrain:SetMaterialColor(Enum.Material.Mud, Color3.fromRGB(96, 84, 64))

-- 바다 --------------------------------------------------------------------------------
for i = -1, 1 do
	for j = -1, 1 do
		Terrain:FillBlock(CFrame.new(i * 1024, -26, j * 1024), Vector3.new(1024, 4, 1024), Enum.Material.Mud)
		Terrain:FillBlock(CFrame.new(i * 1024, -14, j * 1024), Vector3.new(1024, 20, 1024), Enum.Material.Water)
	end
end

-- 섬: 높이 지도 → WriteVoxelChannels --------------------------------------------------------
local HILL = Vector3.new(70, 0, -50)
local POND = Vector3.new(-55, 0, 45)
local function surface(x: number, z: number): (number, any)
	local r = math.sqrt(x * x + z * z)
	-- 가장자리를 조금 울퉁불퉁하게(동심원 과녁처럼 안 보이게)
	local wobble = 10 * math.sin(math.atan2(z, x) * 3 + 0.7) + 6 * math.sin(math.atan2(z, x) * 7)
	local edge = r - wobble
	local h
	if edge < 100 then
		h = 0
	elseif edge < 135 then
		h = -(edge - 100) / 35 * 6
	else
		h = math.max(-24, -6 - (edge - 135) * 0.4) -- 바다 바닥(y -24)보다 깊게 파지 않음
	end
	local material = if edge < 102 then Enum.Material.Grass else Enum.Material.Sand
	local dh = (Vector3.new(x, 0, z) - HILL).Magnitude
	if dh < 45 then
		h = math.max(h, 18 * (1 - (dh / 45) ^ 2))
	end
	local dp = (Vector3.new(x, 0, z) - POND).Magnitude
	if dp < 16 then
		h = math.min(h, -3 * (1 - (dp / 16) ^ 2))
		material = if dp < 12 then Enum.Material.Sand else material
	end
	return h, material
end

local MIN_Y, MAX_Y = -28, 24
local lo = Vector3.new(-176, MIN_Y, -176)
local hi = Vector3.new(176, MAX_Y, 176)
local nx, ny = (hi.X - lo.X) / 4, (hi.Y - lo.Y) / 4
local mats, solids, liquids = {}, {}, {}
for i = 1, nx do
	local mx, sx, lx = {}, {}, {}
	local x = lo.X + (i - 0.5) * 4
	for j = 1, ny do
		mx[j], sx[j], lx[j] = {}, {}, {}
	end
	for k = 1, nx do
		local z = lo.Z + (k - 0.5) * 4
		local h, material = surface(x, z)
		local pond = (Vector3.new(x, 0, z) - POND).Magnitude < 16
		for j = 1, ny do
			local bottom = MIN_Y + (j - 1) * 4
			local occupancy = math.clamp((h - bottom) / 4, 0, 1)
			-- 맨 아래 한 칸은 진흙 바닥(바다와 이어지게)
			mx[j][k] = if occupancy > 0
				then (if bottom < -24 then Enum.Material.Mud else material)
				else Enum.Material.Air
			sx[j][k] = occupancy
			local waterTop = if pond then 0 else -4
			lx[j][k] = if bottom < waterTop then math.clamp((waterTop - bottom) / 4, 0, 1) - occupancy else 0
			lx[j][k] = math.max(0, lx[j][k])
		end
	end
	mats[i], solids[i], liquids[i] = mx, sx, lx
end
Terrain:WriteVoxelChannels(Region3.new(lo, hi), 4, {
	SolidMaterial = mats,
	SolidOccupancy = solids,
	LiquidOccupancy = liquids,
})

-- 칠하기·덧붙이기 -------------------------------------------------------------------------
-- 길: 풀을 Pavement 로(ReplaceMaterial 은 격자에 맞춘 영역)
Terrain:ReplaceMaterial(
	Region3.new(Vector3.new(-100, -8, -6), Vector3.new(20, 4, 6)):ExpandToGrid(4),
	4,
	Enum.Material.Grass,
	Enum.Material.Pavement
)
-- 광장: 얇은 Cobblestone 원기둥(윗면 y 0.4)
Terrain:FillCylinder(CFrame.new(0, -1.6, 0), 4, 22, Enum.Material.Cobblestone)
-- 단: Brick 받침 + WoodPlanks 판
Terrain:FillBlock(CFrame.new(-30, 1, -60), Vector3.new(24, 4, 16), Enum.Material.Brick)
Terrain:FillBlock(CFrame.new(-30, 3.5, -60), Vector3.new(20, 1, 12), Enum.Material.WoodPlanks)
-- 언덕: 바위 + 눈 모자 + 현무암 돌
Terrain:FillBall(HILL + Vector3.new(-18, 8, 12), 7, Enum.Material.Rock)
Terrain:FillBall(HILL + Vector3.new(10, 10, -16), 6, Enum.Material.Rock)
Terrain:FillBall(HILL + Vector3.new(0, 14, 0), 8, Enum.Material.Snow)
Terrain:FillBall(Vector3.new(118, -2, 30), 6, Enum.Material.Basalt)
Terrain:FillBall(Vector3.new(112, -3, 42), 4, Enum.Material.Basalt)
-- 절벽: Slate 쐐기(북쪽 물가)
Terrain:FillWedge(
	CFrame.new(-20, -2, -118) * CFrame.Angles(0, math.pi, 0),
	Vector3.new(40, 16, 20),
	Enum.Material.Slate
)
-- 재질 조각들(윗면을 살짝 칠함)
local patches = {
	{ Enum.Material.Mud, Vector3.new(40, 0, 60) },
	{ Enum.Material.Ground, Vector3.new(60, 0, 40) },
	{ Enum.Material.LeafyGrass, Vector3.new(-80, 0, -30) },
	{ Enum.Material.Salt, Vector3.new(20, 0, 80) },
	{ Enum.Material.Limestone, Vector3.new(-10, 0, 85) },
	{ Enum.Material.Sandstone, Vector3.new(-40, 0, 80) },
	{ Enum.Material.Asphalt, Vector3.new(80, 0, 0) },
	{ Enum.Material.Concrete, Vector3.new(80, 0, 20) },
	{ Enum.Material.Granite, Vector3.new(80, 0, -20) },
}
for _, patch in patches do
	Terrain:FillCylinder(CFrame.new(patch[2] + Vector3.new(0, -1, 0)), 2, 9, patch[1])
end

-- 파트 -------------------------------------------------------------------------------------
local folder = Instance.new("Folder")
folder.Name = "Scenery"
folder.Parent = workspace

local function part(name: string, shape: string?, size: Vector3, cf: CFrame, color: Color3, material): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	if shape then
		p.Shape = shape
	end
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material
	p.Parent = folder
	return p
end

-- 재질 견본: 뒤쪽 줄(z = 20) 위에 5x5x5 상자
local samples = {
	{ "SmoothPlastic", Color3.fromRGB(240, 90, 80) },
	{ "Plastic", Color3.fromRGB(240, 200, 60) },
	{ "Wood", Color3.fromRGB(160, 110, 70) },
	{ "WoodPlanks", Color3.fromRGB(170, 120, 80) },
	{ "Brick", Color3.fromRGB(170, 90, 70) },
	{ "Cobblestone", Color3.fromRGB(150, 145, 135) },
	{ "Concrete", Color3.fromRGB(190, 190, 185) },
	{ "Pavement", Color3.fromRGB(170, 170, 165) },
	{ "Slate", Color3.fromRGB(110, 115, 120) },
	{ "Rock", Color3.fromRGB(130, 125, 120) },
	{ "Marble", Color3.fromRGB(235, 235, 230) },
	{ "Granite", Color3.fromRGB(160, 150, 140) },
	{ "Metal", Color3.fromRGB(150, 160, 170) },
	{ "DiamondPlate", Color3.fromRGB(160, 165, 170) },
	{ "Fabric", Color3.fromRGB(80, 120, 200) },
	{ "Grass", Color3.fromRGB(90, 160, 70) },
	{ "Sand", Color3.fromRGB(230, 205, 150) },
	{ "Ice", Color3.fromRGB(170, 220, 240) },
	{ "Glass", Color3.fromRGB(180, 220, 240) },
	{ "Neon", Color3.fromRGB(255, 80, 200) },
}
for i, sample in samples do
	local x = -57 + (i - 1) * 6
	local p = part(
		"Sample" .. sample[1],
		nil,
		Vector3.new(5, 5, 5),
		CFrame.new(x, 2.5, 20),
		sample[2],
		"Material." .. sample[1]
	)
	if sample[1] == "Glass" then
		p.Transparency = 0.5
	end
end
-- 공·원기둥(곡면 텍스처)
part(
	"BallGrass",
	"PartType.Ball",
	Vector3.new(6, 6, 6),
	CFrame.new(-50, 3, 32),
	Color3.fromRGB(80, 150, 60),
	Enum.Material.Grass
)
part(
	"BallMarble",
	"PartType.Ball",
	Vector3.new(5, 5, 5),
	CFrame.new(-42, 2.5, 32),
	Color3.fromRGB(240, 240, 240),
	Enum.Material.Marble
)
part(
	"CylinderWood",
	"PartType.Cylinder",
	Vector3.new(8, 4, 4),
	CFrame.new(-34, 4, 32) * CFrame.Angles(0, 0, math.pi / 2),
	Color3.fromRGB(140, 95, 60),
	Enum.Material.Wood
)
part(
	"CylinderBrick",
	"PartType.Cylinder",
	Vector3.new(10, 6, 6),
	CFrame.new(-24, 3, 32),
	Color3.fromRGB(180, 100, 80),
	Enum.Material.Brick
)
-- 나무(땅 높이는 Raycast 로 — 지형 광선 점검)
local function groundAt(x: number, z: number): number
	local result = workspace:Raycast(Vector3.new(x, 100, z), Vector3.new(0, -200, 0))
	return if result then result.Position.Y else 0
end
for k, spot in { Vector3.new(35, 0, -35), Vector3.new(50, 0, -62), Vector3.new(-70, 0, 10), Vector3.new(10, 0, 55) } do
	local y = groundAt(spot.X, spot.Z)
	part(
		"Trunk" .. k,
		"PartType.Cylinder",
		Vector3.new(10, 2, 2),
		CFrame.new(spot.X, y + 4.5, spot.Z) * CFrame.Angles(0, 0, math.pi / 2),
		Color3.fromRGB(120, 85, 55),
		Enum.Material.Wood
	)
	part(
		"Leaves" .. k,
		"PartType.Ball",
		Vector3.new(9, 9, 9),
		CFrame.new(spot.X, y + 11, spot.Z),
		Color3.fromRGB(70, 150, 60),
		Enum.Material.LeafyGrass
	)
end
-- 벤치(WoodPlanks 판 + Metal 다리)
part(
	"BenchSeat",
	nil,
	Vector3.new(6, 0.5, 2),
	CFrame.new(10, 2, -12),
	Color3.fromRGB(170, 120, 80),
	Enum.Material.WoodPlanks
)
part(
	"BenchLegA",
	nil,
	Vector3.new(0.4, 1.75, 1.6),
	CFrame.new(7.8, 0.875, -12),
	Color3.fromRGB(60, 60, 64),
	Enum.Material.Metal
)
part(
	"BenchLegB",
	nil,
	Vector3.new(0.4, 1.75, 1.6),
	CFrame.new(12.2, 0.875, -12),
	Color3.fromRGB(60, 60, 64),
	Enum.Material.Metal
)
-- 일부러 틀린 것: 떠 있는 상자(바닥 y 4), 언덕에 파묻힌 상자
part(
	"FloatingCrate",
	nil,
	Vector3.new(3, 3, 3),
	CFrame.new(20, 5.5, -30),
	Color3.fromRGB(200, 150, 60),
	Enum.Material.WoodPlanks
)
part(
	"BuriedRock",
	nil,
	Vector3.new(4, 4, 4),
	CFrame.new(HILL.X, 6, HILL.Z),
	Color3.fromRGB(120, 120, 120),
	Enum.Material.Slate
)
-- 물 위 부두(기둥이 받침)
part(
	"Dock",
	nil,
	Vector3.new(8, 1, 24),
	CFrame.new(0, 0.5, 128),
	Color3.fromRGB(150, 110, 75),
	Enum.Material.WoodPlanks
)
for _, dz in { 120, 128, 136 } do
	for _, dx in { -3.5, 3.5 } do
		part(
			"DockPost",
			"PartType.Cylinder",
			Vector3.new(14, 1, 1),
			CFrame.new(dx, -7, dz) * CFrame.Angles(0, 0, math.pi / 2),
			Color3.fromRGB(110, 80, 55),
			Enum.Material.Wood
		)
	end
end

-- 확인: ReadVoxels 로 섬 가운데 기둥
local materials, occupancies = Terrain:ReadVoxels(Region3.new(Vector3.new(0, -8, 0), Vector3.new(4, 4, 4)), 4)
note(
	string.format(
		"ReadVoxels(0,-8..4,0): %s %.2f / %s %.2f / %s %.2f",
		materials[1][1][1],
		occupancies[1][1][1],
		materials[1][2][1],
		occupancies[1][2][1],
		materials[1][3][1],
		occupancies[1][3][1]
	)
)
local hit = workspace:Raycast(Vector3.new(0, 50, 300), Vector3.new(0, -100, 0))
note("Raycast 바다: " .. (if hit then tostring(hit.Material) .. " y=" .. tostring(hit.Position.Y) else "없음"))

local dump = compile(readfile("tools/world_preview/dump.luau"), "tools/world_preview/dump.luau")()
dump({ Mock = Mock, Harness = Harness, note = note, notes = notes, meta = { test = true } })
