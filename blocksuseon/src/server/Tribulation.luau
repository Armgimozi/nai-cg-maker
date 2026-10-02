-- 천겁: 대경지(결단기 이상)로 돌파할 때 내리는 낙뢰.
--
-- 매 뇌격마다 붉은 원으로 낙뢰 자리를 예고하고, 잠시 뒤 그 자리에 벼락이 떨어진다.
-- 첫 줄기는 언제나 발밑을 노리므로 움직여서 피해야 한다. 끝까지 버티면 돌파,
-- 쓰러지거나 도중에 나가면 실패(경지는 그대로, 영력 일부 손실)다.
-- 피해는 천겁을 맞는 본인에게만 들어간다.

local Players = game:GetService("Players")
local Debris = game:GetService("Debris")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Progression = require(Shared.Progression)
local Format = require(Shared.Format)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)

local GATHER_TIME = 3 -- 겁운이 모이는 시간
local CLOUD_HEIGHT = 60
local BOLT_HEIGHT = 140
local WARNING_COLOR = Color3.fromRGB(255, 70, 60)
local FLAT_DISC = CFrame.Angles(0, 0, math.rad(90))

local Tribulation = {}

local rng = Random.new()

local fxFolder = Instance.new("Folder")
fxFolder.Name = "천겁효과"
fxFolder.Parent = Workspace

local function fxPart(size: Vector3, cframe: CFrame, color: Color3): Part
	local part = Instance.new("Part")
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.CastShadow = false
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = Enum.Material.Neon
	part.Parent = fxFolder
	return part
end

local function groundAt(position: Vector3): Vector3
	local ignore: { Instance } = { fxFolder }
	for _, other in Players:GetPlayers() do
		if other.Character then
			table.insert(ignore, other.Character)
		end
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore
	local hit = Workspace:Raycast(position + Vector3.new(0, 6, 0), Vector3.new(0, -60, 0), params)
	if hit then
		return hit.Position
	end
	return position - Vector3.new(0, 3, 0)
end

local function mark(ground: Vector3, radius: number, duration: number)
	local marker = fxPart(
		Vector3.new(0.2, radius * 2, radius * 2),
		CFrame.new(ground + Vector3.new(0, 0.15, 0)) * FLAT_DISC,
		WARNING_COLOR
	)
	marker.Shape = Enum.PartType.Cylinder
	marker.Transparency = 0.8
	TweenService:Create(marker, TweenInfo.new(duration, Enum.EasingStyle.Linear), { Transparency = 0.25 }):Play()
	Debris:AddItem(marker, duration + 0.1)
end

local function strike(ground: Vector3, radius: number, color: Color3)
	-- 지그재그 벼락 줄기
	local top = ground + Vector3.new(rng:NextNumber(-8, 8), BOLT_HEIGHT, rng:NextNumber(-8, 8))
	local points = { top }
	local segments = 7
	for i = 1, segments - 1 do
		local jitter = Vector3.new(rng:NextNumber(-3, 3), 0, rng:NextNumber(-3, 3))
		table.insert(points, top:Lerp(ground, i / segments) + jitter)
	end
	table.insert(points, ground)
	for i = 1, #points - 1 do
		local a, b = points[i], points[i + 1]
		local segment = fxPart(Vector3.new(0.9, 0.9, (b - a).Magnitude), CFrame.lookAt((a + b) / 2, b), color)
		Debris:AddItem(segment, 0.25)
	end

	local flash = fxPart(Vector3.one * radius * 2, CFrame.new(ground), color)
	flash.Shape = Enum.PartType.Ball
	flash.Transparency = 0.3
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 40
	light.Brightness = 6
	light.Parent = flash
	TweenService:Create(flash, TweenInfo.new(0.4), { Transparency = 1, Size = flash.Size * 1.3 }):Play()
	Debris:AddItem(flash, 0.45)
end

local function cloudCFrame(position: Vector3): CFrame
	return CFrame.new(position + Vector3.new(0, CLOUD_HEIGHT, 0)) * FLAT_DISC
end

-- 이 천겁이 아직 유효하고 플레이어가 살아 있으면 Humanoid 를 돌려준다.
local function stillGoing(player: Player, session, state): Humanoid?
	if Session.get(player) ~= session or session.tribulation ~= state then
		return nil
	end
	return Characters.humanoid(player)
end

