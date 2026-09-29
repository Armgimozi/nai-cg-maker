-- 관광 공원 부지: 광장을 둘러싼 원형 배치. 플레이어마다 부지 하나를 배정하고 미니어처를 전시합니다.
--
-- 배치: 안쪽 고리 8칸(반지름 115), 바깥 고리 16칸(반지름 210). 반지름은 광장 중심에서 부지 "입구"
--   (광장 쪽 가장자리)까지 거리입니다. 부지 중심까지로 잡으면 이웃 부지끼리 겹치기 때문.
-- 부지 좌표계: 부지 중앙 바닥이 원점, -Z(LookVector)가 광장 쪽 = 입구.
-- 전시 칸: 6x6 격자. 입구에 가까운 줄부터, 한 줄 안에서는 가운데에 가까운 칸부터 채워서
--   가장 희귀한 명소가 입구 정면에 오도록 합니다.
-- update 는 칸마다 이전 상태를 기억해 두고 바뀐 칸만 다시 만듭니다(별 개수는 이름표 글자만 바꿈).
-- 간판: 주인이 있으면 입구 아치(나무 판자 + Ink 테두리 + 크림 글자판 + 초록 수입 알약),
--   빈 부지는 길 옆 낮은 말뚝 간판만 세워서 빈 부지가 20곳 넘어도 광장에서 볼 때 어지럽지 않게 합니다.
-- 장식: 둘레 색 띠 + 네 귀퉁이 덤불 + 옆·뒤 낮은 울타리(입구 쪽은 비움). 위에서 봐도 부지가 구분됩니다.
-- 글자 스타일은 DESIGN.md "UI 스타일 가이드 v2" 를 따름(FredokaOne, Ink 테두리, 이모지 없음).

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

-- 간판 배치(부지 좌표)
local SIGN_Z = -PLOT_DEPTH / 2 - BORDER - 1 -- 입구 바로 앞(잔디 위)
local BOARD_SIZE = Vector3.new(28, 6, 0.8) -- 주인 간판 판자
local BOARD_Y = 10.5 -- 판자 중심 높이(판자 아래 7.5 스터드: 사람이 밑으로 지나감)
local FRAME = 0.6 -- 판자 둘레 Ink 테두리 굵기
local POST = 1.6 -- 간판 기둥 굵기
local STAKE_BOARD = Vector3.new(6, 2.6, 0.4) -- 빈 부지 말뚝 간판
local STAKE_X = 9 -- 말뚝 간판 위치: 길(폭 10) 바로 옆
local STAKE_TILT = math.rad(-4) -- 말뚝을 살짝 기울여서 장난스럽게
local FENCE_HEIGHT = 2.2
local RAIL = Vector3.new(0.35, 0.35, 0.35) -- 울타리 가로대 단면

local LABEL_WIDTH = 10 -- 전시 이름표 크기(스터드)
local LABEL_HEIGHT = 2.6

local BASE_COLOR = Color3.fromRGB(226, 220, 204)
local PATH_COLOR = Color3.fromRGB(215, 198, 165)
local PEDESTAL_COLOR = Color3.fromRGB(236, 234, 228)
local LOCKED_COLOR = Color3.fromRGB(120, 124, 138)

-- UI 스타일 가이드 v2 팔레트
local INK = Color3.fromRGB(30, 27, 46)
local CREAM = Color3.fromRGB(255, 244, 220)
local WHITE = Color3.new(1, 1, 1)
local SUN = Color3.fromRGB(255, 197, 61)
local GRASS = Color3.fromRGB(76, 217, 100)
local GRASS_SHADOW = Color3.fromRGB(46, 158, 69)
local STAR_EMPTY = Color3.fromRGB(150, 146, 170) -- 아직 못 딴 별

-- 월드 소품 색
local WOOD = Color3.fromRGB(181, 120, 66) -- 간판 판자(따뜻한 갈색)
local WOOD_DARK = Color3.fromRGB(122, 78, 45) -- 기둥, 말뚝
local FENCE_COLOR = Color3.fromRGB(255, 250, 240)
local BUSH_COLOR = Color3.fromRGB(72, 184, 84)
local BUSH_LIGHT = Color3.fromRGB(122, 214, 104)

