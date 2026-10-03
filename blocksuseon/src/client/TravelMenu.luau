-- 전송진 창: 전송진 위에서 F 를 누르면 열린다. 밟아 본 진을 골라 그리로 간다.
-- 고른 진은 서버에 "Travel" 로 보내고, 서버가 진 위에 서 있는지와 열린 진인지를 다시 본다.
-- 진마다 영석 삯을 보인다. 서버(Travel.fee)와 같은 식으로 선 진과 갈 진 바닥(Waypoint 태그) 사이 거리로 센다.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Currency = require(Shared.Currency)
local Places = require(Shared.Places)
local Ui = require(script.Parent.Ui)
local Notice = require(script.Parent.Notice)

local C = Ui.C
local new, image, setImage, text, row = Ui.new, Ui.image, Ui.setImage, Ui.text, Ui.row

local TravelMenu = {}

local MAX_ENTRIES = 15
local COLUMNS = 3
local ENTRY_W, ENTRY_H, GAP = 172, 52, 8

local player = Players.LocalPlayer
local ui: { [string]: any } = {}
local entries: { { [string]: any } } = {}
local onGo: (id: string) -> ()
local here: string? = nil
local stones = 0 -- 창을 연 때의 지닌 영석

local function close()
	if ui.panel then
		ui.panel.Visible = false
	end
	here = nil
end

-- 맵의 전송진 바닥 (태그 차례대로)
local function pads(): { BasePart }
	local out = {}
	for _, pad in CollectionService:GetTagged("Waypoint") do
		if pad:IsA("BasePart") and type(pad:GetAttribute("WaypointId")) == "string" then
			table.insert(out, pad)
		end
	end
	return out
end

-- 지금 서 있는 진 바닥 (서버 Travel 과 같은 기준). 못 찾으면 F 를 누른 진
local function padHere(list: { BasePart }, fromId: string): BasePart?
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if root and root:IsA("BasePart") then
		for _, pad in list do
			local offset = root.Position - pad.Position
			if Vector3.new(offset.X, 0, offset.Z).Magnitude <= Places.WAYPOINT_RADIUS and math.abs(offset.Y) < 14 then
				return pad
			end
		end
	end
	for _, pad in list do
		if pad:GetAttribute("WaypointId") == fromId then
			return pad
		end
	end
	return nil
end

-- 진 id 마다 삯. 바닥을 못 찾은 진은 빠진다 (그때는 서버가 정한다)
local function fees(fromId: string): { [string]: number }
	local list = pads()
	local from = padHere(list, fromId)
	local out = {}
	if not from then
		return out
	end
	for _, pad in list do
		local id = pad:GetAttribute("WaypointId") :: string
		out[id] = Currency.travelFee((pad.Position - from.Position).Magnitude, id == Places.HOME_WAYPOINT)
	end
	return out
end

