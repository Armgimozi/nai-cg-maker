-- 다른 땅에 들어서면 화면 위쪽에 그 땅 이름을 붓글씨로 잠깐 띄운다.
-- 맵에 이름표를 띄우지 않는 대신 이것과 상태 창의 "지금 있는 곳" 줄로 알려 준다.

local BitmapText = require(script.Parent.BitmapText)
local Ui = require(script.Parent.Ui)

local C = Ui.C
local new = Ui.new

local PlaceBanner = {}

local TITLE_SIZE = 54
local SUB_SIZE = 18
local FADE_IN = 0.6
local HOLD = 2.6
local FADE_OUT = 1.2

local holder: Frame? = nil
local title, sub
local fade: NumberValue? = nil
local shown = 0 -- 마지막으로 띄운 차례 (겹쳐 들어오면 앞의 것은 사라지지 않고 바로 바뀐다)
local showingUntil = 0

function PlaceBanner.build(gui: ScreenGui): Frame
	local frame = new("Frame", {
		Name = "PlaceBanner",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0.2, 0),
		Size = UDim2.fromOffset(640, 110),
		BackgroundTransparency = 1,
		ZIndex = 6,
		Parent = gui,
	})
	new("UIScale", { Parent = frame })
	local titleRow = Ui.row({ Size = UDim2.new(1, 0, 0, 70), Parent = frame })
	title = BitmapText.new({ font = "title", size = TITLE_SIZE, gradient = Ui.GOLD_TEXT, parent = titleRow })
	local subRow = Ui.row({ Position = UDim2.fromOffset(0, 72), Size = UDim2.new(1, 0, 0, 28), Parent = frame })
	sub = BitmapText.new({ font = "body", size = SUB_SIZE, color = C.cream, parent = subRow })

	local value = new("NumberValue", { Value = 1, Parent = frame })
	value.Changed:Connect(function(v: number)
		title:setTransparency(v)
		sub:setTransparency(math.min(1, v + 0.1))
	end)
	title:setTransparency(1)
	sub:setTransparency(1)
	fade = value
	holder = frame
	return frame
end

function PlaceBanner.show(name: string, subtitle: string?)
	local value = fade
	if not holder or not value then
		return
	end
	shown += 1
	local mine = shown
	showingUntil = os.clock() + FADE_IN + HOLD + FADE_OUT
	title:set(name)
	sub:set(subtitle or "")
	Ui.tween(value, TweenInfo.new(FADE_IN), { Value = 0 })
	task.delay(FADE_IN + HOLD, function()
		if shown == mine then
			Ui.tween(value, TweenInfo.new(FADE_OUT), { Value = 1 })
		end
	end)
end

-- 이름이 화면에 떠 있는가 (그동안 알림은 위로 비켜 선다)
function PlaceBanner.isShowing(): boolean
	return os.clock() < showingUntil
end

return PlaceBanner
