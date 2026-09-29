-- 대표 명소를 캐릭터에 표시: 오른쪽 어깨 옆에 작은 모형이 붙어 다니고, 머리 위에 "📍 이름" 표시
-- 모형은 HumanoidRootPart 에 용접(Weld)해서 캐릭터와 함께 움직입니다(무게 없음, 충돌 없음).

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Landmarks = require(Shared.Landmarks)
local Models = require(Shared.Models)

local FX_NAME = "FeaturedLandmark"
local MODEL_SIZE = 2.4
local MAX_DIMENSION = 2.6 -- 가로·세로·높이 중 가장 긴 쪽 상한(키 큰 명소가 캐릭터만큼 커지지 않게)
local SHOULDER_OFFSET = CFrame.new(2.4, 0.9, 0) -- HumanoidRootPart 기준: 오른쪽 어깨 옆(모형 바닥 높이)
local LABEL_DISTANCE = 80

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

local function attachLabel(character: Model, landmark: Landmarks.Landmark)
	local head = character:FindFirstChild("Head")
	if not head or not head:IsA("BasePart") then
		return
	end
	local billboard = Instance.new("BillboardGui")
	billboard.Name = FX_NAME
	billboard.Adornee = head
	billboard.Size = UDim2.fromScale(6, 1.1)
	billboard.StudsOffset = Vector3.new(0, 2.7, 0)
	billboard.MaxDistance = LABEL_DISTANCE
	billboard.LightInfluence = 0

	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Font = Enum.Font.GothamBlack
	label.TextScaled = true
	label.Text = "📍 " .. landmark.Name
	label.TextColor3 = landmark.Tier.Color
	label.Parent = billboard

	local stroke = Instance.new("UIStroke")
	stroke.Thickness = 2
	stroke.Transparency = 0.2
	stroke.Color = Color3.new(0, 0, 0)
	stroke.Parent = label

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
