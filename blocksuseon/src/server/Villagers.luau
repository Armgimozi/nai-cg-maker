-- 마을 사람(NPC)을 진짜 R15 캐릭터로 띄운다. 생김새·자리·대사는 shared/Npcs.luau.
--
-- 노인 셋은 맵의 자리(Seat, 속성 NpcSeat)에 앉혀 앉은 동작을 틀고, 말 걸기는 TaskService 의
-- 과업 자리 버튼(elder_*)이 받는다. 마을 사람 넷은 정해진 길을 천천히 오가고, 스스로 "말 걸기" 버튼을 단다.
-- 말은 말을 건 사람 화면에만 말풍선으로 뜬다(클라이언트가 Speak 를 받아 DisplayBubble).
--
-- 기본 Animate 스크립트는 NPC 에서 돌지 않으므로 지우고, 서버에서 기본 R15 동작을 직접 튼다.

local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Npcs = require(Shared.Npcs)
local Sync = require(script.Parent.Sync)

local Villagers = {}

-- Roblox 기본 R15 동작 (Roblox 소유, 어느 게임에서나 쓴다)
local ANIMATIONS = {
	idle = "rbxassetid://507766388",
	walk = "rbxassetid://507777826",
	sit = "rbxassetid://2506281703",
}

local NPC_GROUP = "Npc"
local PLAYER_GROUP = "PlayerChar"
local TALK_PAUSE = 5 -- 말을 걸면 걷던 사람이 멈춰 서는 시간

type Live = {
	def: Npcs.Npc,
	model: Model,
	humanoid: Humanoid,
	root: BasePart,
	head: BasePart?,
	tracks: { [string]: AnimationTrack },
	pausedUntil: number,
}

local live: { [string]: Live } = {}
local lineIndex: { [Player]: { [string]: number } } = {}
local folder: Folder

local function setupCollisionGroups()
	-- 걷는 마을 사람을 플레이어가 밀거나 길을 막지 않게
	local ok = pcall(function()
		local world = Workspace :: any
		for _, group in { NPC_GROUP, PLAYER_GROUP } do
			if not world:IsCollisionGroupRegistered(group) then
				world:RegisterCollisionGroup(group)
			end
		end
		world:CollisionGroupSetCollidable(NPC_GROUP, PLAYER_GROUP, false)
	end)
	if not ok then
		local PhysicsService = game:GetService("PhysicsService")
		pcall(function()
			for _, group in { NPC_GROUP, PLAYER_GROUP } do
				if not PhysicsService:IsCollisionGroupRegistered(group) then
					PhysicsService:RegisterCollisionGroup(group)
				end
			end
			PhysicsService:CollisionGroupSetCollidable(NPC_GROUP, PLAYER_GROUP, false)
		end)
	end
end

local function setGroup(model: Instance, group: string)
	for _, part in model:GetDescendants() do
		if part:IsA("BasePart") then
			part.CollisionGroup = group
		end
	end
	model.DescendantAdded:Connect(function(part)
		if part:IsA("BasePart") then
			part.CollisionGroup = group
		end
	end)
end

-- 플레이어 캐릭터는 마을 사람과 부딪히지 않는다 (Main 에서 부른다)
function Villagers.tagCharacter(character: Model)
	setGroup(character, PLAYER_GROUP)
end

local function describe(look: Npcs.Look, withAccessories: boolean): HumanoidDescription
	local desc = Instance.new("HumanoidDescription")
	local color = Color3.fromRGB(look.color[1], look.color[2], look.color[3])
	desc.HeadColor = color
	desc.TorsoColor = color
	desc.LeftArmColor = color
	desc.RightArmColor = color
	desc.LeftLegColor = color
	desc.RightLegColor = color
	desc.HeightScale = look.scales.height
	desc.WidthScale = look.scales.width
	desc.HeadScale = look.scales.head
	desc.DepthScale = look.scales.depth or 1
	desc.ProportionScale = 0
	desc.BodyTypeScale = 0
	desc.Face = look.face or 0
	desc.Shirt = look.shirt or 0
	desc.Pants = look.pants or 0
	if withAccessories then
		for slot, ids in look.rigid or {} do
			local list = {}
			for _, id in ids do
				table.insert(list, tostring(id))
			end
			(desc :: any)[slot .. "Accessory"] = table.concat(list, ",")
		end
		local layered = {}
		for index, item in look.layered or {} do
			table.insert(layered, {
				AssetId = item.id,
				AccessoryType = (Enum.AccessoryType :: any)[item.type],
				IsLayered = true,
				Order = index,
			})
		end
		if #layered > 0 then
			desc:SetAccessories(layered, false)
		end
	end
	return desc
end

