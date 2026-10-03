-- 숲과 늪, 하늘섬(HerbZone 태그) 바닥에 영초와 드물게 천년영지, 아주 드물게 홍령삼이 돋는다.
-- 땅은 지형(Terrain)이라 레이캐스트에 지형과 Ground 판을 함께 넣는다. 물 위에는 돋지 않는다.
-- 캐면 주머니에 담긴다. 먹을지, 제물로 바칠지, 단약 재료로 쓸지는 플레이어가 고른다.

local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Balance = require(Shared.Balance)
local Progression = require(Shared.Progression)
local Josa = require(Shared.Josa)
local Races = require(Shared.Races)
local PlayerData = require(script.Parent.PlayerData)
local Sync = require(script.Parent.Sync)
local TaskService = require(script.Parent.TaskService)

local MAX_HERBS = 28
local RARE_CHANCE = 0.1
local HONGSAM_CHANCE = 0.02
local HONGSAM_COOLDOWN = 15 * 60 -- 서버에 홍령삼은 15분에 많아야 한 뿌리
local RESPAWN_MIN, RESPAWN_MAX = 20, 40

local KINDS = {
	herb = { color = Color3.fromRGB(120, 255, 170), light = 7 },
	lingzhi = { color = Color3.fromRGB(255, 210, 90), light = 12 },
	hongsam = { color = Color3.fromRGB(255, 80, 70), light = 16 },
}
local STEM_COLOR = Color3.fromRGB(70, 140, 60)

local Herbs = {}

local rng = Random.new()
local folder: Folder
local lastHongsam = -math.huge

-- 지형과 바닥 판만 맞는 레이캐스트
local function groundParams(): RaycastParams
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	local targets: { Instance } = CollectionService:GetTagged("Ground")
	table.insert(targets, Workspace.Terrain)
	params.FilterDescendantsInstances = targets
	return params
end

-- 위에서 내리쏴 맞은 땅 (물이면 nil)
local function groundBelow(origin: Vector3, length: number, params: RaycastParams): Vector3?
	local hit = Workspace:Raycast(origin, Vector3.new(0, -length, 0), params)
	if hit and hit.Material ~= Enum.Material.Water then
		return hit.Position
	end
	return nil
end

