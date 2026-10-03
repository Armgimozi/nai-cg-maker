-- 무기 든 몸짓 (클라이언트). 무기(Weapon 태그 도구)를 든 가까운 캐릭터마다, 남의 캐릭터까지, 이 클라이언트에서
-- 팔·허리·목 관절 Transform 을 매 프레임 덮어쓴다. 자세와 휘두르기 계산은 shared/WeaponPoses.luau 에 있다.
--
-- RunService.PreSimulation 은 Animator 가 걸음·기본 도구 자세를 쓴 다음에 돈다. 그래서
--   팔(어깨·팔꿈치·손목)은 우리 값으로 덮어쓰고 (기본 toolnone 자세가 보이지 않는다)
--   허리·목·뿌리·엉덩이·무릎은 Animator 값 앞에 덧곱한다 (걷기는 그대로 걷는다).
-- R15 관절은 Motor6D 이거나 AnimationConstraint(아바타 관절 개선)다. 둘 다 Transform 이 있다. R6 은 건너뛴다.
--
-- 내 휘두르기는 도구 Activated 를 여기서도 받아 바로 보여 준다 (서버 판정을 기다리지 않는다).
-- 남의 휘두르기는 서버가 모두에게 보내는 "swing" 소식으로 (CombatHud.event → WeaponAnim.remoteSwing).
-- 내가 맞혀 WeaponEffects.hitstop() 이 남아 있는 동안은 내 몸짓을 멈춘다.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Combat = require(Shared.Combat)
local Mobs = require(Shared.Mobs)
local WeaponPoses = require(Shared.WeaponPoses)
local WeaponEffects = require(script.Parent.WeaponEffects)

local WeaponAnim = {}

local player = Players.LocalPlayer
local RANGE = 160 -- 카메라에서 이보다 먼 캐릭터는 기본 애니메이션 그대로 둔다
local BLEND = 0.1 -- 들고 내릴 때 섞는 시간(초)
local RETRY = 1 -- 관절을 못 찾았으면 이만큼 뒤에 다시 본다
local MAX_FREEZE = 0.15 -- 한 번에 멈추는 몸짓 시간 상한
local WAVE_MEMORY = 0.8 -- 내가 부채를 쳤다고 기억하는 시간 (서버 "wave" 를 겹쳐 그리지 않으려고)

-- 관절 이름 → 그 관절이 든 몸 부분
local ARMS = {
	RightShoulder = "RightUpperArm",
	RightElbow = "RightLowerArm",
	RightWrist = "RightHand",
	LeftShoulder = "LeftUpperArm",
	LeftElbow = "LeftLowerArm",
	LeftWrist = "LeftHand",
}
local BODY = {
	Waist = "UpperTorso",
	Neck = "Head",
	Root = "LowerTorso",
	RightHip = "RightUpperLeg",
	LeftHip = "LeftUpperLeg",
	RightKnee = "RightLowerLeg",
	LeftKnee = "LeftLowerLeg",
}
-- 이 상태에서는 무기 자세를 풀어 Animator 에 맡긴다
local LOOSE = {
	[Enum.HumanoidStateType.Seated] = true,
	[Enum.HumanoidStateType.Climbing] = true,
	[Enum.HumanoidStateType.Swimming] = true,
	[Enum.HumanoidStateType.Dead] = true,
	[Enum.HumanoidStateType.Physics] = true,
	[Enum.HumanoidStateType.Ragdoll] = true,
	[Enum.HumanoidStateType.FallingDown] = true,
	[Enum.HumanoidStateType.PlatformStanding] = true,
}

type Swing = {
	attack: WeaponPoses.Attack,
	from: WeaponPoses.Pose,
	t: number,
	kind: string,
	grade: number,
	combo: number,
	mine: boolean,
	waved: boolean,
}

type State = {
	character: Model,
	humanoid: Humanoid,
	root: BasePart,
	joints: { [string]: any }, -- Motor6D | AnimationConstraint
	rig: WeaponPoses.Rig,
	weight: number,
	kind: string,
	grade: number,
	tool: Tool?,
	swing: Swing?,
	current: WeaponPoses.Pose?,
	written: { [string]: CFrame }, -- 지난 프레임에 우리가 쓴 값
	base: { [string]: CFrame }, -- Animator 가 쓴 값 (Animator 가 쉬면 지난 값)
	phase: number,
}

local states: { [Model]: State } = {}
local failed: { [Model]: number } = {}
local started = false

-- 내 휘두르기
local mine = {
	tool = nil :: Tool?,
	connection = nil :: RBXScriptConnection?,
	last = -math.huge,
	kind = "",
	combo = 0,
	freezeUntil = 0,
	fanAt = -math.huge,
}