-- 엔진 판에 따라 이름과 인자가 다를 수 있어 차례로 해 본다
local function createModel(desc: HumanoidDescription): Model?
	local players = Players :: any
	local attempts = {
		function()
			return players:CreateHumanoidModelFromDescriptionAsync(
				desc,
				Enum.HumanoidRigType.R15,
				(Enum :: any).AssetTypeVerification.Always
			)
		end,
		function()
			return players:CreateHumanoidModelFromDescriptionAsync(desc, Enum.HumanoidRigType.R15)
		end,
		function()
			return players:CreateHumanoidModelFromDescription(desc, Enum.HumanoidRigType.R15)
		end,
	}
	local lastError = nil
	for _, attempt in attempts do
		local ok, result = pcall(attempt)
		if ok and typeof(result) == "Instance" and result:IsA("Model") then
			return result
		end
		lastError = result
	end
	warn("[블록수선전] NPC 를 만들지 못했다:", lastError)
	return nil
end

-- 생김새를 HumanoidDescription 으로. 아이템 값이 잘못돼도 서버가 멈추지 않게 감싼다
local function safeDescribe(look: Npcs.Look, withAccessories: boolean): HumanoidDescription?
	local ok, desc = pcall(describe, look, withAccessories)
	if ok then
		return desc
	end
	warn("[블록수선전] NPC HumanoidDescription 오류:", desc)
	return nil
end

-- 아이템까지 다 입혀 보고, 안 되면 옷과 얼굴만, 그래도 안 되면 맨몸
local function build(def: Npcs.Npc): Model?
	local look = Npcs.look(def.id)
	if not look then
		return nil
	end
	local tries = {
		safeDescribe(look, true),
		safeDescribe(look, false),
		safeDescribe({ color = look.color, scales = look.scales }, false),
	}
	for _, desc in tries do
		local model = desc and createModel(desc)
		if model then
			return model
		end
	end
	return nil
end

local function loadTracks(humanoid: Humanoid): { [string]: AnimationTrack }
	local animator = humanoid:FindFirstChildOfClass("Animator")
	if not animator then
		animator = Instance.new("Animator")
		animator.Parent = humanoid
	end
	-- 멀리서 동작을 건너뛰면 고개 돌림(NpcLook)이 같은 자세 위에 겹쳐 쌓인다. 일곱 명뿐이라 꺼 둔다
	pcall(function()
		(animator :: any).PreferLodEnabled = false
	end)
	local tracks = {}
	for name, id in ANIMATIONS do
		local animation = Instance.new("Animation")
		animation.AnimationId = id
		local ok, track = pcall(function()
			return (animator :: Animator):LoadAnimation(animation)
		end)
		if ok then
			tracks[name] = track
		end
	end
	return tracks
end

local function play(npc: Live, name: string)
	for other, track in npc.tracks do
		if other ~= name and track.IsPlaying then
			track:Stop(0.25)
		end
	end
	local track = npc.tracks[name]
	if track and not track.IsPlaying then
		track:Play(0.25)
	end
end

local function nameTag(npc: Live)
	local adornee = npc.head or npc.root
	local gui = Instance.new("BillboardGui")
	gui.Name = "이름"
	gui.Size = UDim2.fromOffset(160, 26)
	gui.StudsOffset = Vector3.new(0, 2.2, 0)
	gui.MaxDistance = 45
	gui.LightInfluence = 0
	gui.Adornee = adornee
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.FontFace = Font.fromEnum(Enum.Font.GothamMedium)
	label.TextScaled = true
	label.Text = npc.def.name
	label.TextColor3 = Color3.fromRGB(240, 228, 200)
	label.TextStrokeTransparency = 0.5
	label.Parent = gui
	gui.Parent = adornee
end

local function seatOf(id: string): Seat?
	for _, seat in Workspace:GetDescendants() do
		if seat:IsA("Seat") and seat:GetAttribute("NpcSeat") == id then
			return seat
		end
	end
	return nil
end