function TravelMenu.build(gui: ScreenGui, go: (id: string) -> ())
	onGo = go
	local panel = image("panel", {
		Name = "TravelMenu",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(620, 480),
		SliceScale = 0.8,
		Visible = false,
		Active = true,
		ZIndex = 5,
		Parent = gui,
	})
	new("UIScale", { Parent = panel })
	ui.panel = panel
	local titleRow = row({ Position = UDim2.fromOffset(0, 22), Size = UDim2.new(1, 0, 0, 56), Parent = panel })
	text("title", 38, { gradient = Ui.GOLD_TEXT, text = "전송진", parent = titleRow })
	image("divider", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 74),
		Size = UDim2.fromOffset(520, 22),
		Parent = panel,
	})
	local closeButton = image("iconClose", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -24, 0, 24),
		Size = UDim2.fromOffset(32, 32),
		Parent = panel,
	}, "ImageButton")
	closeButton.Activated:Connect(close)

	-- 지닌 영석 (왼쪽 위)
	local stoneRow = row({
		Position = UDim2.fromOffset(40, 30),
		Size = UDim2.fromOffset(200, 30),
		Parent = panel,
	}, Enum.HorizontalAlignment.Left, 6)
	stoneRow:FindFirstChildOfClass("UIListLayout").VerticalAlignment = Enum.VerticalAlignment.Center
	image("gem", { LayoutOrder = 1, Size = UDim2.fromOffset(20, 20), Parent = stoneRow })
	ui.stones = text("body", 19, { color = C.gold, name = "Stones", parent = stoneRow })
	ui.stones.frame.LayoutOrder = 2

	local introRow = row({ Position = UDim2.fromOffset(0, 100), Size = UDim2.new(1, 0, 0, 24), Parent = panel })
	ui.intro = text("body", 16, { color = C.cream, parent = introRow })

	local grid = new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 136),
		Size = UDim2.fromOffset(COLUMNS * ENTRY_W + (COLUMNS - 1) * GAP, 300),
		BackgroundTransparency = 1,
		Parent = panel,
	}, {
		new("UIGridLayout", {
			CellSize = UDim2.fromOffset(ENTRY_W, ENTRY_H),
			CellPadding = UDim2.fromOffset(GAP, GAP),
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	})
	for index = 1, MAX_ENTRIES do
		local button = image("pillStone", {
			LayoutOrder = index,
			SliceScale = 0.5,
			Visible = false,
			Parent = grid,
		}, "ImageButton")
		-- 이름, 그 아래 삯 (삯이 없으면 이름만 가운데)
		local nameRow = row({ Size = UDim2.new(1, 0, 1, -12), Parent = button })
		local name = text("title", 19, { color = C.cream, name = "Name", parent = nameRow })
		local feeRow = row({ Position = UDim2.fromOffset(0, 29), Size = UDim2.new(1, 0, 0, 18), Parent = button })
		local fee = text("body", 13, { color = C.dim, name = "Fee", parent = feeRow })
		local entry = { button = button, name = name, nameRow = nameRow, fee = fee, id = nil, open = false }
		button.Activated:Connect(function()
			if not entry.id or not entry.open or entry.id == here then
				return
			end
			local cost = entry.cost
			if cost and stones < cost then
				Notice.show(
					string.format(
						"전송진 삯이 모자라다. (영석 %s 필요) 걸어서 가면 삯이 들지 않는다.",
						Currency.format(cost)
					),
					"bad"
				)
				return
			end
			onGo(entry.id)
			close()
		end)
		entries[index] = entry
	end
end

function TravelMenu.isOpen(): boolean
	return ui.panel ~= nil and ui.panel.Visible
end

function TravelMenu.close()
	close()
end

-- 지금 선 진(fromId)에서 연다. 목록은 상태(state.waypoints)에서 온다
function TravelMenu.open(fromId: string, state: { [string]: any })
	if not ui.panel then
		return
	end
	here = fromId
	stones = state.stones or 0
	ui.stones:set(Currency.format(stones))
	local list = state.waypoints or {}
	local costs = fees(fromId)
	local openCount = 0
	for index, entry in entries do
		local point = list[index]
		entry.button.Visible = point ~= nil
		entry.id = point and point.id
		-- 지금 선 진은 F 를 누르는 순간 열리므로 서버 상태가 오기 전에도 이름을 보인다
		entry.open = point ~= nil and (point.open == true or point.id == fromId)
		entry.cost = nil
		if point then
			local isHere = point.id == fromId
			if entry.open and not isHere then
				openCount += 1
				entry.cost = costs[point.id]
			end
			local cost = entry.cost
			local short = cost ~= nil and stones < cost
			entry.name:set(if entry.open then point.name else "가 보지 못한 곳")
			entry.name:setColor(if isHere then C.gold elseif entry.open and not short then C.cream else C.dim)
			if cost then
				entry.fee:set(if cost == 0 then "공짜" else string.format("영석 %s", Currency.format(cost)))
				entry.fee:setColor(if short then C.red elseif cost == 0 then C.jade else C.gold)
			else
				entry.fee:set("")
			end
			entry.fee.frame.Visible = cost ~= nil
			entry.nameRow.Size = if cost then UDim2.new(1, 0, 0, 30) else UDim2.new(1, 0, 1, -12)
			setImage(entry.button, if isHere then "pillJade" else "pillStone")
			entry.button.ImageTransparency = if short then 0.35 else 0
		end
	end
	ui.intro:set(
		if openCount > 0
			then "갈 곳을 고른다. 가 본 땅의 전송진으로만 갈 수 있다."
			else "아직 열린 진이 없다. 다른 땅의 전송진을 밟으면 열린다."
	)
	ui.panel.Visible = true
end

-- 열려 있을 때 새 상태로 다시 그린다
function TravelMenu.refresh(state: { [string]: any })
	if here and TravelMenu.isOpen() then
		TravelMenu.open(here, state)
	end
end

return TravelMenu
