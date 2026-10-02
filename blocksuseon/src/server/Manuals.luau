-- 비급(秘笈): 맵 곳곳의 ManualSpot 태그 자리에 나타나는 술법·공법서.
-- 주우면 그 기술을 익힌다. 이미 익혔거나 경지가 모자라면 그대로 남는다.

local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Skills = require(Shared.Skills)
local Progression = require(Shared.Progression)
local Josa = require(Shared.Josa)
local PlayerData = require(script.Parent.PlayerData)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)

local SPAWN_COUNT = 4
local RESPAWN_MIN, RESPAWN_MAX = 60, 120

local PAPER = Color3.fromRGB(236, 224, 190)
local ROLLER = Color3.fromRGB(150, 96, 52)
local ACTIVE_GLOW = Color3.fromRGB(255, 200, 120)
local PASSIVE_GLOW = Color3.fromRGB(140, 230, 200)

local Manuals = {}

local rng = Random.new()
local folder: Folder
local occupied: { [BasePart]: Model } = {}

local function part(parent: Instance, size: Vector3, cframe: CFrame, color: Color3, material: Enum.Material): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanTouch = false
	p.Size = size
	p.CFrame = cframe
	p.Color = color
	p.Material = material
	p.Parent = parent
	return p
end

-- 지금 맵에 없는 기술 중에서 고른다
local function pickSkill(): string
	local spawned = {}
	for _, model in occupied do
		spawned[model:GetAttribute("SkillId")] = true
	end
	local candidates = {}
	local pool = {}
	for _, skill in Skills.list do
		if not skill.granted then
			table.insert(pool, skill.id)
			if not spawned[skill.id] then
				table.insert(candidates, skill.id)
			end
		end
	end
	if #candidates == 0 then
		return pool[rng:NextInteger(1, #pool)]
	end
	return candidates[rng:NextInteger(1, #candidates)]
end

local spawnManual: () -> ()

local function take(player: Player, model: Model, spot: BasePart)
	if model.Parent == nil then
		return
	end
	local data = PlayerData.get(player)
	local id = model:GetAttribute("SkillId")
	if not data or type(id) ~= "string" then
		return
	end
	local ok, message = Progression.learn(data, id)
	if not ok then
		Sync.notify(player, message, "bad")
		return
	end

	model:Destroy()
	occupied[spot] = nil
	local def = Skills.byId[id]
	Sync.notify(player, message .. " 상태창(C)에서 확인할 수 있다.", "good")
	Sync.broadcast(
		string.format("%s님이 비급을 찾아 %s 익혔다.", player.DisplayName, Josa.eul(def.name)),
		"world"
	)
	Fx.burst(player.Character, if def.kind == "active" then ACTIVE_GLOW else PASSIVE_GLOW, 40)
	if id == "geumgang" then
		Characters.applyStats(player, false)
	end
	Sync.state(player)
	task.delay(rng:NextNumber(RESPAWN_MIN, RESPAWN_MAX), spawnManual)
end

spawnManual = function()
	local free = {}
	for _, spot in CollectionService:GetTagged("ManualSpot") do
		if spot:IsA("BasePart") and not occupied[spot] then
			table.insert(free, spot)
		end
	end
	if #free == 0 then
		return
	end
	local spot = free[rng:NextInteger(1, #free)]
	local id = pickSkill()
	local def = Skills.byId[id]
	local glow = if def.kind == "active" then ACTIVE_GLOW else PASSIVE_GLOW

	local model = Instance.new("Model")
	model.Name = def.name .. " 비급"
	model:SetAttribute("SkillId", id)
	local base = spot.Position

	part(
		model,
		Vector3.new(2.6, 1.2, 2.6),
		CFrame.new(base + Vector3.new(0, 0.6, 0)),
		Color3.fromRGB(120, 116, 108),
		Enum.Material.Slate
	)
	-- 떠 있는 두루마리: 종이 한 장과 양 끝 축
	local scroll = Instance.new("Model")
	scroll.Name = "Scroll"
	local center = CFrame.new(base + Vector3.new(0, 3, 0))
		* CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), math.rad(8))
	local paper = part(scroll, Vector3.new(1.8, 1.2, 0.08), center, PAPER, Enum.Material.SmoothPlastic)
	for _, x in { -1, 1 } do
		-- Cylinder 는 X 축이 길이라서 Z 로 90도 세운다
		local roller = part(
			scroll,
			Vector3.new(1.5, 0.3, 0.3),
			center * CFrame.new(x * 1.0, 0, 0) * CFrame.Angles(0, 0, math.rad(90)),
			ROLLER,
			Enum.Material.Wood
		)
		roller.Shape = Enum.PartType.Cylinder
	end
	scroll.PrimaryPart = paper
	scroll.Parent = model

	local light = Instance.new("PointLight")
	light.Color = glow
	light.Range = 14
	light.Brightness = 2
	light.Parent = paper

	local sparkle = Instance.new("ParticleEmitter")
	sparkle.Color = ColorSequence.new(glow)
	sparkle.LightEmission = 1
	sparkle.Rate = 8
	sparkle.Lifetime = NumberRange.new(1, 1.8)
	sparkle.Speed = NumberRange.new(0.5, 1.5)
	sparkle.SpreadAngle = Vector2.new(180, 180)
	sparkle.Size = NumberSequence.new(0.2)
	sparkle.Parent = paper

	local prompt = Instance.new("ProximityPrompt")
	prompt.ActionText = "익히기"
	prompt.KeyboardKeyCode = Enum.KeyCode.F
	prompt.ObjectText = model.Name
	prompt.HoldDuration = 1
	prompt.MaxActivationDistance = 10
	prompt.RequiresLineOfSight = false
	prompt.Parent = paper
	prompt.Triggered:Connect(function(player)
		take(player, model, spot)
	end)

	model.PrimaryPart = paper
	model.Parent = folder
	occupied[spot] = model
end

-- 천기유도(토): 비급 하나를 바로 드러낸다
function Manuals.spawnNow()
	spawnManual()
end

function Manuals.start()
	folder = Instance.new("Folder")
	folder.Name = "비급"
	folder.Parent = Workspace
	for _ = 1, SPAWN_COUNT do
		spawnManual()
	end
end

return Manuals