local function isJoint(item: Instance?): boolean
	return item ~= nil and (item:IsA("Motor6D") or item:IsA("AnimationConstraint"))
end

-- 관절의 C0, C1 (AnimationConstraint 는 붙이개 CFrame)
local function offsets(joint: any): (CFrame, CFrame)
	if joint:IsA("Motor6D") then
		return joint.C0, joint.C1
	end
	local a0, a1 = joint.Attachment0, joint.Attachment1
	return if a0 then a0.CFrame else CFrame.identity, if a1 then a1.CFrame else CFrame.identity
end

local function measureArm(character: Model, joints: { [string]: any }, side: string): WeaponPoses.Arm
	local s0, s1 = offsets(joints[side .. "Shoulder"])
	local e0, e1 = offsets(joints[side .. "Elbow"])
	local w0, w1 = offsets(joints[side .. "Wrist"])
	local handPart = character:FindFirstChild(side .. "Hand")
	local grip = handPart and handPart:FindFirstChild(side .. "GripAttachment")
	local default = WeaponPoses.DEFAULT_RIG.right
	return {
		s0 = s0,
		s1 = s1,
		e0 = e0,
		e1 = e1,
		w0 = w0,
		w1 = w1,
		grip = if grip and grip:IsA("Attachment") then grip.CFrame else default.grip,
	}
end

local function setup(character: Model): State?
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	local root = character:FindFirstChild("HumanoidRootPart")
	if not humanoid or humanoid.RigType ~= Enum.HumanoidRigType.R15 or not root or not root:IsA("BasePart") then
		return nil
	end
	local joints = {}
	for _, list in { ARMS, BODY } do
		for name, partName in list do
			local part = character:FindFirstChild(partName)
			local joint = part and part:FindFirstChild(name)
			if isJoint(joint) then
				joints[name] = joint
			elseif ARMS[name] or name == "Waist" then
				return nil -- 팔과 허리는 꼭 있어야 한다
			end
		end
	end
	local rig = WeaponPoses.rig(measureArm(character, joints, "Right"), measureArm(character, joints, "Left"))
	return {
		character = character,
		humanoid = humanoid,
		root = root,
		joints = joints,
		rig = rig,
		weight = 0,
		kind = "sword",
		grade = 1,
		tool = nil,
		swing = nil,
		current = nil,
		written = {},
		base = {},
		phase = math.random() * 10,
	}
end

local function stateOf(character: Model?): State?
	if not character or not character.Parent then
		return nil
	end
	local state = states[character]
	if state then
		return state
	end
	if os.clock() < (failed[character] or 0) then
		return nil
	end
	state = setup(character)
	if state then
		states[character] = state
		failed[character] = nil
	else
		failed[character] = os.clock() + RETRY
	end
	return state
end

-- 캐릭터가 든 무기 도구
local function weaponOf(character: Model): Tool?
	local tool = character:FindFirstChildOfClass("Tool")
	if tool and (tool:HasTag("Weapon") or tool:GetAttribute("Weapon") ~= nil) then
		return tool
	end
	return nil
end

-- 지난번에 우리가 쓴 값이 그대로면 Animator 가 이 프레임을 건너뛴 것이다 (멀리 있거나 쉬는 중)
local function same(a: CFrame, b: CFrame): boolean
	return (a.Position - b.Position).Magnitude < 1e-4
		and a.LookVector:Dot(b.LookVector) > 0.99999
		and a.UpVector:Dot(b.UpVector) > 0.99999
end

local function baseOf(state: State, name: string, joint: any): CFrame
	local now = joint.Transform
	local wrote = state.written[name]
	if wrote and same(now, wrote) then
		return state.base[name] or CFrame.identity
	end
	state.base[name] = now
	return now
end

-- 우리 값을 다 거두고 Animator 값으로 되돌린다
local function release(state: State)
	for name, joint in state.joints do
		local wrote = state.written[name]
		if wrote then
			if joint.Parent and same(joint.Transform, wrote) then
				joint.Transform = state.base[name] or CFrame.identity
			end
			state.written[name] = nil
		end
	end
end

local function write(state: State, pose: WeaponPoses.Pose)
	local arms, body = WeaponPoses.solve(state.rig, pose)
	local w = state.weight
	for name, value in arms do
		local joint = state.joints[name]
		if joint then
			local base = baseOf(state, name, joint)
			local out = if w >= 1 then value else base:Lerp(value, w)
			joint.Transform = out
			state.written[name] = out
		end
	end
	for name, value in body do
		local joint = state.joints[name]
		if joint then
			local base = baseOf(state, name, joint)
			local out = (if w >= 1 then value else CFrame.identity:Lerp(value, w)) * base
			joint.Transform = out
			state.written[name] = out
		end
	end
