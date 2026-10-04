-- 상태창 갈래들이 함께 쓰는 조각: 카드(판), 그림 칸, 글자 도장, 키 표, 머리글, 카드 격자.
-- 상태창은 StatusWindow, 갈래는 SkillsTab(술법·공법), BeopguTab(법구), PouchTab(주머니).

local Ui = require(script.Parent.Ui)

local C = Ui.C
local new, image, text = Ui.new, Ui.image, Ui.text

local Kit = {}

-- 갈래가 상태창에서 받는 것 (StatusWindow 가 Hud 에서 받아 넘긴다)
export type Context = {
	actions: { [string]: any }, -- Hud.Actions (assign, equip, equipGuard, eat)
	keyboard: boolean,
	touchOnly: boolean,
	startBinding: (slot: number) -> (),
	bindingSlot: () -> number?,
	cooldownLeft: (id: string) -> number, -- 남은 쿨타임(초)
	heldWeapon: () -> number?, -- 손에 든 공격 법구 칸 (도구의 WeaponIndex)
	toast: (message: string, kind: string?) -> (),
	refresh: () -> (), -- 마지막 상태로 다시 그린다 (고르기가 바뀌었을 때)
}

-- 갈래 안 크기. 카드 줄은 W 까지 쓰고, 오른쪽 GUTTER 는 스크롤 막대 자리
Kit.W = 692
Kit.H = 380
Kit.GUTTER = 10
Kit.GAP_X = 11
Kit.GAP_Y = 8
Kit.CARD_H = 80

-- 등급 색: 범품(목) → 극품(천)
Kit.GRADE = {
	C.dim,
	C.cream,
	C.jade,
	Color3.fromRGB(156, 198, 238),
	C.gold,
}

local FILL = Color3.fromRGB(46, 52, 70)
-- 카드 모양: 보통, 고른 것(금테), 눌러서 넣을 곳(옥테), 지닌 것, 흐린 것(아직 못 쓰는 것)
local LOOKS = {
	normal = { fill = FILL, fillT = 0.45, line = C.gold, lineT = 0.78, thick = 1 },
	on = { fill = Color3.fromRGB(44, 80, 72), fillT = 0.2, line = C.gold, lineT = 0, thick = 2 },
	target = { fill = Color3.fromRGB(40, 64, 62), fillT = 0.35, line = C.jade, lineT = 0.2, thick = 2 },
	worn = { fill = Color3.fromRGB(70, 62, 40), fillT = 0.35, line = C.gold, lineT = 0.3, thick = 1.5 },
	dim = { fill = FILL, fillT = 0.78, line = C.gold, lineT = 0.92, thick = 1 },
}
export type Look = "normal" | "on" | "target" | "worn" | "dim"

-- 둥근 카드. clickable 이면 ImageButton (누르면 살짝 줄었다 돌아온다)
function Kit.card(parent: Instance, props: { [string]: any }, clickable: boolean?): (GuiObject, UIStroke)
	local card = new(if clickable then "ImageButton" else "Frame", {
		BackgroundColor3 = FILL,
		BackgroundTransparency = 0.45,
		BorderSizePixel = 0,
	})
	if clickable then
		card.AutoButtonColor = false
		card.Image = ""
	end
	for key, value in props do
		if key ~= "Parent" then
			card[key] = value
		end
	end
	new("UICorner", { CornerRadius = UDim.new(0, 8), Parent = card })
	local stroke = new("UIStroke", {
		Color = C.gold,
		Transparency = 0.78,
		Thickness = 1,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
		Parent = card,
	})
	if clickable then
		local press = new("UIScale", { Parent = card })
		card.MouseButton1Down:Connect(function()
			press.Scale = 0.97
		end)
		card.MouseButton1Up:Connect(function()
			press.Scale = 1
		end)
		card.MouseLeave:Connect(function()
			press.Scale = 1
		end)
		card.Activated:Connect(function()
			press.Scale = 1
		end)
	end
	card.Parent = props.Parent or parent
	return card, stroke
end

function Kit.look(card: GuiObject, stroke: UIStroke, look: Look)
	local spec = LOOKS[look]
	card.BackgroundColor3 = spec.fill
	card.BackgroundTransparency = spec.fillT
	stroke.Color = spec.line
	stroke.Transparency = spec.lineT
	stroke.Thickness = spec.thick
end

-- 그림 칸(slot 판)과 그 안의 그림
function Kit.slot(parent: Instance, size: number, position: UDim2, iconName: string?): (ImageLabel, ImageLabel)
	local frame =
		image("slot", { Name = "Slot", Position = position, Size = UDim2.fromOffset(size, size), Parent = parent })
	local icon = image(iconName or "skillDash", {
		Name = "Icon",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.72, 0.72),
		Visible = iconName ~= nil,
		Parent = frame,
	})
	return frame, icon
end