local FONT = Enum.Font.FredokaOne
local EMPTY_STAR_HEX = Format.hex(STAR_EMPTY)

local EMPTY_TITLE = "빈 부지"
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
	OwnerSign: Model, -- 주인이 있을 때만 부지 모델 아래에 둠
	EmptySign: Model, -- 빈 부지일 때만 부지 모델 아래에 둠
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

-- 장식용 공(덤불, 꼭지). 걸리적거리지 않게 충돌 없음
local function ball(parent: Instance, name: string, diameter: number, cframe: CFrame, color: Color3): Part
	local part =
		newPart(parent, name, Vector3.new(diameter, diameter, diameter), cframe, color, Enum.Material.SmoothPlastic)
	part.Shape = Enum.PartType.Ball
	part.CanCollide = false
	return part
end

-- GUI 헬퍼 ---------------------------------------------------------------

local function textLabel(parent: Instance, size: UDim2, position: UDim2, color: Color3): TextLabel
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = size
	label.Position = position
	label.Font = FONT
	label.TextScaled = true
	label.TextColor3 = color
	label.Text = ""
	label.Parent = parent
	return label
end

local function frame(parent: Instance, size: UDim2, position: UDim2, color: Color3): Frame
	local box = Instance.new("Frame")
	box.Size = size
	box.Position = position
	box.BackgroundColor3 = color
	box.BorderSizePixel = 0
	box.Parent = parent
	return box
end

local function corner(gui: GuiObject, radius: UDim)
	local round = Instance.new("UICorner")
	round.CornerRadius = radius
	round.Parent = gui
end

-- Ink 테두리: 글자에 붙이면 글자 테두리, 상자에 붙이면 상자 테두리
local function stroke(gui: GuiObject, thickness: number)
	local line = Instance.new("UIStroke")
	line.Thickness = thickness
	line.Color = INK
	line.Parent = gui
end

local function padding(gui: GuiObject, x: UDim, y: UDim)
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = x
	pad.PaddingRight = x
	pad.PaddingTop = y
	pad.PaddingBottom = y
	pad.Parent = gui
end

-- 통통한 딱지: 어두운 그림자 판(drop 만큼 아래) 위에 색 앞면(위쪽이 살짝 밝음).
-- position 은 딱지 윗변 가운데. 반환: 앞면(글자를 넣을 곳)
local function chunky(
	parent: Instance,
	size: UDim2,
	position: UDim2,
	drop: UDim,
	color: Color3,
	shadowColor: Color3,
	thickness: number
): Frame
	local shadow = frame(parent, size, position + UDim2.new(UDim.new(), drop), shadowColor)
	shadow.Name = "Shadow"
	shadow.AnchorPoint = Vector2.new(0.5, 0)
	shadow.ZIndex = 1
	corner(shadow, UDim.new(0.5, 0))
	stroke(shadow, thickness)

	local face = frame(parent, size, position, color)
	face.Name = "Face"
	face.AnchorPoint = Vector2.new(0.5, 0)
	face.ZIndex = 2
	corner(face, UDim.new(0.5, 0))
	stroke(face, thickness)
	local shine = Instance.new("UIGradient")
	shine.Color = ColorSequence.new(WHITE, Color3.fromRGB(214, 214, 214))
	shine.Rotation = 90 -- 위 → 아래
	shine.Parent = face
	return face
end

-- 채운 별은 해 색, 못 딴 별은 흐린 색(RichText)
local function starText(stars: number): string
	local text = string.rep("★", stars)
	if stars < MAX_STARS then
		text ..= `<font color="{EMPTY_STAR_HEX}">{string.rep("★", MAX_STARS - stars)}</font>`
	end
	return text
end

local function incomeText(income: number): string
	return "관광 수입 +" .. Format.commas(income) .. "/초"
end

-- 간판 ---------------------------------------------------------------------

local function surfaceGui(board: BasePart, face: Enum.NormalId): SurfaceGui
	local gui = Instance.new("SurfaceGui")
	gui.Name = "SignGui"
	gui.Face = face
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.LightInfluence = 0
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.Parent = board
	return gui