-- 영초가 돋을 자리와 그 범위의 귀한 영초 배율. 넓은 범위일수록 자주 고른다
local function randomGroundPoint(): (Vector3?, number)
	local zones = {}
	local total = 0
	for _, zone in CollectionService:GetTagged("HerbZone") do
		if zone:IsA("BasePart") then
			local area = zone.Size.X * zone.Size.Z
			table.insert(zones, { part = zone, area = area })
			total += area
		end
	end
	if total <= 0 then
		return nil, 1
	end
	local params = groundParams()
	for _ = 1, 10 do
		local pick = rng:NextNumber() * total
		local zone = zones[#zones].part
		for _, entry in zones do
			pick -= entry.area
			if pick <= 0 then
				zone = entry.part
				break
			end
		end
		local offset = Vector3.new(
			rng:NextNumber(-0.5, 0.5) * zone.Size.X,
			zone.Size.Y / 2 + 10,
			rng:NextNumber(-0.5, 0.5) * zone.Size.Z
		)
		local position = groundBelow(zone.CFrame:PointToWorldSpace(offset), zone.Size.Y + 30, params)
		if position then
			local rare = zone:GetAttribute("RareMult")
			return position, if type(rare) == "number" then rare else 1
		end
	end
	return nil, 1
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

local function collect(player: Player, herb: Model, kind: string)
	if herb.Parent == nil then
		return -- 이미 누가 캤다
	end
	local data = PlayerData.get(player)
	if not data then
		return
	end
	herb:Destroy()
	Progression.addItem(data, kind)
	-- 인족, 청림족은 하나 더 얻기도 한다 (홍령삼은 빼고)
	local extra = Races.get(data.race).doubleHerb or 0
	if kind ~= "hongsam" and rng:NextNumber() < extra then
		Progression.addItem(data, kind)
	end
	local name = Balance.ITEMS[kind].name
	local message = string.format(
		"%s 주머니에 담았다. (%d개) 왼쪽 주머니나 상태창(C)에서 먹을 수 있다.",
		Josa.eul(name),
		Progression.itemCount(data, kind)
	)
	if kind == "hongsam" then
		message = "홍령삼을 캤다! 결단기 전에 먹으면 몸이 홍령수지체로 바뀐다."
		Sync.broadcast(string.format("%s님이 홍령삼을 찾았다.", player.DisplayName), "world")
	end
	Sync.notify(player, message, "good")
	TaskService.counter(player, "herb", 10)
	Sync.markDirty(player)
	task.delay(rng:NextNumber(RESPAWN_MIN, RESPAWN_MAX), spawnHerb)
end

-- 원영 출규: 멀리서 캔다
function Herbs.collectFrom(player: Player, herb: Model)
	local kind = herb:GetAttribute("Item")
	if type(kind) == "string" then
		collect(player, herb, kind)
	end
end

local function pickKind(rareMult: number?): string
	local roll = rng:NextNumber() / (rareMult or 1)
	if roll < HONGSAM_CHANCE and os.clock() - lastHongsam > HONGSAM_COOLDOWN then
		lastHongsam = os.clock()
		return "hongsam"
	end
	return if roll < RARE_CHANCE then "lingzhi" else "herb"
end

local function spawnAt(position: Vector3, kind: string)
	local rare = kind ~= "herb"
	local name = Balance.ITEMS[kind].name
	local color = KINDS[kind].color

	local herb = Instance.new("Model")
	herb.Name = name
	herb:SetAttribute("Item", kind)
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
	light.Range = KINDS[kind].light
	light.Brightness = 1.5
	light.Parent = bulb

	if rare then
		local sparkle = Instance.new("ParticleEmitter")
		sparkle.Color = ColorSequence.new(color)
		sparkle.LightEmission = 1
		sparkle.Rate = if kind == "hongsam" then 14 else 6
		sparkle.Lifetime = NumberRange.new(1, 1.6)
		sparkle.Speed = NumberRange.new(1, 2)
		sparkle.Size = NumberSequence.new(0.25)
		sparkle.Parent = bulb
	end

	local prompt = Instance.new("ProximityPrompt")
	prompt.ActionText = "채집"
	prompt.KeyboardKeyCode = Enum.KeyCode.F
	prompt.ObjectText = name
	prompt.HoldDuration = 0.6
	prompt.MaxActivationDistance = 10
	prompt.RequiresLineOfSight = false
	prompt.Parent = bulb
	prompt.Triggered:Connect(function(player)
		collect(player, herb, kind)
	end)

	herb.PrimaryPart = bulb
	herb.Parent = folder
end

spawnHerb = function()
	if #folder:GetChildren() >= MAX_HERBS then
		return
	end
	local position, rareMult = randomGroundPoint()
	if position then
		spawnAt(position, pickKind(rareMult))
	end
end

-- 천기유도: 둘레에 영초를 돋운다
function Herbs.spawnNear(center: Vector3, count: number, kind: string?)
	local params = groundParams()
	for _ = 1, count do
		local angle = rng:NextNumber(0, math.pi * 2)
		local distance = rng:NextNumber(4, 14)
		local origin = center + Vector3.new(math.cos(angle) * distance, 40, math.sin(angle) * distance)
		local position = groundBelow(origin, 120, params)
		if position then
			spawnAt(position, kind or "herb")
		end
	end
end

function Herbs.folder(): Folder
	return folder
end

function Herbs.start()
	folder = Instance.new("Folder")
	folder.Name = "영초"
	folder.Parent = Workspace
	-- 모자라면 채운다 (서버가 지형을 짓는 중이라 처음에 자리를 못 찾았을 때도)
	task.spawn(function()
		while true do
			task.wait(15)
			if #folder:GetChildren() < MAX_HERBS then
				spawnHerb()
			end
		end
	end)
	for _ = 1, MAX_HERBS do
		spawnHerb()
	end
end

return Herbs
