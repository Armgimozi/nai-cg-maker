-- 광장(스폰) + 받침대 위의 거대 지구본 + 뉴스 속보 홀로그램
-- 회전은 클라이언트가 "LandmarkSpin" 태그가 붙은 Model 을 제자리에서 돌려서 보여 줍니다(서버 복제 부담 없음).

local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Landmarks = require(Shared.Landmarks)
local Models = require(Shared.Models)

local SPIN_TAG = "LandmarkSpin"

local PLAZA_RADIUS = 45
local PLAZA_TOP = 1 -- 광장 윗면 높이. 스폰 지점(두께 1)이 이 위에 놓임
local RIM_WIDTH = 3 -- 광장 둘레의 낮은 계단(윗면 0.5)
local EARTH_SPOT = Vector3.new(0, PLAZA_TOP, -26) -- 지구본 받침대 바닥 중앙(스폰 정면 = -Z)
local EARTH_SIZE = 26
local LAMP_COUNT = 16
local LAMP_RADIUS = PLAZA_RADIUS - 3

local HOLOGRAM_SIZE = 60
local HOLOGRAM_HEIGHT = 60 -- 홀로그램 바닥 높이(지구본과 겹치면 그 위로 올림)
local HOLOGRAM_LIFETIME = 12
local HOLOGRAM_TRANSPARENCY = 0.35

local PLAZA_COLOR = Color3.fromRGB(214, 210, 200)
local RIM_COLOR = Color3.fromRGB(165, 160, 150)
local STONE_DARK = Color3.fromRGB(70, 74, 88)
local MARBLE = Color3.fromRGB(240, 238, 232)
local GOLD = Color3.fromRGB(235, 190, 80)
local LAMP_POLE = Color3.fromRGB(45, 48, 60)
local LAMP_LIGHT = Color3.fromRGB(255, 235, 190)

-- 원기둥 파트는 X 축이 기둥 방향이므로 세우려면 Z 축으로 90도 돌림
local UPRIGHT = CFrame.Angles(0, 0, math.rad(90))

local World = {}

local folder: Folder? = nil
local earthTop = PLAZA_TOP + EARTH_SIZE -- 지구본 꼭대기 높이(모형을 만든 뒤 실제 값으로 바뀜)
local hologram: Model? = nil

local function newPart(
	parent: Instance,
	name: string,
	shape: Enum.PartType,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material
): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Shape = shape
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = material
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = parent
	return part
end

-- bottom(바닥 중앙)에서 위로 height 만큼 세운 원기둥
local function disc(
	parent: Instance,
	name: string,
	bottom: Vector3,
	height: number,
	diameter: number,
	color: Color3,
	material: Enum.Material
): Part
	return newPart(
		parent,
		name,
		Enum.PartType.Cylinder,
		Vector3.new(height, diameter, diameter),
		CFrame.new(bottom + Vector3.new(0, height / 2, 0)) * UPRIGHT,
		color,
		material
	)
end

local function lamp(parent: Instance, base: Vector3)
	local pole = newPart(
		parent,
		"LampPost",
		Enum.PartType.Block,
		Vector3.new(0.6, 9, 0.6),
		CFrame.new(base + Vector3.new(0, 4.5, 0)),
		LAMP_POLE,
		Enum.Material.Metal
	)
	pole.CastShadow = false
	local bulb = newPart(
		parent,
		"LampBulb",
		Enum.PartType.Ball,
		Vector3.new(1.8, 1.8, 1.8),
		CFrame.new(base + Vector3.new(0, 9.6, 0)),
		LAMP_LIGHT,
		Enum.Material.Neon
	)
	bulb.CanCollide = false
	bulb.CastShadow = false
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 18
	light.Brightness = 1.2
	light.Parent = bulb
end

