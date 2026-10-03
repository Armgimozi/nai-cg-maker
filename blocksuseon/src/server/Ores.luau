-- 영석 광맥. 위험한 땅(Places.tierAt 이 1 이상)에서만 플레이어 둘레에 돋는다.
-- 땅의 위험도가 높을수록 광맥이 크고 빛깔이 짙으며, 캐는 양도 많다 (Currency.ORE).
-- 자리는 레이캐스트로만 고른다 (지형과 Ground 판, 물과 가파른 비탈, 지붕 아래는 빼고). 맵 좌표를 박아 두지 않는다.
-- F 를 누르고 있으면 캔다. 먼저 캔 사람만 얻는다. 모두에게서 오래 멀리 있던 광맥은 사라진다.

local CollectionService = game:GetService("CollectionService")
local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Currency = require(Shared.Currency)
local Places = require(Shared.Places)
local Progression = require(Shared.Progression)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)

local FOLDER_NAME = "영석 광맥"
local PER_PLAYER = 4 -- 한 사람 둘레(NEAR 안)에 이만큼
local NEAR = 150
local MAX_ORES = 50
local SPAWN_MIN, SPAWN_MAX = 30, 150 -- 사람에게서 떨어진 가로 거리
local SPAWN_EVERY = 2
local TRIES = 6 -- 한 번에 자리를 고르는 횟수
local SPACING = 16 -- 광맥끼리 이만큼은 떨어진다
local DESPAWN_DISTANCE = 300
local DESPAWN_AFTER = 30 -- 모두에게서 멀리 있은 지 이만큼 지나면 사라진다
local MINE_REACH = 12 -- 서버가 다시 보는 캐는 거리
local CAST_UP, CAST_DOWN = 160, 420 -- 사람 높이에서 이만큼 위에서 내리쏜다
local MAX_RISE = 90 -- 사람 높이와 이만큼 넘게 차이 나는 땅(벼랑 위, 떠 있는 섬 아래)은 빼고
local MIN_NORMAL_Y = 0.8 -- 비탈이 이보다 가파르면(약 37도) 빼고
local MINE_SOUND = "rbxasset://sounds/electronicpingshort.wav"

-- 위험도마다 영석 빛깔 (1 옅은 비취, 2 청록, 3 하늘빛, 4 보랏빛, 5 금빛)
local COLORS = {
	Color3.fromRGB(175, 240, 205),
	Color3.fromRGB(80, 230, 230),
	Color3.fromRGB(105, 175, 255),
	Color3.fromRGB(180, 120, 255),
	Color3.fromRGB(255, 205, 80),
}
local ROCK_COLOR = Color3.fromRGB(92, 94, 102)
local DARK_ROCK_COLOR = Color3.fromRGB(62, 62, 70)
local WHITE = Color3.new(1, 1, 1)
local UP = Vector3.new(0, 1, 0)
-- 정육면체를 꼭짓점이 위로 가게 세운다 (수정 끝)
local TIP_TURN = CFrame.Angles(0, 0, math.atan(math.sqrt(2))) * CFrame.Angles(0, math.pi / 4, 0)

type Shard = { parts: { BasePart }, out: Vector3 }
type Node = {
	model: Model,
	center: Vector3, -- 프롬프트와 빛이 있는 자리
	tier: number,
	rocks: { BasePart },
	shards: { Shard },
	light: PointLight,
	prompt: ProximityPrompt,
	farSince: number?,
	taken: boolean,
}

local Ores = {}

local rng = Random.new()
local folder: Folder
local nodes: { Node } = {}

local function playerRoot(player: Player): BasePart?
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if humanoid and humanoid.Health > 0 and root and root:IsA("BasePart") then
		return root
	end
	return nil
end

local function flatDistance(a: Vector3, b: Vector3): number
	return Vector3.new(a.X - b.X, 0, a.Z - b.Z).Magnitude
end

-- 지형과 바닥 판만 맞는 레이캐스트
local function groundParams(): RaycastParams
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	local targets: { Instance } = CollectionService:GetTagged("Ground")
	table.insert(targets, Workspace.Terrain)
	params.FilterDescendantsInstances = targets
	return params
end

-- 자리를 막는 것을 볼 때 빼는 것: 바닥 판, 광맥, 사람
local function blockerIgnore(): { Instance }
	local ignore: { Instance } = CollectionService:GetTagged("Ground")
	table.insert(ignore, folder)
	for _, player in Players:GetPlayers() do
		if player.Character then
			table.insert(ignore, player.Character)
		end
	end
	return ignore
