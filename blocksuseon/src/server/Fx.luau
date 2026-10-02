-- 서버에서 만드는 효과 (모두에게 보인다).

local Debris = game:GetService("Debris")

local Fx = {}

local AURA_NAME = "운기오라"

local function rootOf(character: Model?): BasePart?
	return character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
end

function Fx.setAura(character: Model?, on: boolean)
	local root = rootOf(character)
	if not root then
		return
	end
	local existing = root:FindFirstChild(AURA_NAME)
	if not on then
		if existing then
			existing:Destroy()
		end
		return
	end
	if existing then
		return
	end

	local aura = Instance.new("Attachment")
	aura.Name = AURA_NAME
	aura.Position = Vector3.new(0, -1.5, 0)
	aura.Parent = root

	local motes = Instance.new("ParticleEmitter")
	motes.Color = ColorSequence.new(Color3.fromRGB(150, 235, 255))
	motes.LightEmission = 1
	motes.Rate = 14
	motes.Lifetime = NumberRange.new(1.2, 2)
	motes.Speed = NumberRange.new(1.5, 3)
	motes.SpreadAngle = Vector2.new(180, 0)
	motes.Acceleration = Vector3.new(0, 3, 0)
	motes.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.35),
		NumberSequenceKeypoint.new(1, 0),
	})
	motes.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.1),
		NumberSequenceKeypoint.new(1, 1),
	})
	motes.Parent = aura

	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(150, 235, 255)
	light.Range = 10
	light.Brightness = 1.2
	light.Parent = aura
end

-- 경지가 오를 때 터지는 빛
function Fx.burst(character: Model?, color: Color3, amount: number?)
	local root = rootOf(character)
	if not root then
		return
	end
	local attachment = Instance.new("Attachment")
	attachment.Parent = root

	local burst = Instance.new("ParticleEmitter")
	burst.Color = ColorSequence.new(color)
	burst.LightEmission = 1
	burst.Rate = 0
	burst.Lifetime = NumberRange.new(0.8, 1.4)
	burst.Speed = NumberRange.new(10, 18)
	burst.SpreadAngle = Vector2.new(180, 180)
	burst.Drag = 3
	burst.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.6),
		NumberSequenceKeypoint.new(1, 0),
	})
	burst.Parent = attachment
	burst:Emit(amount or 40)

	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 18
	light.Brightness = 4
	light.Parent = attachment

	Debris:AddItem(attachment, 2)
end

-- 경신술: 몸 뒤로 남는 잔상
function Fx.trail(character: Model?, color: Color3, duration: number)
	local root = rootOf(character)
	if not root then
		return
	end
	local top = Instance.new("Attachment")
	top.Position = Vector3.new(0, 1.2, 0)
	top.Parent = root
	local bottom = Instance.new("Attachment")
	bottom.Position = Vector3.new(0, -1.6, 0)
	bottom.Parent = root

	local trail = Instance.new("Trail")
	trail.Attachment0 = top
	trail.Attachment1 = bottom
	trail.Color = ColorSequence.new(color)
	trail.LightEmission = 1
	trail.Lifetime = 0.3
	trail.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.3),
		NumberSequenceKeypoint.new(1, 1),
	})
	trail.Parent = root

	Debris:AddItem(trail, duration + 0.4)
	Debris:AddItem(top, duration + 0.4)
	Debris:AddItem(bottom, duration + 0.4)
end

-- 호신강기: 몸을 감싸는 금빛 막
function Fx.shield(character: Model?, duration: number)
	local root = rootOf(character)
	if not root then
		return
	end
	local bubble = Instance.new("Part")
	bubble.Name = "호신강기"
	bubble.Shape = Enum.PartType.Ball
	bubble.Size = Vector3.new(8, 8, 8)
	bubble.Material = Enum.Material.ForceField
	bubble.Color = Color3.fromRGB(255, 214, 120)
	bubble.CanCollide = false
	bubble.CanQuery = false
	bubble.CanTouch = false
	bubble.Massless = true
	bubble.CastShadow = false
	bubble.CFrame = root.CFrame
	local weld = Instance.new("WeldConstraint")
	weld.Part0 = bubble
	weld.Part1 = root
	weld.Parent = bubble
	bubble.Parent = character
	Debris:AddItem(bubble, duration)
end

-- 취령진: 발밑에 펼쳐지는 진
function Fx.formation(position: Vector3, radius: number, duration: number): Model
	local formation = Instance.new("Model")
	formation.Name = "취령진"
	local color = Color3.fromRGB(130, 230, 200)
	local flat = CFrame.Angles(0, 0, math.rad(90))

	local function disc(r: number, y: number, transparency: number)
		local part = Instance.new("Part")
		part.Shape = Enum.PartType.Cylinder
		part.Size = Vector3.new(0.2, r * 2, r * 2)
		part.CFrame = CFrame.new(position + Vector3.new(0, y, 0)) * flat
		part.Color = color
		part.Material = Enum.Material.Neon
		part.Transparency = transparency
		part.Anchored = true
		part.CanCollide = false
		part.CanQuery = false
		part.CanTouch = false
		part.CastShadow = false
		part.Parent = formation
		return part
	end
	disc(radius, -2.8, 0.75)
	disc(radius * 0.62, -2.75, 0.6)

	-- 여덟 방위의 빛기둥
	for i = 0, 7 do
		local angle = math.rad(i * 45)
		local pillar = Instance.new("Part")
		pillar.Size = Vector3.new(0.5, 3, 0.5)
		pillar.CFrame = CFrame.new(position + Vector3.new(math.cos(angle) * radius, -1.5, math.sin(angle) * radius))
		pillar.Color = color
		pillar.Material = Enum.Material.Neon
		pillar.Transparency = 0.3
		pillar.Anchored = true
		pillar.CanCollide = false
		pillar.CanQuery = false
		pillar.CanTouch = false
		pillar.Parent = formation
	end

	local center = disc(1, -2.7, 1)
	local motes = Instance.new("ParticleEmitter")
	motes.Color = ColorSequence.new(color)
	motes.LightEmission = 1
	motes.Rate = 20
	motes.Lifetime = NumberRange.new(1.5, 2.5)
	motes.Speed = NumberRange.new(2, 4)
	motes.EmissionDirection = Enum.NormalId.Right
	motes.SpreadAngle = Vector2.new(25, 25)
	motes.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.4),
		NumberSequenceKeypoint.new(1, 0),
	})
	motes.Parent = center

	formation.Parent = workspace
	Debris:AddItem(formation, duration)
	return formation
end

return Fx