-- 글자 도장: 그림 칸 안에 붓글씨 한 글자 (법구·물건은 그림이 없어서 이름 글자로 알아보게 한다)
function Kit.seal(parent: Instance, size: number, position: UDim2): (ImageLabel, any)
	local frame =
		image("slot", { Name = "Seal", Position = position, Size = UDim2.fromOffset(size, size), Parent = parent })
	local holder = Ui.row({ Size = UDim2.new(1, 0, 1, -math.floor(size * 0.1)), Parent = frame })
	holder:FindFirstChildOfClass("UIListLayout").VerticalAlignment = Enum.VerticalAlignment.Center
	local glyph = text("title", math.floor(size * 0.52), { color = C.cream, name = "Glyph", parent = holder })
	return frame, glyph
end

-- 키 표 (금빛 네모에 검은 글자). clickable 이면 ImageButton
function Kit.key(parent: Instance, width: number, height: number, size: number, clickable: boolean?): (GuiObject, any)
	local badge = new(if clickable then "ImageButton" else "Frame", {
		Name = "Key",
		Size = UDim2.fromOffset(width, height),
		BackgroundColor3 = C.keyBack,
		BorderSizePixel = 0,
		ZIndex = 2,
		Parent = parent,
	}, { new("UICorner", { CornerRadius = UDim.new(0, 5) }) })
	if clickable then
		badge.AutoButtonColor = false
		badge.Image = ""
	end
	local holder = Ui.row({ Size = UDim2.new(1, 0, 1, -1), Parent = badge })
	holder:FindFirstChildOfClass("UIListLayout").VerticalAlignment = Enum.VerticalAlignment.Center
	local label = text("body", size, { color = C.keyText, parent = holder })
	return badge, label
end

-- 갈래 안 머리글: 왼쪽 제목, 오른쪽 작은 글 (반환: 오른쪽 글)
function Kit.header(parent: Instance, title: string, position: UDim2, width: number): (Frame, any)
	local holder = new("Frame", {
		Name = "Header",
		Position = position,
		Size = UDim2.fromOffset(width, 28),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	text("title", 21, { gradient = Ui.GOLD_TEXT, text = title, name = "Title", parent = holder })
	local sub = text("body", 14, { color = C.dim, name = "Sub" })
	sub.frame.AnchorPoint = Vector2.new(1, 0)
	sub.frame.Position = UDim2.new(1, -2, 0, 5)
	sub.frame.Parent = holder
	new("Frame", {
		Position = UDim2.new(0, 0, 1, 1),
		Size = UDim2.new(1, 0, 0, 1),
		BackgroundColor3 = C.gold,
		BackgroundTransparency = 0.82,
		BorderSizePixel = 0,
		Parent = holder,
	})
	return holder, sub
end

-- 카드 격자 (세로 스크롤). 반환: 목록, 칸 너비
-- 터치 기기는 아래에 Roblox 도구 칸이 겹치므로 끝에 여백을 두어 마지막 줄도 그 위로 올릴 수 있게 한다
function Kit.grid(
	parent: Instance,
	props: { [string]: any },
	columns: number,
	cellHeight: number,
	touchOnly: boolean
): (ScrollingFrame, number)
	local list = new("ScrollingFrame", {
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 4,
		ScrollBarImageColor3 = C.gold,
		ScrollingDirection = Enum.ScrollingDirection.Y,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
	})
	for key, value in props do
		if key ~= "Parent" then
			list[key] = value
		end
	end
	local cellWidth = math.floor((Kit.W - 4 - (columns - 1) * Kit.GAP_X) / columns)
	new("UIPadding", {
		PaddingLeft = UDim.new(0, 2),
		PaddingTop = UDim.new(0, 2),
		PaddingBottom = UDim.new(0, if touchOnly then 70 else 2),
		Parent = list,
	})
	new("UIGridLayout", {
		CellSize = UDim2.fromOffset(cellWidth, cellHeight),
		CellPadding = UDim2.fromOffset(Kit.GAP_X, Kit.GAP_Y),
		FillDirectionMaxCells = columns,
		SortOrder = Enum.SortOrder.LayoutOrder,
		Parent = list,
	})
	list.Parent = props.Parent or parent
	return list, cellWidth
end

-- 빈 목록에 띄우는 글 (여러 줄)
function Kit.note(
	parent: Instance,
	name: string,
	width: number,
	lines: number,
	position: UDim2
): (Frame, (string) -> ())
	local holder, set = Ui.paragraph("body", 15, width, lines, C.dim, parent)
	holder.Name = name
	holder.Position = position
	return holder, function(message: string)
		set(message)
	end
end

-- 소수 둘째 자리까지, 끝의 0 은 뺀다 (1.30 → 1.3)
function Kit.number(value: number): string
	local shown = string.format("%.2f", value)
	shown = string.gsub(shown, "0+$", "")
	shown = string.gsub(shown, "%.$", "")
	return shown
end

-- 초를 짧게: 60초 넘으면 분
function Kit.seconds(value: number): string
	if value >= 60 and value % 60 == 0 then
		return string.format("%d분", value // 60)
	end
	return string.format("%s초", Kit.number(value))
end

return Kit
