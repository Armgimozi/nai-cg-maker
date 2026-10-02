-- 클라이언트가 직접 처리하는 술법 효과.
-- 캐릭터 물리는 클라이언트 소유라서 경신술 돌진은 여기서 움직이고,
-- 영안 투시도 내 화면에만 보이면 되므로 여기서 Highlight 를 붙인다.

local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Skills = require(Shared.Skills)

local SIGHT_FOLDERS = { "영초", "비급" }
local SIGHT_COLOR = Color3.fromRGB(150, 236, 205)

local Effects = {}

local player = Players.LocalPlayer

function Effects.dash()
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if not root or not humanoid or humanoid.Health <= 0 then
		return
	end
	-- 움직이는 중이면 그쪽으로, 아니면 바라보는 쪽으로
	local direction = humanoid.MoveDirection
	if direction.Magnitude < 0.1 then
		direction = root.CFrame.LookVector
	end
	direction = Vector3.new(direction.X, 0, direction.Z)
	if direction.Magnitude < 0.01 then
		return
	end
	direction = direction.Unit

	local attachment = Instance.new("Attachment")
	attachment.Parent = root
	local push = Instance.new("LinearVelocity")
	push.Attachment0 = attachment
	push.MaxForce = math.huge
	push.RelativeTo = Enum.ActuatorRelativeTo.World
	push.VelocityConstraintMode = Enum.VelocityConstraintMode.Vector
	push.VectorVelocity = direction * Skills.EFFECT.dashSpeed + Vector3.new(0, 6, 0)
	push.Parent = root
	Debris:AddItem(push, Skills.EFFECT.dashTime)
	Debris:AddItem(attachment, Skills.EFFECT.dashTime)
end

local function highlight(model: Instance, duration: number)
	if not model:IsA("Model") or model:FindFirstChild("영안") then
		return
	end
	local glow = Instance.new("Highlight")
	glow.Name = "영안"
	glow.FillColor = SIGHT_COLOR
	glow.FillTransparency = 0.55
	glow.OutlineColor = Color3.new(1, 1, 1)
	glow.DepthMode = Enum.HighlightDepthMode.AlwaysOnTop
	glow.Parent = model
	Debris:AddItem(glow, duration)
end

function Effects.sight(duration: number)
	local connections = {}
	for _, name in SIGHT_FOLDERS do
		local folder = Workspace:FindFirstChild(name)
		if folder then
			for _, model in folder:GetChildren() do
				highlight(model, duration)
			end
			-- 영안을 켠 동안 새로 돋는 것도 보이게
			table.insert(
				connections,
				folder.ChildAdded:Connect(function(model)
					task.defer(highlight, model, duration)
				end)
			)
		end
	end
	task.delay(duration, function()
		for _, connection in connections do
			connection:Disconnect()
		end
	end)
end

return Effects
