-- 화면 알림: 위 가운데에 칠기 띠로 잠깐 떴다가 사라진다.
-- 글자는 BitmapText 글자판으로 찍는다. 플레이어 이름처럼 글자판에 없는 글자가 섞이면
-- 그 알림만 Roblox 글꼴로 찍는다.

local Art = require(script.Parent.Art)
local BitmapText = require(script.Parent.BitmapText)
local Ui = require(script.Parent.Ui)

local C = Ui.C
local new, image = Ui.new, Ui.image

local Notice = {}

local MAX_VISIBLE = 4
local WIDTH = 620
local TEXT_SIZE = 18
local WORLD_SIZE = 16
local LINE_GAP = 6
local FADE = 0.35

local COLORS = {
	info = C.cream,
	good = C.jade,
	bad = C.red,
	tribulation = Color3.fromRGB(242, 176, 94),
	world = C.gold,
}

type Entry = {
	frame: Frame,
	text: string,
	expires: number,
	fade: NumberValue,
	paint: (number) -> (),
}

local holder: Frame? = nil
local entries: { Entry } = {}
local order = 0

local function covered(text: string): boolean
	local glyphs = Art.fonts.body.glyphs
	for _, code in utf8.codes(text) do
		local ch = utf8.char(code)
		if ch ~= " " and not glyphs[ch] then
			return false
		end
	end
	return true
end

local function duration(text: string): number
	return math.clamp(3 + (utf8.len(text) or 40) * 0.06, 3.5, 9)
end

local function remove(entry: Entry)
	local index = table.find(entries, entry)
	if not index then
		return
	end
	table.remove(entries, index)
	Ui.tween(entry.fade, TweenInfo.new(FADE), { Value = 1 })
	task.delay(FADE + 0.05, function()
		entry.frame:Destroy()
	end)
end

function Notice.build(gui: ScreenGui)
	local frame = new("Frame", {
		Name = "Notices",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 92),
		Size = UDim2.fromOffset(WIDTH, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		BackgroundTransparency = 1,
		ZIndex = 8,
		Parent = gui,
	}, {
		new("UIListLayout", {
			SortOrder = Enum.SortOrder.LayoutOrder,
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			Padding = UDim.new(0, 4),
		}),
	})
	new("UIScale", { Parent = frame })
	holder = frame
	return frame
end

-- kind: "info" | "good" | "bad" | "tribulation" | "world"
function Notice.show(message: string, kind: string?)
	local parent = holder
	if not parent or message == "" then
		return
	end
	local now = os.clock()
	-- 같은 알림이 떠 있으면 새로 띄우지 않고 시간만 늘린다
	for _, entry in entries do
		if entry.text == message then
			entry.expires = now + duration(message)
			return
		end
	end

	local color = COLORS[kind or "info"] or C.cream
	local size = if kind == "world" then WORLD_SIZE else TEXT_SIZE
	order += 1
	local strip = image("notice", {
		LayoutOrder = order,
		Size = UDim2.fromOffset(WIDTH, 0),
		SliceScale = 0.8,
		ImageTransparency = 1,
		Parent = parent,
	})

	-- 투명도를 바꿀 함수들 (글자판 글자와 Roblox 글자를 같은 방식으로 다룬다)
	local painters: { (number) -> () } = {}
	local lineCount = 1
	if covered(message) then
		local lines = Ui.wrap("body", size, message, WIDTH - 90)
		lineCount = math.max(1, #lines)
		for i, line in lines do
			local lineRow = Ui.row({
				Position = UDim2.fromOffset(0, 9 + (i - 1) * (size + LINE_GAP)),
				Size = UDim2.new(1, 0, 0, size + LINE_GAP),
				Parent = strip,
			})
			local label = BitmapText.new({ font = "body", size = size, color = color, text = line, parent = lineRow })
			table.insert(painters, function(value: number)
				label:setTransparency(value)
			end)
		end
	else
		-- 글자판에 없는 글자(이름 등)가 있으면 Roblox 글꼴로
		local label = new("TextLabel", {
			Position = UDim2.fromOffset(45, 8),
			Size = UDim2.new(1, -90, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			BackgroundTransparency = 1,
			Font = Enum.Font.GothamMedium,
			TextSize = size - 1,
			TextColor3 = color,
			TextStrokeTransparency = 0.6,
			TextWrapped = true,
			Text = message,
			TextTransparency = 1,
			Parent = strip,
		})
		lineCount = math.clamp(math.ceil((utf8.len(message) or 1) * size * 0.9 / (WIDTH - 90)), 1, 3)
		table.insert(painters, function(value: number)
			label.TextTransparency = value
		end)
	end
	strip.Size = UDim2.fromOffset(WIDTH, 18 + lineCount * (size + LINE_GAP))

	local fade = new("NumberValue", { Value = 1, Parent = strip })
	local function paint(value: number)
		strip.ImageTransparency = 0.05 + value * 0.95
		for _, painter in painters do
			painter(value)
		end
	end
	fade.Changed:Connect(paint)
	paint(1)

	local entry: Entry =
		{ frame = strip, text = message, expires = now + duration(message), fade = fade, paint = paint }
	table.insert(entries, entry)
	Ui.tween(fade, TweenInfo.new(FADE), { Value = 0 })

	while #entries > MAX_VISIBLE do
		remove(entries[1])
	end

	task.delay(duration(message), function()
		-- 같은 알림이 다시 와서 시간이 늘었으면 그때까지 기다린다
		while table.find(entries, entry) and os.clock() < entry.expires do
			task.wait(entry.expires - os.clock())
		end
		remove(entry)
	end)
end

-- 테스트용
function Notice.count(): number
	return #entries
end

return Notice
