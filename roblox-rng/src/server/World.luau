-- 광장(스폰) + 받침대 위의 거대 지구본 + 광장 둘레 나무 + 뉴스 속보 홀로그램
-- 회전은 클라이언트가 "LandmarkSpin" 태그가 붙은 Model 을 제자리에서 돌려서 보여 줍니다(서버 복제 부담 없음).
-- 홀로그램 제목은 글자 최소: "속보!" 딱지 + 명소 이름. Shared/ImageIds.news 그림이 있으면 딱지 옆에 신문 아이콘.

local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Landmarks = require(Shared.Landmarks)
local Models = require(Shared.Models)

-- 그림 Id 표 (없거나 깨져도 코드로 그린 모양으로 동작)
local function loadImageIds(): { [string]: any }
	local module = Shared:FindFirstChild("ImageIds")
	if module and module:IsA("ModuleScript") then
		local ok, result = pcall(require, module)
		if ok and type(result) == "table" then
			return result
		end
	end
	return {}
end
local ImageIds = loadImageIds()

-- 그림 Id ("rbxassetid://...") 또는 nil
local function imageId(name: string): string?
	local value = ImageIds[name]
	if type(value) == "number" then
		return "rbxassetid://" .. tostring(value)
	elseif type(value) == "string" and value ~= "" then
		return if value:match("^%d+$") then "rbxassetid://" .. value else value
	end
	return nil
end

local SPIN_TAG = "LandmarkSpin"

local PLAZA_RADIUS = 45
local PLAZA_TOP = 1 -- 광장 윗면 높이. 스폰 지점(두께 1)이 이 위에 놓임
local RIM_WIDTH = 3 -- 광장 둘레의 낮은 계단(윗면 0.5)
local EARTH_SPOT = Vector3.new(0, PLAZA_TOP, -26) -- 지구본 받침대 바닥 중앙(스폰 정면 = -Z)
local EARTH_SIZE = 26
local LAMP_COUNT = 16
local LAMP_RADIUS = PLAZA_RADIUS - 3
local TREE_COUNT = 8
local TREE_RADIUS = PLAZA_RADIUS + RIM_WIDTH + 8 -- 광장 둘레 계단 바로 바깥 잔디

local HOLOGRAM_SIZE = 60
local HOLOGRAM_HEIGHT = 60 -- 홀로그램 바닥 높이(지구본과 겹치면 그 위로 올림)
local HOLOGRAM_LIFETIME = 12
local HOLOGRAM_TRANSPARENCY = 0.35
local TITLE_WIDTH = 80 -- 홀로그램 제목 크기(스터드)
local TITLE_HEIGHT = 20

local PLAZA_COLOR = Color3.fromRGB(214, 210, 200)
local RIM_COLOR = Color3.fromRGB(165, 160, 150)
local STONE_DARK = Color3.fromRGB(70, 74, 88)
local MARBLE = Color3.fromRGB(240, 238, 232)
local GOLD = Color3.fromRGB(235, 190, 80)
local LAMP_POLE = Color3.fromRGB(45, 48, 60)
local LAMP_LIGHT = Color3.fromRGB(255, 235, 190)
local TRUNK = Color3.fromRGB(122, 78, 45)
local LEAF = Color3.fromRGB(72, 184, 84)
local LEAF_LIGHT = Color3.fromRGB(122, 214, 104)

-- UI 스타일 가이드 v2 팔레트(홀로그램 제목)
local INK = Color3.fromRGB(30, 27, 46)
local WHITE = Color3.new(1, 1, 1)
local CORAL = Color3.fromRGB(255, 94, 91)
local CORAL_SHADOW = Color3.fromRGB(201, 58, 56)

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

-- 동글동글한 나무: 줄기(원기둥) + 잎(큰 공 + 위에 작은 밝은 공). 잎은 머리에 걸리지 않게 충돌 없음.
-- scale 로 크기를, turn(라디안)으로 작은 공 방향을 바꿔서 나무마다 조금씩 다르게 보이게 함
local function tree(parent: Instance, base: Vector3, scale: number, turn: number)
	disc(parent, "TreeTrunk", base, 6 * scale, 1.6 * scale, TRUNK, Enum.Material.Wood)
	local leaves = {
		{ Offset = Vector3.new(0, 8, 0), Diameter = 7.5, Color = LEAF },
		{ Offset = Vector3.new(1.2, 11, -0.6), Diameter = 4.6, Color = LEAF_LIGHT },
	}
	for _, leaf in leaves do
		local offset = CFrame.Angles(0, turn, 0):VectorToWorldSpace(leaf.Offset) * scale
		local diameter = leaf.Diameter * scale
		local part = newPart(
			parent,
			"TreeLeaves",
			Enum.PartType.Ball,
			Vector3.new(diameter, diameter, diameter),
			CFrame.new(base + offset),
			leaf.Color,
			Enum.Material.SmoothPlastic
		)
		part.CanCollide = false
	end
end

