-- 마을 사람이 가까이 온 나를 고개 돌려 본다. 내 화면에서만 돌리므로 서버 부담이 없다.
-- 애니메이션이 목 관절(Neck)에 자세를 쓴 뒤, 그 위에 돌림을 얹는다.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local NpcLook = {}

local RANGE = 16
local MAX_YAW = math.rad(60)
local MAX_PITCH = math.rad(25)

local player = Players.LocalPlayer
local state: { [Model]: { yaw: number, pitch: number } } = {}

local function neckOf(model: Model): any
	local head = model:FindFirstChild("Head")
	local neck = head and head:FindFirstChild("Neck")
	if neck and (neck:IsA("Motor6D") or neck:IsA("AnimationConstraint")) then
		return neck
	end
	return nil
end

local function step(dt: number)
	local character = player.Character
	local myHead = character and character:FindFirstChild("Head") :: BasePart?
	for _, model in CollectionService:GetTagged("Npc") do
		if not model:IsA("Model") or not model.Parent then
			continue
		end
		local neck = neckOf(model)
		local torso = model:FindFirstChild("UpperTorso") :: BasePart?
		if not neck or not torso then
			continue
		end
		local look = state[model] or { yaw = 0, pitch = 0 }
		state[model] = look
		local targetYaw, targetPitch = 0, 0
		if myHead and (myHead.Position - torso.Position).Magnitude < RANGE then
			local ok, rel = pcall(function()
				return (torso.CFrame * neck.C0):PointToObjectSpace(myHead.Position)
			end)
			if ok then
				targetYaw = math.clamp(math.atan2(-rel.X, -rel.Z), -MAX_YAW, MAX_YAW)
				targetPitch =
					math.clamp(math.atan2(rel.Y, math.sqrt(rel.X * rel.X + rel.Z * rel.Z)), -MAX_PITCH, MAX_PITCH)
			end
		end
		local blend = 1 - math.exp(-6 * dt)
		look.yaw += (targetYaw - look.yaw) * blend
		look.pitch += (targetPitch - look.pitch) * blend
		-- 동작 계산을 건너뛴 프레임에는 지난 자세가 남아 있으므로 얹지 않는다 (겹쳐 돌아가지 않게)
		local humanoid = model:FindFirstChildOfClass("Humanoid")
		local animator = humanoid and humanoid:FindFirstChildOfClass("Animator")
		local throttled = false
		if animator then
			pcall(function()
				throttled = (animator :: any).EvaluationThrottled == true
			end)
		end
		if not throttled and (math.abs(look.yaw) > 0.001 or math.abs(look.pitch) > 0.001) then
			pcall(function()
				neck.Transform = CFrame.Angles(look.pitch, look.yaw, 0) * neck.Transform
			end)
		end
	end
	for model in state do
		if not model.Parent then
			state[model] = nil
		end
	end
end

function NpcLook.start()
	local signal = (RunService :: any).PreSimulation or RunService.Stepped
	if signal == RunService.Stepped then
		RunService.Stepped:Connect(function(_, dt)
			step(dt)
		end)
	else
		signal:Connect(step)
	end
end

return NpcLook
