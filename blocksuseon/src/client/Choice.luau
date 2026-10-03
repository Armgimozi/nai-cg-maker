-- 고르기 창: 영근 깨우기, 칠수, 본명 속성.
-- 고른 값은 서버에 "Choose" 로 보내고, 서버가 확인한 뒤 상태로 돌려준다.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Roots = require(Shared.Roots)
local Tasks = require(Shared.Tasks)
local Ui = require(script.Parent.Ui)

local C = Ui.C
local new, image, setImage, text, row = Ui.new, Ui.image, Ui.setImage, Ui.text, Ui.row

local Choice = {}

local ui: { [string]: any } = {}
local onChoose: (key: string, value: any) -> ()
local currentKey: string? = nil
local picked: { string } = {}
local optionRows: { { [string]: any } } = {}
local lastRoot: Roots.Root? = nil

-- 1.30 → "1.3", 1.00 → "1"
local function mult(value: number): string
	local out = string.format("%.2f", value)
	out = string.gsub(out, "0+$", "")
	out = string.gsub(out, "%.$", "")
	return out
end

local function close()
	ui.panel.Visible = false
	currentKey = nil
end

-- 영근 창 ------------------------------------------------------------------------------

local function refreshRoot()
	for _, entry in ui.elementButtons do
		local on = table.find(picked, entry.element) ~= nil
		setImage(entry.button, if on then "orbGold" else "orbStone")
	end
	local root = Roots.make(picked)
	if root then
		local kind = Roots.KIND[root.kind]
		ui.rootName:set(Roots.describe(root))
		ui.setRootSummary(kind.summary)
		ui.rootStats:set(
			string.format(
				"흡수 ×%s   내관 판정 ×%s   시운 %d초   무극영운 가닥 %d",
				mult(Roots.gain(root)),
				mult(Roots.band(root)),
				Roots.window(root),
				Roots.strands(root)
			)
		)
	else
		ui.rootName:set("기운 하나를 고른다")
		ui.setRootSummary("")
		ui.rootStats:set("")
	end
	setImage(ui.confirm, if root then "pillJade" else "pillStone")
	ui.confirmText:setColor(if root then C.cream else C.dim)
end

local function buildRoot(panel: Instance)
	local page = new("Frame", {
		Name = "Root",
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Parent = panel,
	})
	local _, setIntro = Ui.paragraph("body", 16, 520, 2, C.cream, page)
	_.Position = UDim2.fromOffset(50, 96)
	setIntro(
		"몸에 반응하는 기운 하나를 고른다. 그 속성이 영근이자 본명 속성이 된다. 한 번 깨어난 영근은 바꿀 수 없다."
	)

	local buttons = row({
		Position = UDim2.fromOffset(0, 162),
		Size = UDim2.new(1, 0, 0, 96),
		Parent = page,
	}, nil, 18)
	ui.elementButtons = {}
	for index, element in Roots.ELEMENTS do
		local def = Roots.ELEMENT[element]
		local holder = new("Frame", {
			LayoutOrder = index,
			Size = UDim2.fromOffset(78, 96),
			BackgroundTransparency = 1,
			Parent = buttons,
		})
		local button = image("orbStone", { Size = UDim2.fromOffset(78, 78), Parent = holder }, "ImageButton")
		local nameRow = row({ Size = UDim2.new(1, 0, 1, -6), Parent = button })
		text("title", 34, {
			color = Color3.fromRGB(def.color[1], def.color[2], def.color[3]),
			text = def.name,
			parent = nameRow,
		})
		button.Activated:Connect(function()
			-- 영근은 한 속성만 지닌다: 누르면 그 속성 하나로 바뀐다
			picked = if picked[1] == element then {} else { element }
			refreshRoot()
		end)
		table.insert(ui.elementButtons, { element = element, button = button })
	end

	local nameRow = row({ Position = UDim2.fromOffset(0, 268), Size = UDim2.new(1, 0, 0, 40), Parent = page })
	ui.rootName = text("title", 28, { gradient = Ui.GOLD_TEXT, parent = nameRow })
	local summaryHolder, setSummary = Ui.paragraph("body", 15, 520, 2, C.cream, page)
	summaryHolder.Position = UDim2.fromOffset(50, 316)
	ui.setRootSummary = setSummary
	ui.rootStats = text("body", 14, { color = C.jade })
	ui.rootStats.frame.Position = UDim2.fromOffset(50, 366)
	ui.rootStats.frame.Parent = page
	ui.rootPage = page
end

-- 여러 개 중 하나 고르기 (칠수, 본명 속성) ---------------------------------------------------

