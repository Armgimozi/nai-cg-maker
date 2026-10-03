-- 블록수선전 클라이언트 진입점: 입력과 서버 이벤트를 UI 에 잇는다.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Net = require(Shared.Net)
local Progression = require(Shared.Progression)
local Realms = require(Shared.Realms)
local Places = require(Shared.Places)
local Hud = require(script.Parent.Hud)
local Effects = require(script.Parent.Effects)
local NpcLook = require(script.Parent.NpcLook)
local Plaques = require(script.Parent.Plaques)
local MobAnimator = require(script.Parent.MobAnimator)

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
	travel = function(id: string)
		request("Travel", id)
	end,
}

Hud.build(actions)

-- 과업 자리의 F 버튼(팔괘 기둥, 칠성단)은 지금 쓸 때만 보이게 한다 (내 화면에서만 바뀐다)
local function promptUse(site: string, snapshot): string?
	if site == "furnace" then
		return "축기단 빚기"
	elseif string.sub(site, 1, 6) == "elder_" then
		-- 노인은 언제든 말을 걸 수 있다. 부탁할 때면 영초를 건넨다
		for _, job in snapshot.tasks or {} do
			if job.kind == "offer" and job.open and not job.done and job.sites and table.find(job.sites, site) then
				return "영초 건네기"
			end
		end
		return "말 걸기"
	elseif site == "starseed" then
		return if Realms.get(snapshot.step).realm.id == "chukgi" then "별씨 줍기" else nil
	end
	for _, job in snapshot.tasks or {} do
		if job.open and not job.done then
			local here = job.sites ~= nil and table.find(job.sites, site) ~= nil
			if job.kind == "touch" and string.sub(site, 1, 4) == "tri_" then
				return "괘 새기기"
			elseif job.kind == "offer" and here then
				if string.sub(site, 1, 6) == "elder_" then
					return "영초 건네기"
				end
				return if job.id == "offer" then "제물 바치기" else "내려놓기"
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
remotes.Combat.OnClientEvent:Connect(Hud.combat)
remotes.Cinematic.OnClientEvent:Connect(Hud.cinematic)
remotes.Trial.OnClientEvent:Connect(Hud.openTrial)
remotes.Speak.OnClientEvent:Connect(function(part: BasePart, text: string)
	if typeof(part) ~= "Instance" or type(text) ~= "string" then
		return
	end
	local ok = pcall(function()
		game:GetService("TextChatService"):DisplayBubble(part, text)
	end)
	if not ok then
		Hud.toast(text, "info")
	end
end)
NpcLook.start()
Plaques.start()
MobAnimator.start()

-- 전송진: F 를 누르면 갈 곳 고르는 창을 연다. 진에서 멀어지면 닫는다
local travelPad: BasePart? = nil
game:GetService("ProximityPromptService").PromptTriggered:Connect(function(prompt: ProximityPrompt)
	local id = prompt:GetAttribute("Waypoint")
	local pad = prompt.Parent
	if type(id) == "string" and pad and pad:IsA("BasePart") then
		travelPad = pad
		Hud.openTravel(id)
	end
end)
RunService.Heartbeat:Connect(function()
	local pad = travelPad
	if not pad or not Hud.travelOpen() then
		travelPad = nil
		return
	end
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	-- 서버가 받아 주는 거리(수평 Places.WAYPOINT_RADIUS)를 벗어나면 닫는다
	local offset = if root and root:IsA("BasePart") then root.Position - pad.Position else nil
	local far = offset == nil
		or Vector3.new(offset.X, 0, offset.Z).Magnitude > Places.WAYPOINT_RADIUS
		or math.abs(offset.Y) >= 14
	if far or not pad.Parent then
		travelPad = nil
		Hud.closeTravel()
	end
end)
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
