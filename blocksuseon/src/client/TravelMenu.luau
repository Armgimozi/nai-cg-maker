-- 전송진 창: 전송진 위에서 F 를 누르면 열린다. 밟아 본 진을 골라 그리로 간다.
-- 고른 진은 서버에 "Travel" 로 보내고, 서버가 진 위에 서 있는지와 열린 진인지를 다시 본다.

local Ui = require(script.Parent.Ui)

local C = Ui.C
local new, image, setImage, text, row = Ui.new, Ui.image, Ui.setImage, Ui.text, Ui.row

local TravelMenu = {}

local MAX_ENTRIES = 15
local COLUMNS = 3
local ENTRY_W, ENTRY_H, GAP = 172, 46, 8

local ui: { [string]: any } = {}
local entries: { { [string]: any } } = {}
local onGo: (id: string) -> ()
local here: string? = nil

local function close()
	if ui.panel then
		ui.panel.Visible = false
	end
	here = nil
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

	local introRow = row({ Position = UDim2.fromOffset(0, 100), Size = UDim2.new(1, 0, 0, 24), Parent = panel })
	ui.intro = text("body", 16, { color = C.cream, parent = introRow })

	local grid = new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 138),
		Size = UDim2.fromOffset(COLUMNS * ENTRY_W + (COLUMNS - 1) * GAP, 320),
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
		local labelRow = row({ Size = UDim2.new(1, 0, 1, -2), Parent = button })
		local name = text("title", 19, { color = C.cream, parent = labelRow })
		local entry = { button = button, name = name, id = nil, open = false }
		button.Activated:Connect(function()
			if entry.id and entry.open and entry.id ~= here then
				onGo(entry.id)
				close()
			end
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
	local list = state.waypoints or {}
	local openCount = 0
	for index, entry in entries do
		local point = list[index]
		entry.button.Visible = point ~= nil
		entry.id = point and point.id
		-- 지금 선 진은 F 를 누르는 순간 열리므로 서버 상태가 오기 전에도 이름을 보인다
		entry.open = point ~= nil and (point.open == true or point.id == fromId)
		if point then
			local isHere = point.id == fromId
			if entry.open and not isHere then
				openCount += 1
			end
			entry.name:set(if entry.open then point.name else "가 보지 못한 곳")
			entry.name:setColor(if isHere then C.gold elseif entry.open then C.cream else C.dim)
			setImage(entry.button, if isHere then "pillJade" else "pillStone")
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
