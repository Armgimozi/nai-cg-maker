-- 천애(天涯): 바다 끝. 보이지 않는 벽은 없다.
--   Land.SWIM 보다 멀리 헤엄치면 해류가 가운데 쪽으로 밀어낸다 (멀수록 세게).
--   천애 너머로 떨어지거나 아주 깊이 떨어지면 가장 가까운 전송진 곁에서 깨운다.
-- 캐릭터는 플레이어 쪽에서 물리를 돌리므로, 미는 힘은 서버가 VectorForce 로 걸어 둔다(복제되어 그쪽에서 돈다).

local RunService = game:GetService("RunService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Land = require(Shared.Land)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Waypoints = require(script.Parent.Waypoints)

local Edge = {}

local TICK = 0.3
local PUSH_MIN, PUSH_MAX = 25, 90 -- 해류가 미는 가속 (스터드/초²)
local FELL_RADIUS = Land.EDGE + 6 -- 이보다 멀면 떨어졌다
local FELL_DEPTH = -60 -- 바다 끝 근처에서 이보다 낮으면 떨어졌다
local VOID_DEPTH = -200 -- 어디서든 이보다 낮으면
local NOTICE_EVERY = 60

local lastNotice: { [Player]: number } = {}

-- 가운데 쪽으로 미는 세기 (0 이면 밀지 않는다). 순수 계산이라 테스트에서 부른다
function Edge.pushAccel(radius: number): number
	if radius <= Land.SWIM then
		return 0
	end
	local k = math.clamp((radius - Land.SWIM) / (Land.EDGE - Land.SWIM), 0, 1)
	return PUSH_MIN + (PUSH_MAX - PUSH_MIN) * k
end

-- 떨어졌는가
function Edge.fell(position: Vector3): boolean
	local radius = Vector3.new(position.X, 0, position.Z).Magnitude
	if radius > FELL_RADIUS or position.Y < VOID_DEPTH then
		return true
	end
	return position.Y < FELL_DEPTH and radius > Land.EDGE - 300
end

local function current(root: BasePart): VectorForce
	local force = root:FindFirstChild("해류")
	if force and force:IsA("VectorForce") then
		return force
	end
	local attachment = root:FindFirstChild("해류자리") or Instance.new("Attachment")
	attachment.Name = "해류자리"
	attachment.Parent = root
	local made = Instance.new("VectorForce")
	made.Name = "해류"
	made.Attachment0 = attachment :: Attachment
	made.RelativeTo = Enum.ActuatorRelativeTo.World
	made.ApplyAtCenterOfMass = true
	made.Force = Vector3.zero
	made.Enabled = false
	made.Parent = root
	return made
end

local function notice(player: Player, text: string, kind: string)
	local now = os.clock()
	if now - (lastNotice[player] or -math.huge) >= NOTICE_EVERY then
		lastNotice[player] = now
		Sync.notify(player, text, kind)
	end
end

-- 가장 가까운 전송진 곁으로
local function rescue(player: Player, root: BasePart)
	local character = player.Character
	if not character then
		return
	end
	local here = Vector3.new(root.Position.X, 0, root.Position.Z)
	local best: BasePart? = nil
	local bestDistance = math.huge
	for _, pad in Waypoints.pads() do
		local d = (Vector3.new(pad.Position.X, 0, pad.Position.Z) - here).Magnitude
		if d < bestDistance then
			best, bestDistance = pad, d
		end
	end
	local target = if best then best.Position + Vector3.new(4, 4, 0) else Vector3.new(0, 8, 0)
	root.AssemblyLinearVelocity = Vector3.zero
	character:PivotTo(CFrame.new(target))
	lastNotice[player] = nil
	notice(player, "운해에 떨어졌다가 바닷가에서 깨어났다.", "bad")
end

local function step()
	for player, session in Session.all() do
		local root = Characters.root(player)
		if root and root.Parent then
			local position = root.Position
			if Edge.fell(position) then
				if not session.tribulation then
					rescue(player, root)
				end
			else
				local flat = Vector3.new(position.X, 0, position.Z)
				local accel = Edge.pushAccel(flat.Magnitude)
				local force = current(root)
				if accel > 0 then
					force.Force = -flat.Unit * root.AssemblyMass * accel
					force.Enabled = true
					notice(player, "거센 해류가 바다 끝에서 밀어낸다.", "bad")
				elseif force.Enabled then
					force.Enabled = false
				end
			end
		end
	end
end

function Edge.start()
	local elapsed = 0
	RunService.Heartbeat:Connect(function(dt)
		elapsed += dt
		if elapsed >= TICK then
			elapsed = 0
			step()
		end
	end)
	game:GetService("Players").PlayerRemoving:Connect(function(player)
		lastNotice[player] = nil
	end)
end

return Edge