end

-- 부채 바람칼이 닿을 곳: 앞 줄에서 처음 맞는 요수 (서버 CombatService 와 같은 판정), 없으면 닿는 끝
local function waveTarget(root: BasePart, from: Vector3, weapon: Combat.Weapon): Vector3
	local kind = Combat.KINDS[weapon.kind]
	local look = root.CFrame.LookVector
	local flat = Vector3.new(look.X, 0, look.Z)
	if flat.Magnitude < 0.1 then
		return from + look * kind.range
	end
	flat = flat.Unit
	local origin = root.Position
	local best: Vector3? = nil
	local bestDistance = math.huge
	for _, model in CollectionService:GetTagged("Mob") do
		local def = Mobs.byId[model:GetAttribute("MobId") or ""]
		local body = model:FindFirstChild("HumanoidRootPart")
		local hp = model:GetAttribute("Hp")
		if def and body and body:IsA("BasePart") and (type(hp) ~= "number" or hp > 0) then
			local p = body.Position
			if
				math.abs(p.Y - origin.Y) < def.height + 6
				and Combat.inReach(origin.X, origin.Z, flat.X, flat.Z, p.X, p.Z, def.radius, weapon)
			then
				local distance = (p - origin).Magnitude
				if distance < bestDistance then
					best, bestDistance = p, distance
				end
			end
		end
	end
	return best or (from + flat * kind.range)
end

local function waveFrom(state: State): Vector3
	local tool = state.tool
	local handle = tool and tool:FindFirstChild("Handle")
	local tip = handle and handle:FindFirstChild("TrailTip")
	if tip and tip:IsA("Attachment") then
		return tip.WorldPosition
	end
	return state.root.Position + state.root.CFrame.LookVector * 2
end

local function startSwing(state: State, kind: string, grade: number, combo: number, isMine: boolean)
	local attack = WeaponPoses.attack(kind, combo)
	state.swing = {
		attack = attack,
		from = state.current or WeaponPoses.idle(kind, os.clock() + state.phase),
		t = 0,
		kind = kind,
		grade = grade,
		combo = combo,
		mine = isMine,
		waved = false,
	}
	if state.tool then
		-- 휘두르기 시작에 부른다: 소리는 지금, 자취는 젖힘이 끝난 뒤 벰·따라감 동안 (WeaponEffects 가 나눈다)
		WeaponEffects.swing(
			state.character,
			state.tool,
			kind,
			grade,
			combo,
			attack.windup + attack.strike + attack.follow
		)
	end
end

local function step(state: State, dt: number, now: number)
	local character = state.character
	local tool = weaponOf(character)
	local humanoid = state.humanoid
	local holding = tool ~= nil
		and humanoid.Health > 0
		and not humanoid.Sit
		and not LOOSE[humanoid:GetState()]
		and humanoid.RigType == Enum.HumanoidRigType.R15
	if tool and tool ~= state.tool then
		state.tool = tool
		local kind = tool:GetAttribute("Weapon")
		state.kind = if type(kind) == "string" and Combat.KINDS[kind] then kind else "sword"
		local grade = tool:GetAttribute("Grade")
		state.grade = if type(grade) == "number" then grade else 1
		-- 몸 크기가 바뀌었을 수 있다 (아바타가 늦게 입혀짐)
		local remeasured = setup(character)
		if remeasured then
			state.rig = remeasured.rig
		end
	elseif not tool then
		state.tool = nil
	end
	local target = if holding then 1 else 0
	if state.weight < target then
		state.weight = math.min(target, state.weight + dt / BLEND)
	elseif state.weight > target then
		state.weight = math.max(target, state.weight - dt / BLEND)
	end
	if state.weight <= 0 then
		if state.swing and state.swing.mine and not state.swing.waved then
			mine.fanAt = -math.huge -- 바람칼을 못 날렸으니 서버 것을 그린다
		end
		state.swing = nil
		state.current = nil
		release(state)
		return
	end

	local kind = state.kind
	local idle = WeaponPoses.idle(kind, now + state.phase)
	local pose = idle
	local swing = state.swing
	if swing and swing.kind ~= kind then
		if swing.mine and not swing.waved then
			mine.fanAt = -math.huge
		end
		swing = nil
		state.swing = nil
	end
	if swing then
		local advance = dt
		if swing.mine then
			-- 내가 맞혔으면 잠깐 멈춘다 (WeaponEffects 가 남은 시간을 알려 준다)
			local stop = WeaponEffects.hitstop()
			if stop > 0 and swing.t >= swing.attack.windup then
				mine.freezeUntil = math.max(mine.freezeUntil, now + math.min(stop, MAX_FREEZE))
			end
			if now < mine.freezeUntil then
				advance = 0
			end
		end
		swing.t += advance
		local attack = swing.attack
		-- 부채: 벰이 닿는 순간 내 바람칼을 바로 날린다 (서버 "wave" 는 남의 것만 그린다)
		if swing.mine and kind == "fan" and not swing.waved and swing.t >= attack.hit then
			swing.waved = true
			local from = waveFrom(state)
			WeaponEffects.wave(
				from,
				waveTarget(state.root, from, { kind = kind, grade = swing.grade }),
				swing.grade,
				false
			)
		end
		if swing.t >= attack.duration then
			state.swing = nil
		else
			pose = WeaponPoses.sample(attack, swing.from, idle, swing.t)
		end
	end
	state.current = pose
	write(state, pose)
