-- 관광 공원 부지: 광장을 둘러싼 원형 배치. 플레이어마다 부지 하나를 배정하고 미니어처를 전시합니다.
--
-- 배치: 안쪽 고리 8칸(반지름 115), 바깥 고리 16칸(반지름 210). 반지름은 광장 중심에서 부지 "입구"
--   (광장 쪽 가장자리)까지 거리입니다. 부지 중심까지로 잡으면 이웃 부지끼리 겹치기 때문.
-- 부지 좌표계: 부지 중앙 바닥이 원점, -Z(LookVector)가 광장 쪽 = 입구.
-- 전시 칸: 6x6 격자. 입구에 가까운 줄부터, 한 줄 안에서는 가운데에 가까운 칸부터 채워서
--   가장 희귀한 명소가 입구 정면에 오도록 합니다.
-- update 는 칸마다 이전 상태를 기억해 두고 바뀐 칸만 다시 만듭니다(별 개수는 이름표 글자만 바꿈).

local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local Models = require(Shared.Models)
local PlayerState = require(Shared.PlayerState)

local INNER_RADIUS = 115
local OUTER_RADIUS = 210
local PLAZA_EDGE = 44 -- 길이 시작되는 곳(광장 둘레 계단 아래에서부터)

local PLOT_WIDTH = 76
local PLOT_DEPTH = 80
local BASE_TOP = 0.6 -- 부지 윗면 높이
local BORDER = 1.5 -- 부지 둘레 색 띠 폭

local GRID = 6
local SPACING = 12
local FRONT_MARGIN = 6 -- 입구와 첫 줄 사이 빈 공간
local PEDESTAL_SIZE = 10
local PEDESTAL_HEIGHT = 0.6
local MINIATURE_SIZE = 9
local LABEL_DISTANCE = 60
local PATH_WIDTH = 10

local MAX_STARS = #Config.STAR_THRESHOLDS

local BASE_COLOR = Color3.fromRGB(226, 220, 204)
local PATH_COLOR = Color3.fromRGB(215, 198, 165)
local PEDESTAL_COLOR = Color3.fromRGB(236, 234, 228)
local LOCKED_COLOR = Color3.fromRGB(120, 124, 138)
local SIGN_COLOR = Color3.fromRGB(250, 246, 234)
local SIGN_TEXT = Color3.fromRGB(45, 45, 60)
local INCOME_TEXT = Color3.fromRGB(40, 150, 75)
local STAR_COLOR = Color3.fromRGB(255, 210, 70)

local EMPTY_TITLE = "🏞️ 빈 부지"
local EMPTY_SUBTITLE = "주인을 기다리는 중"

-- 칸 상태 키: 명소 Id 이거나 아래 둘 중 하나(명소 Id 는 '#' 으로 시작하지 않음)
local KEY_LOCKED = "#locked"
local KEY_EMPTY = "#empty"

type Slot = {
	Key: string,
	Container: Model,
	StarLabel: TextLabel?,
	Stars: number,
}

type Plot = {
	Index: number,
	CFrame: CFrame,
	Model: Model,
	SlotFolder: Folder,
	TitleLabels: { TextLabel },
	IncomeLabels: { TextLabel },
	Owner: Player?,
	Slots: { Slot },
}

type Layout = { Angle: number, Radius: number, Path: boolean }

-- 부지 순서 = 배정 순서(가장 작은 빈 번호부터). 첫 부지는 스폰 정면(-Z = 270도) 근처.
local LAYOUT: { Layout } = {}
for i = 0, 7 do
	table.insert(LAYOUT, { Angle = math.rad(247.5 + 45 * i), Radius = INNER_RADIUS, Path = true })
end
-- 바깥 고리: 안쪽 부지 사이 틈으로 광장에서 바로 보이는 8칸 먼저, 안쪽 부지 뒤에 있는 8칸은 나중에
for i = 0, 7 do
	table.insert(LAYOUT, { Angle = math.rad(270 + 45 * i), Radius = OUTER_RADIUS, Path = true })
end
for i = 0, 7 do
	table.insert(LAYOUT, { Angle = math.rad(247.5 + 45 * i), Radius = OUTER_RADIUS, Path = false })
end

