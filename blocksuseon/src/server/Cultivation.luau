-- 운기조식(영력 흡수), 영맥·취령진 판정, 돌파.

local CollectionService = game:GetService("CollectionService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Progression = require(Shared.Progression)
local Tasks = require(Shared.Tasks)
local Roots = require(Shared.Roots)
local Format = require(Shared.Format)
local Josa = require(Shared.Josa)
local Skills = require(Shared.Skills)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)
local Tribulation = require(script.Parent.Tribulation)
local TaskService = require(script.Parent.TaskService)

local MOVE_TOLERANCE = 3 -- 운기조식 중 이만큼 움직이면 풀린다
local STEP_COLOR = Color3.fromRGB(150, 235, 255)
local MAJOR_COLOR = Color3.fromRGB(255, 230, 150)

local Cultivation = {}

local function flatDistance(a: Vector3, b: Vector3): number
	return Vector3.new(a.X - b.X, 0, a.Z - b.Z).Magnitude
end

-- 서 있는 자리의 영맥. 반환: 쓸 수 있는 영맥 id, 배율, 경지가 모자라 못 쓰는 영맥 id
local function veinAt(position: Vector3?, step: number): (string?, number, string?)
	if not position then
		return nil, 1, nil
	end
	local bestId, bestMult, blockedId = nil, 1, nil
	for _, pool in CollectionService:GetTagged("Vein") do
		local id = pool:GetAttribute("VeinId")
		local radius = pool:GetAttribute("Radius")
		local def = Balance.VEINS[id]
		if def and type(radius) == "number" and pool:IsA("BasePart") then
			local dy = position.Y - pool.Position.Y
			if flatDistance(position, pool.Position) <= radius and dy > -4 and dy < 10 then
				if step >= Realms.firstStepById[def.minRealm] then
					if def.mult > bestMult then
						bestId, bestMult = id, def.mult
					end
				else
					blockedId = id
				end
			end
		end
	end
	return bestId, bestMult, if bestId then nil else blockedId
end

-- 더 쌓이지 않는 상태 (영력이 찼는데 과업이 남았거나 돌파가 필요하다)
local function isFull(data): boolean
	return Progression.isCapped(data) and Progression.isFull(data)
end

-- 돌파(B)를 누를 수 있는 상태
local function isReady(data): boolean
	return (Progression.canBreakthrough(data))
end

function Cultivation.setMeditating(player: Player, on: boolean)
	local session = Session.get(player)
	if not session or session.meditating == on then
		return
	end
	local humanoid = Characters.humanoid(player)
	if on then
		local root = Characters.root(player)
		if session.tribulation then
			Sync.notify(player, "천겁을 맞는 중에는 운기조식을 할 수 없다.", "bad")
			return
		end
		if not humanoid or not root then
			return
		end
		session.meditating = true
		session.anchor = root.Position
		humanoid.Sit = true
		Fx.setAura(player.Character, true)
	else
		session.meditating = false
		session.anchor = nil
		if humanoid and humanoid.Sit and not humanoid.SeatPart then
			humanoid.Sit = false
		end
		Fx.setAura(player.Character, false)
	end
	Sync.markDirty(player)
end

-- 단계가 오르거나 영력이 차거나 돌파할 수 있게 되면 알린다
local function announce(player: Player, data, advanced: number, notes: { string }, wasFull: boolean, wasReady: boolean)
	if advanced > 0 then
		Sync.notify(player, string.format("%s에 올랐다.", Realms.label(data.step)), "good")
		Fx.burst(player.Character, STEP_COLOR, 25)
		if Tasks.hasTasks(data.step) then
			Sync.notify(player, "새 과업이 생겼다. 왼쪽 과업 목록을 본다.", "info")
		end
	end
	for _, note in notes do
		Sync.notify(player, note, "good")
	end
	if data.step >= Realms.maxStep and isFull(data) and not wasFull then
		Sync.notify(player, "천인 대원만, 하계에서 오를 수 있는 끝에 닿았다.", "good")
		return
	end
	if isReady(data) and not wasReady then
		local entry = Progression.nextEntry(data)
		if entry and entry.kind == "tribulation" then
			local trib = Realms.tribulationAfter(data.step)
			Sync.notify(
				player,
				string.format(
					"모든 준비가 끝났다. B 를 누르면 %s 내린다.",
					Josa.i(if trib then trib.name else "천겁")
				),
				"good"
			)
		elseif entry and entry.kind == "trial" then
			Sync.notify(
				player,
				string.format(
					"모든 준비가 끝났다. B 를 눌러 %s 시작한다.",
					Josa.eul(entry.title or "돌파")
				),
				"good"
			)
		else
			local target = Realms.get(data.step + 1).realm
			Sync.notify(
				player,
				string.format("모든 준비가 끝났다. B 를 눌러 %s 돌파한다.", Josa.ro(target.name)),
				"good"
			)
		end
	elseif isFull(data) and not wasFull and not isReady(data) then
		Sync.notify(player, "영력이 가득 찼다. 남은 과업을 마치면 오른다.", "info")
	end
end

-- 영력을 주고 알린다.
function Cultivation.grantQi(player: Player, amount: number)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local wasFull, wasReady = isFull(data), isReady(data)
	local advanced, notes = Progression.addQi(data, amount)
	announce(player, data, advanced, notes, wasFull, wasReady)
	Sync.markDirty(player)
end

-- 과업이 끝났을 때 등: 영력이 이미 찼으면 단계를 올린다
function Cultivation.settle(player: Player)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local wasReady = isReady(data)
	local advanced, notes = Progression.tryAdvance(data)
	announce(player, data, advanced, notes, false, wasReady)
	Sync.markDirty(player)
