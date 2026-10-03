-- 요수 몸짓. 서버는 요수의 뿌리(HumanoidRootPart)만 옮기고, 가까운 요수의 몸은 여기서 흔든다.
-- 몸 메시는 뿌리에 Motor6D "Body" 로 붙어 있어 Transform 만 바꾸면 된다 (server/MobService.luau).
--   quad     네 발 짐승. 뼈가 있으면 대각선 다리끼리 함께 걷고, 머리·꼬리도 움직인다
--   serpent  좌우로 굽이친다
--   bird     둥실 뜨고 날갯짓하듯 오르내리며, 돌 때 기운다
--   crawler  낮게 붙어 빠르게 떤다
--   biped    무겁게 좌우로 흔들리며 걷는다
-- 덤빌 때(Strike 속성): 뜸 동안 뒤로 웅크렸다가 앞으로 덮친다.

local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local MobAnimator = {}

local RANGE = 180
local LUNGE_TIME = 0.35
local LEGS = { FL = 0, BR = 0, FR = math.pi, BL = math.pi } -- 대각선 다리끼리 같은 박자

type State = {
	model: Model,
	root: BasePart,
	motor: Motor6D,
	bones: { [string]: Bone },
	anim: string,
	size: number,
	phase: number,
	yaw: number,
	bank: number,
}

local states: { [Model]: State } = {}

local function setup(model: Instance)
	if not model:IsA("Model") or states[model] then
		return
	end
	local root = model:WaitForChild("HumanoidRootPart", 5)
	local motor = root and root:WaitForChild("Body", 5)
	if not root or not root:IsA("BasePart") or not motor or not motor:IsA("Motor6D") or not model.Parent then
		return
	end
	local bones = {}
	for _, item in model:GetDescendants() do
		if item:IsA("Bone") then
			bones[item.Name] = item
		end
	end
	local _, yaw = root.CFrame:ToOrientation()
	states[model] = {
		model = model,
		root = root,
		motor = motor,
		bones = bones,
		anim = model:GetAttribute("Anim") or "quad",
		size = model:GetAttribute("Size") or 6,
		phase = math.random() * math.pi * 2,
		yaw = yaw,
		bank = 0,
	}
end

-- 덤비기: 웅크림(0~1)과 덮침(0~1~0)
local function strike(model: Model, now: number): (number, number)
	local at = model:GetAttribute("Strike")
	if type(at) ~= "number" then
		return 0, 0
	end
	local windup = model:GetAttribute("Windup") or 0.4
	local t = now - at
	if t < -windup or t > LUNGE_TIME then
		return 0, 0
	end
	if t < 0 then
		return math.clamp(1 + t / windup, 0, 1), 0
	end
	return 0, math.sin(math.clamp(t / LUNGE_TIME, 0, 1) * math.pi)
end

local function legs(state: State, moving: number, lunge: number, t: number)
	local b = state.bones
	for leg, offset in LEGS do
		local s = math.sin(state.phase + offset)
		local upper, lower = b[leg .. "_Upper"], b[leg .. "_Lower"]
		if upper then
			upper.Transform = CFrame.Angles(math.rad(24) * s * moving, 0, 0)
		end
		if lower then
			lower.Transform = CFrame.Angles(math.rad(20) * math.max(0, -math.cos(state.phase + offset)) * moving, 0, 0)
		end
	end
	local breathe = math.sin(t * 2.2)
	if b.Head then
		b.Head.Transform = CFrame.Angles(math.rad(-5 * breathe * (1 - moving) + 22 * lunge), 0, 0)
	end
	if b.Tail then
		b.Tail.Transform = CFrame.Angles(0, math.rad(15 + 10 * moving) * math.sin(t * 5), 0)
	end
end

local function step(state: State, dt: number, now: number, t: number)
	local root = state.root
	local velocity = root.AssemblyLinearVelocity
	local speed = Vector3.new(velocity.X, 0, velocity.Z).Magnitude
	local moving = math.clamp(speed / 8, 0, 1)
	local L = state.size
	local stride = math.max(2, L * 0.9)
	state.phase += dt * (speed / stride) * math.pi * 2 + dt * 1.2
	local crouch, lunge = strike(state.model, now)
	local phase = state.phase
	local breathe = math.sin(t * 2.2) * 0.01 * L

	-- 도는 빠르기 (나는 요수가 기울 때)
	local _, yaw = root.CFrame:ToOrientation()
	local turn = (yaw - state.yaw + math.pi) % (math.pi * 2) - math.pi
	state.yaw = yaw
	local turnRate = if dt > 0 then turn / dt else 0
	state.bank += (math.clamp(-turnRate * 0.25, -0.6, 0.6) - state.bank) * math.min(1, dt * 4)

	local anim = state.anim
	local cf: CFrame
	if anim == "serpent" then
		local sway = math.sin(t * 3 + phase) * math.rad(8 + 6 * moving)
		cf = CFrame.new(math.sin(phase) * 0.03 * L, breathe - crouch * 0.05 * L, crouch * 0.08 * L - lunge * 0.3 * L)
			* CFrame.Angles(math.rad(crouch * 8 - lunge * 14), sway, 0)
	elseif anim == "bird" then
		local hover = math.sin(t * 2.4) * 0.6 + math.sin(t * 7) * 0.15
		cf = CFrame.new(0, hover + crouch * 0.6 - lunge * 1.5, crouch * 0.5 - lunge * 0.35 * L)
			* CFrame.Angles(math.rad(math.sin(t * 7) * 3 + crouch * 10 - lunge * 22), 0, state.bank)
	elseif anim == "crawler" then
		local skitter = math.sin(phase * 2) * 0.015 * L * moving
		cf = CFrame.new(0, skitter + breathe - crouch * 0.04 * L, crouch * 0.06 * L - lunge * 0.25 * L)
			* CFrame.Angles(math.rad(crouch * 5 - lunge * 8), math.sin(phase) * math.rad(4) * moving, 0)
	elseif anim == "biped" then
		local bob = math.abs(math.sin(phase)) * 0.035 * L * moving
		cf = CFrame.new(0, bob + breathe - crouch * 0.03 * L, crouch * 0.05 * L - lunge * 0.2 * L)
			* CFrame.Angles(math.rad(crouch * 6 - lunge * 12), 0, math.sin(phase) * math.rad(5) * moving)
	else
		local bob = math.abs(math.sin(phase)) * 0.05 * L * moving
		cf = CFrame.new(0, bob + breathe - crouch * 0.05 * L, crouch * 0.07 * L - lunge * 0.3 * L)
			* CFrame.Angles(math.rad(crouch * 6 - lunge * 10), 0, math.sin(phase) * math.rad(3) * moving)
		legs(state, moving, lunge, t)
	end
	state.motor.Transform = cf
end

function MobAnimator.start()
	for _, model in CollectionService:GetTagged("Mob") do
		task.spawn(setup, model)
	end
	CollectionService:GetInstanceAddedSignal("Mob"):Connect(function(model)
		task.spawn(setup, model)
	end)
	CollectionService:GetInstanceRemovedSignal("Mob"):Connect(function(model)
		states[model :: Model] = nil
	end)
	RunService.Stepped:Connect(function(t, dt)
		local camera = Workspace.CurrentCamera
		if not camera then
			return
		end
		local eye = camera.CFrame.Position
		local now = Workspace:GetServerTimeNow()
		for model, state in states do
			if not model.Parent or not state.root.Parent then
				states[model] = nil
			elseif (state.root.Position - eye).Magnitude < RANGE then
				step(state, dt, now, t)
			end
		end
	end)
end

return MobAnimator
