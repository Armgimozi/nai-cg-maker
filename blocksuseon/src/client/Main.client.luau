-- 블록수선전 클라이언트 진입점: 입력과 서버 이벤트를 UI 에 잇는다.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Net = require(Shared.Net)
local Progression = require(Shared.Progression)
local Realms = require(Shared.Realms)
local Hud = require(script.Parent.Hud)
local Effects = require(script.Parent.Effects)

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
	-- 단축칸에 넣은 술법을 쓴다
	useSlot = function(slot: number)
		local id = state and state.hotbar[slot]
		if not id or id == "" then
			Hud.toast("이 칸에 넣은 술법이 없다. 상태창(C)에서 넣을 수 있다.", "info")
		elseif not Hud.knows(id) then
			Hud.toast("아직 익히지 못한 술법이다. 맵에서 비급을 찾아야 한다.", "bad")
		elseif Hud.cooldownReady(id) then
			request("UseSkill", id)
		end
	end,
	assign = function(slot: number, id: string)
		request("AssignSkill", { slot = slot, id = id })
	end,
	equip = function(id: string, on: boolean)
		request(if on then "Equip" else "Unequip", id)
	end,
	startTask = function(id: string)
		request("StartTask", id)
	end,
	skipTask = function(id: string)
		request("SkipTask", id)
	end,
	choose = function(key: string, value: any)
		request("Choose", { key = key, value = value })
	end,
	eat = function(item: string)
		request("Eat", item)
	end,
	trialResult = function(payload)
		request("TrialResult", payload)
	end,
	trialCancel = function()
		request("TrialCancel")
	end,
}

Hud.build(actions)

-- 과업 자리의 F 버튼(팔괘 기둥, 칠성단)은 지금 쓸 때만 보이게 한다 (내 화면에서만 바뀐다)
local function promptUse(site: string, snapshot): string?
	if site == "furnace" then
		return "축기단 빚기"
	elseif site == "starseed" then
		return if Realms.get(snapshot.step).realm.id == "chukgi" then "별씨 줍기" else nil
	end
	for _, job in snapshot.tasks or {} do
		if job.open and not job.done then
			if job.kind == "touch" and string.sub(site, 1, 4) == "tri_" then
				return "괘 새기기"
			elseif job.kind == "offer" and site == "altar" then
				return "제물 바치기"
			elseif job.kind == "ritual" and site == "altar" then
				return "제의 올리기"
			end
		end
	end
	return nil
end

local function refreshPrompts()
	if not state then
		return
	end
	for _, prompt in CollectionService:GetTagged("TaskPrompt") do
		local site = prompt:GetAttribute("Site")
		local use = if type(site) == "string" then promptUse(site, state) else nil
		prompt.Enabled = use ~= nil
		if use then
			prompt.ActionText = use
		end
	end
end
CollectionService:GetInstanceAddedSignal("TaskPrompt"):Connect(function()
	task.defer(refreshPrompts)
end)

remotes.State.OnClientEvent:Connect(function(snapshot)
	state = snapshot
	Hud.update(snapshot)
	refreshPrompts()
end)
remotes.Notify.OnClientEvent:Connect(Hud.toast)
remotes.Cinematic.OnClientEvent:Connect(Hud.cinematic)
remotes.Trial.OnClientEvent:Connect(Hud.openTrial)
remotes.Skill.OnClientEvent:Connect(function(payload)
	Hud.skillUsed(payload)
	if payload.id == "gyeongsin" then
		Effects.dash(payload.power)
	elseif payload.id == "yeongan" then
		Effects.sight(payload.duration or 10)
	end
end)

UserInputService.InputBegan:Connect(function(input: InputObject, processed: boolean)
	if processed or input.UserInputType ~= Enum.UserInputType.Keyboard then
		return
	end
	local keyName = input.KeyCode.Name

	-- 상태창에서 단축키를 바꾸는 중이면 이번 키를 그 칸에 묶는다
	local binding = Hud.bindingSlot()
	if binding then
		Hud.stopBinding()
		if Progression.isBindable(keyName) then
			request("BindKey", { slot = binding, key = keyName })
		else
			Hud.toast(
				"그 키는 단축키로 쓸 수 없다. ("
					.. table.concat(Progression.BINDABLE_KEYS, " ")
					.. " 중에서)",
				"bad"
			)
		end
		return
	end

	if input.KeyCode == Enum.KeyCode.R then
		actions.meditate()
	elseif input.KeyCode == Enum.KeyCode.B then
		actions.breakthrough()
	elseif input.KeyCode == Enum.KeyCode.C then
		Hud.toggleStatus()
	elseif state then
		local slot = table.find(state.keys, keyName)
		if slot then
			actions.useSlot(slot)
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
