-- 블록수선전 클라이언트 진입점: 입력과 서버 이벤트를 UI 에 잇는다.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Net = require(Shared.Net)
local Hud = require(script.Parent.Hud)

local player = Players.LocalPlayer
local remotes = Net.get()
local state: { [string]: any }? = nil

local function request(action: string, arg: any?)
	remotes.Request:FireServer(action, arg)
end

local actions = {
	meditate = function()
		if state then
			request("Meditate", not state.meditating)
		end
	end,
	breakthrough = function()
		request("Breakthrough")
	end,
	buyInsight = function(id: string)
		request("BuyInsight", id)
	end,
}

Hud.build(actions)

remotes.State.OnClientEvent:Connect(function(snapshot)
	state = snapshot
	Hud.update(snapshot)
end)
remotes.Notify.OnClientEvent:Connect(Hud.toast)
remotes.Cinematic.OnClientEvent:Connect(Hud.cinematic)

UserInputService.InputBegan:Connect(function(input: InputObject, processed: boolean)
	if processed then
		return
	end
	if input.KeyCode == Enum.KeyCode.R then
		actions.meditate()
	elseif input.KeyCode == Enum.KeyCode.B then
		actions.breakthrough()
	elseif input.KeyCode == Enum.KeyCode.T then
		Hud.togglePanel()
	end
end)

-- 움직이거나 뛰면 운기조식을 푼다 (서버도 위치로 따로 확인한다)
local lastStop = 0
RunService.Heartbeat:Connect(function()
	if not state or not state.meditating then
		return
	end
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if not humanoid then
		return
	end
	local moving = humanoid.MoveDirection.Magnitude > 0.1 or humanoid.Jump
	if moving and os.clock() - lastStop > 0.5 then
		lastStop = os.clock()
		request("Meditate", false)
	end
end)

local function onCharacter(character: Model)
	local humanoid = character:WaitForChild("Humanoid") :: Humanoid
	humanoid.Died:Connect(function()
		Hud.cinematic({ kind = "down" })
	end)
end

player.CharacterAdded:Connect(onCharacter)
if player.Character then
	task.spawn(onCharacter, player.Character)
end