end

local function crowded(ground: Vector3, spacing: number): boolean
	for _, node in nodes do
		if flatDistance(node.center, ground) < spacing then
			return true
		end
	end
	return false
end

-- 위가 트였고(지붕, 나무, 바위 아래가 아니고) 둘레에 벽이나 나무줄기가 없는가.
-- 부딪히는 것만 본다 (보이지 않는 범위 판은 CanCollide 가 꺼져 있다)
local function clear(ground: Vector3, width: number, ignore: { Instance }): boolean
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore
	params.RespectCanCollide = true
	if Workspace:Raycast(ground + Vector3.new(0, 40, 0), Vector3.new(0, -39.5, 0), params) then
		return false
	end
	local boxIgnore = table.clone(ignore)
	table.insert(boxIgnore, Workspace.Terrain)
	local overlap = OverlapParams.new()
	overlap.FilterType = Enum.RaycastFilterType.Exclude
	overlap.FilterDescendantsInstances = boxIgnore
	overlap.RespectCanCollide = true
	local box = CFrame.new(ground + Vector3.new(0, 3.5, 0))
	return #Workspace:GetPartBoundsInBox(box, Vector3.new(width, 5, width), overlap) == 0
end

local function scaleOf(tier: number): number
	return 1 + (tier - 1) * 0.2
end

