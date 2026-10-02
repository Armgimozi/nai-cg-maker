-- 화면 UI 공용 도우미와 색. Hud, 고르기 창(Choice), 내관 창(Naegwan)이 함께 쓴다.

local TweenService = game:GetService("TweenService")

local Art = require(script.Parent.Art)
local BitmapText = require(script.Parent.BitmapText)

local Ui = {}

Ui.IMG = Art.images

Ui.C = {
	cream = Color3.fromRGB(239, 226, 192),
	dim = Color3.fromRGB(178, 166, 138),
	jade = Color3.fromRGB(150, 222, 192),
	red = Color3.fromRGB(240, 140, 120),
	gold = Color3.fromRGB(240, 212, 140),
	keyBack = Color3.fromRGB(226, 196, 122),
	keyText = Color3.fromRGB(58, 42, 16),
	ink = Color3.fromRGB(22, 20, 26),
}
Ui.GOLD_TEXT = ColorSequence.new({
	ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 246, 214)),
	ColorSequenceKeypoint.new(0.55, Color3.fromRGB(226, 188, 110)),
	ColorSequenceKeypoint.new(1, Color3.fromRGB(178, 136, 66)),
})
Ui.RED_TEXT = ColorSequence.new(Color3.fromRGB(255, 220, 180), Color3.fromRGB(218, 86, 62))

function Ui.new(className: string, props: { [string]: any }?, children: { Instance }?): any
	local inst = Instance.new(className)
	local parent = nil
	for key, value in props or {} do
		if key == "Parent" then
			parent = value
		else
			(inst :: any)[key] = value
		end
	end
	for _, child in children or {} do
		child.Parent = inst
	end
	if parent then
		inst.Parent = parent
	end
	return inst
end

-- Art 그림 하나. 9-slice 그림이면 Slice 로 늘인다.
function Ui.image(name: string, props: { [string]: any }, className: string?): any
	local def = Ui.IMG[name]
	local base: { [string]: any } = {
		BackgroundTransparency = 1,
		Image = def.id,
	}
	if def.slice and props.ScaleType == nil then
		base.ScaleType = Enum.ScaleType.Slice
		base.SliceCenter = def.slice
	end
	if className == "ImageButton" then
		base.AutoButtonColor = false
	end
	for key, value in props do
		base[key] = value
	end
	return Ui.new(className or "ImageLabel", base)
end

function Ui.setImage(target: ImageLabel | ImageButton, name: string)
	local def = Ui.IMG[name]
	target.Image = def.id
	if def.slice then
		target.SliceCenter = def.slice
	end
end

function Ui.text(font: string, size: number, props: { [string]: any }?)
	local options = { font = font, size = size }
	for key, value in props or {} do
		options[key] = value
	end
	return BitmapText.new(options :: any)
end

-- 가운데 정렬 등 줄 배치용 틀
function Ui.row(props: { [string]: any }, align: Enum.HorizontalAlignment?, padding: number?): Frame
	local frame = Ui.new("Frame", props)
	frame.BackgroundTransparency = 1
	Ui.new("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		HorizontalAlignment = align or Enum.HorizontalAlignment.Center,
		VerticalAlignment = Enum.VerticalAlignment.Bottom,
		SortOrder = Enum.SortOrder.LayoutOrder,
		Padding = UDim.new(0, padding or 6),
		Parent = frame,
	})
	return frame
end

function Ui.tween(target: Instance, info: TweenInfo, goal: { [string]: any })
	TweenService:Create(target, info, goal):Play()
end

-- 글자 너비에 맞춰 줄을 나눈다 (BitmapText 는 줄바꿈을 하지 않는다)
function Ui.wrap(font: string, size: number, text: string, width: number): { string }
	local lines = {}
	local current = ""
	for word in string.gmatch(text, "%S+") do
		local candidate = if current == "" then word else current .. " " .. word
		if current ~= "" and BitmapText.measure(font, size, candidate).X > width then
			table.insert(lines, current)
			current = word
		else
			current = candidate
		end
	end
	if current ~= "" then
		table.insert(lines, current)
	end
	return lines
end

-- 여러 줄 글. 반환: 틀, 줄 BitmapText 목록, 다시 쓰기 함수
function Ui.paragraph(font: string, size: number, width: number, maxLines: number, color: Color3, parent: Instance)
	local holder = Ui.new("Frame", {
		Size = UDim2.fromOffset(width, maxLines * (size + 8)),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	local lines = {}
	for i = 1, maxLines do
		local line = Ui.text(font, size, { color = color })
		line.frame.Position = UDim2.fromOffset(0, (i - 1) * (size + 8))
		line.frame.Parent = holder
		lines[i] = line
	end
	local function set(text: string, newColor: Color3?)
		local wrapped = Ui.wrap(font, size, text, width)
		for i, line in lines do
			line:set(wrapped[i] or "")
			if newColor then
				line:setColor(newColor)
			end
		end
	end
	return holder, set
end

-- 옥·돌 알약 버튼 (글자 하나)
function Ui.pill(label: string, width: number, height: number, size: number, parent: Instance, onClick: () -> ())
	local button = Ui.image("pillJade", {
		Size = UDim2.fromOffset(width, height),
		SliceScale = 0.55,
		Parent = parent,
	}, "ImageButton")
	local labelRow = Ui.row({ Size = UDim2.new(1, 0, 1, -2), Parent = button })
	local caption = Ui.text("body", size, { color = Ui.C.cream, text = label, parent = labelRow })
	local press = Ui.new("UIScale", { Parent = button })
	button.MouseButton1Down:Connect(function()
		press.Scale = 0.94
	end)
	button.MouseButton1Up:Connect(function()
		press.Scale = 1
	end)
	button.MouseLeave:Connect(function()
		press.Scale = 1
	end)
	button.Activated:Connect(function()
		press.Scale = 1
		onClick()
	end)
	return button, caption
end

return Ui