local function succeed(player: Player, session, state, color: Color3)
	session.tribulation = nil
	local data = PlayerData.get(player)
	if not data or data.step + 1 ~= state.targetStep then
		return
	end
	local points = Progression.passTribulation(data)
	Characters.applyStats(player, true)
	Fx.burst(player.Character, color, 80)
	Sync.notify(player, string.format("천겁을 넘었다  ·  깨달음 +%d", points), "good")
	Sync.broadcast(
		string.format("%s님이 천겁을 넘어 %s에 올랐다", player.DisplayName, Realms.label(data.step)),
		"world"
	)
	Sync.cinematic(player, {
		kind = "ascend",
		step = data.step,
		realm = Realms.label(data.step),
		blurb = Realms.get(data.step).realm.blurb,
	})
	Sync.markDirty(player)
end

local function run(player: Player, session, state, trib)
	local color = Color3.fromRGB(trib.color[1], trib.color[2], trib.color[3])
	local root = Characters.root(player)
	if not root then
		Tribulation.fail(player)
		return
	end

	local cloud = fxPart(Vector3.new(6, 80, 80), cloudCFrame(root.Position), Color3.fromRGB(38, 38, 50))
	cloud.Shape = Enum.PartType.Cylinder
	cloud.Material = Enum.Material.SmoothPlastic
	cloud.Transparency = 0.15

	task.wait(GATHER_TIME)

	local data = PlayerData.get(player)
	local telegraph = Balance.telegraphTime(trib.telegraph, if data then Progression.insight(data, "geobun") else 0)
	local passed = true

	for wave = 1, trib.waves do
		local humanoid = stillGoing(player, session, state)
		root = Characters.root(player)
		if not humanoid or not root then
			passed = false
			break
		end
		state.wave = wave
		Sync.markDirty(player)
		TweenService:Create(cloud, TweenInfo.new(0.5), { CFrame = cloudCFrame(root.Position) }):Play()

		local targets = {}
		for i = 1, trib.simul do
			local offset = Vector3.zero
			if i > 1 then
				local angle = rng:NextNumber(0, math.pi * 2)
				local distance = rng:NextNumber(trib.radius * 0.8, math.max(trib.spread, trib.radius))
				offset = Vector3.new(math.cos(angle) * distance, 0, math.sin(angle) * distance)
			end
			local ground = groundAt(root.Position + offset)
			table.insert(targets, ground)
			mark(ground, trib.radius, telegraph)
		end

		task.wait(telegraph)

		humanoid = stillGoing(player, session, state)
		if not humanoid then
			passed = false
			break
		end
		root = Characters.root(player)
		local hits = 0
		for _, ground in targets do
			strike(ground, trib.radius, color)
			if root then
				local offset = root.Position - ground
				local flat = Vector3.new(offset.X, 0, offset.Z).Magnitude
				if flat <= trib.radius and offset.Y > -4 and offset.Y < 14 then
					hits += 1
				end
			end
		end
		if hits > 0 then
			humanoid:TakeDamage(trib.damage * hits)
		end

		task.wait(trib.interval)
	end

	cloud:Destroy()

	-- 죽음·퇴장으로 이미 실패 처리됐으면 할 일이 없다
	if Session.get(player) ~= session or session.tribulation ~= state then
		return
	end
	if passed and Characters.humanoid(player) then
		succeed(player, session, state, color)
	else
		Tribulation.fail(player)
	end
end

function Tribulation.start(player: Player)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session or session.tribulation or data.step >= Realms.maxStep then
		return
	end
	local target = Realms.get(data.step + 1)
	local trib = target.realm.tribulation
	if not trib then
		return
	end

	local state = { name = trib.name, wave = 0, waves = trib.waves, targetStep = target.index }
	session.tribulation = state
	Sync.notify(player, "붉은 원을 피해 끝까지 버텨라", "tribulation")
	Sync.broadcast(string.format("%s님 머리 위로 겁운이 모여든다", player.DisplayName), "tribulation")
	Sync.markDirty(player)
	task.spawn(run, player, session, state, trib)
end

-- 천겁 도중 쓰러지거나 나가면 실패. 경지는 그대로, 영력 일부를 잃는다.
function Tribulation.fail(player: Player)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	local state = session and session.tribulation
	if not data or not session or not state then
		return
	end
	session.tribulation = nil
	local lost = Progression.failTribulation(data)
	Sync.notify(player, string.format("천겁 실패  ·  경지는 지켰다  ·  영력 -%s", Format.qi(lost)), "bad")
	Sync.broadcast(string.format("%s님이 천겁을 넘지 못했다", player.DisplayName), "tribulation")
	Sync.markDirty(player)
end

function Tribulation.isActive(player: Player): boolean
	local session = Session.get(player)
	return session ~= nil and session.tribulation ~= nil
end

return Tribulation
