-- 클라이언트로 상태·알림 보내기, 리더보드 갱신.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local Progression = require(Shared.Progression)
local Net = require(Shared.Net)
local Skills = require(Shared.Skills)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)

local Sync = {}

local remotes = Net.get()
Sync.remotes = remotes

function Sync.setupLeaderstats(player: Player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local realm = Instance.new("StringValue")
	realm.Name = "경지"
	realm.Parent = stats
	stats.Parent = player
end

local function updateLeaderstats(player: Player, data)
	local stats = player:FindFirstChild("leaderstats")
	if not stats then
		return
	end
	local realm = stats:FindFirstChild("경지") :: StringValue?
	if realm then
		realm.Value = Realms.label(data.step)
	end
end

function Sync.state(player: Player)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session then
		return
	end
	session.dirty = false

	local tribulation = session.tribulation
	remotes.State:FireClient(player, {
		step = data.step,
		qi = data.qi,
		req = Balance.qiRequired(data.step),
		gain = Progression.qiPerSecond(
			data,
			session.veinMult,
			if session.inFormation then Skills.EFFECT.formationMult else 1
		),
		meditating = session.meditating,
		veinId = session.veinId,
		veinBlocked = session.veinBlocked,
		breakChance = Progression.breakChance(data),
		skills = data.skills,
		equipped = data.equipped,
		slots = Progression.slots(data),
		stats = data.stats,
		inFormation = session.inFormation,
		maxHealth = Progression.maxHealth(data),
		tribulation = if tribulation
			then { name = tribulation.name, wave = tribulation.wave, waves = tribulation.waves }
			else nil,
		canSave = PlayerData.canSave(player),
	})
	updateLeaderstats(player, data)
end

-- 대경지에 올라 공법 칸이 늘었으면 알린다
function Sync.announceSlots(player: Player, before: number)
	local data = PlayerData.get(player)
	if data and Progression.slots(data) > before then
		Sync.notify(player, string.format("공법 칸이 %d칸으로 늘었다.", Progression.slots(data)), "good")
	end
end

function Sync.markDirty(player: Player)
	local session = Session.get(player)
	if session then
		session.dirty = true
	end
end

function Sync.flush()
	for player, session in Session.all() do
		if session.dirty then
			Sync.state(player)
		end
	end
end

-- kind: "info" | "good" | "bad" | "tribulation" | "world"
function Sync.notify(player: Player, text: string, kind: string?)
	remotes.Notify:FireClient(player, text, kind or "info")
end

function Sync.broadcast(text: string, kind: string?)
	remotes.Notify:FireAllClients(text, kind or "world")
end

function Sync.cinematic(player: Player, payload: { [string]: any })
	remotes.Cinematic:FireClient(player, payload)
end

return Sync
