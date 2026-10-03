-- 요수 띄우기와 움직임. 플레이어 둘레에 땅의 위험도(Places.tierAt)에 맞는 요수가 나오고,
-- 가까이 오면 쫓아와 문다. 마을처럼 위험도 0 인 곳에는 들어오지 않고, 그리로 달아난 사람은 놓아준다.
-- 플레이어가 멀어지면 사라진다. 피해 주고받기는 CombatService 가 맡는다.

local CollectionService = game:GetService("CollectionService")
local InsertService = game:GetService("InsertService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Mobs = require(Shared.Mobs)
local Places = require(Shared.Places)
local Session = require(script.Parent.Session)
local Tribulation = require(script.Parent.Tribulation)

local MobService = {}

local PER_PLAYER = 4 -- 한 사람 둘레(160)에 많아야
local MAX_MOBS = 40
local SPAWN_MIN, SPAWN_MAX = 60, 140
local DESPAWN_DISTANCE = 280
local DESPAWN_AFTER = 20 -- 멀리 있은 지 이만큼 지나면 사라진다
local LEASH = 110 -- 태어난 자리에서 이만큼 멀어지면 돌아간다
local TICK = 0.2
local SPAWN_EVERY = 2

export type Live = {
	def: Mobs.Mob,
	model: Model,
	root: BasePart,
	humanoid: Humanoid,
	hp: number,
	maxHp: number,
	home: Vector3,
	target: Player?,
	attacking: boolean,
	nextAttack: number,
	nextWander: number,
	farSince: number?,
	dead: boolean,
	lastHitBy: Player?,
}

local live: { Live } = {}
local folder: Folder
local rng = Random.new()
local templates: { [string]: Model | false } = {}

-- 플레이어가 맞았을 때 (CombatService 가 채운다)
MobService.onBite = nil :: ((mob: Live, player: Player, damage: number) -> ())?

local function groundParams(): RaycastParams
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	local targets: { Instance } = CollectionService:GetTagged("Ground")
	table.insert(targets, Workspace.Terrain)
	params.FilterDescendantsInstances = targets
	return params
end

local function groundAt(x: number, z: number, fromY: number?): Vector3?
	local hit = Workspace:Raycast(Vector3.new(x, (fromY or 500) + 0, z), Vector3.new(0, -900, 0), groundParams())
	if hit and hit.Material ~= Enum.Material.Water then
		return hit.Position
	end
	return nil
end

local function playerRoot(player: Player): BasePart?
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if humanoid and humanoid.Health > 0 and root and root:IsA("BasePart") then
		return root
	end
	return nil
end

local function safeAt(position: Vector3): boolean
	return Places.tierAt(position.X, position.Z, position.Y) <= 0
end

-- Meshy 모델: 처음 한 번 불러와 둔다. 못 불러오면 블록 모양으로
local function template(def: Mobs.Mob): Model?
	if not def.asset or def.asset == 0 then
		return nil
	end
	local cached = templates[def.id]
	if cached ~= nil then
		return cached or nil
	end
	local ok, result = pcall(function()
		return InsertService:LoadAsset(def.asset :: number)
	end)
	local modelFound: Model? = nil
	if ok and result then
		for _, child in result:GetChildren() do
			if child:IsA("Model") then
				modelFound = child
				break
			end
		end
		if not modelFound then
			-- 메시 하나만 들어 있으면 모델로 감싼다
			local wrap = Instance.new("Model")
			for _, child in result:GetChildren() do
				if child:IsA("BasePart") then
					child.Parent = wrap
				end
			end
			if #wrap:GetChildren() > 0 then
				modelFound = wrap
			end
		end
	else
		warn("[블록수선전] 요수 모델을 못 불러왔다:", def.name, result)
	end
	templates[def.id] = modelFound or false
	return modelFound
end

local function weld(part: BasePart, root: BasePart)
	part.Anchored = false
	part.CanCollide = false
	part.CanQuery = false
	part.Massless = true
	local w = Instance.new("WeldConstraint")
	w.Part0 = root
	w.Part1 = part
	w.Parent = part
end

local function build(def: Mobs.Mob, at: CFrame): Live
	local model = Instance.new("Model")
	model.Name = def.name
	local rootSize = Vector3.new(def.radius * 1.4, 2, def.radius * 1.8)
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Size = rootSize
	root.Transparency = 1
	root.CanCollide = true
	root.CFrame = at
	root.Parent = model
	model.PrimaryPart = root

	local mesh = template(def)
	if mesh then
		local copy = mesh:Clone()
		local _, size = copy:GetBoundingBox()
		local longest = math.max(size.X, size.Y, size.Z)
		if longest > 0 then
			copy:ScaleTo(copy:GetScale() * (def.assetSize or def.radius * 2.6) / longest)
		end
		copy:PivotTo(at)
		for _, part in copy:GetDescendants() do
			if part:IsA("BasePart") then
				weld(part, root)
			end
		end
		copy.Parent = model
	else
		for _, spec in def.parts do
			local part = Instance.new("Part")
			part.Name = spec.name
			part.Size = Vector3.new(spec.size[1], spec.size[2], spec.size[3])
			part.CFrame = at * CFrame.new(spec.at[1], spec.at[2], spec.at[3])
			part.Color = Color3.fromRGB(spec.color[1], spec.color[2], spec.color[3])
			part.Material = if spec.neon
				then Enum.Material.Neon
				elseif spec.material then (Enum.Material :: any)[spec.material]
				else Enum.Material.SmoothPlastic
			if spec.shape then
				part.Shape = (Enum.PartType :: any)[spec.shape]
			end
			part.TopSurface = Enum.SurfaceType.Smooth
			part.BottomSurface = Enum.SurfaceType.Smooth
			part.CastShadow = false
			weld(part, root)
			part.Parent = model
		end
	end

	local humanoid = Instance.new("Humanoid")
	-- 다리 파트 없이 HipHeight 로 뜨게 하려면 R15 로 둔다
	humanoid.RigType = Enum.HumanoidRigType.R15
	humanoid.HipHeight = def.height - rootSize.Y / 2
	humanoid.WalkSpeed = def.speed * 0.5
	humanoid.MaxHealth = 1e6
	humanoid.Health = 1e6
	humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	humanoid.BreakJointsOnDeath = false
	humanoid.RequiresNeck = false
	humanoid.Parent = model

	model:SetAttribute("MobId", def.id)
	model:SetAttribute("MobName", def.name)
	model:SetAttribute("Tier", def.tier)
	model:SetAttribute("Hp", def.hp)
	model:SetAttribute("MaxHp", def.hp)
	model:AddTag("Mob")
	model.Parent = folder
	pcall(function()
		root:SetNetworkOwner(nil)
	end)
	return {
		def = def,
		model = model,
		root = root,
		humanoid = humanoid,
		hp = def.hp,
		maxHp = def.hp,
		home = at.Position,
		target = nil,
		attacking = false,
		nextAttack = 0,
		nextWander = 0,
		farSince = nil,
		dead = false,
		lastHitBy = nil,
	}
end

function MobService.all(): { Live }
	return live
end

function MobService.byModel(model: Instance): Live?
	for _, mob in live do
		if mob.model == model then
			return mob
		end
	end
	return nil
end

local function remove(mob: Live)
	mob.dead = true
	local index = table.find(live, mob)
	if index then
		table.remove(live, index)
	end
end

-- 쓰러뜨렸다: 몸이 잦아들며 사라진다
function MobService.kill(mob: Live)
	if mob.dead then
		return
	end
	remove(mob)
	mob.humanoid:MoveTo(mob.root.Position)
	mob.model:SetAttribute("Hp", 0)
	for _, part in mob.model:GetDescendants() do
		if part:IsA("BasePart") then
			part.CanCollide = false
		end
	end
	task.delay(1, function()
		mob.model:Destroy()
	end)
end

function MobService.setHp(mob: Live, hp: number)
	mob.hp = math.max(0, hp)
	mob.model:SetAttribute("Hp", math.floor(mob.hp + 0.5))
end

-- 맞으면 때린 사람을 쫓는다
function MobService.provoke(mob: Live, player: Player)
	mob.lastHitBy = player
	if not mob.target then
		mob.target = player
	end
end

local function validTarget(mob: Live, player: Player?): BasePart?
	if not player or not player.Parent then
		return nil
	end
	local root = playerRoot(player)
	if not root then
		return nil
	end
	local session = Session.get(player)
	if (session and session.tribulation) or Tribulation.isActive(player) then
		return nil -- 천겁을 맞는 사람은 건드리지 않는다
	end
	if safeAt(root.Position) then
		return nil
	end
	if (root.Position - mob.root.Position).Magnitude > mob.def.aggro * 1.8 then
		return nil
	end
	return root
end

local function nearestTarget(mob: Live): Player?
	local best, bestDistance = nil, mob.def.aggro
	for _, player in Players:GetPlayers() do
		local root = playerRoot(player)
		if root and not safeAt(root.Position) then
			local d = (root.Position - mob.root.Position).Magnitude
			if d < bestDistance then
				best, bestDistance = player, d
			end
		end
	end
	return best
end

-- 덤비기: 앞쪽 땅에 붉은 원이 보이고, 뜸이 지나면 그 안의 사람을 문다
local function attack(mob: Live, targetRoot: BasePart)
	mob.attacking = true
	local def = mob.def
	mob.humanoid:MoveTo(mob.root.Position)
	local flat =
		Vector3.new(targetRoot.Position.X - mob.root.Position.X, 0, targetRoot.Position.Z - mob.root.Position.Z)
	local look = if flat.Magnitude > 0.1 then flat.Unit else mob.root.CFrame.LookVector
	mob.root.CFrame = CFrame.new(mob.root.Position, mob.root.Position + look)
	local center = mob.root.Position + look * def.reach * 0.55
	local radius = def.reach * 0.6
	local ground = Tribulation.groundAt(center)
	Tribulation.mark(ground, radius, def.windup, Color3.fromRGB(255, 80, 60))
	task.delay(def.windup, function()
		if mob.dead then
			return
		end
		-- 앞으로 덤빈다
		mob.humanoid.WalkSpeed = def.speed * 2
		mob.humanoid:MoveTo(center + look * 2)
		for _, player in Players:GetPlayers() do
			local root = playerRoot(player)
			if root and not safeAt(root.Position) then
				local d = Vector3.new(root.Position.X - center.X, 0, root.Position.Z - center.Z).Magnitude
				if d <= radius + 1.2 and math.abs(root.Position.Y - ground.Y) < 8 and MobService.onBite then
					MobService.onBite(mob, player, def.damage)
				end
			end
		end
		task.delay(0.3, function()
			mob.attacking = false
			mob.humanoid.WalkSpeed = def.speed
		end)
	end)
	mob.nextAttack = os.clock() + def.windup + def.cooldown
end

local function think(mob: Live, now: number)
	local def = mob.def
	local position = mob.root.Position
	if position.Y < -200 then
		MobService.kill(mob) -- 떨어졌다
		return
	end
	if mob.attacking then
		return
	end
	-- 너무 멀리 왔거나 안전한 곳 가까이면 돌아간다
	local fromHome = Vector3.new(position.X - mob.home.X, 0, position.Z - mob.home.Z).Magnitude
	if fromHome > LEASH or safeAt(position) then
		mob.target = nil
		mob.humanoid.WalkSpeed = def.speed
		mob.humanoid:MoveTo(mob.home)
		MobService.setHp(mob, math.min(mob.maxHp, mob.hp + mob.maxHp * 0.05))
		return
	end
	local targetRoot = validTarget(mob, mob.target)
	if not targetRoot then
		mob.target = nearestTarget(mob)
		targetRoot = validTarget(mob, mob.target)
	end
	if targetRoot then
		mob.humanoid.WalkSpeed = def.speed
		local d = Vector3.new(targetRoot.Position.X - position.X, 0, targetRoot.Position.Z - position.Z).Magnitude
		if d <= def.reach + def.radius * 0.5 and now >= mob.nextAttack then
			attack(mob, targetRoot)
		elseif d > def.reach * 0.7 then
			-- 사람 바로 앞까지만 (마을 안으로는 들어가지 않는다)
			local step = targetRoot.Position
			if safeAt(step) then
				mob.target = nil
			else
				mob.humanoid:MoveTo(step)
			end
		end
		return
	end
	-- 아무도 없으면 둘레를 어슬렁거린다
	if now >= mob.nextWander then
		mob.nextWander = now + rng:NextNumber(4, 9)
		local angle = rng:NextNumber(0, math.pi * 2)
		local distance = rng:NextNumber(6, 24)
		local goal = mob.home + Vector3.new(math.cos(angle) * distance, 0, math.sin(angle) * distance)
		if not safeAt(goal) then
			mob.humanoid.WalkSpeed = def.speed * 0.4
			mob.humanoid:MoveTo(goal)
		end
	end
end

-- 플레이어 둘레에 요수를 띄운다
local function trySpawn(player: Player)
	local root = playerRoot(player)
	if not root or #live >= MAX_MOBS then
		return
	end
	local near = 0
	for _, mob in live do
		if (mob.root.Position - root.Position).Magnitude < 160 then
			near += 1
		end
	end
	if near >= PER_PLAYER then
		return
	end
	for _ = 1, 4 do
		local angle = rng:NextNumber(0, math.pi * 2)
		local distance = rng:NextNumber(SPAWN_MIN, SPAWN_MAX)
		local x = root.Position.X + math.cos(angle) * distance
		local z = root.Position.Z + math.sin(angle) * distance
		-- 떠 있는 섬에 선 사람이면 섬 위에, 아니면 땅에
		local ground = groundAt(x, z, root.Position.Y + 80)
		if ground and math.abs(ground.Y - root.Position.Y) < 80 then
			local region = Places.regionAt(ground.X, ground.Z, ground.Y)
			if region.tier > 0 then
				local def = Mobs.pick(region.id, region.tier, rng:NextNumber())
				if def then
					local mob = build(def, CFrame.new(ground + Vector3.new(0, def.height + 0.5, 0)))
					table.insert(live, mob)
					return
				end
			end
		end
	end
end

local function sweep(now: number)
	for i = #live, 1, -1 do
		local mob = live[i]
		local nearest = math.huge
		for _, player in Players:GetPlayers() do
			local root = playerRoot(player)
			if root then
				nearest = math.min(nearest, (root.Position - mob.root.Position).Magnitude)
			end
		end
		if nearest > DESPAWN_DISTANCE then
			mob.farSince = mob.farSince or now
			if now - mob.farSince > DESPAWN_AFTER then
				remove(mob)
				mob.model:Destroy()
			end
		else
			mob.farSince = nil
		end
	end
end

function MobService.start()
	folder = Instance.new("Folder")
	folder.Name = "요수"
	folder.Parent = Workspace
	local thinkElapsed, spawnElapsed = 0, 0
	RunService.Heartbeat:Connect(function(dt)
		thinkElapsed += dt
		spawnElapsed += dt
		local now = os.clock()
		if thinkElapsed >= TICK then
			thinkElapsed = 0
			for _, mob in table.clone(live) do
				if not mob.dead and mob.model.Parent then
					think(mob, now)
				elseif not mob.dead then
					remove(mob)
				end
			end
		end
		if spawnElapsed >= SPAWN_EVERY then
			spawnElapsed = 0
			sweep(now)
			for _, player in Players:GetPlayers() do
				trySpawn(player)
			end
		end
	end)
end

return MobService