-- 서버 시작 시 한 번: 광장, 가로등, 둘레 나무, 받침대 + 거대 지구본
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

	-- 나무: 광장 바로 바깥 잔디, 길(22.5도마다) 사이 틈 하나 건너 하나에(가로등 바로 뒤)
	for i = 1, TREE_COUNT do
		local angle = (i - 0.75) / TREE_COUNT * math.pi * 2 -- 11.25도 + 45도 간격
		local base = Vector3.new(math.cos(angle) * TREE_RADIUS, 0, math.sin(angle) * TREE_RADIUS)
		tree(world, base, if i % 2 == 0 then 1 else 0.85, angle)
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

-- 통통한 상자: 둥근 모서리 + Ink 테두리. position 은 윗변 가운데
local function chunkyBox(
	parent: Instance,
	name: string,
	size: UDim2,
	position: UDim2,
	color: Color3,
	zIndex: number
): Frame
	local box = Instance.new("Frame")
	box.Name = name
	box.AnchorPoint = Vector2.new(0.5, 0)
	box.Size = size
	box.Position = position
	box.BackgroundColor3 = color
	box.BorderSizePixel = 0
	box.ZIndex = zIndex
	local round = Instance.new("UICorner")
	round.CornerRadius = UDim.new(0.3, 0)
	round.Parent = box
	local line = Instance.new("UIStroke")
	line.Thickness = 5
	line.Color = INK
	line.Parent = box
	box.Parent = parent
	return box
end

-- 위쪽이 살짝 밝은 그라데이션
local function shine(box: Frame)
	local gradient = Instance.new("UIGradient")
	gradient.Color = ColorSequence.new(WHITE, Color3.fromRGB(214, 214, 214))
	gradient.Rotation = 90 -- 위 → 아래
	gradient.Parent = box
end

-- 흰 LuckiestGuy 글자 + 굵은 Ink 글자 테두리
local function bigText(parent: Frame, text: string, thickness: number)
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Font = Enum.Font.LuckiestGuy
	label.TextScaled = true
	label.Text = text
	label.TextColor3 = WHITE
	local line = Instance.new("UIStroke")
	line.Thickness = thickness
	line.Color = INK
	line.Parent = label
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0.05, 0)
	pad.PaddingRight = UDim.new(0.05, 0)
	pad.PaddingTop = UDim.new(0.16, 0)
	pad.PaddingBottom = UDim.new(0.16, 0)
	pad.Parent = label
	label.Parent = parent
end

-- 홀로그램 제목: 빨간 "속보!" 딱지(살짝 기울임) + 등급 색 리본 위에 명소 이름
local function titleBillboard(parent: BasePart, landmark: Landmarks.Landmark)
	local billboard = Instance.new("BillboardGui")
	billboard.Name = "Title"
	billboard.Adornee = parent
	billboard.Size = UDim2.fromScale(TITLE_WIDTH, TITLE_HEIGHT)
	billboard.StudsOffset = Vector3.new(0, 2 - TITLE_HEIGHT / 2, 0) -- 윗변이 기준점 조금 위, 나머지는 아래로
	billboard.LightInfluence = 0
	billboard.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	local text = landmark.Name
	-- 리본 너비: 글자 수 × 글자 높이(약 8.6 스터드) + 여백
	local chars = utf8.len(text) or #text
	local ribbonWidth = math.clamp((chars * 8.6 + 12) / TITLE_WIDTH, 0.4, 1)
	local ribbonSize = UDim2.fromScale(ribbonWidth, 0.6)
	local tier = landmark.Tier.Color
	chunkyBox(billboard, "RibbonShadow", ribbonSize, UDim2.fromScale(0.5, 0.36), tier:Lerp(INK, 0.4), 1)
	local ribbon = chunkyBox(billboard, "Ribbon", ribbonSize, UDim2.fromScale(0.5, 0.3), tier, 2)
	shine(ribbon)
	bigText(ribbon, text, 6)

	local tagSize = UDim2.fromScale(0.24, 0.3)
	local tagShadow = chunkyBox(billboard, "TagShadow", tagSize, UDim2.fromScale(0.5, 0.05), CORAL_SHADOW, 3)
	local tag = chunkyBox(billboard, "Tag", tagSize, UDim2.fromScale(0.5, 0.02), CORAL, 4)
	tagShadow.Rotation = -4
	tag.Rotation = -4
	shine(tag)
	bigText(tag, "속보!", 4)

	local newsId = imageId("news")
	if newsId then
		-- 딱지 왼쪽에 신문 아이콘(딱지보다 조금 크게)
		local news = Instance.new("ImageLabel")
		news.Name = "NewsIcon"
		news.BackgroundTransparency = 1
		news.Image = newsId
		news.ScaleType = Enum.ScaleType.Fit
		news.SizeConstraint = Enum.SizeConstraint.RelativeYY
		news.Size = UDim2.fromScale(1.4, 1.4)
		news.AnchorPoint = Vector2.new(0.75, 0.5)
		news.Position = UDim2.fromScale(0, 0.5)
		news.Rotation = -10
		news.ZIndex = 5
		news.Parent = tag
	end

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
