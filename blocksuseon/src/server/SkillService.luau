-- 술법 쓰기와 공법 장착.
-- 경신술(돌진)과 영안(투시)은 움직임·화면 효과라서 클라이언트가 실제로 처리하고,
-- 서버는 익혔는지·쿨타임만 확인한 뒤 "Skill" 이벤트로 허락을 보낸다.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Skills = require(Shared.Skills)
local Progression = require(Shared.Progression)
local Realms = require(Shared.Realms)
local Roots = require(Shared.Roots)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)
local Herbs = require(script.Parent.Herbs)
local Manuals = require(script.Parent.Manuals)
local Cultivation = require(script.Parent.Cultivation)

local DASH_COLOR = Color3.fromRGB(170, 240, 220)

local SkillService = {}

local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")

-- 허공이동: 보는 방향으로 순간이동. 벽이 있으면 그 앞에서 멈춘다
local function blink(player: Player, root: BasePart)
	local look = root.CFrame.LookVector
	local direction = Vector3.new(look.X, 0, look.Z)
	if direction.Magnitude < 0.01 then
		return
	end
	direction = direction.Unit * Skills.EFFECT.blinkDistance
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { player.Character :: Instance }
	local hit = Workspace:Raycast(root.Position, direction, params)
	local target = if hit then hit.Position - direction.Unit * 3 else root.Position + direction
	Fx.burst(player.Character, Color3.fromRGB(255, 240, 170), 30);
	(player.Character :: Model):PivotTo(CFrame.new(target) * root.CFrame.Rotation)
	Fx.burst(player.Character, Color3.fromRGB(150, 235, 255), 30)
end

-- 원영 출규: 가장 가까운 영초를 원영이 대신 캔다
local function sendSpirit(player: Player, root: BasePart): boolean
	local folder = Herbs.folder()
	local best, bestDistance = nil, Skills.EFFECT.spiritRange
	for _, herb in (if folder then folder:GetChildren() else {}) do
		if herb:IsA("Model") and herb.PrimaryPart then
			local distance = (herb.PrimaryPart.Position - root.Position).Magnitude
			if distance < bestDistance then
				best, bestDistance = herb, distance
			end
		end
	end
	if not best then
		Sync.notify(player, "원영이 닿는 곳에 영초가 없다.", "bad")
		return false
	end
	Fx.trail(player.Character, Color3.fromRGB(255, 240, 170), 0.5)
	Herbs.collectFrom(player, best)
	return true
end

-- 천기유도: 오악 중심 속성의 천지 현상
local function weather(player: Player, data, root: BasePart)
	local element = data.choice.center or data.choice.element or (data.root and data.root.elements[1]) or "water"
	local name = player.DisplayName
	if element == "water" then
		Herbs.spawnNear(root.Position, 5)
		Sync.broadcast(string.format("%s님이 비를 부른다. 젖은 땅에 영초가 돋는다.", name), "world")
	elseif element == "wood" then
		Herbs.spawnNear(root.Position, 2, "lingzhi")
		Sync.broadcast(string.format("%s님이 숲을 키운다. 천년영지가 고개를 든다.", name), "world")
	elseif element == "earth" then
		Manuals.spawnNow()
		Sync.broadcast(string.format("%s님이 땅을 흔든다. 묻혀 있던 비급이 드러난다.", name), "world")
	elseif element == "fire" then
		for _, other in Players:GetPlayers() do
			local otherRoot = Characters.root(other)
			local otherData = PlayerData.get(other)
			if otherRoot and otherData and (otherRoot.Position - root.Position).Magnitude <= 40 then
				Cultivation.grantQi(other, Progression.requiredQi(otherData) * 0.15)
				Fx.burst(other.Character, Color3.fromRGB(255, 150, 80), 20)
			end
		end
		Sync.broadcast(
			string.format(
				"%s님이 들불을 일으킨다. 둘레의 수도자들이 열기로 영력을 얻는다.",
				name
			),
			"world"
		)
	elseif element == "metal" then
		local pulled = 0
		for _, folderName in { "영초", "별씨" } do
			local folder = Workspace:FindFirstChild(folderName)
			for _, item in (if folder then folder:GetChildren() else {}) do
				if item:IsA("Model") and item.PrimaryPart then
					local offset = item.PrimaryPart.Position - root.Position
					if offset.Magnitude <= 70 and offset.Magnitude > 6 then
						local goal = root.Position + offset.Unit * 5
						item:PivotTo(CFrame.new(goal.X, item.PrimaryPart.Position.Y, goal.Z))
						pulled += 1
					end
				end
			end
		end
		Sync.broadcast(
			string.format("%s님이 폭풍을 부른다. 둘레의 영물 %d개가 끌려온다.", name, pulled),
			"world"
		)
	end
	Fx.burst(player.Character, Color3.fromRGB(255, 255, 255), 60)
	Sync.notify(player, string.format("천기유도 (%s)", Roots.ELEMENT[element].name), "good")