end

local function update(dt: number)
	local now = os.clock()
	local camera = Workspace.CurrentCamera
	local eye = if camera then camera.CFrame.Position else nil
	local seen: { [Model]: boolean } = {}
	for _, other in Players:GetPlayers() do
		local character = other.Character
		if character then
			seen[character] = true
			local state = states[character]
			local root = character:FindFirstChild("HumanoidRootPart")
			local near = eye == nil or (root and root:IsA("BasePart") and (root.Position - eye).Magnitude < RANGE)
			if not near then
				if state then
					release(state)
					state.weight = 0
					state.swing = nil
				end
			elseif state or weaponOf(character) then
				state = stateOf(character)
				if state then
					step(state, dt, now)
				end
			end
		end
	end
	for character in states do
		if not seen[character] or not character.Parent then
			states[character] = nil
		end
	end
	for character in failed do
		if not character.Parent then
			failed[character] = nil
		end
	end
end

-- 내가 든 무기를 휘둘렀다 (클라이언트 Activated). 서버와 같은 간격으로만 받는다
local function onActivated(tool: Tool)
	local character = player.Character
	if not character or tool.Parent ~= character then
		return
	end
	local kindId = tool:GetAttribute("Weapon")
	local kind = if type(kindId) == "string" then Combat.KINDS[kindId] else nil
	if not kind then
		return
	end
	local now = os.clock()
	if now - mine.last < kind.cooldown * 0.9 then
		return
	end
	if mine.kind ~= kind.id or now - mine.last > WeaponPoses.COMBO_RESET then
		mine.combo = 0
	end
	mine.combo = mine.combo % (WeaponPoses.COMBO[kind.id] or 1) + 1
	mine.kind = kind.id
	mine.last = now
	local state = stateOf(character)
	if state then
		if kind.ranged then
			mine.fanAt = now -- 바람칼은 여기서 날린다 (step)
		end
		state.tool = tool
		state.kind = kind.id
		local grade = tool:GetAttribute("Grade")
		state.grade = if type(grade) == "number" then grade else 1
		startSwing(state, kind.id, state.grade, mine.combo, true)
	end
end

local function watchTool()
	local character = player.Character
	local tool = character and weaponOf(character)
	if tool == mine.tool then
		return
	end
	if mine.connection then
		mine.connection:Disconnect()
		mine.connection = nil
	end
	mine.tool = tool
	if tool then
		mine.connection = tool.Activated:Connect(function()
			onActivated(tool)
		end)
	end
end

-- 남이 휘둘렀다 (서버 "swing" 소식). 내 것은 이미 Activated 로 보여 주었으므로 넘긴다
function WeaponAnim.remoteSwing(payload: { [string]: any })
	local who = payload.player
	if typeof(who) ~= "Instance" or not who:IsA("Player") or who == player then
		return
	end
	local kind = payload.weapon
	if type(kind) ~= "string" or not Combat.KINDS[kind] then
		return
	end
	local state = stateOf(who.Character)
	if not state then
		return
	end
	local tool = weaponOf(state.character)
	if tool then
		state.tool = tool
	end
	state.kind = kind
	state.grade = tonumber(payload.grade) or state.grade
	startSwing(state, kind, state.grade, tonumber(payload.combo) or 1, false)
end

-- 서버가 보낸 내 부채 "wave" 를 그릴지: 방금 내가 부채를 쳐서 이미 그렸으면 true (한 번만)
function WeaponAnim.consumeWave(): boolean
	if os.clock() - mine.fanAt < WAVE_MEMORY then
		mine.fanAt = -math.huge
		return true
	end
	return false
end

function WeaponAnim.start()
	if started then
		return
	end
	started = true
	RunService.PreSimulation:Connect(function(dt: number)
		watchTool()
		update(dt)
	end)
end

return WeaponAnim
