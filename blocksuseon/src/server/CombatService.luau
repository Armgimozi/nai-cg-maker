-- 싸움: 무기(도구)로 요수를 베고, 요수에게 물리고, 쓰러뜨리면 요단과 무기를 얻는다.
--
-- 무기는 Roblox 도구다. 지닌 무기(data.weapons)마다 가방에 도구가 들어가 숫자 키 1~9 로 든다.
-- 도구를 쓰면(클릭) 서버가 앞쪽 요수를 찾아 피해를 준다. 맞는 판정과 쿨타임은 서버가 정한다.
-- 피해 숫자를 공중에 띄우지 않는다. 화면 위 대상 창(client/CombatHud.luau)으로 알린다.
--
-- 칼질은 모든 클라이언트에 알린다 (remotes.Combat:FireAllClients). 몸짓과 효과는 클라이언트가 그린다
-- (client/WeaponAnim.luau, client/WeaponEffects.luau).
--   { kind = "swing", player, weapon = 종류 id, grade, combo }   받아들인 칼질마다 (쿨타임을 넘긴 뒤)
--   { kind = "impact", player, position, weapon, grade }         맞은 요수마다 (부채는 바람칼이 닿을 때)
--   { kind = "wave", player, from, to, grade, hit }              부채 바람칼
-- 휘두른 사람과 맞은 사람에게만 가는 "hit"·"hurt"·"blocked" 는 그대로다.

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
local CHEST = 0.7 -- 뿌리(HumanoidRootPart)에서 가슴까지 높이
local WAVE_SPEED = 150 -- 바람칼 빠르기(스터드/초). client/WeaponEffects.luau 의 WAVE_SPEED 와 같은 값
local WAVE_TIME_MIN, WAVE_TIME_MAX = 0.1, 0.28
local COMBO_RESET = 1.2 -- 이만큼 쉬면 연속 공격이 첫 수로 돌아간다
local COMBO_LENGTH = { sword = 3, saber = 2, spear = 2, fan = 1 } -- 종류마다 연속 공격 수

type Combo = { kind: string, count: number, at: number }
local combos: { [Player]: Combo } = {}

local function event(player: Player, payload: { [string]: any })
	remotes.Combat:FireClient(player, payload)
end

-- 모두에게 (칼질 몸짓과 효과)
local function broadcast(payload: { [string]: any })
	remotes.Combat:FireAllClients(payload)
end

-- 몇 번째 연속 공격인가 (종류를 바꾸거나 쉬면 처음부터)
local function nextCombo(player: Player, kind: string, now: number): number
	local state = combos[player]
	if not state or state.kind ~= kind or now - state.at > COMBO_RESET then
		state = { kind = kind, count = 0, at = now }
		combos[player] = state
	end
	state.count = state.count % (COMBO_LENGTH[kind] or 1) + 1
	state.at = now
	return state.count
end

-- 맞은 자리: 요수 몸 겉에서 나를 향한 쪽, 내 가슴 높이 (요수 몸 높이 안으로)
local function hitPoint(from: Vector3, mob: MobService.Live): Vector3
	local p = mob.root.Position
	local flat = Vector3.new(from.X - p.X, 0, from.Z - p.Z)
	local y = math.clamp(from.Y + CHEST, p.Y - mob.def.height * 0.5, p.Y + mob.def.height * 0.5)
	local toward = if flat.Magnitude > 0.1
		then flat.Unit * math.min(mob.def.radius * 0.8, flat.Magnitude * 0.7)
		else Vector3.zero
	return Vector3.new(p.X, y, p.Z) + toward
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
	broadcast({
		kind = "swing",
		player = player,
		weapon = weapon.kind,
		grade = weapon.grade,
		combo = nextCombo(player, weapon.kind, now),
	})
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
		-- 바람칼: 앞줄에서 처음 닿는 요수까지, 없으면 끝까지 날아간다
		local first = hits[1]
		local chest = root.Position + Vector3.new(0, CHEST, 0)
		local to = if first then hitPoint(root.Position, first.mob) else chest + flat * kind.range
		-- 부채 끝쯤에서 떠난다 (바로 붙은 요수면 가슴에서)
		local from = chest + flat * math.clamp((to - chest):Dot(flat) - 1, 0, 2)
		broadcast({ kind = "wave", player = player, from = from, to = to, grade = weapon.grade, hit = first ~= nil })
		if first then
			-- 피해는 바로 주고, 맞은 자리 효과는 바람칼이 닿을 때 보인다
			local travel = math.clamp((to - from).Magnitude / WAVE_SPEED, WAVE_TIME_MIN, WAVE_TIME_MAX)
			task.delay(travel, broadcast, {
				kind = "impact",
				player = player,
				position = to,
				weapon = weapon.kind,
				grade = weapon.grade,
			})
			hitMob(player, first.mob, damage)
		end
		return
	end
	for i = 1, math.min(MAX_HITS, #hits) do
		local mob = hits[i].mob
		broadcast({
			kind = "impact",
			player = player,
			position = hitPoint(root.Position, mob),
			weapon = weapon.kind,
			grade = weapon.grade,
		})
		hitMob(player, mob, damage)
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
	combos[player] = nil
end

return CombatService
