-- 대표 명소를 캐릭터에 표시: 오른쪽 어깨 옆에 작은 모형이 붙어 다니고, 머리 위에 명소 이름표
-- 모형은 HumanoidRootPart 에 용접(Weld)해서 캐릭터와 함께 움직입니다(무게 없음, 충돌 없음).
-- 이름표는 UI 스타일 가이드 v2 를 따름: 등급 색 통통한 딱지 + 흰 FredokaOne 글자 + Ink 테두리(이모지 없음).
-- Shared/ImageIds.star 그림이 있으면 이름 왼쪽에 작은 별 아이콘을 붙임.

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

local FX_NAME = "FeaturedLandmark"
local MODEL_SIZE = 2.4
local MAX_DIMENSION = 2.6 -- 가로·세로·높이 중 가장 긴 쪽 상한(키 큰 명소가 캐릭터만큼 커지지 않게)
local SHOULDER_OFFSET = CFrame.new(2.4, 0.9, 0) -- HumanoidRootPart 기준: 오른쪽 어깨 옆(모형 바닥 높이)
local LABEL_DISTANCE = 80
local TAG_HEIGHT = 1.1 -- 이름표 높이(스터드). 너비는 이름 길이에 맞춤

local INK = Color3.fromRGB(30, 27, 46)
local WHITE = Color3.new(1, 1, 1)

local FeaturedDisplay = {}

local function clear(character: Model)
	for _, descendant in character:GetDescendants() do
		if descendant.Name == FX_NAME then
			descendant:Destroy()
		end
	end
end

local function attachModel(character: Model, landmark: Landmarks.Landmark)
	local root = character:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") then
		return
	end
	local ok, result = pcall(Models.create, landmark, MODEL_SIZE, { Anchored = false })
	if not ok then
		warn("[FeaturedDisplay] " .. landmark.Id .. " 모형을 만들지 못했습니다: " .. tostring(result))
		return
	end
	local model = result :: Model
	model.Name = FX_NAME
	local extents = model:GetExtentsSize()
	local longest = math.max(extents.X, extents.Y, extents.Z)
	if longest > MAX_DIMENSION then
		model:ScaleTo(model:GetScale() * MAX_DIMENSION / longest)
	end
	model:PivotTo(root.CFrame * SHOULDER_OFFSET)

	-- 파트마다 지금 위치 그대로 HumanoidRootPart 에 고정
	for _, descendant in model:GetDescendants() do
		if descendant:IsA("BasePart") then
			descendant.Anchored = false
			descendant.Massless = true
			descendant.CanCollide = false
			descendant.CastShadow = false
			local weld = Instance.new("Weld")
			weld.C0 = root.CFrame:ToObjectSpace(descendant.CFrame)
			weld.Part0 = root
			weld.Part1 = descendant
			weld.Parent = descendant
		end
	end
	model.Parent = character
end

local function corner(gui: GuiObject)
	local round = Instance.new("UICorner")
	round.CornerRadius = UDim.new(0.5, 0) -- 캡슐 모양
	round.Parent = gui
end

local function stroke(gui: GuiObject, thickness: number)
	local line = Instance.new("UIStroke")
	line.Thickness = thickness
	line.Color = INK
	line.Parent = gui
end

-- 머리 위 이름표: 어두운 그림자 판 위에 등급 색 앞면(위쪽이 살짝 밝음), 흰 이름 + Ink 글자 테두리
local function attachLabel(character: Model, landmark: Landmarks.Landmark)
	local head = character:FindFirstChild("Head")
	if not head or not head:IsA("BasePart") then
		return
	end
	-- 한글 한 글자 폭 ≈ 글자 높이(약 0.7 스터드) + 양옆 여백. 별 아이콘이 있으면 그만큼 넓힘
	local chars = utf8.len(landmark.Name) or #landmark.Name
	local starId = imageId("star")
	local iconWidth = if starId then TAG_HEIGHT * 0.9 else 0
	local width = math.clamp(chars * 0.72 + 0.9, 2.6, 8) + iconWidth

	local billboard = Instance.new("BillboardGui")
	billboard.Name = FX_NAME
	billboard.Adornee = head
	billboard.Size = UDim2.fromScale(width, TAG_HEIGHT)
	billboard.StudsOffset = Vector3.new(0, 2.7, 0)
	billboard.MaxDistance = LABEL_DISTANCE
	billboard.LightInfluence = 0
	billboard.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	local tier = landmark.Tier.Color
	local shadow = Instance.new("Frame")
	shadow.Name = "Shadow"
	shadow.Size = UDim2.fromScale(1, 0.86)
	shadow.Position = UDim2.fromScale(0, 0.14)
	shadow.BackgroundColor3 = tier:Lerp(INK, 0.4)
	shadow.BorderSizePixel = 0
	shadow.ZIndex = 1
	corner(shadow)
	stroke(shadow, 2)
	shadow.Parent = billboard

	local face = Instance.new("Frame")
	face.Name = "Face"
	face.Size = UDim2.fromScale(1, 0.86)
	face.BackgroundColor3 = tier
	face.BorderSizePixel = 0
	face.ZIndex = 2
	corner(face)
	stroke(face, 2)
	local shine = Instance.new("UIGradient")
	shine.Color = ColorSequence.new(WHITE, Color3.fromRGB(214, 214, 214))
	shine.Rotation = 90 -- 위 → 아래
	shine.Parent = face
	face.Parent = billboard

	local label = Instance.new("TextLabel")
	label.Name = "Name"
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Font = Enum.Font.FredokaOne
	label.TextScaled = true
	label.Text = landmark.Name
	label.TextColor3 = WHITE
	stroke(label, 2)
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0.08 + iconWidth / width, 0)
	pad.PaddingRight = UDim.new(0.08, 0)
	pad.PaddingTop = UDim.new(0.14, 0)
	pad.PaddingBottom = UDim.new(0.14, 0)
	pad.Parent = label
	label.Parent = face

	if starId then
		-- 이름 왼쪽 별 (딱지 높이보다 조금 커서 위아래로 살짝 삐져나옴)
		local star = Instance.new("ImageLabel")
		star.Name = "Star"
		star.BackgroundTransparency = 1
		star.Image = starId
		star.ScaleType = Enum.ScaleType.Fit
		star.SizeConstraint = Enum.SizeConstraint.RelativeYY
		star.Size = UDim2.fromScale(1.3, 1.3)
		star.AnchorPoint = Vector2.new(0, 0.5)
		star.Position = UDim2.new(0, 0, 0.5, 0)
		star.ZIndex = 3
		star.Parent = face
	end

	billboard.Parent = head
end

-- 이전 표시를 지우고, landmark 가 있으면 새로 붙임(nil 이면 지우기만)
function FeaturedDisplay.apply(character: Model?, landmark: Landmarks.Landmark?)
	if not character then
		return
	end
	clear(character)
	if landmark then
		attachModel(character, landmark)
		attachLabel(character, landmark)
	end
end

return FeaturedDisplay
