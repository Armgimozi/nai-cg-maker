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

return Fx
