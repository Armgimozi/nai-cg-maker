-- 목인장(TrainingDummy 태그)에서 무공을 수련한다.

local CollectionService = game:GetService("CollectionService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Balance = require(Shared.Balance)
local MartialRanks = require(Shared.MartialRanks)
local Progression = require(Shared.Progression)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Cultivation = require(script.Parent.Cultivation)
local Fx = require(script.Parent.Fx)

local RANK_COLOR = Color3.fromRGB(255, 170, 120)
local ANNOUNCE_FROM = 5 -- 절정부터는 모두에게 알린다

local Martial = {}

local function train(player: Player, post: BasePart)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session or not Characters.humanoid(player) then
		return
	end
	local now = os.clock()
	if now - session.lastTraining < Balance.MARTIAL_COOLDOWN then
		return
	end
	session.lastTraining = now

	if session.meditating then
		Cultivation.setMeditating(player, false)
	end

	local exp = Balance.martialExpPerHit(data.step, Progression.insight(data, "oseong"))
	local rankUp = Progression.addMartialExp(data, exp)
	Fx.spark(post, RANK_COLOR)

	if rankUp then
		local rank = MartialRanks.list[rankUp]
		Characters.applyStats(player, false)
		Fx.burst(player.Character, RANK_COLOR, 30)
		Sync.notify(player, string.format("무공 %s  ·  체력과 경공이 오른다", rank.name), "good")
		if rankUp >= ANNOUNCE_FROM then
			Sync.broadcast(
				string.format("%s님의 무공이 %s에 이르렀다", player.DisplayName, rank.name),
				"world"
			)
		end
	end
	Sync.markDirty(player)
end

local function attach(post: Instance)
	if not post:IsA("BasePart") or post:FindFirstChildOfClass("ProximityPrompt") then
		return
	end
	local prompt = Instance.new("ProximityPrompt")
	prompt.ActionText = "수련"
	prompt.ObjectText = "목인장"
	prompt.HoldDuration = 0.25
	prompt.MaxActivationDistance = 8
	prompt.RequiresLineOfSight = false
	prompt.Parent = post
	prompt.Triggered:Connect(function(player)
		train(player, post)
	end)
end

function Martial.start()
	for _, post in CollectionService:GetTagged("TrainingDummy") do
		attach(post)
	end
	CollectionService:GetInstanceAddedSignal("TrainingDummy"):Connect(attach)
end

return Martial