-- 전시 칸 위치(부지 좌표, Y = 부지 윗면). 입구 쪽 줄부터, 줄 안에서는 가운데부터.
local SLOT_OFFSETS: { Vector3 } = {}
do
	local columns = {}
	for c = 1, GRID do
		table.insert(columns, (c - (GRID + 1) / 2) * SPACING)
	end
	table.sort(columns, function(a, b)
		if math.abs(a) ~= math.abs(b) then
			return math.abs(a) < math.abs(b)
		end
		return a < b
	end)
	local firstRow = -PLOT_DEPTH / 2 + FRONT_MARGIN + SPACING / 2
	for row = 0, GRID - 1 do
		for _, x in columns do
			table.insert(SLOT_OFFSETS, Vector3.new(x, BASE_TOP, firstRow + row * SPACING))
		end
	end
end

local ParkService = {}

local folder: Folder? = nil
local plots: { Plot } = {}
local plotByPlayer: { [Player]: Plot } = {}

local function newPart(
	parent: Instance,
	name: string,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material
): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = material
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = parent
	return part
end

local function textLabel(parent: Instance, size: UDim2, position: UDim2, color: Color3, font: Enum.Font): TextLabel
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = size
	label.Position = position
	label.Font = font
	label.TextScaled = true
	label.TextColor3 = color
	label.Text = ""
	label.Parent = parent
	return label
end

local function outline(label: TextLabel, thickness: number)
	local stroke = Instance.new("UIStroke")
	stroke.Thickness = thickness
	stroke.Color = Color3.new(0, 0, 0)
	stroke.Transparency = 0.2
	stroke.Parent = label
end

local function starText(stars: number): string
	return string.rep("★", stars) .. string.rep("☆", MAX_STARS - stars)
end

local function incomeText(income: number): string
	return "관광 수입 +" .. Format.commas(income) .. "/초"
end

-- 간판 한 면(SurfaceGui). 반환: 제목 라벨, 수입 라벨
local function signFace(board: BasePart, face: Enum.NormalId): (TextLabel, TextLabel)
	local gui = Instance.new("SurfaceGui")
	gui.Name = "SignGui"
	gui.Face = face
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.LightInfluence = 0
	gui.Parent = board
	local title =
		textLabel(gui, UDim2.fromScale(0.94, 0.54), UDim2.fromScale(0.03, 0.06), SIGN_TEXT, Enum.Font.GothamBlack)
	local income =
		textLabel(gui, UDim2.fromScale(0.94, 0.32), UDim2.fromScale(0.03, 0.62), INCOME_TEXT, Enum.Font.GothamBold)
	return title, income
end

local function setSign(plot: Plot, title: string, subtitle: string)
	for _, label in plot.TitleLabels do
		label.Text = title
	end
	for _, label in plot.IncomeLabels do
		label.Text = subtitle
	end
end