end

-- 주인 간판 한 면: 가장자리에 나무가 보이는 크림 글자판 + 제목(Ink) + 초록 수입 알약. 반환: 제목, 수입 라벨
local function signFace(board: BasePart, face: Enum.NormalId): (TextLabel, TextLabel)
	local gui = surfaceGui(board, face)
	local panel = frame(gui, UDim2.new(1, -40, 1, -36), UDim2.fromScale(0.5, 0.5), CREAM)
	panel.Name = "Panel"
	panel.AnchorPoint = Vector2.new(0.5, 0.5)
	corner(panel, UDim.new(0, 24))
	stroke(panel, 6)

	local title = textLabel(panel, UDim2.new(1, -48, 0.46, 0), UDim2.new(0, 24, 0.06, 0), INK)
	title.Name = "Title"

	local pill =
		chunky(panel, UDim2.fromScale(0.62, 0.34), UDim2.fromScale(0.5, 0.56), UDim.new(0, 6), GRASS, GRASS_SHADOW, 4)
	local income = textLabel(pill, UDim2.fromScale(1, 1), UDim2.new(), WHITE)
	income.Name = "Income"
	padding(income, UDim.new(0.06, 0), UDim.new(0.14, 0))
	stroke(income, 3)
	return title, income
end

-- 주인 간판(입구 아치): 나무 판자 + Ink 테두리 + 양옆 기둥(부지 색 모자, 금색 꼭지).
-- 반환: 간판 모델, 제목 라벨들, 수입 라벨들(앞뒤 두 면)
local function buildOwnerSign(cf: CFrame, color: Color3): (Model, { TextLabel }, { TextLabel })
	local sign = Instance.new("Model")
	sign.Name = "Sign"
	local base = cf * CFrame.new(0, 0, SIGN_Z) -- 간판 바닥 가운데(땅 높이)
	local width, height = BOARD_SIZE.X, BOARD_SIZE.Y

	local board = newPart(sign, "Board", BOARD_SIZE, base * CFrame.new(0, BOARD_Y, 0), WOOD, Enum.Material.Wood)

	-- Ink 테두리: 판자보다 두꺼워서 앞뒤로 살짝 튀어나온 액자. 위아래 막대가 모서리까지 덮음
	local depth = BOARD_SIZE.Z + 0.4
	for _, side in { -1, 1 } do
		newPart(
			sign,
			"BoardFrame",
			Vector3.new(width + FRAME * 2, FRAME, depth),
			base * CFrame.new(0, BOARD_Y + side * (height + FRAME) / 2, 0),
			INK,
			Enum.Material.SmoothPlastic
		)
		newPart(
			sign,
			"BoardFrame",
			Vector3.new(FRAME, height, depth),
			base * CFrame.new(side * (width + FRAME) / 2, BOARD_Y, 0),
			INK,
			Enum.Material.SmoothPlastic
		)
	end

	-- 판자 양옆 기둥 + 부지 색 모자 + 금색 꼭지
	local postX = width / 2 + FRAME + POST / 2
	local postTop = BOARD_Y + height / 2 + FRAME + 0.6
	for _, side in { -1, 1 } do
		newPart(
			sign,
			"Post",
			Vector3.new(POST, postTop, POST),
			base * CFrame.new(side * postX, postTop / 2, 0),
			WOOD_DARK,
			Enum.Material.Wood
		)
		newPart(
			sign,
			"PostCap",
			Vector3.new(POST + 0.8, 0.7, POST + 0.8),
			base * CFrame.new(side * postX, postTop + 0.35, 0),
			color,
			Enum.Material.SmoothPlastic
		)
		ball(sign, "PostKnob", 1.3, base * CFrame.new(side * postX, postTop + 1.2, 0), SUN)
	end

	local frontTitle, frontIncome = signFace(board, Enum.NormalId.Front)
	local backTitle, backIncome = signFace(board, Enum.NormalId.Back)
	return sign, { frontTitle, backTitle }, { frontIncome, backIncome }
