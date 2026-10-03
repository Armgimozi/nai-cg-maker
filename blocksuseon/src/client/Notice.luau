-- 화면 알림: 위 가운데에 칠기 띠로 잠깐 떴다가 사라진다.
-- 글자는 BitmapText 글자판으로 찍는다. 플레이어 이름처럼 글자판에 없는 글자가 섞이면
-- 그 알림만 Roblox 글꼴로 찍는다.
--
-- 한꺼번에 몰려도 버리지 않는다. 자리가 차면 줄을 세웠다가 앞의 것이 사라지는 대로 띄운다.
-- 경지 연출이 화면을 덮는 동안에는 잠시 멈추고(hold), 창(상태창·고르기·내관)이 열려 있으면
-- 창 제목을 가리지 않게 화면 맨 위로 올려 둘만 띄운다(compact).

local TextService = game:GetService("TextService")

local Art = require(script.Parent.Art)
local BitmapText = require(script.Parent.BitmapText)
local Ui = require(script.Parent.Ui)

local C = Ui.C
local new, image = Ui.new, Ui.image

local Notice = {}

local MAX_VISIBLE = 4
local MAX_COMPACT = 2
local WIDTH = 620
local TEXT_WIDTH = WIDTH - 90
local TEXT_SIZE = 18
local WORLD_SIZE = 16
local LINE_GAP = 6
local FADE = 0.35
local NORMAL_Y = 92
local COMPACT_Y = 6

local COLORS = {
	info = C.cream,
	good = C.jade,
	bad = C.red,
	tribulation = Color3.fromRGB(242, 176, 94),
	world = C.gold,
}

type Entry = {
	frame: ImageLabel,
	text: string,
	expires: number,
	fade: NumberValue,
}

type Pending = { text: string, kind: string? }

local holder: Frame? = nil
local entries: { Entry } = {}
local pending: { Pending } = {}
local order = 0
local holdUntil = 0
local compact = false

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

local function capacity(): number
	return if compact then MAX_COMPACT else MAX_VISIBLE
end

local pump: () -> ()

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
	pump()
end

-- 정해진 때까지 기다렸다가 사라진다. 그 사이 같은 알림이 와서 시간이 늘었으면 더 기다린다
local function expireLater(entry: Entry)
	task.spawn(function()
		while table.find(entries, entry) and os.clock() < entry.expires do
			task.wait(entry.expires - os.clock())
		end
		remove(entry)
	end)
end

-- 글자판에 없는 글자가 있을 때: Roblox 글꼴 글자의 높이
local function fallbackHeight(text: string, size: number): number
	local ok, bounds = pcall(function()
		return TextService:GetTextSize(text, size, Enum.Font.GothamMedium, Vector2.new(TEXT_WIDTH, 1000))
	end)
	if ok and typeof(bounds) == "Vector2" then
		return bounds.Y
	end
	local lines = math.clamp(math.ceil((utf8.len(text) or 1) * size * 0.9 / TEXT_WIDTH), 1, 3)
	return lines * (size + 4)
end

local function display(message: string, kind: string?)
	local parent = holder
	if not parent then
		return
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
	local textHeight
	if covered(message) then
		local lines = Ui.wrap("body", size, message, TEXT_WIDTH)
		textHeight = math.max(1, #lines) * (size + LINE_GAP)
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
		textHeight = math.max(size + LINE_GAP, fallbackHeight(message, size - 1) + 4)
		local label = new("TextLabel", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromOffset(TEXT_WIDTH, textHeight),
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
		table.insert(painters, function(value: number)
			label.TextTransparency = value
		end)
	end
	strip.Size = UDim2.fromOffset(WIDTH, 18 + textHeight)

	local fade = new("NumberValue", { Value = 1, Parent = strip })
	local function paint(value: number)
		strip.ImageTransparency = 0.05 + value * 0.95
		for _, painter in painters do
			painter(value)
		end
	end
	fade.Changed:Connect(paint)
	paint(1)

	-- 사라질 때는 화면에 뜬 때부터 센다
	local entry: Entry = { frame = strip, text = message, expires = os.clock() + duration(message), fade = fade }
	table.insert(entries, entry)
	Ui.tween(fade, TweenInfo.new(FADE), { Value = 0 })
	expireLater(entry)
end

pump = function()
	if os.clock() < holdUntil then
		return
	end
	while #entries < capacity() and #pending > 0 do
		local nextOne = table.remove(pending, 1) :: Pending
		display(nextOne.text, nextOne.kind)
	end
end

function Notice.build(gui: ScreenGui)
	local frame = new("Frame", {
		Name = "Notices",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, NORMAL_Y),
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
	if not holder or message == "" then
		return
	end
	-- 같은 알림이 떠 있거나 기다리는 중이면 겹쳐 쌓지 않는다
	for _, entry in entries do
		if entry.text == message then
			entry.expires = math.max(entry.expires, os.clock() + duration(message))
			return
		end
	end
	for _, waiting in pending do
		if waiting.text == message then
			return
		end
	end
	table.insert(pending, { text = message, kind = kind })
	pump()
end

-- 경지 연출처럼 화면을 덮는 동안 멈춘다. 떠 있던 알림도 그만큼 더 남는다
function Notice.hold(seconds: number)
	local now = os.clock()
	local untilTime = now + seconds
	if untilTime <= holdUntil then
		return
	end
	local extra = untilTime - math.max(now, holdUntil)
	holdUntil = untilTime
	for _, entry in entries do
		entry.expires += extra
	end
	task.delay(seconds + 0.05, pump)
end

-- 창이 열려 있으면 맨 위로 올리고 둘만 띄운다
function Notice.setCompact(on: boolean)
	if compact == on or not holder then
		return
	end
	compact = on
	holder.Position = UDim2.new(0.5, 0, 0, if on then COMPACT_Y else NORMAL_Y)
	pump()
end

-- 테스트용
function Notice.count(): number
	return #entries
end

function Notice.pendingCount(): number
	return #pending
end

function Notice.clear()
	table.clear(pending)
	for _, entry in table.clone(entries) do
		remove(entry)
	end
	holdUntil = 0
end

return Notice
