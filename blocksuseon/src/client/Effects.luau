-- 클라이언트가 직접 처리하는 술법 효과.
-- 캐릭터 물리는 클라이언트 소유라서 경신술 돌진은 여기서 움직이고,
-- 영안 투시도 내 화면에만 보이면 되므로 여기서 Highlight 를 붙인다.

local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Skills = require(Shared.Skills)

local SIGHT_FOLDERS = { "영초", "비급", "별씨" }
local SIGHT_COLOR = Color3.fromRGB(150, 236, 205)

local Effects = {}

local player = Players.LocalPlayer

-- power: 결단기 비둔술이면 1보다 크다
function Effects.dash(power: number?)
	local strength = power or 1
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
	push.VectorVelocity = direction * Skills.EFFECT.dashSpeed * strength + Vector3.new(0, 6 + (strength - 1) * 30, 0)
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

-- Roblox 는 한 화면에 Highlight 를 31개까지만 그린다. 맵이 넓어 영초가 많으므로 가까운 것부터 25개만
local MAX_HIGHLIGHTS = 25

function Effects.sight(duration: number)
	local connections = {}
	local camera = Workspace.CurrentCamera
	local eye = if camera then camera.CFrame.Position else Vector3.zero
	local found = {}
	for _, name in SIGHT_FOLDERS do
		local folder = Workspace:FindFirstChild(name)
		if folder then
			for _, model in folder:GetChildren() do
				if model:IsA("Model") then
					table.insert(found, { model = model, d = (model:GetPivot().Position - eye).Magnitude })
				end
			end
		end
	end
	table.sort(found, function(a, b)
		return a.d < b.d
	end)
	for i = 1, math.min(MAX_HIGHLIGHTS, #found) do
		highlight(found[i].model, duration)
	end
	for _, name in SIGHT_FOLDERS do
		local folder = Workspace:FindFirstChild(name)
		if folder then
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