-- 서버 시작 시 한 번: 광장, 가로등, 받침대 + 거대 지구본
function World.build()
	if folder then
		return
	end
	local world = Instance.new("Folder")
	world.Name = "World"
	folder = world

	-- 광장: 둘레 계단(윗면 0.5) 위에 광장(윗면 1). 한 번에 0.5 씩이라 걸어서 오를 수 있음
	disc(
		world,
		"PlazaRim",
		Vector3.zero,
		PLAZA_TOP / 2,
		(PLAZA_RADIUS + RIM_WIDTH) * 2,
		RIM_COLOR,
		Enum.Material.Concrete
	)
	disc(world, "Plaza", Vector3.zero, PLAZA_TOP, PLAZA_RADIUS * 2, PLAZA_COLOR, Enum.Material.Concrete)

	-- 가로등: 공원으로 가는 길(22.5도 간격) 사이사이에
	for i = 1, LAMP_COUNT do
		local angle = (i - 0.5) / LAMP_COUNT * math.pi * 2
		lamp(world, Vector3.new(math.cos(angle) * LAMP_RADIUS, PLAZA_TOP, math.sin(angle) * LAMP_RADIUS))
	end

	-- 지구본 받침대
	disc(world, "PedestalBase", EARTH_SPOT, 1.5, 18, STONE_DARK, Enum.Material.Slate)
	disc(world, "PedestalColumn", EARTH_SPOT + Vector3.new(0, 1.5, 0), 5, 10, MARBLE, Enum.Material.Marble)
	disc(world, "PedestalTop", EARTH_SPOT + Vector3.new(0, 6.5, 0), 1, 15, GOLD, Enum.Material.Metal)
	local pedestalTop = EARTH_SPOT.Y + 7.5

	-- 거대 지구본 (모형 코드에 문제가 있어도 광장은 만들어지도록 pcall)
	local ok, err = pcall(function()
		local earth = Models.create(Landmarks.ById.earth, EARTH_SIZE)
		earth.Name = "Earth"
		earth:PivotTo(CFrame.new(EARTH_SPOT.X, pedestalTop, EARTH_SPOT.Z))
		earthTop = pedestalTop + earth:GetExtentsSize().Y
		CollectionService:AddTag(earth, SPIN_TAG)
		-- 스트리밍이 켜져 있어도 통째로 내려받게 해야 클라이언트 회전 때 일부 파트만 어긋나지 않음
		earth.ModelStreamingMode = Enum.ModelStreamingMode.Atomic
		earth.Parent = world
	end)
	if not ok then
		warn("[World] 지구본 모형을 만들지 못했습니다: " .. tostring(err))
	end

	world.Parent = Workspace
end

-- 광장으로 순간이동할 때 캐릭터 피벗(HumanoidRootPart) 위치: 스폰 바로 앞에서 지구본을 바라봄
function World.plazaCFrame(): CFrame
	local position = Vector3.new(0, PLAZA_TOP + 3.5, 10)
	return CFrame.lookAt(position, Vector3.new(EARTH_SPOT.X, position.Y, EARTH_SPOT.Z))
end

local function titleBillboard(parent: BasePart, landmark: Landmarks.Landmark)
	local billboard = Instance.new("BillboardGui")
	billboard.Name = "Title"
	billboard.Adornee = parent
	billboard.Size = UDim2.fromScale(80, 12)
	billboard.LightInfluence = 0

	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Font = Enum.Font.GothamBlack
	label.TextScaled = true
	label.Text = "📰 " .. landmark.Name .. " 발견!"
	label.TextColor3 = landmark.Tier.Color
	label.Parent = billboard

	local stroke = Instance.new("UIStroke")
	stroke.Thickness = 3
	stroke.Color = Color3.new(0, 0, 0)
	stroke.Parent = label

	billboard.Parent = parent
end

-- 광장 하늘에 거대한 반투명 홀로그램(한 번에 하나, 12초 뒤 사라짐)
function World.hologram(landmark: Landmarks.Landmark)
	if hologram then
		hologram:Destroy()
		hologram = nil
	end

	local ok, result = pcall(Models.create, landmark, HOLOGRAM_SIZE)
	if not ok then
		warn("[World] 홀로그램 모형을 만들지 못했습니다: " .. tostring(result))
		return
	end
	local model = result :: Model
	model.Name = "Hologram"
	for _, descendant in model:GetDescendants() do
		if descendant:IsA("BasePart") then
			-- 원래 투명한 파트(Root 등)는 그대로 두고, 보이는 파트만 색은 유지한 채 홀로그램 재질로
			if descendant.Transparency < 1 then
				descendant.Transparency = math.max(descendant.Transparency, HOLOGRAM_TRANSPARENCY)
				descendant.Material = Enum.Material.ForceField
			end
			descendant.Anchored = true
			descendant.CanCollide = false
			descendant.CanQuery = false
			descendant.CanTouch = false
			descendant.CastShadow = false
		end
	end

	local bottom = math.max(HOLOGRAM_HEIGHT, earthTop + 10)
	model:PivotTo(CFrame.new(0, bottom, 0))

	-- 제목은 홀로그램 바로 아래(땅에서 올려다볼 때 잘 보이게). 회전축 위에 있어서 돌려도 제자리
	local anchor = Instance.new("Part")
	anchor.Name = "TitleAnchor"
	anchor.Size = Vector3.new(1, 1, 1)
	anchor.CFrame = CFrame.new(0, bottom - 5, 0)
	anchor.Transparency = 1
	anchor.Anchored = true
	anchor.CanCollide = false
	anchor.CanQuery = false
	anchor.CanTouch = false
	anchor.Parent = model
	titleBillboard(anchor, landmark)

	CollectionService:AddTag(model, SPIN_TAG)
	model.ModelStreamingMode = Enum.ModelStreamingMode.Atomic
	model.Parent = folder or Workspace
	hologram = model

	task.delay(HOLOGRAM_LIFETIME, function()
		if hologram == model then
			hologram = nil
		end
		model:Destroy()
	end)
end

return World