-- 부지 바닥, 둘레 색 띠, 입구 아치 간판, 광장까지 길
local function buildPlot(parent: Instance, index: number, layout: Layout): Plot
	local direction = Vector3.new(math.cos(layout.Angle), 0, math.sin(layout.Angle))
	local center = direction * (layout.Radius + PLOT_DEPTH / 2)
	local cf = CFrame.lookAt(center, Vector3.zero) -- -Z(LookVector)가 광장 쪽
	-- 이웃 부지와 색이 겹치지 않게 황금비 간격으로 색상환을 돔
	local color = Color3.fromHSV(((index - 1) * 0.618034) % 1, 0.6, 0.95)

	local model = Instance.new("Model")
	model.Name = "Plot" .. index

	-- 둘레 띠(윗면 0.4) 위에 부지 바닥(윗면 0.6): 계단처럼 걸어서 오를 수 있음
	newPart(
		model,
		"Border",
		Vector3.new(PLOT_WIDTH + BORDER * 2, BASE_TOP - 0.2, PLOT_DEPTH + BORDER * 2),
		cf * CFrame.new(0, (BASE_TOP - 0.2) / 2, 0),
		color,
		Enum.Material.SmoothPlastic
	)
	newPart(
		model,
		"Base",
		Vector3.new(PLOT_WIDTH, BASE_TOP, PLOT_DEPTH),
		cf * CFrame.new(0, BASE_TOP / 2, 0),
		BASE_COLOR,
		Enum.Material.Concrete
	)

	-- 입구 아치: 기둥 두 개 + 간판(사람이 밑으로 지나갈 수 있는 높이)
	local signZ = -PLOT_DEPTH / 2 - BORDER - 1
	for _, x in { -12, 12 } do
		newPart(model, "SignPost", Vector3.new(1, 11, 1), cf * CFrame.new(x, 5.5, signZ), color, Enum.Material.Wood)
	end
	local board = newPart(
		model,
		"Sign",
		Vector3.new(26, 5, 0.6),
		cf * CFrame.new(0, 9, signZ),
		SIGN_COLOR,
		Enum.Material.SmoothPlastic
	)
	local frontTitle, frontIncome = signFace(board, Enum.NormalId.Front)
	local backTitle, backIncome = signFace(board, Enum.NormalId.Back)

	-- 광장에서 입구까지 길(안쪽 고리와, 안쪽 부지 사이로 보이는 바깥 부지만). 부지/광장 아래로 살짝 들어감
	if layout.Path then
		local from, to = PLAZA_EDGE, layout.Radius + 1
		local length = to - from
		local mid = direction * ((from + to) / 2) + Vector3.new(0, 0.1, 0)
		local path = newPart(
			model,
			"Path",
			Vector3.new(PATH_WIDTH, 0.2, length),
			CFrame.lookAt(mid, Vector3.new(0, 0.1, 0)),
			PATH_COLOR,
			Enum.Material.Concrete
		)
		path.CastShadow = false
	end

	local slotFolder = Instance.new("Folder")
	slotFolder.Name = "Slots"
	slotFolder.Parent = model
	model.Parent = parent

	local plot: Plot = {
		Index = index,
		CFrame = cf,
		Model = model,
		SlotFolder = slotFolder,
		TitleLabels = { frontTitle, backTitle },
		IncomeLabels = { frontIncome, backIncome },
		Owner = nil,
		Slots = {},
	}
	setSign(plot, EMPTY_TITLE, EMPTY_SUBTITLE)
	return plot
end

-- 서버 시작 시 한 번: 모든 부지의 바닥/간판/길을 만들어 둠(주인 없는 부지는 "빈 부지")
function ParkService.init()
	if folder then
		return
	end
	local parks = Instance.new("Folder")
	parks.Name = "Parks"
	folder = parks
	for index, layout in LAYOUT do
		table.insert(plots, buildPlot(parks, index, layout))
	end
	parks.Parent = Workspace
end

-- 칸 위 작은 이름표: 이름(등급 색) + 별
local function addLabel(pedestal: BasePart, landmark: Landmarks.Landmark, modelHeight: number): TextLabel
	local anchor = Instance.new("Attachment")
	anchor.Name = "LabelAnchor"
	anchor.Position = Vector3.new(0, PEDESTAL_HEIGHT / 2 + modelHeight + 1.4, 0)
	anchor.Parent = pedestal

	local billboard = Instance.new("BillboardGui")
	billboard.Name = "Label"
	billboard.Adornee = anchor
	billboard.Size = UDim2.fromScale(10, 2.4)
	billboard.MaxDistance = LABEL_DISTANCE
	billboard.LightInfluence = 0

	local name = textLabel(
		billboard,
		UDim2.fromScale(1, 0.58),
		UDim2.fromScale(0, 0),
		landmark.Tier.Color,
		Enum.Font.GothamBlack
	)
	name.Text = landmark.Name
	outline(name, 2)
	local stars =
		textLabel(billboard, UDim2.fromScale(1, 0.4), UDim2.fromScale(0, 0.6), STAR_COLOR, Enum.Font.GothamBold)
	outline(stars, 1.5)

	billboard.Parent = anchor
	return stars
end

