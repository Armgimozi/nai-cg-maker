-- 전송진: 땅마다 하나씩 놓인 돌 진. 한 번 밟아 본 진끼리는 F 로 오갈 수 있다.
--
-- 진 목록은 Waypoints.luau. 밟아 본 진은 data.waypoints 에 남는다. 송계 진(Places.HOME_WAYPOINT)은 처음부터 열려 있다.
-- 진을 쓰면 영석 삯을 낸다 (Currency.travelFee: 선 진과 갈 진 사이 거리. 송계 진으로 돌아가는 길은 공짜).

local RunService = game:GetService("RunService")

local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Waypoints = require(script.Parent.Waypoints)
local Cultivation = require(script.Parent.Cultivation)
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Places = require(Shared.Places)
local Currency = require(Shared.Currency)
local Progression = require(Shared.Progression)

local Travel = {}

local DISCOVER_RADIUS = 12
local USE_RADIUS = Places.WAYPOINT_RADIUS
local COOLDOWN = 3

local lastTravel: { [Player]: number } = {}

local function near(position: Vector3, pad: BasePart, radius: number): boolean
	local offset = position - pad.Position
	return Vector3.new(offset.X, 0, offset.Z).Magnitude <= radius and math.abs(offset.Y) < 14
end

-- 이 플레이어가 지금 서 있는 진
local function padAt(player: Player, radius: number): BasePart?
	local root = Characters.root(player)
	if not root then
		return nil
	end
	for _, pad in Waypoints.pads() do
		if near(root.Position, pad, radius) then
			return pad
		end
	end
	return nil
end

local function discover(player: Player, pad: BasePart)
	local data = PlayerData.get(player)
	local id = pad:GetAttribute("WaypointId") :: string
	if not data or Waypoints.isOpen(data, id) then
		return
	end
	data.waypoints[id] = true
	Sync.notify(
		player,
		string.format(
			"%s 전송진이 열렸다. 다른 전송진에서 이곳으로 올 수 있다.",
			tostring(pad:GetAttribute("Name"))
		),
		"good"
	)
	Sync.markDirty(player)
end

-- 선 진에서 갈 진까지 삯 (화면의 전송진 창도 진 바닥 위치로 같은 값을 보여 준다)
function Travel.fee(from: BasePart, to: BasePart): number
	local id = to:GetAttribute("WaypointId")
	return Currency.travelFee((to.Position - from.Position).Magnitude, id == Places.HOME_WAYPOINT)
end

-- 다른 일을 하는 중에는 떠나지 못한다
local function busy(player: Player): string?
	local session = Session.get(player)
	if not session then
		return "잠시 뒤에 다시."
	end
	if session.tribulation then
		return "천겁을 맞는 중에는 진을 쓸 수 없다."
	elseif session.trial then
		return "내관 중에는 진을 쓸 수 없다."
	elseif session.ritual then
		return "제의 중에는 진을 쓸 수 없다."
	end
	return nil
end

function Travel.go(player: Player, id: any)
	if type(id) ~= "string" then
		return
	end
	local data = PlayerData.get(player)
	local target = Waypoints.byId(id)
	if not data or not target then
		return
	end
	if not Waypoints.isOpen(data, id) then
		Sync.notify(player, "아직 밟아 보지 못한 전송진이다.", "bad")
		return
	end
	local here = padAt(player, USE_RADIUS)
	if not here then
		Sync.notify(player, "전송진 위에 서야 떠날 수 있다.", "bad")
		return
	end
	if here == target then
		return
	end
	local reason = busy(player)
	if reason then
		Sync.notify(player, reason, "bad")
		return
	end
	local now = os.clock()
	if now - (lastTravel[player] or -math.huge) < COOLDOWN then
		return
	end
	local character = player.Character
	if not character or not character.Parent or not Characters.humanoid(player) then
		return
	end
	-- 삯은 떠나기 바로 앞에서 낸다. 모자라면 떠나지 않는다
	local fee = Travel.fee(here, target)
	if not Progression.spendStones(data, fee) then
		Sync.notify(
			player,
			string.format(
				"전송진 삯이 모자라다. (영석 %s 필요) 걸어서 가면 삯이 들지 않는다.",
				Currency.format(fee)
			),
			"bad"
		)
		return
	end
	lastTravel[player] = now
	Cultivation.setMeditating(player, false)
	-- 진 가운데에서 조금 비켜 선다 (여럿이 한꺼번에 와도 겹치지 않게)
	local angle = math.random() * math.pi * 2
	local offset = Vector3.new(math.cos(angle) * 4, 4, math.sin(angle) * 4)
	character:PivotTo(CFrame.new(target.Position + offset) * CFrame.Angles(0, angle, 0))
	if fee > 0 then
		Sync.notify(player, string.format("전송진 삯으로 영석 %s개를 냈다.", Currency.format(fee)), "info")
	end
	Sync.markDirty(player)
end

function Travel.start()
	-- 밟아 본 진을 연다 (1초마다)
	local elapsed = 0
	RunService.Heartbeat:Connect(function(dt)
		elapsed += dt
		if elapsed < 1 then
			return
		end
		elapsed = 0
		for player in Session.all() do
			local pad = padAt(player, DISCOVER_RADIUS)
			if pad then
				discover(player, pad)
			end
		end
	end)

	for _, pad in Waypoints.pads() do
		local prompt = Instance.new("ProximityPrompt")
		prompt.Name = "TravelPrompt"
		prompt.ActionText = "전송진"
		prompt.ObjectText = tostring(pad:GetAttribute("Name"))
		prompt.KeyboardKeyCode = Enum.KeyCode.F
		prompt.HoldDuration = 0.2
		prompt.MaxActivationDistance = USE_RADIUS
		prompt.RequiresLineOfSight = false
		prompt:SetAttribute("Waypoint", pad:GetAttribute("WaypointId"))
		prompt.Triggered:Connect(function(player)
			discover(player, pad)
		end)
		prompt.Parent = pad
	end
end

function Travel.forget(player: Player)
	lastTravel[player] = nil
end

return Travel