-- 이 둘레(가로 거리 minR~maxR)에서 광맥을 놓을 땅. 반환: 땅, 땅의 법선, 그 땅의 위험도
local function findSpot(
	center: Vector3,
	minR: number,
	maxR: number,
	maxRise: number?,
	spacing: number,
	allowSafe: boolean
): (Vector3?, Vector3?, number)
	local params = groundParams()
	local ignore = blockerIgnore()
	for _ = 1, TRIES do
		local angle = rng:NextNumber(0, math.pi * 2)
		local distance = math.sqrt(rng:NextNumber(minR * minR, maxR * maxR))
		local x = center.X + math.cos(angle) * distance
		local z = center.Z + math.sin(angle) * distance
		local hit = Workspace:Raycast(Vector3.new(x, center.Y + CAST_UP, z), Vector3.new(0, -CAST_DOWN, 0), params)
		if hit and hit.Material ~= Enum.Material.Water and hit.Normal.Y >= MIN_NORMAL_Y then
			local ground = hit.Position
			local tier = Places.tierAt(ground.X, ground.Z, ground.Y)
			local level = maxRise == nil or math.abs(ground.Y - center.Y) <= maxRise
			if (tier > 0 or allowSafe) and level and not crowded(ground, spacing) then
				local width = 4 + 3 * scaleOf(math.clamp(tier, 1, #Currency.ORE))
				if clear(ground, width, ignore) then
					return ground, hit.Normal, tier
				end
			end
		end
	end
	return nil, nil, 0
end

-- 광맥이 앉을 틀: 땅 기울기를 조금 따르고, 도는 방향은 아무렇게나
local function surfaceFrame(ground: Vector3, normal: Vector3): CFrame
	local yaw = CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0)
	local axis = UP:Cross(normal)
	if axis.Magnitude < 1e-3 then
		return CFrame.new(ground) * yaw
	end
	local angle = math.acos(math.clamp(normal.Y, -1, 1)) * 0.6
	return CFrame.new(ground) * CFrame.fromAxisAngle(axis.Unit, angle) * yaw
end

local function newPart(model: Model, size: Vector3, cframe: CFrame, color: Color3, material: Enum.Material): Part
	local part = Instance.new("Part")
	part.Anchored = true
	part.CanTouch = false
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = material
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = model
	return part
end

local function crystalPart(model: Model, size: Vector3, cframe: CFrame, color: Color3, core: boolean): Part
	local part = newPart(model, size, cframe, color, if core then Enum.Material.Neon else Enum.Material.Glass)
	part.Transparency = if core then 0.15 else 0.25
	part.CanCollide = false
	part.CanQuery = false
	part.CastShadow = false
	return part
end

local function jitter(): Vector3
	return Vector3.new(rng:NextNumber(0.85, 1.15), rng:NextNumber(0.85, 1.15), rng:NextNumber(0.85, 1.15))
end

-- 바위 위로 솟은 수정 한 줄기: 기둥, 뾰족한 끝, 안에서 빛나는 심
local function addShard(
	model: Model,
	frame: CFrame,
	offset: Vector3,
	azimuth: number,
	tilt: number,
	height: number,
	width: number,
	tier: number
): Shard
	local color = COLORS[tier]
	local root = frame
		* CFrame.new(offset)
		* CFrame.Angles(0, -azimuth, 0)
		* CFrame.Angles(0, 0, -tilt)
		* CFrame.Angles(0, rng:NextNumber(0, math.pi / 2), 0)
	local tipSize = width * 0.72
	local parts: { BasePart } = {
		crystalPart(model, Vector3.new(width, height, width), root * CFrame.new(0, height / 2, 0), color, false),
		crystalPart(
			model,
			Vector3.new(tipSize, tipSize, tipSize),
			root * CFrame.new(0, height, 0) * TIP_TURN,
			color,
			false
		),
		crystalPart(
			model,
			Vector3.new(width * 0.42, height * 0.8, width * 0.42),
			root * CFrame.new(0, height * 0.45, 0),
			color:Lerp(WHITE, 0.45),
			true
		),
	}
	-- 깨질 때 튀어 나갈 쪽 (기울어진 쪽, 곧게 선 줄기는 아무 쪽)
	local up = root.UpVector
	local out = Vector3.new(up.X, 0, up.Z)
	if out.Magnitude < 0.05 then
		local angle = rng:NextNumber(0, math.pi * 2)
		out = Vector3.new(math.cos(angle), 0, math.sin(angle))
	end
	return { parts = parts, out = out.Unit }
end

local forget: (node: Node) -> ()
local mine: (player: Player, node: Node) -> ()

local function build(ground: Vector3, normal: Vector3, tier: number): Node
	local color = COLORS[tier]
	local scale = scaleOf(tier)
	local frame = surfaceFrame(ground, normal)

	local model = Instance.new("Model")
	model.Name = FOLDER_NAME
	model:SetAttribute("Ore", true)
	model:SetAttribute("Tier", tier)

	-- 거친 바위 받침. 반쯤 땅에 묻는다
	local rocks: { BasePart } = {}
	local base = newPart(
		model,
		Vector3.new(3.4, 1.7, 3) * scale * jitter(),
		frame
			* CFrame.new(0, 0.3 * scale, 0)
			* CFrame.Angles(rng:NextNumber(-0.15, 0.15), rng:NextNumber(0, math.pi), rng:NextNumber(-0.15, 0.15)),
		ROCK_COLOR,
		Enum.Material.Slate
	)
	table.insert(rocks, base)
	local sideRocks = if tier >= 3 then 2 else 1
	local sideStart = rng:NextNumber(0, math.pi * 2)
	for i = 1, sideRocks do
		local angle = sideStart + (i - 1) * rng:NextNumber(1.8, 2.6)
		local distance = rng:NextNumber(1.7, 2.2) * scale
		local size = Vector3.new(rng:NextNumber(1.5, 2.1), rng:NextNumber(0.9, 1.3), rng:NextNumber(1.3, 1.9))
		table.insert(
			rocks,
			newPart(
				model,
				size * scale,
				frame
					* CFrame.new(math.cos(angle) * distance, 0.15 * scale, math.sin(angle) * distance)
					* CFrame.Angles(
						rng:NextNumber(-0.25, 0.25),
						rng:NextNumber(0, math.pi),
						rng:NextNumber(-0.25, 0.25)
					),
				DARK_ROCK_COLOR,
				Enum.Material.Basalt
			)
		)
	end

	-- 수정 4~7 줄기. 가운데 큰 줄기 하나와 둘레로 기운 줄기들
	local shards: { Shard } = {}
	local count = math.clamp(3 + tier + rng:NextInteger(0, 1), 4, 7)
	local main = addShard(
		model,
		frame,
		Vector3.new(0, 0.7 * scale, 0),
		rng:NextNumber(0, math.pi * 2),
		rng:NextNumber(0, 0.12),
		(3 + rng:NextNumber(0, 0.6)) * scale,
		0.95 * scale,
		tier
	)
	table.insert(shards, main)
	local ringStart = rng:NextNumber(0, math.pi * 2)
	for i = 1, count - 1 do
		local azimuth = ringStart + (i - 1) / (count - 1) * math.pi * 2 + rng:NextNumber(-0.3, 0.3)
		local reach = rng:NextNumber(0.5, 1.1) * scale
		table.insert(
			shards,
			addShard(
				model,
				frame,
				Vector3.new(math.cos(azimuth) * reach, 0.75 * scale, math.sin(azimuth) * reach),
				azimuth,
				rng:NextNumber(0.3, 0.65),
				rng:NextNumber(1.3, 2.5) * scale,
				rng:NextNumber(0.55, 0.8) * scale,
				tier
			)
		)
	end

	-- 빛과 프롬프트는 무더기 한가운데
	local centerCFrame = frame * CFrame.new(0, 1.8 * scale, 0)
	local anchor = Instance.new("Attachment")
	anchor.Name = "광맥"
	anchor.CFrame = base.CFrame:ToObjectSpace(centerCFrame)
	anchor.Parent = base

	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 8 + tier * 2
	light.Brightness = 1 + tier * 0.25
	light.Shadows = false
	light.Parent = anchor

	-- 위험도 3 부터는 잔빛이 인다
	if tier >= 3 then
		local sparkle = Instance.new("ParticleEmitter")
		sparkle.Color = ColorSequence.new(color:Lerp(WHITE, 0.3))
		sparkle.LightEmission = 1
		sparkle.Rate = (tier - 2) * 2
		sparkle.Lifetime = NumberRange.new(0.8, 1.6)
		sparkle.Speed = NumberRange.new(0.3, 0.9)
		sparkle.SpreadAngle = Vector2.new(180, 180)
		sparkle.Acceleration = Vector3.new(0, 1.5, 0)
		sparkle.Size = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.1),
			NumberSequenceKeypoint.new(0.4, 0.28),
			NumberSequenceKeypoint.new(1, 0),
		})
		sparkle.Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.2),
			NumberSequenceKeypoint.new(1, 1),
		})
		sparkle.Parent = main.parts[1]
	end

	local prompt = Instance.new("ProximityPrompt")
	prompt.ActionText = "채굴"
	prompt.ObjectText = "영석 광맥"
	prompt.KeyboardKeyCode = Enum.KeyCode.F
	prompt.HoldDuration = Currency.ORE[tier].hold
	prompt.MaxActivationDistance = 10
	prompt.RequiresLineOfSight = false
	prompt.Parent = anchor

	model.PrimaryPart = base
	model.Parent = folder

	local node: Node = {
		model = model,
		center = centerCFrame.Position,
		tier = tier,
		rocks = rocks,
		shards = shards,
		light = light,
		prompt = prompt,
		farSince = nil,
		taken = false,
	}
	table.insert(nodes, node)
	prompt.Triggered:Connect(function(player)
		mine(player, node)
	end)
	return node
