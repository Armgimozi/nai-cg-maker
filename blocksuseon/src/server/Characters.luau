-- 캐릭터 스탯(체력·이동 속도) 적용.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Progression = require(Shared.Progression)
local PlayerData = require(script.Parent.PlayerData)

local Characters = {}

function Characters.humanoid(player: Player): Humanoid?
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if humanoid and humanoid.Health > 0 then
		return humanoid
	end
	return nil
end

function Characters.root(player: Player): BasePart?
	local character = player.Character
	return character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
end

-- heal 이면 체력을 가득 채우고, 아니면 늘어난 최대 체력만큼만 더한다.
function Characters.applyStats(player: Player, heal: boolean)
	local data = PlayerData.get(player)
	local humanoid = Characters.humanoid(player)
	if not data or not humanoid then
		return
	end
	local maxHealth = Progression.maxHealth(data)
	local gained = math.max(0, maxHealth - humanoid.MaxHealth)
	humanoid.MaxHealth = maxHealth
	if heal then
		humanoid.Health = maxHealth
	else
		humanoid.Health = math.min(maxHealth, humanoid.Health + gained)
	end
	humanoid.WalkSpeed = Progression.walkSpeed(data)
end

return Characters
