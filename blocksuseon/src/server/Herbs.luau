-- 영초숲(HerbZone 태그) 바닥에 영초와 드물게 천년영지가 돋는다.

local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Balance = require(Shared.Balance)
local Progression = require(Shared.Progression)
local Format = require(Shared.Format)
local PlayerData = require(script.Parent.PlayerData)
local Sync = require(script.Parent.Sync)
local Cultivation = require(script.Parent.Cultivation)

local MAX_HERBS = 16
local RARE_CHANCE = 0.06
local RESPAWN_MIN, RESPAWN_MAX = 20, 40

local HERB_COLOR = Color3.fromRGB(120, 255, 170)
local RARE_COLOR = Color3.fromRGB(255, 210, 90)
local STEM_COLOR = Color3.fromRGB(70, 140, 60)

local Herbs = {}

local rng = Random.new()
local folder: Folder

local function randomGroundPoint(): Vector3?
	local zones = CollectionService:GetTagged("HerbZone")
	if #zones == 0 then
		return nil
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = CollectionService:GetTagged("Ground")

	for _ = 1, 10 do
		local zone = zones[rng:NextInteger(1, #zones)]
		if zone:IsA("BasePart") then
			local offset =
				Vector3.new(rng:NextNumber(-0.5, 0.5) * zone.Size.X, 0, rng:NextNumber(-0.5, 0.5) * zone.Size.Z)
			local origin = zone.CFrame:PointToWorldSpace(offset) + Vector3.new(0, 50, 0)
			local hit = Workspace:Raycast(origin, Vector3.new(0, -150, 0), params)
			if hit then
				return hit.Position
			end
		end
	end
	return nil
end

local function herbPart(parent: Instance, size: Vector3, cframe: CFrame, color: Color3, material: Enum.Material): Part
	local part = Instance.new("Part")
	part.Anchored = true
	part.CanCollide = false
	part.CanTouch = false
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = material
	part.Parent = parent
	return part
end

local spawnHerb: () -> ()

local function collect(player: Player, herb: Model, rare: boolean)
	if herb.Parent == nil then
		return -- 이미 누가 캤다
	end
	local data = PlayerData.get(player)
	if not data then
		return
	end
	if Cultivation.isFull(player) then
		Sync.notify(player, "영력이 가득 차서 더 받아들일 수 없다. 먼저 돌파해야 한다.", "bad")
		return
	end

	herb:Destroy()
	data.stats.herbs += 1
	local amount = Progression.herbQi(data, rare)
	if rare then
		data.enlightenment += Balance.RARE_HERB_POINTS
		Sync.notify(
			player,
			string.format(
				"천년영지를 먹었다! 영력 +%s, 깨달음 +%d",
				Format.qi(amount),
				Balance.RARE_HERB_POINTS
			),
			"good"
		)
	else
		Sync.notify(player, string.format("영초를 먹었다. 영력 +%s", Format.qi(amount)), "good")
	end
	Cultivation.grantQi(player, amount)
	task.delay(rng:NextNumber(RESPAWN_MIN, RESPAWN_MAX), spawnHerb)
end

spawnHerb = function()
	local position = randomGroundPoint()
	if not position then
		return
	end
	local rare = rng:NextNumber() < RARE_CHANCE
	local name = if rare then "천년영지" else "영초"
	local color = if rare then RARE_COLOR else HERB_COLOR

	local herb = Instance.new("Model")
	herb.Name = name
	herbPart(
		herb,
		Vector3.new(0.3, 1.6, 0.3),
		CFrame.new(position + Vector3.new(0, 0.8, 0)),
		STEM_COLOR,
		Enum.Material.Grass
	)
	for _, angle in { 0, 120, 240 } do
		herbPart(
			herb,
			Vector3.new(1.2, 0.1, 0.5),
			CFrame.new(position + Vector3.new(0, 0.6, 0))
				* CFrame.Angles(0, math.rad(angle), math.rad(20))
				* CFrame.new(0.5, 0, 0),
			STEM_COLOR,
			Enum.Material.Grass
		)
	end
	local bulb = herbPart(
		herb,
		Vector3.new(1, 1, 1),
		CFrame.new(position + Vector3.new(0, 1.9, 0)) * CFrame.Angles(0, math.rad(45), math.rad(45)),
		color,
		Enum.Material.Neon
	)

	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = if rare then 12 else 7
	light.Brightness = 1.5
	light.Parent = bulb

	if rare then
		local sparkle = Instance.new("ParticleEmitter")
		sparkle.Color = ColorSequence.new(color)
		sparkle.LightEmission = 1
		sparkle.Rate = 6
		sparkle.Lifetime = NumberRange.new(1, 1.6)
		sparkle.Speed = NumberRange.new(1, 2)
		sparkle.Size = NumberSequence.new(0.25)
		sparkle.Parent = bulb
	end

	local prompt = Instance.new("ProximityPrompt")
	prompt.ActionText = "채집"
	prompt.ObjectText = name
	prompt.HoldDuration = 0.6
	prompt.MaxActivationDistance = 10
	prompt.RequiresLineOfSight = false
	prompt.Parent = bulb
	prompt.Triggered:Connect(function(player)
		collect(player, herb, rare)
	end)

	herb.PrimaryPart = bulb
	herb.Parent = folder
end

function Herbs.start()
	folder = Instance.new("Folder")
	folder.Name = "영초"
	folder.Parent = Workspace
	for _ = 1, MAX_HERBS do
		spawnHerb()
	end
end

return Herbs