local function buildOptions(panel: Instance)
	local page = new("Frame", {
		Name = "Options",
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Parent = panel,
	})
	local introHolder, setIntro = Ui.paragraph("body", 16, 520, 2, C.cream, page)
	introHolder.Position = UDim2.fromOffset(50, 96)
	ui.setOptionsIntro = setIntro
	local list = new("Frame", {
		Position = UDim2.fromOffset(50, 152),
		Size = UDim2.fromOffset(520, 240),
		BackgroundTransparency = 1,
		Parent = page,
	}, {
		new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder, Padding = UDim.new(0, 6) }),
	})
	for index = 1, 5 do
		local button = image("pillStone", {
			LayoutOrder = index,
			Size = UDim2.new(1, 0, 0, 52),
			SliceScale = 0.5,
			Visible = false,
			Parent = list,
		}, "ImageButton")
		local name = text("title", 22, { color = C.cream })
		name.frame.Position = UDim2.fromOffset(18, 4)
		name.frame.Parent = button
		local summary = text("body", 13, { color = C.dim })
		summary.frame.Position = UDim2.fromOffset(150, 14)
		summary.frame.Parent = button
		local entry = { button = button, name = name, summary = summary, value = nil }
		button.Activated:Connect(function()
			if entry.value then
				picked = { entry.value }
				for _, other in optionRows do
					setImage(other.button, if other.value == entry.value then "pillJade" else "pillStone")
				end
				setImage(ui.confirm, "pillJade")
				ui.confirmText:setColor(C.cream)
			end
		end)
		optionRows[index] = entry
	end
	ui.optionsPage = page
end

local function showOptions(intro: string, options: { { value: string, name: string, summary: string } })
	ui.setOptionsIntro(intro)
	for index, entry in optionRows do
		local option = options[index]
		entry.button.Visible = option ~= nil
		entry.value = option and option.value
		if option then
			entry.name:set(option.name)
			entry.summary:set(option.summary)
			setImage(entry.button, "pillStone")
		end
	end
	setImage(ui.confirm, "pillStone")
	ui.confirmText:setColor(C.dim)
end

-- 공개 ---------------------------------------------------------------------------------

function Choice.build(gui: ScreenGui, choose: (key: string, value: any) -> ())
	onChoose = choose
	local panel = image("panel", {
		Name = "Choice",
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
	ui.title = text("title", 38, { gradient = Ui.GOLD_TEXT, parent = titleRow })
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

	buildRoot(panel)
	buildOptions(panel)

	local confirm, confirmText = Ui.pill("정했다", 200, 44, 18, panel, function()
		if not currentKey or #picked == 0 then
			return
		end
		if currentKey == "root" then
			if not Roots.make(picked) then
				return
			end
			onChoose("root", table.clone(picked))
		else
			onChoose(currentKey, picked[1])
		end
		close()
	end)
	confirm.AnchorPoint = Vector2.new(0.5, 1)
	confirm.Position = UDim2.new(0.5, 0, 1, -26)
	ui.confirm = confirm
	ui.confirmText = confirmText
end

function Choice.isOpen(): boolean
	return ui.panel ~= nil and ui.panel.Visible
end

function Choice.close()
	close()
end

-- key: "root" | "chilsu" | "element"
function Choice.open(key: string, state: { [string]: any })
	currentKey = key
	picked = {}
	lastRoot = state.root
	ui.rootPage.Visible = key == "root"
	ui.optionsPage.Visible = key ~= "root"
	if key == "root" then
		ui.title:set("영근 깨우기")
		refreshRoot()
	elseif key == "chilsu" then
		ui.title:set("칠수 고르기")
		local options = {}
		for _, id in Tasks.CHOICES.chilsu do
			local def = Tasks.CHILSU[id]
			table.insert(options, { value = id, name = def.name, summary = def.summary })
		end
		showOptions(
			"스물여덟 별 가운데 제사를 올릴 일곱 별을 고른다. 축기기에서 그 수의 별을 맺을 때 도움을 받는다.",
			options
		)
	elseif key == "element" then
		ui.title:set("본명 속성")
		local options = {}
		for _, element in (if lastRoot then lastRoot.elements else {}) do
			local def = Roots.ELEMENT[element]
			table.insert(options, {
				value = element,
				name = def.name .. " 속성",
				summary = string.format("%s에서 닦는다", def.place),
			})
		end
		showOptions("내 영근 속성 가운데 공법의 주 속성으로 삼을 하나를 고른다.", options)
	elseif key == "center" then
		ui.title:set("오악의 중심")
		local options = {}
		local effects = {
			water = "비를 불러 영초를 돋운다",
			wood = "숲을 키워 천년영지를 돋운다",
			earth = "땅을 흔들어 비급을 드러낸다",
			fire = "들불로 둘레 수도자에게 영력을 준다",
			metal = "폭풍으로 둘레의 영물을 끌어온다",
		}
		for _, element in Roots.ELEMENTS do
			local def = Roots.ELEMENT[element]
			table.insert(
				options,
				{ value = element, name = def.name .. " 속성", summary = "천기유도: " .. effects[element] }
			)
		end
		showOptions(
			"오악 가운데 중심에 둘 속성을 고른다. 천인기의 천기유도가 이 속성을 따른다.",
			options
		)
	elseif key == "dosim" then
		ui.title:set("도심")
		local options = {}
		for _, id in Tasks.CHOICES.dosim do
			local def = Tasks.DOSIM[id]
			table.insert(options, { value = id, name = def.name, summary = def.summary })
		end
		showOptions(
			"미쳐 버릴 만큼 몰입할 일을 고른다. 천인기에서는 이 일을 할 때만 광기가 찬다.",
			options
		)
	end
	ui.panel.Visible = true
end

return Choice
