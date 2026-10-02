-- 운기조식(영력 흡수), 영맥 판정, 돌파, 깨달음 강화.

local CollectionService = game:GetService("CollectionService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Progression = require(Shared.Progression)
local Format = require(Shared.Format)
local Josa = require(Shared.Josa)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)
local Tribulation = require(script.Parent.Tribulation)

local MOVE_TOLERANCE = 3 -- 운기조식 중 이만큼 움직이면 풀린다
local STEP_COLOR = Color3.fromRGB(150, 235, 255)
local MAJOR_COLOR = Color3.fromRGB(255, 230, 150)

local Cultivation = {}

local rng = Random.new()

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

local function isFull(data): boolean
	return Progression.isCapped(data) and data.qi >= Balance.qiRequired(data.step)
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

-- 영력을 주고, 단계가 오르거나 병목에 닿으면 알린다.
function Cultivation.grantQi(player: Player, amount: number)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local wasFull = isFull(data)
	local advanced, points = Progression.addQi(data, amount)

	if advanced > 0 then
		Sync.notify(player, string.format("%s에 올랐다. (깨달음 +%d)", Realms.label(data.step), points), "good")
		Fx.burst(player.Character, STEP_COLOR, 25)
	end
	if not wasFull and isFull(data) then
		if data.step >= Realms.maxStep then
			Sync.notify(player, "더 오를 경지가 없다. 지금으로서는 여기가 끝이다.", "good")
		else
			local target = Realms.get(data.step + 1).realm
			local message = if target.tribulation
				then string.format(
					"영력이 가득 찼다. %s에 오르려면 천겁을 넘어야 한다.",
					target.name
				)
				else string.format(
					"영력이 가득 찼다. 이제 %s 돌파할 수 있다.",
					Josa.ro(target.name)
				)
			Sync.notify(player, message, "good")
		end
	end
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

		if session.meditating then
			local anchor = session.anchor
			if
				not root
				or not anchor
				or not Characters.humanoid(player)
				or flatDistance(root.Position, anchor) > MOVE_TOLERANCE
			then
				Cultivation.setMeditating(player, false)
			elseif not isFull(data) then
				Cultivation.grantQi(player, Progression.qiPerSecond(data, mult) * dt)
			end
		end
	end
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
	if not Characters.humanoid(player) then
		return
	end

	local result = Progression.attemptBreakthrough(data, rng:NextNumber())
	if result.kind == "blocked" then
		Sync.notify(player, result.reason or "지금은 돌파할 수 없다.", "bad")
	elseif result.kind == "success" then
		Characters.applyStats(player, true)
		Fx.burst(player.Character, MAJOR_COLOR, 60)
		Sync.notify(player, string.format("돌파에 성공했다! (깨달음 +%d)", result.points or 0), "good")
		Sync.broadcast(string.format("%s님이 %s에 올랐다.", player.DisplayName, Realms.label(data.step)), "world")
		Sync.cinematic(player, {
			kind = "ascend",
			step = data.step,
			realm = Realms.label(data.step),
			blurb = Realms.get(data.step).realm.blurb,
		})
	elseif result.kind == "fail" then
		Sync.notify(
			player,
			string.format(
				"돌파에 실패해 주화입마에 빠졌다. 영력 %s 잃었다.",
				Josa.eul(Format.qi(result.lost or 0))
			),
			"bad"
		)
	elseif result.kind == "tribulation" then
		Cultivation.setMeditating(player, false)
		Tribulation.start(player)
	end
	Sync.state(player)
end

function Cultivation.buyInsight(player: Player, id: string)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local ok, message = Progression.buyInsight(data, id)
	if ok then
		Sync.notify(player, message, "good")
		if id == "danche" then
			Characters.applyStats(player, false)
		end
	else
		Sync.notify(player, message, "bad")
	end
	Sync.state(player)
end

return Cultivation