-- key: KEY_LOCKED(흐릿한 바닥) / KEY_EMPTY(빈 받침대) / 명소 Id(받침대 + 미니어처 + 이름표)
local function buildSlot(plot: Plot, index: number, key: string): Slot
	local floor = plot.CFrame * CFrame.new(SLOT_OFFSETS[index]) -- 칸 바닥 중앙(부지 윗면)
	local container = Instance.new("Model")
	container.Name = "Slot" .. index
	local slot: Slot = { Key = key, Container = container, StarLabel = nil, Stars = -1 }

	if key == KEY_LOCKED then
		local tile = newPart(
			container,
			"Locked",
			Vector3.new(PEDESTAL_SIZE, 0.1, PEDESTAL_SIZE),
			floor * CFrame.new(0, 0.08, 0),
			LOCKED_COLOR,
			Enum.Material.SmoothPlastic
		)
		tile.Transparency = 0.7
		tile.CanCollide = false
		tile.CastShadow = false
	else
		local pedestal = newPart(
			container,
			"Pedestal",
			Vector3.new(PEDESTAL_SIZE, PEDESTAL_HEIGHT, PEDESTAL_SIZE),
			floor * CFrame.new(0, PEDESTAL_HEIGHT / 2, 0),
			PEDESTAL_COLOR,
			Enum.Material.Marble
		)
		local landmark = if key ~= KEY_EMPTY then Landmarks.ById[key] else nil
		if landmark then
			pedestal.Color = landmark.Tier.Color:Lerp(PEDESTAL_COLOR, 0.6)
			-- 모형 하나가 잘못돼도 나머지 칸/이름표는 만들어지도록 pcall. 반환: 모형 높이
			local ok, result = pcall(function(): number
				local model = Models.create(landmark, MINIATURE_SIZE)
				model:PivotTo(floor * CFrame.new(0, PEDESTAL_HEIGHT, 0))
				model.Parent = container
				return model:GetExtentsSize().Y
			end)
			if not ok then
				warn("[ParkService] " .. landmark.Id .. " 모형을 만들지 못했습니다: " .. tostring(result))
			end
			slot.StarLabel = addLabel(pedestal, landmark, if ok then result else 0)
		end
	end

	container.Parent = plot.SlotFolder
	return slot
end

local function clearSlots(plot: Plot)
	for _, slot in plot.Slots do
		slot.Container:Destroy()
	end
	table.clear(plot.Slots)
end

-- 가장 작은 빈 부지 번호를 배정. 부지가 모자라면 nil(공원 없이 플레이).
function ParkService.assign(player: Player): number?
	ParkService.init()
	local existing = plotByPlayer[player]
	if existing then
		return existing.Index
	end
	for _, plot in plots do
		if not plot.Owner then
			plot.Owner = player
			plotByPlayer[player] = plot
			setSign(plot, player.DisplayName .. " 님의 관광 공원", incomeText(0))
			return plot.Index
		end
	end
	warn("[ParkService] 빈 공원 부지가 없습니다: " .. player.Name)
	return nil
end

-- 퇴장: 전시물을 모두 치우고 부지를 비움
function ParkService.release(player: Player)
	local plot = plotByPlayer[player]
	if not plot then
		return
	end
	plotByPlayer[player] = nil
	plot.Owner = nil
	clearSlots(plot)
	setSign(plot, EMPTY_TITLE, EMPTY_SUBTITLE)
end

-- 전시 상태를 data 에 맞춤. data 는 Data 또는 같은 필드(Inventory, Upgrades)를 가진 표.
function ParkService.update(player: Player, data: PlayerState.Data)
	local plot = plotByPlayer[player]
	if not plot then
		return
	end
	local park = PlayerState.park(data)
	local unlocked = math.min(PlayerState.slots(data), #SLOT_OFFSETS)

	for index = 1, #SLOT_OFFSETS do
		local id = park[index]
		local key = if id then id elseif index <= unlocked then KEY_EMPTY else KEY_LOCKED
		local slot = plot.Slots[index]
		if not slot or slot.Key ~= key then
			if slot then
				slot.Container:Destroy()
			end
			slot = buildSlot(plot, index, key)
			plot.Slots[index] = slot
		end
		local starLabel = slot.StarLabel
		if id and starLabel then
			local stars = PlayerState.stars(data.Inventory[id] or 0)
			if stars ~= slot.Stars then
				slot.Stars = stars
				starLabel.Text = starText(stars)
			end
		end
	end

	setSign(plot, player.DisplayName .. " 님의 관광 공원", incomeText(PlayerState.incomePerSecond(data)))
end

-- 공원 입구 안쪽 바닥(부지 윗면)에서 공원 안쪽을 바라보는 CFrame. 부지가 없으면 nil.
function ParkService.entranceCFrame(player: Player): CFrame?
	local plot = plotByPlayer[player]
	if not plot then
		return nil
	end
	local position = plot.CFrame:PointToWorldSpace(Vector3.new(0, BASE_TOP, -PLOT_DEPTH / 2 + 3))
	return CFrame.lookAt(position, position - plot.CFrame.LookVector)
end

return ParkService