end

function SkillService.use(player: Player, id: string)
	local def = Skills.byId[id]
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not def or def.kind ~= "active" or not data or not session then
		return
	end
	if not Progression.knows(data, id) then
		Sync.notify(player, "아직 익히지 못한 술법이다. 맵에서 비급을 찾아야 한다.", "bad")
		return
	end
	local root = Characters.root(player)
	if not root or not Characters.humanoid(player) then
		return
	end
	local now = os.clock()
	if now < (session.cooldowns[id] or 0) - 0.1 then
		return -- 아직 쿨타임 (클라이언트도 막지만 한 번 더 확인)
	end
	session.cooldowns[id] = now + (def.cooldown or 0)

	if id == "heogong" then
		blink(player, root)
	elseif id == "yeongchul" then
		if not sendSpirit(player, root) then
			session.cooldowns[id] = now + 2
		end
	elseif id == "yudo" then
		weather(player, data, root)
	elseif id == "gyeongsin" then
		Fx.trail(player.Character, DASH_COLOR, Skills.EFFECT.dashTime)
	elseif id == "hosin" then
		session.shieldUntil = now + (def.duration or 0)
		Fx.shield(player.Character, def.duration or 0)
	elseif id == "chwiryeong" then
		session.formation = { position = root.Position, untilTime = now + (def.duration or 0) }
		Fx.formation(root.Position, Skills.EFFECT.formationRadius, def.duration or 0)
		Sync.markDirty(player)
	end

	-- 결단기부터 경신술은 비둔술: 빛줄기로 더 멀리, 조금 떠서 난다
	local power = if id == "gyeongsin" and data.step >= Realms.firstStepById.gyeoldan then 1.6 else 1
	Sync.remotes.Skill:FireClient(
		player,
		{ id = id, cooldown = math.max(0, session.cooldowns[id] - now), duration = def.duration, power = power }
	)
end

function SkillService.setEquipped(player: Player, id: string, equip: boolean)
	local data = PlayerData.get(player)
	if not data or not Skills.byId[id] then
		return
	end
	local ok, message
	if equip then
		ok, message = Progression.equip(data, id)
	else
		ok, message = Progression.unequip(data, id)
	end
	Sync.notify(player, message, if ok then "info" else "bad")
	if ok and id == "geumgang" then
		Characters.applyStats(player, false)
	end
	Sync.state(player)
end

function SkillService.assign(player: Player, slot: any, id: any)
	local data = PlayerData.get(player)
	if not data or type(id) ~= "string" then
		return
	end
	local ok, message = Progression.assignSkill(data, slot, id)
	Sync.notify(player, message, if ok then "info" else "bad")
	Sync.state(player)
end

function SkillService.bindKey(player: Player, slot: any, key: any)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local ok, message = Progression.bindKey(data, slot, key)
	Sync.notify(player, message, if ok then "info" else "bad")
	Sync.state(player)
end

return SkillService