end

-- 빈 부지 말뚝 간판: 길 옆에 낮게, 살짝 기울여서. 광장 쪽 면에만 글자
local function buildEmptySign(cf: CFrame): Model
	local sign = Instance.new("Model")
	sign.Name = "EmptySign"
	local base = cf * CFrame.new(STAKE_X, 0, SIGN_Z) * CFrame.Angles(0, 0, STAKE_TILT)
	local boardY = 2 + STAKE_BOARD.Y / 2

	-- 말뚝은 판자 뒤(부지 쪽)에 붙임
	newPart(
		sign,
		"Stake",
		Vector3.new(0.5, boardY, 0.5),
		base * CFrame.new(0, boardY / 2, STAKE_BOARD.Z / 2 + 0.25),
		WOOD_DARK,
		Enum.Material.Wood
	)
	local board = newPart(sign, "Board", STAKE_BOARD, base * CFrame.new(0, boardY, 0), WOOD, Enum.Material.Wood)

	local gui = surfaceGui(board, Enum.NormalId.Front)
	local panel = frame(gui, UDim2.new(1, -16, 1, -16), UDim2.fromScale(0.5, 0.5), CREAM)
	panel.Name = "Panel"
	panel.AnchorPoint = Vector2.new(0.5, 0.5)
	corner(panel, UDim.new(0, 14))
	stroke(panel, 4)

	local title = textLabel(panel, UDim2.new(1, -16, 0.54, 0), UDim2.new(0, 8, 0.08, 0), INK)
	title.Text = EMPTY_TITLE
	title.TextTransparency = 0.15
	local subtitle = textLabel(panel, UDim2.new(1, -28, 0.26, 0), UDim2.new(0, 14, 0.64, 0), INK)
	subtitle.Text = EMPTY_SUBTITLE
	subtitle.TextTransparency = 0.4
	return sign
end

local function setSign(plot: Plot, title: string, subtitle: string)
	for _, label in plot.TitleLabels do
		label.Text = title
	end
	for _, label in plot.IncomeLabels do
		label.Text = subtitle
	end
end

-- 주인이 있으면 입구 아치 간판, 없으면 말뚝 간판만 보이게
local function showSign(plot: Plot, owned: boolean)
	plot.OwnerSign.Parent = if owned then plot.Model else nil
	plot.EmptySign.Parent = if owned then nil else plot.Model
end

-- 부지 장식 ---------------------------------------------------------------

type FenceSide = { Center: Vector3, Axis: Vector3, Length: number }

-- 위에서 봐도 부지가 보이게: 둘레 띠 위에 옆·뒤 낮은 울타리 + 네 귀퉁이 덤불. 입구(앞) 쪽은 비워 둠.
-- 부지 하나에 파트 20개(가로대 6, 기둥 6, 덤불 8)
local function decorate(model: Model, cf: CFrame)
	local edgeX = PLOT_WIDTH / 2 + BORDER / 2 -- 둘레 띠 가운데
	local edgeZ = PLOT_DEPTH / 2 + BORDER / 2
	local ground = BASE_TOP - 0.2 -- 둘레 띠 윗면

	local sides: { FenceSide } = {
		{ Center = Vector3.new(-edgeX, ground, 0), Axis = Vector3.new(0, 0, 1), Length = edgeZ * 2 },
		{ Center = Vector3.new(edgeX, ground, 0), Axis = Vector3.new(0, 0, 1), Length = edgeZ * 2 },
		{ Center = Vector3.new(0, ground, edgeZ), Axis = Vector3.new(1, 0, 0), Length = edgeX * 2 },
	}
	for _, side in sides do
		-- 가로대 두 줄(양 끝은 귀퉁이 덤불에 묻힘)
		for _, y in { 0.9, 1.8 } do
			newPart(
				model,
				"FenceRail",
				RAIL + side.Axis * (side.Length - RAIL.X),
				cf * CFrame.new(side.Center + Vector3.new(0, y, 0)),
				FENCE_COLOR,
				Enum.Material.SmoothPlastic
			)
		end
		-- 기둥은 3등분 지점에 두 개
		for _, t in { -1, 1 } do
			newPart(
				model,
				"FencePost",
				Vector3.new(0.6, FENCE_HEIGHT, 0.6),
				cf * CFrame.new(side.Center + side.Axis * (t * side.Length / 6) + Vector3.new(0, FENCE_HEIGHT / 2, 0)),
				FENCE_COLOR,
				Enum.Material.SmoothPlastic
			)
		end
	end

	-- 귀퉁이 덤불: 큰 공 + 위에 작은 밝은 공
	for _, sx in { -1, 1 } do
		for _, sz in { -1, 1 } do
			local spot = Vector3.new(sx * edgeX, ground, sz * edgeZ)
			ball(model, "Bush", 3.4, cf * CFrame.new(spot + Vector3.new(0, 1.2, 0)), BUSH_COLOR)
			ball(model, "Bush", 2.2, cf * CFrame.new(spot + Vector3.new(-sx * 0.7, 2.5, -sz * 0.5)), BUSH_LIGHT)
		end
	end
