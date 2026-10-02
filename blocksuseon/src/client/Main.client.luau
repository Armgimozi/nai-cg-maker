-- 블록수선전 클라이언트 진입점: 입력과 서버 이벤트를 UI 에 잇는다.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Net = require(Shared.Net)
local Skills = require(Shared.Skills)
local Hud = require(script.Parent.Hud)
local Effects = require(script.Parent.Effects)

local player = Players.LocalPlayer

-- 도구를 쓰지 않으니 기본 가방을 꺼서 1~4 키를 술법에 쓴다
pcall(function()
	game:GetService("StarterGui"):SetCoreGuiEnabled(Enum.CoreGuiType.Backpack, false)
end)
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
	useSkill = function(id: string)
		if not Hud.knows(id) then
			Hud.toast("아직 익히지 못한 술법이다. 맵에서 비급을 찾아야 한다.", "bad")
		elseif Hud.cooldownReady(id) then
			request("UseSkill", id)
		end
	end,
	equip = function(id: string, on: boolean)
		request(if on then "Equip" else "Unequip", id)
	end,
}

-- 숫자 키 → 술법
local SKILL_KEYS = {
	[Enum.KeyCode.One] = 1,
	[Enum.KeyCode.Two] = 2,
	[Enum.KeyCode.Three] = 3,
	[Enum.KeyCode.Four] = 4,
}

Hud.build(actions)

remotes.State.OnClientEvent:Connect(function(snapshot)
	state = snapshot
	Hud.update(snapshot)
end)
remotes.Notify.OnClientEvent:Connect(Hud.toast)
remotes.Cinematic.OnClientEvent:Connect(Hud.cinematic)
remotes.Skill.OnClientEvent:Connect(function(payload)
	Hud.skillUsed(payload)
	if payload.id == "gyeongsin" then
		Effects.dash()
	elseif payload.id == "yeongan" then
		Effects.sight(payload.duration or 10)
	end
end)

UserInputService.InputBegan:Connect(function(input: InputObject, processed: boolean)
	if processed then
		return
	end
	if input.KeyCode == Enum.KeyCode.R then
		actions.meditate()
	elseif input.KeyCode == Enum.KeyCode.B then
		actions.breakthrough()
	elseif input.KeyCode == Enum.KeyCode.C then
		Hud.toggleStatus()
	elseif SKILL_KEYS[input.KeyCode] then
		local skill = Skills.actives[SKILL_KEYS[input.KeyCode]]
		if skill then
			actions.useSkill(skill.id)
		end
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
