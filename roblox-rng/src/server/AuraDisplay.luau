-- 장착한 오라를 캐릭터에 표시: 머리 위 이름표 + 등급에 따른 파티클/빛
-- 그라데이션 회전 애니메이션은 클라이언트가 "AuraGradient" 태그를 보고 처리합니다(서버 복제 부담 없음).

local CollectionService = game:GetService("CollectionService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Auras = require(Shared.Auras)
local Format = require(Shared.Format)

local FX_NAME = "AuraFX"

local AuraDisplay = {}

local function colorSequence(colors: { Color3 }): ColorSequence
	if #colors == 1 then
		return ColorSequence.new(colors[1])
	end
	local keypoints = {}
	for i, color in colors do
		table.insert(keypoints, ColorSequenceKeypoint.new((i - 1) / (#colors - 1), color))
	end
	return ColorSequence.new(keypoints)
end

local function auraColors(aura: Auras.Aura): { Color3 }
	return aura.Gradient or { aura.Color }
end

local function clear(character: Model)
	for _, descendant in character:GetDescendants() do
		if descendant.Name == FX_NAME then
			descendant:Destroy()
		end
	end
end

local function makeLabel(parent: Instance, text: string, size: UDim2, position: UDim2, aura: Auras.Aura): TextLabel
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = size
	label.Position = position
	label.Font = Enum.Font.GothamBlack
	label.TextScaled = true
	label.Text = text
	label.TextColor3 = if aura.Gradient then Color3.new(1, 1, 1) else aura.Color
	label.Parent = parent

	local stroke = Instance.new("UIStroke")
	stroke.Thickness = 2
	stroke.Transparency = 0.2
	stroke.Color = Color3.new(0, 0, 0)
	stroke.Parent = label

	if aura.Gradient then
		local gradient = Instance.new("UIGradient")
		gradient.Color = colorSequence(aura.Gradient)
		gradient.Parent = label
		CollectionService:AddTag(gradient, "AuraGradient")
	end
	return label
end

local function addBillboard(character: Model, aura: Auras.Aura)
	local head = character:FindFirstChild("Head")
	if not head or not head:IsA("BasePart") then
		return
	end
	local billboard = Instance.new("BillboardGui")
	billboard.Name = FX_NAME
	billboard.Adornee = head
	billboard.Size = UDim2.new(7, 0, 1.8, 0)
	billboard.StudsOffset = Vector3.new(0, 2.6, 0)
	billboard.MaxDistance = 120
	billboard.LightInfluence = 0

	makeLabel(billboard, aura.Name, UDim2.fromScale(1, 0.62), UDim2.fromScale(0, 0), aura)
	makeLabel(
		billboard,
		Format.oneIn(aura.OneIn) .. " · " .. aura.Tier.Name,
		UDim2.fromScale(1, 0.34),
		UDim2.fromScale(0, 0.64),
		aura
	)
	billboard.Parent = head
end

local function addParticles(character: Model, aura: Auras.Aura)
	local root = character:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") then
		return
	end
	local rank = aura.Tier.Rank
	if rank < 3 then
		return -- 일반/고급 등급은 이름표만
	end

	local attachment = Instance.new("Attachment")
	attachment.Name = FX_NAME
	attachment.Parent = root

	local sparkles = Instance.new("ParticleEmitter")
	sparkles.Color = colorSequence(auraColors(aura))
	sparkles.LightEmission = 1
	sparkles.LightInfluence = 0
	sparkles.Lifetime = NumberRange.new(1, 1.8)
	sparkles.Rate = 6 * rank
	sparkles.Speed = NumberRange.new(1, 2 + rank * 0.5)
	sparkles.SpreadAngle = Vector2.new(180, 180)
	sparkles.Rotation = NumberRange.new(0, 360)
	sparkles.RotSpeed = NumberRange.new(-90, 90)
	sparkles.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0),
		NumberSequenceKeypoint.new(0.2, 0.25 + rank * 0.05),
		NumberSequenceKeypoint.new(1, 0),
	})
	sparkles.Acceleration = Vector3.new(0, 1.5, 0)
	sparkles.Parent = attachment

	if rank >= 4 then
		local light = Instance.new("PointLight")
		light.Name = FX_NAME
		light.Color = aura.Color
		light.Range = 6 + rank * 2
		light.Brightness = 1.5
		light.Parent = root
	end

	if rank >= 6 then
		-- 신화/초월: 발밑에서 올라오는 두 번째 파티클 기둥
		local pillar = Instance.new("ParticleEmitter")
		pillar.Color = sparkles.Color
		pillar.LightEmission = 1
		pillar.LightInfluence = 0
		pillar.Lifetime = NumberRange.new(1.2, 2)
		pillar.Rate = 30
		pillar.Speed = NumberRange.new(4, 7)
		pillar.EmissionDirection = Enum.NormalId.Top
		pillar.SpreadAngle = Vector2.new(8, 8)
		pillar.Size = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.6),
			NumberSequenceKeypoint.new(1, 0),
		})
		pillar.Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.2),
			NumberSequenceKeypoint.new(1, 1),
		})
		pillar.Parent = attachment
	end
end

-- aura 가 nil 이면 효과 제거만
function AuraDisplay.apply(character: Model?, aura: Auras.Aura?)
	if not character then
		return
	end
	clear(character)
	if aura then
		addBillboard(character, aura)
		addParticles(character, aura)
	end
end

return AuraDisplay
