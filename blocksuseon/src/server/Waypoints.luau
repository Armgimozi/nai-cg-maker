-- 맵의 전송진 목록. Travel(오가기)과 Sync(상태 보내기)가 같이 쓴다.
-- 맵(World.luau)이 진 바닥에 Waypoint 태그와 속성 WaypointId, Name, Order 를 달아 둔다.

local CollectionService = game:GetService("CollectionService")
local Places = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared").Places)

local Waypoints = {}

-- 처음부터 열려 있는 진 (연국)
Waypoints.HOME = Places.HOME_WAYPOINT

function Waypoints.pads(): { BasePart }
	local out = {}
	for _, pad in CollectionService:GetTagged("Waypoint") do
		if pad:IsA("BasePart") and type(pad:GetAttribute("WaypointId")) == "string" then
			table.insert(out, pad)
		end
	end
	return out
end

function Waypoints.byId(id: string): BasePart?
	for _, pad in Waypoints.pads() do
		if pad:GetAttribute("WaypointId") == id then
			return pad
		end
	end
	return nil
end

function Waypoints.isOpen(data, id: string): boolean
	return id == Waypoints.HOME or (type(data.waypoints) == "table" and data.waypoints[id] == true)
end

-- 상태로 보낼 목록 (맵에 적힌 차례대로)
function Waypoints.snapshot(data): { { id: string, name: string, open: boolean } }
	local out = {}
	for _, pad in Waypoints.pads() do
		local id = pad:GetAttribute("WaypointId") :: string
		local order = pad:GetAttribute("Order")
		table.insert(out, {
			id = id,
			name = tostring(pad:GetAttribute("Name") or id),
			order = if type(order) == "number" then order else 99,
			open = Waypoints.isOpen(data, id),
		})
	end
	table.sort(out, function(a, b)
		return a.order < b.order
	end)
	for _, entry in out do
		entry.order = nil
	end
	return out
end

return Waypoints
