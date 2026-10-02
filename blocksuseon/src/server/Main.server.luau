-- 블록수선전 서버 진입점.

local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Lighting = game:GetService("Lighting")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local World = require(script.Parent.World)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Cultivation = require(script.Parent.Cultivation)
local Tribulation = require(script.Parent.Tribulation)
local Herbs = require(script.Parent.Herbs)
local Manuals = require(script.Parent.Manuals)
local SkillService = require(script.Parent.SkillService)

local RESPAWN_DELAY = 4
local REQUEST_INTERVAL = 0.12

-- 데이터를 다 불러온 뒤에 캐릭터를 내보낸다
Players.CharacterAutoLoads = false

if not Workspace:FindFirstChild(World.MODEL_NAME) then
	World.build(Workspace, Lighting)
end

Herbs.start()
Manuals.start()
PlayerData.startAutosave()

local function onCharacterAdded(player: Player, character: Model)
	local humanoid = character:WaitForChild("Humanoid") :: Humanoid
	Characters.applyStats(player, true)
	Sync.markDirty(player)

	humanoid.Died:Connect(function()
		local session = Session.get(player)
		if session then
			session.meditating = false
			session.anchor = nil
		end
		Tribulation.fail(player)
		Sync.markDirty(player)
		task.delay(RESPAWN_DELAY, function()
			if player.Parent then
				player:LoadCharacter()
			end
		end)
	end)
end

local function onPlayerAdded(player: Player)
	Session.start(player)
	Sync.setupLeaderstats(player)
	local data, canSave = PlayerData.load(player)
	if not player.Parent then
		-- 불러오는 사이에 나갔다
		Session.stop(player)
		PlayerData.release(player)
		return
	end

	player.CharacterAdded:Connect(function(character)
		onCharacterAdded(player, character)
	end)
	player:LoadCharacter()

	Sync.cinematic(player, {
		kind = "intro",
		realm = Realms.label(data.step),
		returning = data.step > 1,
	})
	if not canSave then
		Sync.notify(
			player,
			"저장소에 연결하지 못했다. 이번 접속의 기록은 저장되지 않는다.",
			"bad"
		)
	end
	Sync.state(player)
end

Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end

Players.PlayerRemoving:Connect(function(player)
	Tribulation.fail(player) -- 천겁 도중에 나가면 실패로 친다
	Session.stop(player)
	PlayerData.release(player)
end)

Sync.remotes.Request.OnServerEvent:Connect(function(player: Player, action: any, arg: any)
	local session = Session.get(player)
	if not session or type(action) ~= "string" then
		return
	end
	local now = os.clock()
	if now - session.lastRequest < REQUEST_INTERVAL then
		return
	end
	session.lastRequest = now

	if action == "Meditate" then
		Cultivation.setMeditating(player, arg == true)
		Sync.state(player)
	elseif action == "Breakthrough" then
		Cultivation.breakthrough(player)
	elseif action == "UseSkill" and type(arg) == "string" then
		SkillService.use(player, arg)
	elseif (action == "Equip" or action == "Unequip") and type(arg) == "string" then
		SkillService.setEquipped(player, arg, action == "Equip")
	end
end)

while true do
	local dt = task.wait(Balance.TICK)
	Cultivation.tick(dt)
	Sync.flush()
end
