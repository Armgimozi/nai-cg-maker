-- 싸움: 무기(도구)로 요수를 베고, 요수에게 물리고, 쓰러뜨리면 요단과 무기를 얻는다.
--
-- 무기는 Roblox 도구다. 지닌 무기(data.weapons)마다 가방에 도구가 들어가 숫자 키 1~9 로 든다.
-- 도구를 쓰면(클릭) 서버가 앞쪽 요수를 찾아 피해를 준다. 맞는 판정과 쿨타임은 서버가 정한다.
-- 피해 숫자를 공중에 띄우지 않는다. 화면 위 대상 창(client/CombatHud.luau)으로 알린다.

local Debris = game:GetService("Debris")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Combat = require(Shared.Combat)
local Mobs = require(Shared.Mobs)
local Progression = require(Shared.Progression)
local Josa = require(Shared.Josa)
local Net = require(Shared.Net)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Cultivation = require(script.Parent.Cultivation)
local MobService = require(script.Parent.MobService)
local Weapons = require(script.Parent.Weapons)

local CombatService = {}

local remotes = Net.get()
local rng = Random.new()
local lastSwing: { [Player]: number } = {}
local MAX_HITS = 4 -- 한 번에 벨 수 있는 요수

local function event(player: Player, payload: { [string]: any })
	remotes.Combat:FireClient(player, payload)
end

-- 요수를 쓰러뜨렸다
local function reward(player: Player, mob: MobService.Live)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local loot = Mobs.LOOT[mob.def.tier] or Mobs.LOOT[1]
	Progression.addItem(data, "yodan", loot.cores)
	data.stats.kills = (data.stats.kills or 0) + 1
	local parts = { string.format("요단 %d", loot.cores) }
	if rng:NextNumber() < loot.weapon then
		local kind = Combat.KIND_ORDER[rng:NextInteger(1, #Combat.KIND_ORDER)]
		local weapon = { kind = kind, grade = mob.def.tier }
		if Progression.addWeapon(data, weapon) then
			table.insert(parts, Combat.weaponName(weapon))
			Weapons.give(player)
		else
			-- 이미 더 좋은 것을 가졌으면 요단으로
			Progression.addItem(data, "yodan", 1)
			parts[1] = string.format("요단 %d", loot.cores + 1)
		end
	end
	Sync.notify(
		player,
		string.format("%s 쓰러뜨렸다. %s", Josa.eul(mob.def.name), table.concat(parts, ", ")),
		"good"
	)
	Sync.markDirty(player)
end

local function hitMob(player: Player, mob: MobService.Live, damage: number)
	if mob.dead then
		return
	end
	MobService.provoke(mob, player)
	MobService.setHp(mob, mob.hp - damage)
	local killed = mob.hp <= 0
	event(player, {
		kind = "hit",
		mob = mob.model,
		name = mob.def.name,
		tier = mob.def.tier,
		hp = mob.hp,
		maxHp = mob.maxHp,
		killed = killed,
	})
	if killed then
		MobService.kill(mob)
		reward(player, mob)
	end
end

-- 날리는 기운 (부채): 눈에 보이는 옥빛 줄기
local function wave(from: Vector3, to: Vector3)
	local part = Instance.new("Part")
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.Material = Enum.Material.Neon
	part.Color = Color3.fromRGB(150, 230, 200)
	part.Transparency = 0.3
	part.Size = Vector3.new(3, 0.3, 2)
	part.CFrame = CFrame.new(from, to)
	part.Parent = Workspace
	TweenService:Create(part, TweenInfo.new(0.25), { CFrame = CFrame.new(to, to + (to - from)), Transparency = 1 })
		:Play()
	Debris:AddItem(part, 0.3)
end

-- 도구를 썼다 (서버에서 Tool.Activated)
function CombatService.swing(player: Player, index: number)
	local data = PlayerData.get(player)
	local weapon = data and data.weapons[index]
	local root = Characters.root(player)
	local humanoid = Characters.humanoid(player)
	if not data or not weapon or not root or not humanoid then
		return
	end
	local kind = Combat.KINDS[weapon.kind]
	local now = os.clock()
	if now - (lastSwing[player] or -math.huge) < kind.cooldown * 0.9 then
		return
	end
	lastSwing[player] = now
	local session = Session.get(player)
	if session and session.meditating then
		Cultivation.setMeditating(player, false)
	end
	local look = root.CFrame.LookVector
	local flat = Vector3.new(look.X, 0, look.Z)
	if flat.Magnitude < 0.1 then
		return
	end
	flat = flat.Unit
	local damage = Combat.damage(data.step, weapon, data.race)
	local hits = {}
	for _, mob in MobService.all() do
		local p = mob.root.Position
		if
			not mob.dead
			and math.abs(p.Y - root.Position.Y) < mob.def.height + 6
			and Combat.inReach(root.Position.X, root.Position.Z, flat.X, flat.Z, p.X, p.Z, mob.def.radius, weapon)
		then
			table.insert(hits, { mob = mob, d = (p - root.Position).Magnitude })
		end
	end
	table.sort(hits, function(a, b)
		return a.d < b.d
	end)
	if kind.ranged then
		local first = hits[1]
		local reach = if first then first.d else kind.range
		wave(root.Position + flat * 2, root.Position + flat * reach)
		if first then
			hitMob(player, first.mob, damage)
		end
		return
	end
	for i = 1, math.min(MAX_HITS, #hits) do
		hitMob(player, hits[i].mob, damage)
	end
end

-- 요수에게 물렸다
local function bitten(mob: MobService.Live, player: Player, damage: number)
	local humanoid = Characters.humanoid(player)
	local session = Session.get(player)
	if not humanoid or not session then
		return
	end
	-- 호신강기
	if os.clock() < session.shieldUntil then
		event(player, { kind = "blocked", name = mob.def.name })
		return
	end
	if session.meditating then
		Cultivation.setMeditating(player, false)
		Sync.notify(player, "요수에게 물려 운기조식이 끊겼다.", "bad")
	end
	humanoid:TakeDamage(damage)
	event(player, { kind = "hurt", amount = damage, name = mob.def.name, mob = mob.model })
end

function CombatService.start()
	MobService.onBite = bitten
	Weapons.onSwing = CombatService.swing
end

function CombatService.forget(player: Player)
	lastSwing[player] = nil
end

return CombatService
