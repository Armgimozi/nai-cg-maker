-- 영성우(靈星雨): 밤마다 하늘에서 영성이 떨어져 땅에 별씨가 박힌다. 축기기 수도자가 주워 단전에 별로 응결한다.
-- 원작에 없는 게임 해석이다(축기기에 별을 맺는 과정을 블록 월드의 일로 옮겼다).
-- 축기기 플레이어가 있을 때만, 그 수에 맞춰 내린다. 떨어질 자리는 푸른 원으로 미리 보인다.

local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Progression = require(Shared.Progression)
local PlayerData = require(script.Parent.PlayerData)
local Sync = require(script.Parent.Sync)
local Tribulation = require(script.Parent.Tribulation)
local DayNight = require(script.Parent.DayNight)

local SEED_COLOR = Color3.fromRGB(150, 200, 255)
local AREA_CENTER = Vector3.new(-20, 0, -40)
local AREA_RADIUS = 170
local MAX_SEEDS = 14
local SEED_LIFE = 90
local TELEGRAPH = 2.5

local StarRain = {}

local rng = Random.new()
local folder: Folder
local wasNight = false

local function chukgiPlayers(): number
	local count = 0
	local first = Realms.firstStepById.chukgi
	local last = Realms.firstStepById.gyeoldan
	for _, player in Players:GetPlayers() do
		local data = PlayerData.get(player)
		if data and data.step >= first and data.step < last then
			count += 1
		end
	end
	return count
end

local function groundPoint(): Vector3?
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	local ignore: { Instance } = { folder }
	for _, player in Players:GetPlayers() do
		if player.Character then
			table.insert(ignore, player.Character)
		end
	end
	params.FilterDescendantsInstances = ignore
	for _ = 1, 8 do
		local angle = rng:NextNumber(0, math.pi * 2)
		local distance = math.sqrt(rng:NextNumber()) * AREA_RADIUS
		local origin = AREA_CENTER + Vector3.new(math.cos(angle) * distance, 120, math.sin(angle) * distance)
		local hit = Workspace:Raycast(origin, Vector3.new(0, -200, 0), params)
		if hit and hit.Instance.CanCollide and hit.Position.Y < 60 then
			return hit.Position
		end
	end
	return nil
end

local function take(player: Player, seed: Model)
	if seed.Parent == nil then
		return
	end
	local data = PlayerData.get(player)
	if not data then
		return
	end
	if data.step < Realms.firstStepById.chukgi then
		Sync.notify(player, "아직 별씨를 다룰 수 없다. 축기기부터 단전에 별을 맺는다.", "bad")
		return
	end
	seed:Destroy()
	Progression.addItem(data, "starSeed")
	Sync.notify(
		player,
		string.format(
			"별씨를 주웠다. (%d개) 과업의 내관으로 별을 응결한다.",
			Progression.itemCount(data, "starSeed")
		),
		"good"
	)
	Sync.markDirty(player)
end

local function spawnSeed()
	local ground = groundPoint()
	if not ground then
		return
	end
	Tribulation.mark(ground, 3.5, TELEGRAPH, SEED_COLOR)
	task.delay(TELEGRAPH, function()
		Tribulation.strike(ground, 3, SEED_COLOR)
		local seed = Instance.new("Model")
		seed.Name = "별씨"
		local core = Instance.new("Part")
		core.Name = "Core"
		core.Shape = Enum.PartType.Ball
		core.Size = Vector3.new(1.4, 1.4, 1.4)
		core.Material = Enum.Material.Neon
		core.Color = SEED_COLOR
		core.Anchored = true
		core.CanCollide = false
		core.CanTouch = false
		core.CFrame = CFrame.new(ground + Vector3.new(0, 1.2, 0))
		core.Parent = seed
		local light = Instance.new("PointLight")
		light.Color = SEED_COLOR
		light.Range = 12
		light.Brightness = 2
		light.Parent = core
		local sparkle = Instance.new("ParticleEmitter")
		sparkle.Color = ColorSequence.new(SEED_COLOR)
		sparkle.LightEmission = 1
		sparkle.Rate = 10
		sparkle.Lifetime = NumberRange.new(0.8, 1.4)
		sparkle.Speed = NumberRange.new(1, 3)
		sparkle.SpreadAngle = Vector2.new(180, 180)
		sparkle.Size = NumberSequence.new(0.2)
		sparkle.Parent = core

		local prompt = Instance.new("ProximityPrompt")
		prompt.ActionText = "별씨 줍기"
		prompt.ObjectText = "별씨"
		prompt.KeyboardKeyCode = Enum.KeyCode.F
		prompt.HoldDuration = 0.3
		prompt.MaxActivationDistance = 10
		prompt.RequiresLineOfSight = false
		prompt:SetAttribute("Site", "starseed")
		prompt:AddTag("TaskPrompt")
		prompt.Parent = core
		prompt.Triggered:Connect(function(player)
			take(player, seed)
		end)
		seed.PrimaryPart = core
		seed.Parent = folder
		task.delay(SEED_LIFE, function()
			if seed.Parent then
				seed:Destroy()
			end
		end)
	end)
end

function StarRain.start()
	folder = Instance.new("Folder")
	folder.Name = "별씨"
	folder.Parent = Workspace
	task.spawn(function()
		while true do
			local players = chukgiPlayers()
			local night = DayNight.phase() == "night"
			if night and not wasNight and players > 0 then
				Sync.broadcast(
					"밤하늘에서 영성우가 내린다. 푸른 빛이 떨어진 자리에 별씨가 박힌다.",
					"world"
				)
			end
			wasNight = night
			if night and players > 0 and #folder:GetChildren() < MAX_SEEDS then
				spawnSeed()
			end
			-- 축기기 플레이어가 많을수록 자주 내린다
			task.wait(if players > 0 then math.max(2, 7 - players) else 5)
		end
	end)
end

-- 영안으로 별씨도 보이게 (Effects 가 Workspace 의 "별씨" 폴더를 본다)
StarRain.FOLDER_NAME = "별씨"

return StarRain