-- 한 사람 띄우기
local function spawn(def: Npcs.Npc)
	local model = build(def)
	if not model then
		return
	end
	model.Name = def.name
	local animate = model:FindFirstChild("Animate")
	if animate then
		animate:Destroy()
	end
	local humanoid = model:FindFirstChildOfClass("Humanoid")
	local root = model:FindFirstChild("HumanoidRootPart") :: BasePart?
	if not humanoid or not root then
		model:Destroy()
		return
	end
	humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	humanoid.BreakJointsOnDeath = false
	humanoid.RequiresNeck = false
	for _, state in
		{
			Enum.HumanoidStateType.Dead,
			Enum.HumanoidStateType.FallingDown,
			Enum.HumanoidStateType.Ragdoll,
			Enum.HumanoidStateType.Climbing,
			Enum.HumanoidStateType.Swimming,
			Enum.HumanoidStateType.Jumping,
		}
	do
		humanoid:SetStateEnabled(state, false)
	end
	model:SetAttribute("NpcId", def.id)
	model:AddTag("Npc")

	local seat = if def.seated then seatOf(def.id) else nil
	local start = if seat then seat.CFrame * CFrame.new(0, 3, 0) else CFrame.new(def.position + Vector3.new(0, 3.5, 0))
	model:PivotTo(start)
	model.Parent = folder
	setGroup(model, NPC_GROUP)

	local npc: Live = {
		def = def,
		model = model,
		humanoid = humanoid,
		root = root,
		head = model:FindFirstChild("Head") :: BasePart?,
		tracks = loadTracks(humanoid),
		pausedUntil = 0,
	}
	live[def.id] = npc
	-- 앉은 노인은 맵 표지판이 이름을 보여 준다
	if not def.seated then
		nameTag(npc)
	end

	if seat then
		seat:Sit(humanoid)
		play(npc, "sit")
		return
	elseif def.seated then
		-- 앉을 자리가 없는 맵(예전 판): 그 자리에 서 있게 한다
		root.Anchored = true
		play(npc, "idle")
		return
	end

	-- 걷는 사람: 서버가 물리를 맡고, 걸을 때와 설 때 동작을 바꾼다
	humanoid.WalkSpeed = def.walkSpeed or 6
	pcall(function()
		if root:CanSetNetworkOwnership() then
			root:SetNetworkOwner(nil)
		end
	end)
	humanoid.Running:Connect(function(speed)
		if speed > 0.75 then
			play(npc, "walk")
			local walk = npc.tracks.walk
			if walk then
				walk:AdjustSpeed(speed / 6.4 / math.max(0.5, humanoid.HipHeight / 2))
			end
		else
			play(npc, "idle")
		end
	end)
	play(npc, "idle")

	if not def.seated then
		local prompt = Instance.new("ProximityPrompt")
		prompt.ActionText = "말 걸기"
		prompt.ObjectText = def.name
		prompt.KeyboardKeyCode = Enum.KeyCode.F
		-- 영초·노인 버튼과 F 를 나눠 쓰므로 조금 눌러야 하고, 가까이 가야 뜬다
		prompt.HoldDuration = 0.3
		prompt.MaxActivationDistance = 7
		prompt.RequiresLineOfSight = false
		local attachment = Instance.new("Attachment")
		attachment.Position = Vector3.new(0, 1, 0)
		attachment.Parent = root
		prompt.Parent = attachment
		prompt.Triggered:Connect(function(player)
			Villagers.talk(player, def.id)
		end)
	end

	task.spawn(function()
		local route = def.route or { def.position }
		local index = 1
		local resume = false -- 말 거느라 멈췄으면 가던 곳으로 다시 간다
		while npc.model.Parent do
			if os.clock() < npc.pausedUntil then
				resume = true
				task.wait(0.5)
				continue
			end
			if not resume then
				index = index % #route + 1
			end
			resume = false
			local goal = route[index]
			-- MoveTo 는 8초가 지나면 저절로 끝나므로 5초마다 다시 건다. 12초 안에 못 닿으면 걸린 것으로 본다
			local finished, reached = false, false
			local connection = humanoid.MoveToFinished:Connect(function(ok)
				finished, reached = true, ok
			end)
			humanoid:MoveTo(goal)
			local started = os.clock()
			local lastIssue = started
			while not reached and os.clock() - started < 12 do
				if os.clock() < npc.pausedUntil then
					break
				end
				if finished and not reached then
					finished = false
					humanoid:MoveTo(goal)
					lastIssue = os.clock()
				elseif os.clock() - lastIssue > 5 then
					humanoid:MoveTo(goal)
					lastIssue = os.clock()
				end
				task.wait(0.25)
			end
			connection:Disconnect()
			if os.clock() < npc.pausedUntil then
				continue
			end
			if not reached then
				-- 어디 걸렸으면 가려던 자리로 옮겨 놓는다
				model:PivotTo(CFrame.new(goal + Vector3.new(0, 3.5, 0)))
			end
			task.wait(2 + (#def.name % 3))
		end
	end)
end

-- 말풍선 (말을 건 사람에게만)
function Villagers.say(player: Player, id: string, text: string)
	local npc = live[id]
	local part = npc and (npc.head or npc.root)
	if part then
		Sync.remotes.Speak:FireClient(player, part, text)
	else
		Sync.notify(player, string.format("%s: %s", Npcs.byId[id].name, text), "info")
	end
end

-- 평소 대사를 차례로 (사람마다 따로 센다)
function Villagers.talk(player: Player, id: string)
	local def = Npcs.byId[id]
	if not def then
		return
	end
	local npc = live[id]
	if npc and not def.seated then
		-- 걷던 사람은 멈춰서 말하는 쪽을 본다
		npc.pausedUntil = os.clock() + TALK_PAUSE
		npc.humanoid:MoveTo(npc.root.Position)
		local character = player.Character
		local target = character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
		if target then
			local from = npc.root.Position
			npc.model:PivotTo(CFrame.lookAt(from, Vector3.new(target.Position.X, from.Y, target.Position.Z)))
		end
	end
	local counts = lineIndex[player] or {}
	lineIndex[player] = counts
	local index = (counts[id] or 0) % #def.lines + 1
	counts[id] = index
	Villagers.say(player, id, def.lines[index])
end

function Villagers.start()
	folder = Instance.new("Folder")
	folder.Name = "마을사람"
	folder.Parent = Workspace
	setupCollisionGroups()
	for _, def in Npcs.list do
		task.spawn(spawn, def)
	end
	Players.PlayerRemoving:Connect(function(player)
		lineIndex[player] = nil
	end)
end

return Villagers