end

-- 부지 바닥, 둘레 색 띠, 장식, 간판(주인용/빈 부지용), 광장까지 길
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
	decorate(model, cf)

	-- 간판 두 종류를 미리 만들어 두고 주인 유무에 따라 하나만 부지 아래에 둠
	local ownerSign, titleLabels, incomeLabels = buildOwnerSign(cf, color)
	local emptySign = buildEmptySign(cf)

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

	local plot: Plot = {
		Index = index,
		CFrame = cf,
		Model = model,
		SlotFolder = slotFolder,
		OwnerSign = ownerSign,
		EmptySign = emptySign,
		TitleLabels = titleLabels,
		IncomeLabels = incomeLabels,
		Owner = nil,
		Slots = {},
	}
	showSign(plot, false)
	model.Parent = parent
	return plot
end

-- 서버 시작 시 한 번: 모든 부지의 바닥/장식/간판/길을 만들어 둠(주인 없는 부지는 "빈 부지" 말뚝 간판)
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

-- 칸 위 작은 이름표: 등급 색 둥근 딱지(흰 이름 + Ink 테두리) + 그 아래 별(해 색 + Ink 테두리)
local function addLabel(pedestal: BasePart, landmark: Landmarks.Landmark, modelHeight: number): TextLabel
	local anchor = Instance.new("Attachment")
	anchor.Name = "LabelAnchor"
	anchor.Position = Vector3.new(0, PEDESTAL_HEIGHT / 2 + modelHeight + 1.4, 0)
	anchor.Parent = pedestal

	local billboard = Instance.new("BillboardGui")
	billboard.Name = "Label"
	billboard.Adornee = anchor
	billboard.Size = UDim2.fromScale(LABEL_WIDTH, LABEL_HEIGHT)
	billboard.MaxDistance = LABEL_DISTANCE
	billboard.LightInfluence = 0
	billboard.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	-- 딱지 너비는 이름 길이에 맞춤(한글 한 글자 폭 ≈ 글자 높이 ≈ 1 스터드)
	local chars = utf8.len(landmark.Name) or #landmark.Name
	local width = math.clamp((chars * 1.05 + 1.4) / LABEL_WIDTH, 0.3, 1)
	local tier = landmark.Tier.Color
	local tag = chunky(
		billboard,
		UDim2.fromScale(width, 0.52),
		UDim2.fromScale(0.5, 0),
		UDim.new(0.07, 0),
		tier,
		tier:Lerp(INK, 0.4),
		2
	)
	local name = textLabel(tag, UDim2.fromScale(1, 1), UDim2.new(), WHITE)
	name.Name = "Name"
	name.Text = landmark.Name
	padding(name, UDim.new(0.08, 0), UDim.new(0.14, 0))
	stroke(name, 2)

	local stars = textLabel(billboard, UDim2.fromScale(1, 0.34), UDim2.fromScale(0, 0.64), SUN)
	stars.Name = "Stars"
	stars.RichText = true
	stroke(stars, 2)

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
			showSign(plot, true)
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
	showSign(plot, false)
	setSign(plot, "", "")
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
