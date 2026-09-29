-- 메뉴 창: 가방(장착), 도감(발견 현황), 상점(물약)

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Auras = require(Shared.Auras)
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local PlayerState = require(Shared.PlayerState)

local Ui = require(script.Parent.Ui)
local Theme = Ui.Theme

type Handlers = {
	Equip: (string?) -> (),
	Buy: (string) -> (),
	ToggleAutoEquip: () -> (),
}

local TITLES = {
	Inventory = "🎒 가방",
	Index = "📖 도감",
	Shop = "🛒 상점",
}

local Panels = {}

local window: Frame
local titleLabel: TextLabel
local headerButton: TextButton
local body: ScrollingFrame
local handlers: Handlers
local openName: string? = nil
local lastState: PlayerState.Snapshot? = nil

local function clearBody()
	for _, child in body:GetChildren() do
		child:Destroy()
	end
end

local function gridLayout()
	Ui.new("UIGridLayout", {
		CellSize = UDim2.fromOffset(142, 112),
		CellPadding = UDim2.fromOffset(10, 10),
		SortOrder = Enum.SortOrder.LayoutOrder,
		HorizontalAlignment = Enum.HorizontalAlignment.Center,
		Parent = body,
	})
	Ui.padding(6).Parent = body
end

local function auraCard(order: number, aura: Auras.Aura, known: boolean, footer: string, highlight: boolean): TextButton
	local card = Ui.new("TextButton", {
		LayoutOrder = order,
		Text = "",
		AutoButtonColor = true,
		BackgroundColor3 = if highlight then Color3.fromRGB(60, 52, 110) else Theme.PanelLight,
		Parent = body,
	})
	Ui.corner(12).Parent = card
	Ui.stroke(if known then aura.Tier.Color else Theme.Stroke, if highlight then 3 else 2, if known then 0.1 else 0.5).Parent =
		card
	Ui.padding(8).Parent = card

	local name = Ui.label({
		Size = UDim2.new(1, 0, 0.42, 0),
		Font = Theme.FontHeavy,
		Text = if known then aura.Name else "???",
		TextColor3 = Theme.SubText,
		Parent = card,
	}, 26)
	if known then
		Ui.paintAura(name, aura)
	end
	Ui.label({
		Position = UDim2.fromScale(0, 0.44),
		Size = UDim2.new(1, 0, 0.26, 0),
		Text = Format.oneIn(aura.OneIn),
		TextColor3 = aura.Tier.Color,
		Parent = card,
	}, 18)
	Ui.label({
		Position = UDim2.fromScale(0, 0.72),
		Size = UDim2.new(1, 0, 0.28, 0),
		Text = footer,
		TextColor3 = Theme.SubText,
		Parent = card,
	}, 16)
	return card
end

local function renderInventory(state: PlayerState.Snapshot)
	headerButton.Visible = true
	headerButton.Text = if state.Settings.AutoEquip
		then "더 희귀하면 자동 장착: 켬"
		else "더 희귀하면 자동 장착: 끔"
	gridLayout()

	local count = 0
	for order, aura in Auras.RarestFirst do
		local owned = state.Inventory[aura.Id] or 0
		if owned > 0 then
			count += 1
			local equipped = state.Equipped == aura.Id
			local footer =
				string.format("x%s · %s", Format.commas(owned), if equipped then "장착 중" else "눌러서 장착")
			local card = auraCard(order, aura, true, footer, equipped)
			card.Activated:Connect(function()
				handlers.Equip(if equipped then nil else aura.Id)
			end)
		end
	end
	if count == 0 then
		Ui.label({
			Size = UDim2.new(1, 0, 0, 40),
			Text = "아직 오라가 없어요. 굴려 보세요!",
			TextColor3 = Theme.SubText,
			Parent = body,
		}, 24)
	end
end

