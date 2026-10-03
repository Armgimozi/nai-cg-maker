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
local TaskService = require(script.Parent.TaskService)
local DayNight = require(script.Parent.DayNight)
local StarRain = require(script.Parent.StarRain)
local DevCommands = require(script.Parent.DevCommands)
local Villagers = require(script.Parent.Villagers)

local RESPAWN_DELAY = 4
local REGEN_COOLDOWN = 600 -- 금단 재생: 10분에 한 번 쓰러진 자리에서 일어난다
local REQUEST_INTERVAL = 0.12

-- 데이터를 다 불러온 뒤에 캐릭터를 내보낸다
Players.CharacterAutoLoads = false

if not Workspace:FindFirstChild(World.MODEL_NAME) then
	World.build(Workspace, Lighting)
end

DayNight.start()
TaskService.setupPrompts()
DevCommands.setup()
Herbs.start()
StarRain.start()
Villagers.start()
Manuals.start()
PlayerData.startAutosave()

local function onCharacterAdded(player: Player, character: Model)
	local humanoid = character:WaitForChild("Humanoid") :: Humanoid
	Villagers.tagCharacter(character)
	Characters.applyStats(player, true)
	Sync.markDirty(player)

	humanoid.Died:Connect(function()
		local session = Session.get(player)
		if session then
			session.meditating = false
			session.anchor = nil
		end
		TaskService.cancelTrial(player)
		Tribulation.fail(player)
		Sync.markDirty(player)

		local data = PlayerData.get(player)
		local root = Characters.root(player)
		local deathPosition = root and root.Position
		local regen = data ~= nil
			and session ~= nil
			and deathPosition ~= nil
			and data.step >= Realms.firstStepById.gyeoldan + 3
			and os.clock() - session.lastRegen >= REGEN_COOLDOWN
		task.delay(if regen then 2 else RESPAWN_DELAY, function()
			if not player.Parent then
				return
			end
			player:LoadCharacter()
			if regen and session and deathPosition then
				session.lastRegen = os.clock()
				local newRoot = player.Character and player.Character:WaitForChild("HumanoidRootPart", 5)
				if newRoot and newRoot:IsA("BasePart") then
					newRoot.CFrame = CFrame.new(deathPosition + Vector3.new(0, 3, 0))
				end
				Sync.notify(
					player,
					"금단이 몸을 다시 빚었다. 쓰러진 자리에서 일어난다. (10분에 한 번)",
					"good"
				)
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
	TaskService.cancelTrial(player) -- 돌파 내관 도중에 나가도 실패
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
	elseif action == "AssignSkill" and type(arg) == "table" then
		SkillService.assign(player, arg.slot, arg.id)
	elseif action == "BindKey" and type(arg) == "table" then
		SkillService.bindKey(player, arg.slot, arg.key)
	elseif action == "StartTask" then
		TaskService.startTask(player, arg)
	elseif action == "SkipTask" then
		TaskService.skip(player, arg)
	elseif action == "TrialResult" then
		TaskService.trialResult(player, arg)
	elseif action == "TrialCancel" then
		TaskService.cancelTrial(player)
	elseif action == "Choose" and type(arg) == "table" then
		TaskService.choose(player, arg.key, arg.value)
	elseif action == "Eat" then
		local qi = TaskService.eat(player, arg)
		if qi then
			Cultivation.grantQi(player, qi)
		end
		Sync.state(player)
	end
end)

while true do
	local dt = task.wait(Balance.TICK)
	DayNight.tick()
	Cultivation.tick(dt)
	Sync.flush()
end