end

function Cultivation.isFull(player: Player): boolean
	local data = PlayerData.get(player)
	return data ~= nil and isFull(data)
end

function Cultivation.tick(dt: number)
	for player, session in Session.all() do
		local data = PlayerData.get(player)
		if not data then
			continue
		end
		local root = Characters.root(player)
		local veinId, mult, blockedId = veinAt(root and root.Position, data.step)
		if veinId ~= session.veinId or blockedId ~= session.veinBlocked then
			session.veinId, session.veinBlocked = veinId, blockedId
			session.dirty = true
		end
		session.veinMult = mult

		-- 취령진: 진 안에 있으면 흡수 배율이 붙는다
		local formation = session.formation
		local inFormation = false
		if formation then
			if os.clock() > formation.untilTime then
				session.formation = nil
			elseif root then
				local dy = root.Position.Y - formation.position.Y
				inFormation = flatDistance(root.Position, formation.position) <= Skills.EFFECT.formationRadius
					and math.abs(dy) < 8
			end
		end
		if inFormation ~= session.inFormation then
			session.inFormation = inFormation
			session.dirty = true
		end

		if session.meditating then
			local anchor = session.anchor
			if
				not root
				or not anchor
				or not Characters.humanoid(player)
				or flatDistance(root.Position, anchor) > MOVE_TOLERANCE
			then
				Cultivation.setMeditating(player, false)
			else
				TaskService.meditateTick(player, data, session, root.Position, dt)
				if not isFull(data) then
					Cultivation.grantQi(
						player,
						Progression.qiPerSecond(data, mult, Cultivation.extraMult(session)) * dt
					)
				end
			end
		end
	end
end

local function ascended(player: Player, data, slotsBefore: number, notes: { string })
	Characters.applyStats(player, true)
	Fx.burst(player.Character, MAJOR_COLOR, 60)
	Sync.announceSlots(player, slotsBefore)
	for _, note in notes do
		Sync.notify(player, note, "good")
	end
	Sync.broadcast(string.format("%s님이 %s에 올랐다.", player.DisplayName, Realms.label(data.step)), "world")
	Sync.cinematic(player, {
		kind = "ascend",
		step = data.step,
		realm = Realms.label(data.step),
		blurb = Realms.get(data.step).realm.blurb,
	})
	if Tasks.hasTasks(data.step) then
		Sync.notify(player, "새 과업이 생겼다. 왼쪽 과업 목록을 본다.", "info")
	end
end

-- 무극영운처럼 B 로 시작하는 돌파 내관
local function startEntryTrial(player: Player, data, mode: string, title: string)
	if mode == "strands" then
		local count = Roots.strands(data.root)
		local pill = Progression.takeItems(data, { pill = 1 })
		if pill then
			Sync.notify(player, "축기단을 삼켰다. 변화의 가닥이 한결 느려진다.", "good")
		elseif count > 1 then
			Sync.notify(player, "축기단 없이 단전을 터뜨린다. 가닥이 거세다.", "bad")
		end
		TaskService.startEntry(player, mode, title, {
			count = count,
			time = (8 + count) * (if pill then 1.5 else 1),
			speed = if pill then 0.6 else 1,
		})
	else
		TaskService.startEntry(player, mode, title, {})
	end
end

TaskService.onEntryTrial = function(player: Player, success: boolean)
	local data = PlayerData.get(player)
	if not data or not (Progression.canBreakthrough(data)) then
		return
	end
	if success then
		local slotsBefore = Progression.slots(data)
		local notes = Progression.passBreakthrough(data, false)
		Progression.addLog(data, "entry_" .. Realms.get(data.step).realm.id)
		Sync.notify(
			player,
			"단전이 터지며 영운이 피어났다. 그 안에 첫 영성이 태어난다!",
			"good"
		)
		ascended(player, data, slotsBefore, notes)
	else
		local lost = Progression.failTrial(data)
		Sync.notify(
			player,
			string.format(
				"가닥을 다 붙잡지 못해 수행이 흔들렸다. 영력 %s 잃었다.",
				Josa.eul(Format.qi(lost))
			),
			"bad"
		)
	end
	Sync.state(player)
end

function Cultivation.breakthrough(player: Player)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session then
		return
	end
	if session.tribulation then
		Sync.notify(player, "이미 천겁을 맞고 있다.", "bad")
		return
	end
	if session.trial then
		Sync.notify(player, "내관 중이다.", "bad")
		return
	end
	if not Characters.humanoid(player) then
		return
	end

	local slotsBefore = Progression.slots(data)
	local result = Progression.attemptBreakthrough(data)
	if result.kind == "blocked" then
		Sync.notify(player, result.reason or "지금은 돌파할 수 없다.", "bad")
	elseif result.kind == "success" then
		Progression.addLog(data, "entry_" .. Realms.get(data.step).realm.id)
		Sync.notify(player, "돌파했다!", "good")
		ascended(player, data, slotsBefore, {})
	elseif result.kind == "trial" then
		local entry = Progression.nextEntry(data)
		startEntryTrial(player, data, result.mode or "", if entry and entry.title then entry.title else "돌파")
	elseif result.kind == "tribulation" then
		Cultivation.setMeditating(player, false)
		Tribulation.start(player)
	end
	Sync.state(player)
end

-- 영맥 말고 그 밖의 흡수 배율 (취령진)
function Cultivation.extraMult(session): number
	return if session.inFormation then Skills.EFFECT.formationMult else 1
end

TaskService.settle = Cultivation.settle
TaskService.setMeditating = Cultivation.setMeditating

return Cultivation