local function renderIndex(state: PlayerState.Snapshot)
	local found = 0
	for _, aura in Auras.List do
		if (state.Inventory[aura.Id] or 0) > 0 then
			found += 1
		end
	end
	titleLabel.Text = string.format("%s  (%d / %d 발견)", TITLES.Index, found, #Auras.List)
	gridLayout()
	for order, aura in Auras.List do
		local known = (state.Inventory[aura.Id] or 0) > 0
		auraCard(order, aura, known, aura.Tier.Name .. " · " .. aura.Subtitle, false)
	end
end

local function renderShop(state: PlayerState.Snapshot)
	local layout = Ui.list(Enum.FillDirection.Vertical, 10, Enum.HorizontalAlignment.Center)
	layout.VerticalAlignment = Enum.VerticalAlignment.Top
	layout.Parent = body
	Ui.padding(6).Parent = body

	for order, potion in Config.Potions do
		local row = Ui.new("Frame", {
			LayoutOrder = order,
			Size = UDim2.new(1, -12, 0, 86),
			BackgroundColor3 = Theme.PanelLight,
			Parent = body,
		})
		Ui.corner(12).Parent = row
		Ui.stroke(potion.Color, 2, 0.2).Parent = row
		Ui.padding(10).Parent = row

		local remaining = state.Potions[potion.Id]
		Ui.label({
			Size = UDim2.new(0.68, 0, 0.5, 0),
			TextXAlignment = Enum.TextXAlignment.Left,
			Font = Theme.FontHeavy,
			Text = potion.Name .. (if remaining then "  (사용 중)" else ""),
			TextColor3 = potion.Color,
			Parent = row,
		}, 26)
		Ui.label({
			Position = UDim2.fromScale(0, 0.52),
			Size = UDim2.new(0.68, 0, 0.48, 0),
			TextXAlignment = Enum.TextXAlignment.Left,
			Text = potion.Description,
			TextColor3 = Theme.SubText,
			Parent = row,
		}, 20)

		local affordable = state.Coins >= potion.Price
		local buy = Ui.button({
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.fromScale(1, 0.5),
			Size = UDim2.new(0.3, 0, 1, 0),
			BackgroundColor3 = if affordable then Theme.Good else Theme.PanelLight,
			TextColor3 = if affordable then Color3.new(0.05, 0.1, 0.05) else Theme.SubText,
			Text = "🪙 " .. Format.commas(potion.Price),
			Parent = row,
		}, 24)
		buy.Activated:Connect(function()
			handlers.Buy(potion.Id)
		end)
	end

	Ui.label({
		LayoutOrder = 100,
		Size = UDim2.new(1, -12, 0, 30),
		Text = string.format(
			"같은 물약은 시간만 늘어나요(최대 %d분). 다른 물약끼리는 효과가 곱해져요.",
			Config.MAX_POTION_SECONDS // 60
		),
		TextColor3 = Theme.SubText,
		Parent = body,
	}, 18)
end

local function render()
	if not openName then
		return
	end
	clearBody()
	titleLabel.Text = TITLES[openName]
	headerButton.Visible = false
	local state = lastState
	if not state then
		return
	end
	if openName == "Inventory" then
		renderInventory(state)
	elseif openName == "Index" then
		renderIndex(state)
	elseif openName == "Shop" then
		renderShop(state)
	end
end

function Panels.init(parent: ScreenGui, callbacks: Handlers)
	handlers = callbacks

	window = Ui.new("Frame", {
		Name = "Window",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(660, 450),
		BackgroundColor3 = Theme.Panel,
		BackgroundTransparency = 0.05,
		Visible = false,
		ZIndex = 5,
		Parent = parent,
	})
	Ui.corner(16).Parent = window
	Ui.stroke(Theme.Accent, 2, 0.2).Parent = window
	Ui.autoScale(window)

	titleLabel = Ui.label({
		Position = UDim2.fromOffset(16, 10),
		Size = UDim2.new(0.5, 0, 0, 36),
		TextXAlignment = Enum.TextXAlignment.Left,
		Font = Theme.FontHeavy,
		Parent = window,
	}, 28)

	headerButton = Ui.button({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -64, 0, 10),
		Size = UDim2.fromOffset(250, 38),
		Visible = false,
		Parent = window,
	}, 18)
	headerButton.Activated:Connect(function()
		handlers.ToggleAutoEquip()
	end)

	local close = Ui.button({
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -12, 0, 10),
		Size = UDim2.fromOffset(40, 38),
		BackgroundColor3 = Theme.Bad,
		Text = "✕",
		Parent = window,
	}, 22)
	close.Activated:Connect(Panels.close)

	body = Ui.new("ScrollingFrame", {
		Position = UDim2.fromOffset(12, 58),
		Size = UDim2.new(1, -24, 1, -70),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 6,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		ScrollingDirection = Enum.ScrollingDirection.Y,
		Parent = window,
	})
end

-- 같은 창 버튼을 다시 누르면 닫힘
function Panels.toggle(name: string)
	if openName == name then
		Panels.close()
		return
	end
	openName = name
	window.Visible = true
	render()
end

function Panels.close()
	openName = nil
	window.Visible = false
	clearBody()
end

function Panels.render(state: PlayerState.Snapshot?)
	lastState = state
	render()
end

return Panels