end

forget = function(node: Node)
	local index = table.find(nodes, node)
	if index then
		table.remove(nodes, index)
	end
end

-- 깨지는 연출: 수정 조각이 튀어 흩어지고 바위가 부서져 내린다
local function shatter(node: Node)
	local color = COLORS[node.tier]
	node.prompt.Enabled = false

	-- 광맥이 사라진 뒤에도 남아야 하는 빛가루와 소리는 따로 둔다
	local spot = Instance.new("Attachment")
	spot.Name = "영석 채굴"
	spot.Position = node.center
	spot.Parent = Workspace.Terrain

	local burst = Instance.new("ParticleEmitter")
	burst.Color = ColorSequence.new(color)
	burst.LightEmission = 1
	burst.Rate = 0
	burst.Lifetime = NumberRange.new(0.5, 1)
	burst.Speed = NumberRange.new(5, 10)
	burst.SpreadAngle = Vector2.new(180, 180)
	burst.Acceleration = Vector3.new(0, -18, 0)
	burst.Drag = 2
	burst.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.45),
		NumberSequenceKeypoint.new(1, 0),
	})
	burst.Parent = spot
	burst:Emit(12 + node.tier * 4)

	local sound = Instance.new("Sound")
	sound.SoundId = MINE_SOUND
	sound.Volume = 0.5
	sound.PlaybackSpeed = 1.1 + node.tier * 0.08
	sound.RollOffMaxDistance = 80
	sound.Parent = spot
	sound:Play()
	Debris:AddItem(spot, 2)

	local fly = TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	for _, shard in node.shards do
		local push = shard.out * rng:NextNumber(2, 4) + Vector3.new(0, rng:NextNumber(1.5, 3), 0)
		local spin = CFrame.Angles(rng:NextNumber(-1, 1), rng:NextNumber(-1, 1), rng:NextNumber(-1, 1))
		for _, piece in shard.parts do
			TweenService:Create(piece, fly, { CFrame = CFrame.new(push) * piece.CFrame * spin, Transparency = 1 })
				:Play()
		end
	end
	local crumble = TweenInfo.new(0.7, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
	for _, rock in node.rocks do
		rock.CanCollide = false
		TweenService:Create(rock, crumble, { Size = rock.Size * 0.5, Transparency = 1 }):Play()
	end
	TweenService:Create(node.light, TweenInfo.new(0.6), { Brightness = 0 }):Play()
	Debris:AddItem(node.model, 0.8)
end

mine = function(player: Player, node: Node)
	if node.taken or node.model.Parent == nil then
		return -- 이미 누가 캤다
	end
	local data = PlayerData.get(player)
	local root = playerRoot(player)
	if not data or not root then
		return
	end
	if (root.Position - node.center).Magnitude > MINE_REACH then
		return
	end
	local session = Session.get(player)
	if session and session.tribulation then
		Sync.notify(player, "천겁을 맞는 중에는 광맥을 캘 수 없다.", "bad")
		return
	end
	if data.stones >= Currency.MAX then
		Sync.notify(player, "영석을 더 지닐 수 없다.", "bad")
		return
	end
	node.taken = true
	forget(node)

	local ore = Currency.ORE[node.tier]
	local before = data.stones
	Progression.addStones(data, rng:NextInteger(ore.min, ore.max))
	local gained = data.stones - before
	data.stats.mined = (data.stats.mined or 0) + 1
	Sync.notify(
		player,
		string.format(
			"영석 %s개를 캤다. (지닌 영석 %s)",
			Currency.format(gained),
			Currency.format(data.stones)
		),
		"good"
	)
	Sync.markDirty(player)
	shatter(node)
end

-- 모두에게서 오래 멀리 있던 광맥은 치운다
local function sweep(now: number, roots: { BasePart })
	for i = #nodes, 1, -1 do
		local node = nodes[i]
		if node.model.Parent == nil then
			table.remove(nodes, i)
		else
			local nearest = math.huge
			for _, root in roots do
				nearest = math.min(nearest, flatDistance(root.Position, node.center))
			end
			if nearest > DESPAWN_DISTANCE then
				node.farSince = node.farSince or now
				if now - (node.farSince :: number) > DESPAWN_AFTER then
					table.remove(nodes, i)
					node.model:Destroy()
				end
			else
				node.farSince = nil
			end
		end
	end
end

-- 이 사람 둘레에 광맥이 모자라면 하나 놓는다
local function trySpawn(root: BasePart)
	if #nodes >= MAX_ORES then
		return
	end
	local near = 0
	for _, node in nodes do
		if flatDistance(node.center, root.Position) < NEAR then
			near += 1
		end
	end
	if near >= PER_PLAYER then
		return
	end
	local ground, normal, tier = findSpot(root.Position, SPAWN_MIN, SPAWN_MAX, MAX_RISE, SPACING, false)
	if ground and normal and tier > 0 then
		build(ground, normal, math.min(tier, #Currency.ORE))
	end
end

local function step()
	local roots: { BasePart } = {}
	for _, player in Players:GetPlayers() do
		local root = playerRoot(player)
		if root then
			table.insert(roots, root)
		end
	end
	sweep(os.clock(), roots)
	for _, root in roots do
		trySpawn(root)
	end
end

function Ores.folder(): Folder
	return folder
end

-- 이 자리 가까이에 광맥을 바로 하나 놓는다 (시험용).
-- tier 를 안 주면 그 땅의 위험도를 따른다 (안전한 땅이면 1)
function Ores.spawnNear(position: Vector3, tier: number?): Model?
	if not folder then
		return nil
	end
	local ground, normal, landTier = findSpot(position, 4, 16, nil, 6, true)
	if not ground or not normal then
		return nil
	end
	local chosen = math.clamp(math.floor(tier or landTier), 1, #Currency.ORE)
	return build(ground, normal, chosen).model
end

function Ores.start()
	folder = Instance.new("Folder")
	folder.Name = FOLDER_NAME
	folder.Parent = Workspace
	task.spawn(function()
		while true do
			task.wait(SPAWN_EVERY)
			local ok, err = pcall(step)
			if not ok then
				warn("[블록수선전] 영석 광맥:", err)
			end
		end
	end)
end

return Ores
