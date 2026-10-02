-- 술법 쓰기와 공법 장착.
-- 경신술(돌진)과 영안(투시)은 움직임·화면 효과라서 클라이언트가 실제로 처리하고,
-- 서버는 익혔는지·쿨타임만 확인한 뒤 "Skill" 이벤트로 허락을 보낸다.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Skills = require(Shared.Skills)
local Progression = require(Shared.Progression)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)

local DASH_COLOR = Color3.fromRGB(170, 240, 220)

local SkillService = {}

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

	if id == "gyeongsin" then
		Fx.trail(player.Character, DASH_COLOR, Skills.EFFECT.dashTime)
	elseif id == "hosin" then
		session.shieldUntil = now + (def.duration or 0)
		Fx.shield(player.Character, def.duration or 0)
	elseif id == "chwiryeong" then
		session.formation = { position = root.Position, untilTime = now + (def.duration or 0) }
		Fx.formation(root.Position, Skills.EFFECT.formationRadius, def.duration or 0)
		Sync.markDirty(player)
	end

	Sync.remotes.Skill:FireClient(player, { id = id, cooldown = def.cooldown, duration = def.duration })
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

return SkillService
