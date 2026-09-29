-- UI 생성 헬퍼와 테마. 모든 화면은 코드로 만들어서 .rbxm 없이도 동작합니다.
-- 스타일: 인기 로블록스 게임식 통통한 UI (밝은 색 + 굵은 Ink 테두리 + 눌리는 3D 버튼, 이모지 없음).
-- 자세한 규칙은 DESIGN.md 의 "UI 스타일 가이드 (v2)" 참고.
-- 그림 에셋: Shared/ImageIds 에 Id 가 들어 있으면 버튼·창·알약·리본·딱지는 9-slice 그림(Ui.skin)으로,
--   아이콘은 ImageLabel 로 그립니다(Ui.icon). 비어 있으면 지금처럼 Frame/3D 모형으로 그립니다.

local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Format = require(Shared.Format)

local Ui = {}

-- 그림 Id 표. 모듈이 없거나 깨져도 기본 모양으로 동작하도록 빈 표로 대체
local function loadImageIds(): { [string]: any }
	local module = Shared:FindFirstChild("ImageIds") or Shared:WaitForChild("ImageIds", 5)
	if module and module:IsA("ModuleScript") then
		local ok, result = pcall(require, module)
		if ok and type(result) == "table" then
			return result
		end
		warn("[LandmarkRNG] ImageIds 를 읽지 못했어요: " .. tostring(result))
	end
	return {}
end
local imageIds = loadImageIds()

export type ColorPair = { Face: Color3, Shadow: Color3 }

local rgb = Color3.fromRGB
local WHITE = Color3.new(1, 1, 1)

-- 버튼/리본 색 (앞면 / 그림자)
local COLORS: { [string]: ColorPair } = {
	Sky = { Face = rgb(57, 160, 255), Shadow = rgb(31, 111, 204) },
	Grass = { Face = rgb(76, 217, 100), Shadow = rgb(46, 158, 69) },
	Sun = { Face = rgb(255, 197, 61), Shadow = rgb(217, 144, 15) },
	Coral = { Face = rgb(255, 94, 91), Shadow = rgb(201, 58, 56) },
	Grape = { Face = rgb(155, 107, 255), Shadow = rgb(106, 69, 201) },
	Gray = { Face = rgb(172, 170, 190), Shadow = rgb(116, 112, 138) },
}

Ui.Theme = {
	Ink = rgb(30, 27, 46), -- 모든 굵은 테두리·글자 테두리
	Cream = rgb(255, 244, 220), -- 창 바탕
	Paper = rgb(255, 230, 176), -- 카드/여권 종이
	PaperDark = rgb(222, 178, 104), -- 창 아래 두께(립), 빈 막대
	White = WHITE,
	Colors = COLORS,
	Font = Enum.Font.FredokaOne,
	FontTitle = Enum.Font.LuckiestGuy, -- 큰 제목(명소 공개, 속보)
	-- 알림 색 (init.client 에서 알림 알약 색으로 넘김)
	Good = COLORS.Grass.Face,
	Bad = COLORS.Coral.Face,
	Gold = COLORS.Sun.Face,
	SubText = COLORS.Gray.Face,
	Text = WHITE,
}

-- 화면 크기 기준 해상도. 이보다 작으면(휴대폰) 줄이고, 크면 조금 키웁니다.
local DESIGN_SIZE = Vector2.new(1280, 720)
local MIN_SCALE, MAX_SCALE = 0.55, 0.9

local SHADOW_DEPTH = 6 -- 통통 버튼: 그림자 판이 앞면보다 아래로 나온 두께
local PRESS_DEPTH = 4 -- 누르면 앞면이 내려가는 거리
local BUTTON_CORNER = 14

local PRESS_TWEEN = TweenInfo.new(0.06, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local RELEASE_TWEEN = TweenInfo.new(0.16, Enum.EasingStyle.Back, Enum.EasingDirection.Out)
local HOVER_TWEEN = TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)

-- 9-slice 스킨 그림(256x256)마다: 그림 속 바깥 모서리 반지름(Radius, px)과 SliceCenter 여백(Margin, px).
-- SliceCenter = Margin..(256 - Margin). 여백은 모서리 곡선(과 광택 줄)이 끝나는 곳 이상이어야 곧은 가장자리만 늘어남.
-- 여백 = 바깥 빈칸 + 반지름이면, 모서리 조각(여백 x SliceScale)을 높이의 절반까지 키웠을 때 끝이 딱 반원(캡슐)이 됨.
--   tag         빈칸 2 + 반지름 44 = 46 -> SliceCenter 46..210 (딱지가 캡슐로 나옴)
--   pill        빈칸 1 + 반지름 63 ≈ 64 (SliceScale = 높이/128 이면 반원)
--   button_*    반지름 50, 위 광택 줄이 y 56 까지라 여백 64
--   panel_paper 반지름 46, 여백 64
--   ribbon      모서리 대신 SliceScale = 그림 높이/256 (Ui.ribbonArt)
local SKIN_SIZE = 256
local SKINS: { [string]: { Radius: number, Margin: number } } = {
	button_face = { Radius = 50, Margin = 64 },
	button_shadow = { Radius = 50, Margin = 64 },
	panel_paper = { Radius = 46, Margin = 64 },
	pill = { Radius = 64, Margin = 64 },
	tag = { Radius = 44, Margin = 46 },
	ribbon = { Radius = 50, Margin = 64 },
}
local DEFAULT_SKIN = { Radius = 50, Margin = 64 }

-- pill.png 는 이미 Ink 색 + 몸통 불투명도 62%(테두리는 불투명)라 물들이지 않음. 더 투명하게 해 달라고 할 때만 그만큼 더 투명하게
local PILL_ART_OPACITY = 0.62

-- ribbon.png 속 띠: Ink 테두리 포함 y 30..170, 안쪽 색 x 52..204 · y 40..160 (256 기준). 꼬리는 좌우 조각에서 아래로 처짐
local RIBBON_FILL = { Side = 52, Top = 40, Bottom = 160 }
local RIBBON_TEXT_PAD = 4 -- 띠 안쪽 좌우에서 글자까지
local RIBBON_TEXT_FILL = 0.85 -- 제목 최대 글자 크기 = 띠 안쪽 높이 x 이 값 (글자 테두리까지 띠 안에 들어가게)

-- close.png: 빨간 동그라미 닫기 버튼 완성 그림(지름 216/256, 아래 두께 포함)
local CLOSE_ART_SIZE = 60

-- Icons 는 Viewport -> Ui 를 require 하므로, 순환을 피하려고 처음 쓸 때 불러옴
local iconsModule: any = nil
local function icons(): any
	if not iconsModule then
		iconsModule = require(script.Parent:WaitForChild("Icons")) :: any
	end
	return iconsModule
end

-- 그림 Id ("rbxassetid://...") 또는 nil(아직 그림 없음). 숫자만 넣어 둬도 받아 줌
function Ui.imageId(name: string?): string?
	if not name then
		return nil
	end
	local value = imageIds[name]
	if type(value) == "number" then
		return "rbxassetid://" .. tostring(value)
	elseif type(value) == "string" and value ~= "" then
		return if value:match("^%d+$") then "rbxassetid://" .. value else value
	end
	return nil
end

-- Ui.new("Frame", { Size = ..., Parent = ... }, { 자식들 })
function Ui.new(className: string, props: { [string]: any }?, children: { Instance }?): any
	local instance = Instance.new(className)
	local parent = nil
	for key, value in props or {} do
		if key == "Parent" then
			parent = value
		else
			(instance :: any)[key] = value
		end
	end
	for _, child in children or {} do
		child.Parent = instance
	end
	if parent then
		instance.Parent = parent
	end
	return instance
end

function Ui.corner(radius: number?): UICorner
	return Ui.new("UICorner", { CornerRadius = UDim.new(0, radius or 12) })
end

-- 완전히 둥근 모서리(알약/동그라미)
function Ui.round(): UICorner
	return Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) })
end

-- 테두리 선 (기본: Ink 3px)
function Ui.stroke(color: Color3?, thickness: number?, transparency: number?): UIStroke
	return Ui.new("UIStroke", {
		Color = color or Ui.Theme.Ink,
		Thickness = thickness or 3,
		Transparency = transparency or 0,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
	})
end

-- 글자 테두리 (Contextual = 글자에 적용)
function Ui.outline(label: GuiObject, thickness: number?, color: Color3?): UIStroke
	return Ui.new("UIStroke", {
		Color = color or Ui.Theme.Ink,
		Thickness = thickness or 2,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual,
		Parent = label,
	})
end

function Ui.padding(px: number): UIPadding
	local u = UDim.new(0, px)
	return Ui.new("UIPadding", { PaddingTop = u, PaddingBottom = u, PaddingLeft = u, PaddingRight = u })
end

function Ui.list(direction: Enum.FillDirection, gap: number, hAlign: Enum.HorizontalAlignment?): UIListLayout
	return Ui.new("UIListLayout", {
		FillDirection = direction,
		Padding = UDim.new(0, gap),
		SortOrder = Enum.SortOrder.LayoutOrder,
		HorizontalAlignment = hAlign or Enum.HorizontalAlignment.Left,
		VerticalAlignment = Enum.VerticalAlignment.Center,
	})
end

-- 이름 -> 색 쌍 (모르는 이름이면 회색)
function Ui.colorPair(name: string?): ColorPair
	return COLORS[name or "Gray"] or COLORS.Gray
end

-- 위쪽이 살짝 밝은 세로 그라데이션. 배경색은 흰색으로 두고 이 그라데이션 색이 곧 면 색이 됨
function Ui.faceGradient(color: Color3): ColorSequence
	return ColorSequence.new({
		ColorSequenceKeypoint.new(0, color:Lerp(WHITE, 0.32)),
		ColorSequenceKeypoint.new(0.5, color),
		ColorSequenceKeypoint.new(1, color),
	})
end

-- 글자 크기 자동(TextScaled) + 최대 크기 제한. 기본 글꼴 FredokaOne, 기본 글자색 Ink(크림 바탕용)
function Ui.label(props: { [string]: any }, maxTextSize: number?): TextLabel
	local label = Ui.new("TextLabel", {
		Text = "",
		BackgroundTransparency = 1,
		Font = Ui.Theme.Font,
		TextColor3 = Ui.Theme.Ink,
		TextScaled = true,
		RichText = true,
	})
	for key, value in props do
		if key ~= "Parent" then
			(label :: any)[key] = value
		end
	end
	Ui.new("UITextSizeConstraint", { MaxTextSize = maxTextSize or 28, Parent = label })
	label.Parent = props.Parent
	return label
end

-- 텍스트에 명소 등급 색을 입힘
function Ui.paintTier(label: TextLabel | TextButton, tier: { Color: Color3 })
	label.TextColor3 = tier.Color
end

-- 별 개수(0~max) -> "★★★☆☆"
function Ui.stars(count: number, max: number?): string
	local total = max or 5
	local filled = math.clamp(math.floor(count), 0, total)
	return string.rep("★", filled) .. string.rep("☆", total - filled)
end

-- RichText 별: 채운 별은 Sun 색, 빈 별은 흐린 색 (글자 테두리와 함께 쓰면 통통한 별이 됨)
function Ui.starsRich(count: number, max: number?, emptyColor: Color3?): string
	local total = max or 5
	local filled = math.clamp(math.floor(count), 0, total)
	return string.format(
		'<font color="%s">%s</font><font color="%s">%s</font>',
		Format.hex(COLORS.Sun.Face),
		string.rep("★", filled),
		Format.hex(emptyColor or rgb(226, 212, 182)),
		string.rep("★", total - filled)
	)
end

-- 1.25 -> "×1.25"
function Ui.times(value: number): string
	return "×" .. Format.multiplier(value):sub(2)
end

-- 그림 --------------------------------------------------------------------------

-- 화면 모서리 반지름(px) -> SliceScale. height 를 주면 모서리 조각이 높이의 절반을 넘지 않게
local function sliceScale(name: string, radius: number, height: number?): number
	local spec = SKINS[name] or DEFAULT_SKIN
	local scale = radius / spec.Radius
	if height then
		scale = math.min(scale, height / 2 / spec.Margin)
	end
	return scale
end

-- 9-slice 설정. options: { Scale?(SliceScale 직접) 또는 Radius + Height?, CenterColor? }
-- CenterColor: 늘어나는 가운데 조각을 그 색 평면으로 덮음(종이 점무늬가 한쪽으로 몇 배씩 늘어나 얼룩지지 않게)
local function applySlice(image: ImageLabel, name: string, options: { [string]: any })
	local margin = (SKINS[name] or DEFAULT_SKIN).Margin
	local scale = options.Scale or sliceScale(name, options.Radius, options.Height)
	image.ScaleType = Enum.ScaleType.Slice
	image.SliceCenter = Rect.new(margin, margin, SKIN_SIZE - margin, SKIN_SIZE - margin)
	image.SliceScale = scale
	if options.CenterColor then
		local inset = margin * scale
		Ui.new("Frame", {
			Name = "Center",
			Position = UDim2.fromOffset(inset, inset),
			Size = UDim2.new(1, -2 * inset, 1, -2 * inset),
			BackgroundColor3 = options.CenterColor,
			BorderSizePixel = 0,
			Parent = image,
		})
	end
end

-- 스킨 그림을 대상 맨 뒤에 깔고 대상의 바탕·테두리(UIStroke)는 끔. 그림 Id 가 없으면 nil(기존 Frame 모양 그대로).
-- 테두리를 붙인 "뒤에" 불러야 함. 크기가 고정이고 UIPadding/UIListLayout 이 없는 상자용
-- (알약·딱지처럼 자동 크기/여백이 있는 상자는 Ui.box). props: { Radius?(화면에서 보일 모서리 반지름 px,
--   없으면 통째로 늘임), Height?(대상 높이 px), Scale?(SliceScale 직접), CenterColor?, Color?(ImageColor3), Transparency? }
function Ui.skin(target: GuiObject, name: string, props: { [string]: any }?): ImageLabel?
	local id = Ui.imageId(name)
	if not id then
		return nil
	end
	local options = props or {}
	target.BackgroundTransparency = 1
	for _, child in target:GetChildren() do
		if child:IsA("UIStroke") and child.ApplyStrokeMode == Enum.ApplyStrokeMode.Border then
			child.Enabled = false
		end
	end
	local image = Ui.new("ImageLabel", {
		Name = "Skin",
		BackgroundTransparency = 1,
		Image = id,
		ImageColor3 = options.Color or WHITE,
		ImageTransparency = options.Transparency or 0,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 0, -- 대상 안의 다른 것들(글자·아이콘)보다 뒤
	})
	if options.Radius or options.Scale then
		applySlice(image, name, options)
	else
		image.ScaleType = Enum.ScaleType.Stretch
	end
	image.Parent = target
	return image
end

-- 스킨 그림 "자체"가 상자인 ImageLabel(그림이 있을 때) 또는 평범한 Frame(없을 때).
-- 자동 크기(AutomaticSize)나 UIPadding/UIListLayout 이 붙는 상자(알약·딱지)용: 그림이 여백·배치에 밀리지 않음.
-- props: { Radius, Height?, Color?(Frame 바탕색 = 그림 색), Transparency?,
--          ImageColor?/ImageTransparency?(그림일 때만 다르게: 이미 색이 칠해진 그림용) }
-- 반환: 상자, 스킨 여부(Frame 이면 UICorner/UIStroke 는 부르는 쪽이 붙임)
function Ui.box(name: string, props: { [string]: any }): (GuiObject, boolean)
	local id = Ui.imageId(name)
	if not id then
		return Ui.new("Frame", {
			BackgroundColor3 = props.Color or WHITE,
			BackgroundTransparency = props.Transparency or 0,
		}),
			false
	end
	local image = Ui.new("ImageLabel", {
		BackgroundTransparency = 1,
		Image = id,
		ImageColor3 = props.ImageColor or props.Color or WHITE,
		ImageTransparency = props.ImageTransparency or props.Transparency or 0,
	})
	applySlice(image, name, props)
	image:SetAttribute("Skin", name)
	return image, true
end

-- 리본 그림(ribbon.png)을 입힘. 그림이 없으면 nil (Frame 으로 그린 리본 그대로).
-- root: 리본 전체 Frame (Position 이 띠 가운데 자리), main: root 를 꽉 채우는 띠 Frame(여기에 그림이 깔림),
-- label: main 안의 제목 글자(Ui.label), artHeight: 꼬리까지 포함한 그림 높이.
-- SliceScale = artHeight/256 이라 세로 비율은 그림 그대로(가로로만 늘어남). 띠는 그림 위쪽(y 40..160)에 있어서
-- 띠 가운데가 원래 자리에 오도록 root 를 내리고, 글자 상자·최대 크기를 띠 안쪽에 맞춤
function Ui.ribbonArt(root: GuiObject, main: GuiObject, label: TextLabel, artHeight: number): ImageLabel?
	local scale = artHeight / SKIN_SIZE
	local skin = Ui.skin(main, "ribbon", { Scale = scale })
	if not skin then
		return nil
	end
	local anchorY = root.AnchorPoint.Y
	local oldCenter = root.Size.Y.Offset * (0.5 - anchorY) -- 기준점에서 원래 띠 가운데까지
	local newCenter = (RIBBON_FILL.Top + RIBBON_FILL.Bottom) / 2 * scale - artHeight * anchorY
	root.Position += UDim2.fromOffset(0, oldCenter - newCenter)
	root.Size = UDim2.new(root.Size.X.Scale, root.Size.X.Offset, 0, artHeight)

	local side = RIBBON_FILL.Side * scale + RIBBON_TEXT_PAD
	local bandHeight = (RIBBON_FILL.Bottom - RIBBON_FILL.Top) * scale
	label.Position = UDim2.fromOffset(side, RIBBON_FILL.Top * scale)
	label.Size = UDim2.new(1, -2 * side, 0, bandHeight)
	local limit = label:FindFirstChildOfClass("UITextSizeConstraint")
	if limit then
		limit.MaxTextSize = math.floor(bandHeight * RIBBON_TEXT_FILL)
	end
	return skin
end

-- 바탕색 바꾸기 (스킨 그림이면 그림 색을)
function Ui.tint(target: GuiObject, color: Color3)
	if target:IsA("ImageLabel") and target:GetAttribute("Skin") ~= nil then
		target.ImageColor3 = color
		return
	end
	target.BackgroundColor3 = color
	local skin = target:FindFirstChild("Skin")
	if skin and skin:IsA("ImageLabel") then
		skin.ImageColor3 = color
	end
end

-- 아이콘 하나: 그림이 있으면 ImageLabel, 없으면 3D 미니 모형. 자세한 건 Icons.view
-- props: { Size, Position, AnchorPoint, ZIndex, LayoutOrder, Spin?, Color?(그림 ImageColor3), Transparency? }
function Ui.icon(parent: Instance?, name: string, props: { [string]: any }?): Frame
	return icons().view(parent, name, props)
end

-- 키보드 단축키 키캡 (작은 크림색 네모 + Ink 글자). 키보드가 없는 기기에서는 숨김
-- props: { Size?(한 변 px), Position, AnchorPoint, Rotation?, ZIndex? }
function Ui.keyCap(parent: Instance, key: string, props: { [string]: any }?): Frame
	local options = props or {}
	local size = options.Size or 26
	local cap = Ui.new("Frame", {
		Name = "Key" .. key,
		AnchorPoint = options.AnchorPoint or Vector2.new(0.5, 0.5),
		Position = options.Position or UDim2.new(),
		Size = UDim2.fromOffset(size, size),
		BackgroundColor3 = Ui.Theme.Cream,
		Rotation = options.Rotation or -8,
		ZIndex = options.ZIndex or 7,
		Visible = UserInputService.KeyboardEnabled,
	})
	Ui.corner(7).Parent = cap
	Ui.stroke(Ui.Theme.Ink, 2.5).Parent = cap
	Ui.label({
		Name = "Key",
		Text = key,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 2,
		Parent = cap,
	}, math.floor(size * 0.72))
	cap.Parent = parent
	return cap
end

-- 통통 버튼 ------------------------------------------------------------------

export type ChunkyButton = {
	Root: Frame,
	Face: TextButton,
	Shadow: Frame,
	Label: TextLabel,
	Icon: Frame?,
	Activated: RBXScriptSignal,
	SetColor: (name: string) -> (),
	SetText: (text: string) -> (),
	SetIcon: (name: string?) -> (),
}

-- 누른 채로 버튼 밖에서 손을 떼도 앞면이 다시 올라오도록, 눌린 버튼을 모아 두었다가 입력이 끝나면 모두 올림
local held: { [() -> ()]: boolean } = {}
UserInputService.InputEnded:Connect(function(input)
	local kind = input.UserInputType
	if kind ~= Enum.UserInputType.MouseButton1 and kind ~= Enum.UserInputType.Touch then
		return
	end
	local list = {}
	for release in held do
		table.insert(list, release)
	end
	table.clear(held)
	for _, release in list do
		release()
	end
end)

-- props: { Color = "Grass"|"Sky"|"Sun"|"Coral"|"Grape"|"Gray", Size, Position, AnchorPoint, LayoutOrder, Text,
--          TextSize?(최대 글자 크기), Parent, Icon?(Icons 이름), IconSize?, IconSpin?, Vertical?(아이콘 위·글자 아래),
--          Round?(동그라미), Name?, ZIndex?, Visible? }
-- Size 는 그림자까지 포함한 전체 크기(오프셋). 앞면 높이 = Size.Y - 6. 글자가 비어 있으면 아이콘을 가운데에.
-- 스킨: ImageIds.button_face / button_shadow 가 있으면 그 그림을 색으로 물들여 씀
function Ui.chunkyButton(props: { [string]: any }): ChunkyButton
	local size: UDim2 = props.Size or UDim2.fromOffset(160, 64)
	local faceHeight = math.max(12, size.Y.Offset - SHADOW_DEPTH)
	local radius = if props.Round then UDim.new(0.5, 0) else UDim.new(0, props.CornerRadius or BUTTON_CORNER)
	local vertical = props.Vertical == true
	local iconSize = props.IconSize or math.floor(faceHeight * (if vertical then 0.58 else 0.8))
	local skinRadius = if props.Round then faceHeight / 2 else (props.CornerRadius or BUTTON_CORNER)

	local root = Ui.new("Frame", {
		Name = props.Name or "Button",
		Size = size,
		Position = props.Position or UDim2.new(),
		AnchorPoint = props.AnchorPoint or Vector2.new(0, 0),
		LayoutOrder = props.LayoutOrder or 0,
		ZIndex = props.ZIndex or 1,
		Visible = props.Visible ~= false,
		BackgroundTransparency = 1,
	})
	local hover = Ui.new("UIScale", { Parent = root })

	local shadow = Ui.new("Frame", {
		Name = "Shadow",
		Position = UDim2.fromOffset(0, SHADOW_DEPTH),
		Size = UDim2.new(1, 0, 1, -SHADOW_DEPTH),
		BorderSizePixel = 0,
		ZIndex = 1,
		Parent = root,
	})
	Ui.new("UICorner", { CornerRadius = radius, Parent = shadow })
	Ui.stroke().Parent = shadow
	local shadowSkin = Ui.skin(shadow, "button_shadow", { Radius = skinRadius, Height = faceHeight })

	local face = Ui.new("TextButton", {
		Name = "Face",
		Text = "",
		AutoButtonColor = false,
		Size = UDim2.new(1, 0, 1, -SHADOW_DEPTH),
		BackgroundColor3 = WHITE,
		BorderSizePixel = 0,
		ZIndex = 2,
		Parent = root,
	})
	Ui.new("UICorner", { CornerRadius = radius, Parent = face })
	Ui.stroke().Parent = face
	local gradient = Ui.new("UIGradient", { Rotation = 90, Parent = face })
	local faceSkin = Ui.skin(face, "button_face", { Radius = skinRadius, Height = faceHeight })

	-- 왼쪽 위 반짝이(만화풍 광택). 스킨 그림에는 광택이 그려져 있음
	if not props.Round and not faceSkin then
		local shine = Ui.new("Frame", {
			Name = "Shine",
			Position = UDim2.fromOffset(9, 5),
			Size = UDim2.new(0.32, 0, 0, 6),
			BackgroundColor3 = WHITE,
			BackgroundTransparency = 0.55,
			BorderSizePixel = 0,
			ZIndex = 1,
			Parent = face,
		})
		Ui.round().Parent = shine
	end

	local label = Ui.label({
		Name = "Label",
		Text = props.Text or "",
		TextColor3 = WHITE,
		ZIndex = 4,
		Parent = face,
	}, props.TextSize or 26)
	Ui.outline(label, props.OutlineThickness or 2.5)

	local button = {
		Root = root,
		Face = face,
		Shadow = shadow,
		Label = label,
		Icon = nil,
		Activated = face.Activated,
	} :: any

	local iconName: string? = nil
	local function layout()
		local icon = button.Icon
		if icon and label.Text == "" then
			icon.AnchorPoint = Vector2.new(0.5, 0.5)
			icon.Position = UDim2.fromScale(0.5, 0.5)
			icon.Size = UDim2.fromOffset(iconSize, iconSize)
		elseif icon and vertical then
			icon.AnchorPoint = Vector2.new(0.5, 0)
			icon.Position = UDim2.new(0.5, 0, 0, 3)
			icon.Size = UDim2.fromOffset(iconSize, iconSize)
			label.Position = UDim2.fromOffset(4, iconSize + 2)
			label.Size = UDim2.new(1, -8, 1, -(iconSize + 6))
		elseif icon then
			icon.AnchorPoint = Vector2.new(0, 0.5)
			icon.Position = UDim2.new(0, 6, 0.5, 0)
			icon.Size = UDim2.fromOffset(iconSize, iconSize)
			label.Position = UDim2.fromOffset(iconSize + 8, 4)
			label.Size = UDim2.new(1, -(iconSize + 16), 1, -8)
		else
			label.Position = UDim2.fromOffset(8, 4)
			label.Size = UDim2.new(1, -16, 1, -8)
		end
	end

	-- 아이콘 바꾸기 (nil 이면 아이콘 없이 글자만)
	local function setIcon(name: string?)
		if name == iconName then
			return
		end
		iconName = name
		local icon = button.Icon
		if name and icon then
			icons().set(icon, name)
		elseif name then
			button.Icon = icons().view(face, name, { ZIndex = 3, Spin = props.IconSpin })
		elseif icon then
			icon:Destroy()
			button.Icon = nil
		end
		layout()
	end

	local colorName: string? = nil
	local function setColor(name: string)
		if name == colorName then
			return
		end
		colorName = name
		local pair = Ui.colorPair(name)
		gradient.Color = Ui.faceGradient(pair.Face)
		shadow.BackgroundColor3 = pair.Shadow
		if faceSkin then
			faceSkin.ImageColor3 = pair.Face
		end
		if shadowSkin then
			shadowSkin.ImageColor3 = pair.Shadow
		end
	end

	-- 누름: 앞면이 4px 내려갔다가 올라옴 / 마우스를 올리면 1.05배
	local pressed = false
	local lastPress = 0
	local function release()
		held[release] = nil
		if not pressed then
			return
		end
		pressed = false
		TweenService:Create(face, RELEASE_TWEEN, { Position = UDim2.fromOffset(0, 0) }):Play()
	end
	local function press()
		lastPress = os.clock()
		if pressed then
			return
		end
		pressed = true
		held[release] = true
		TweenService:Create(face, PRESS_TWEEN, { Position = UDim2.fromOffset(0, PRESS_DEPTH) }):Play()
	end
	face.MouseButton1Down:Connect(press)
	face.MouseButton1Up:Connect(release)
	face.MouseEnter:Connect(function()
		if UserInputService.MouseEnabled then
			TweenService:Create(hover, HOVER_TWEEN, { Scale = 1.05 }):Play()
		end
	end)
	face.MouseLeave:Connect(function()
		release()
		TweenService:Create(hover, HOVER_TWEEN, { Scale = 1 }):Play()
	end)
	face.Activated:Connect(function()
		if pressed then
			release()
		elseif os.clock() - lastPress > 0.4 then
			-- 키보드/게임패드로 누른 경우: 짧게 눌렸다 올라옴
			press()
			task.delay(0.07, release)
		end
	end)

	button.SetColor = setColor
	button.SetText = function(text: string)
		if label.Text ~= text then
			local relayout = label.Text == "" or text == ""
			label.Text = text
			if relayout then
				layout()
			end
		end
	end
	button.SetIcon = setIcon

	setColor(props.Color or "Sky")
	setIcon(props.Icon)
	layout()

	root.Parent = props.Parent
	return button :: ChunkyButton
end

-- 창 -------------------------------------------------------------------------

-- 닫기 버튼: close 그림이 있으면 그림 한 장(ImageButton), 없으면 빨간 동그라미 통통 버튼
export type CloseButton = { Root: GuiObject, Activated: RBXScriptSignal }

export type Window = {
	Root: Frame,
	Panel: Frame,
	Body: Frame,
	Ribbon: Frame,
	Title: TextLabel,
	Close: CloseButton,
	SetColor: (name: string) -> (),
}

local RIBBON_HEIGHT = 54 -- Frame 리본 높이 (창 몸통 위치의 기준)
local RIBBON_ART_HEIGHT = 72 -- 리본 그림 높이(꼬리 포함). 띠 안쪽 높이 = 72 x 120/256 ≈ 34

-- 그림 한 장이 곧 버튼(close.png 처럼 완성된 버튼 그림). 마우스를 올리면 1.08배, 누르면 0.9배
local function imageButton(props: { [string]: any }): ImageButton
	local button = Ui.new("ImageButton", {
		Name = props.Name or "ImageButton",
		AnchorPoint = props.AnchorPoint or Vector2.new(0.5, 0.5),
		Position = props.Position or UDim2.new(),
		Size = props.Size,
		BackgroundTransparency = 1,
		Image = props.Image,
		ScaleType = Enum.ScaleType.Fit,
		AutoButtonColor = false,
		ZIndex = props.ZIndex or 1,
	})
	local scale = Ui.new("UIScale", { Parent = button })
	local hovered = false
	local function scaleTo(value: number)
		TweenService:Create(scale, HOVER_TWEEN, { Scale = value }):Play()
	end
	local function release()
		held[release] = nil
		scaleTo(if hovered then 1.08 else 1)
	end
	button.MouseEnter:Connect(function()
		hovered = UserInputService.MouseEnabled
		scaleTo(if hovered then 1.08 else 1)
	end)
	button.MouseLeave:Connect(function()
		hovered = false
		release()
	end)
	button.MouseButton1Down:Connect(function()
		held[release] = true
		scaleTo(0.9)
	end)
	button.MouseButton1Up:Connect(release)
	button.Parent = props.Parent
	return button
end

-- props: { Size, Position, AnchorPoint, Title, Color(리본 색 이름), RibbonWidth?, Name?, ZIndex?, Visible?, Parent }
-- Cream 바탕 + Ink 테두리 4 + 모서리 18, 위 가운데에 색 리본 제목, 오른쪽 위에 빨간 동그라미 닫기 버튼
-- 스킨: ImageIds.panel_paper(창 바탕, 물들이지 않음) / ribbon(리본, 색으로 물들임) / close(닫기 버튼 그림 그대로)
function Ui.window(props: { [string]: any }): Window
	local theme = Ui.Theme
	local root = Ui.new("Frame", {
		Name = props.Name or "Window",
		Size = props.Size or UDim2.fromOffset(720, 480),
		Position = props.Position or UDim2.fromScale(0.5, 0.5),
		AnchorPoint = props.AnchorPoint or Vector2.new(0.5, 0.5),
		ZIndex = props.ZIndex or 1,
		Visible = props.Visible ~= false,
		BackgroundTransparency = 1,
	})

	-- 아래 두께(립): 종이 책처럼 두툼하게
	local lip = Ui.new("Frame", {
		Name = "Lip",
		Position = UDim2.fromOffset(0, 8),
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = theme.PaperDark,
		ZIndex = 1,
		Parent = root,
	})
	Ui.corner(18).Parent = lip
	Ui.stroke(theme.Ink, 4).Parent = lip
	Ui.skin(lip, "panel_paper", { Radius = 18, Color = theme.PaperDark })

	local panel = Ui.new("Frame", {
		Name = "Panel",
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = theme.Cream,
		ZIndex = 2,
		Parent = root,
	})
	Ui.corner(18).Parent = panel
	Ui.stroke(theme.Ink, 4).Parent = panel
	-- 안쪽 종이 테두리
	local inner = Ui.new("Frame", {
		Name = "Inner",
		Position = UDim2.fromOffset(8, 8),
		Size = UDim2.new(1, -16, 1, -16),
		BackgroundTransparency = 1,
		Parent = panel,
	})
	Ui.corner(12).Parent = inner
	Ui.stroke(theme.Paper, 3).Parent = inner
	-- 종이 가운데 조각은 창 크기만큼(가로 약 5배) 늘어나 점무늬가 얼룩지므로 같은 크림색 평면으로 덮음
	if Ui.skin(panel, "panel_paper", { Radius = 18, CenterColor = theme.Cream }) then
		inner.Visible = false -- 종이 그림에 안쪽 테두리가 들어 있음
	end

	-- 리본 제목
	local ribbon = Ui.new("Frame", {
		Name = "Ribbon",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, 0, 0, 4),
		Size = UDim2.fromOffset(props.RibbonWidth or 340, RIBBON_HEIGHT),
		BackgroundTransparency = 1,
		ZIndex = 3,
		Parent = root,
	})
	local tails = {}
	for _, side in { 0, 1 } do
		local tail = Ui.new("Frame", {
			Name = "Tail",
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(side, if side == 0 then -16 else 16, 0.5, 10),
			Size = UDim2.fromOffset(48, 40),
			BorderSizePixel = 0,
			ZIndex = 1,
			Parent = ribbon,
		})
		Ui.corner(8).Parent = tail
		Ui.stroke(theme.Ink, 3).Parent = tail
		table.insert(tails, tail)
	end
	local main = Ui.new("Frame", {
		Name = "Main",
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = WHITE,
		BorderSizePixel = 0,
		ZIndex = 2,
		Parent = ribbon,
	})
	Ui.corner(12).Parent = main
	Ui.stroke(theme.Ink, 3).Parent = main
	local gradient = Ui.new("UIGradient", { Rotation = 90, Parent = main })
	local title = Ui.label({
		Name = "Title",
		Position = UDim2.fromOffset(14, 5),
		Size = UDim2.new(1, -28, 1, -10),
		Text = props.Title or "",
		TextColor3 = WHITE,
		ZIndex = 3,
		Parent = main,
	}, 32)
	Ui.outline(title, 3)
	-- 리본 그림: 띠 가운데는 그대로(창 위 4px), 글자는 띠 안쪽에 맞춤
	local ribbonSkin = Ui.ribbonArt(ribbon, main, title, RIBBON_ART_HEIGHT)
	if ribbonSkin then
		for _, tail in tails do
			tail.Visible = false -- 리본 그림에 꼬리가 들어 있음
		end
	end

	-- 닫기: close.png 는 빨간 동그라미 + X 가 다 그려진 버튼 그림이라 그대로 버튼으로 씀
	local closeImage = Ui.imageId("close")
	local close: CloseButton
	if closeImage then
		local button = imageButton({
			Name = "Close",
			Image = closeImage,
			Position = UDim2.new(1, -8, 0, 8),
			Size = UDim2.fromOffset(CLOSE_ART_SIZE, CLOSE_ART_SIZE),
			ZIndex = 4,
			Parent = root,
		})
		close = { Root = button, Activated = button.Activated }
	else
		close = Ui.chunkyButton({
			Name = "Close",
			Color = "Coral",
			Round = true,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(1, -8, 0, 8),
			Size = UDim2.fromOffset(52, 58),
			Text = "X",
			TextSize = 30,
			OutlineThickness = 3,
			ZIndex = 4,
			Parent = root,
		})
	end

	local top = RIBBON_HEIGHT / 2 + 4 + 14
	local body = Ui.new("Frame", {
		Name = "Body",
		Position = UDim2.fromOffset(18, top),
		Size = UDim2.new(1, -36, 1, -(top + 16)),
		BackgroundTransparency = 1,
		Parent = panel,
	})

	local colorName: string? = nil
	local function setColor(name: string)
		if name == colorName then
			return
		end
		colorName = name
		local pair = Ui.colorPair(name)
		gradient.Color = Ui.faceGradient(pair.Face)
		if ribbonSkin then
			ribbonSkin.ImageColor3 = pair.Face
		end
		for _, tail in tails do
			tail.BackgroundColor3 = pair.Shadow
		end
	end
	setColor(props.Color or "Sky")

	root.Parent = props.Parent
	return {
		Root = root,
		Panel = panel,
		Body = body,
		Ribbon = ribbon,
		Title = title,
		Close = close,
		SetColor = setColor,
	}
end

-- 알약 / 칩 --------------------------------------------------------------------

export type Pill = { Root: GuiObject, Label: TextLabel, Icon: Frame? }

-- 캡슐 모양 반투명 Ink 바탕 + 흰 글자(테두리). 왼쪽에 테두리를 살짝 넘는 동그란 아이콘(선택).
-- 스킨: ImageIds.pill 이 있으면 그 그림을 씀. 그림이 이미 반투명 Ink(+ 불투명 테두리·광택)라 물들이지 않음
-- props: { Size(높이는 오프셋), Position, AnchorPoint, LayoutOrder, Parent, Text, TextColor3?, MaxTextSize?,
--          AutoWidth?(글자 길이에 맞춰 가로 자동, TextSize 사용), TextSize?, TextXAlignment?,
--          Icon?(Icons 이름), IconSize?, IconSpin?, IconBack?(아이콘 뒤 동그라미 색), BackgroundTransparency?, Name?, ZIndex?, Visible? }
function Ui.pill(props: { [string]: any }): Pill
	local theme = Ui.Theme
	local size: UDim2 = props.Size or UDim2.fromOffset(200, 40)
	local height = size.Y.Offset
	local autoWidth = props.AutoWidth == true
	local iconSize = props.IconSize or math.floor(height * 1.3)
	-- 아이콘 중심은 알약 왼쪽 끝에서 조금 안쪽 → 아이콘이 왼쪽 테두리를 살짝 넘어감
	local iconCenter = math.floor(iconSize * 0.28)
	local leftPad = if props.Icon then iconCenter + math.ceil(iconSize / 2) + 6 else 16

	local transparency = props.BackgroundTransparency or 0.3
	local root, skinned = Ui.box("pill", {
		Radius = height / 2,
		Height = height,
		Color = theme.Ink,
		Transparency = transparency,
		-- 그림은 물들이지 않고, 그림 몸통(불투명도 62%)보다 더 투명하게 해 달라고 할 때만 그만큼 더 투명하게
		ImageColor = WHITE,
		ImageTransparency = math.max(0, 1 - (1 - transparency) / PILL_ART_OPACITY),
	})
	root.Name = props.Name or "Pill"
	root.Size = if autoWidth then UDim2.fromOffset(0, height) else size
	root.AutomaticSize = if autoWidth then Enum.AutomaticSize.X else Enum.AutomaticSize.None
	root.Position = props.Position or UDim2.new()
	root.AnchorPoint = props.AnchorPoint or Vector2.new(0, 0)
	root.LayoutOrder = props.LayoutOrder or 0
	root.ZIndex = props.ZIndex or 1
	root.Visible = props.Visible ~= false
	if not skinned then
		Ui.round().Parent = root
		Ui.stroke(theme.Ink, 3).Parent = root
	end
	Ui.new("UIPadding", {
		PaddingLeft = UDim.new(0, leftPad),
		PaddingRight = UDim.new(0, props.PadRight or 16),
		Parent = root,
	})

	local label = Ui.label({
		Name = "Label",
		Text = props.Text or "",
		TextColor3 = props.TextColor3 or WHITE,
		TextXAlignment = props.TextXAlignment or Enum.TextXAlignment.Left,
		TextScaled = not autoWidth,
		TextSize = props.TextSize or 20,
		AutomaticSize = if autoWidth then Enum.AutomaticSize.X else Enum.AutomaticSize.None,
		Size = if autoWidth then UDim2.fromScale(0, 1) else UDim2.fromScale(1, 1),
		ZIndex = 2,
		Parent = root,
	}, props.MaxTextSize or 30)
	Ui.outline(label, 2.5)

	local icon: Frame? = nil
	if props.Icon then
		-- UIPadding 만큼 안쪽에서 시작하므로 왼쪽 여백을 빼서 위치를 맞춤
		local position = UDim2.new(0, iconCenter - leftPad, 0.5, 0)
		if props.IconBack then
			local disc = Ui.new("Frame", {
				Name = "IconBack",
				AnchorPoint = Vector2.new(0.5, 0.5),
				Position = position,
				Size = UDim2.fromOffset(iconSize, iconSize),
				BackgroundColor3 = props.IconBack,
				ZIndex = 3,
				Parent = root,
			})
			Ui.round().Parent = disc
			Ui.stroke(theme.Ink, 3).Parent = disc
			icon = icons().view(disc, props.Icon, {
				AnchorPoint = Vector2.new(0.5, 0.5),
				Position = UDim2.fromScale(0.5, 0.5),
				Size = UDim2.fromScale(0.84, 0.84),
				ZIndex = 4,
				Spin = props.IconSpin,
			})
		else
			icon = icons().view(root, props.Icon, {
				AnchorPoint = Vector2.new(0.5, 0.5),
				Position = position,
				Size = UDim2.fromOffset(iconSize, iconSize),
				ZIndex = 3,
				Spin = props.IconSpin,
			})
		end
	end

	root.Parent = props.Parent
	return { Root = root, Label = label, Icon = icon }
end

export type Chip = { Root: GuiObject, Label: TextLabel, Icon: Frame? }

local CHIP_PAD = 0.42 -- 딱지 좌우 여백 (높이 대비)
local CHIP_ICON_PAD = 0.12 -- 아이콘 쪽 여백 (아이콘이 딱지 끝에 붙어 살짝 삐져나옴)

-- 작은 색 캡슐 딱지 (글자 길이에 맞춰 가로 자동). 흰 글자 + Ink 테두리. 아이콘을 주면 [아이콘][글자].
-- props: { Color = 색 이름 또는 Color3, Text, Height?, TextSize?, TextColor3?, Font?, Outline?(false 면 글자 테두리 없음),
--          StrokeThickness?, CornerRadius?, MinWidth?, Rotation?, Icon?(Icons 이름), IconSize?, IconOnly?(글자 없이 아이콘만),
--          Position, AnchorPoint, LayoutOrder, ZIndex, Visible, Parent }
-- 스킨: ImageIds.tag 가 있으면 그 그림을 바탕색으로 물들여 씀 (색을 바꿀 땐 Ui.tint(chip.Root, 색))
function Ui.chip(props: { [string]: any }): Chip
	local height = props.Height or 28
	local color = props.Color
	local background = if typeof(color) == "Color3" then color else Ui.colorPair(color or "Sky").Face
	local iconName = props.Icon
	local iconOnly = iconName ~= nil and props.IconOnly == true

	local root, skinned =
		Ui.box("tag", { Radius = props.CornerRadius or height / 2, Height = height, Color = background })
	root.Name = props.Name or "Chip"
	root.Size = UDim2.fromOffset(props.MinWidth or 0, height)
	root.AutomaticSize = Enum.AutomaticSize.X
	root.Position = props.Position or UDim2.new()
	root.AnchorPoint = props.AnchorPoint or Vector2.new(0, 0)
	root.LayoutOrder = props.LayoutOrder or 0
	root.Rotation = props.Rotation or 0
	root.ZIndex = props.ZIndex or 1
	root.Visible = props.Visible ~= false
	if not skinned then
		if props.CornerRadius then
			Ui.corner(props.CornerRadius).Parent = root
		else
			Ui.round().Parent = root
		end
		Ui.stroke(Ui.Theme.Ink, props.StrokeThickness or 2.5).Parent = root
	end
	local pad = math.floor(height * CHIP_PAD)
	local iconPad = math.floor(height * CHIP_ICON_PAD)
	Ui.new("UIPadding", {
		PaddingLeft = UDim.new(0, if iconName then iconPad else pad),
		PaddingRight = UDim.new(0, if iconOnly then iconPad else pad),
		Parent = root,
	})

	local label = Ui.label({
		Name = "Label",
		LayoutOrder = 2,
		Text = props.Text or "",
		Font = props.Font or Ui.Theme.Font,
		TextColor3 = props.TextColor3 or WHITE,
		TextScaled = false,
		TextSize = props.TextSize or math.floor(height * 0.62),
		AutomaticSize = Enum.AutomaticSize.X,
		Size = UDim2.fromScale(0, 1),
		ZIndex = 2,
		Parent = root,
	}, 100)
	if props.Outline ~= false then
		Ui.outline(label, props.OutlineThickness or 2)
	end
	label.Visible = not iconOnly -- 안 보이는 글자는 UIListLayout 이 건너뜀

	local icon: Frame? = nil
	if iconName then
		-- 아이콘은 딱지보다 살짝 커서 위아래로 조금 삐져나옴
		Ui.new("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			Padding = UDim.new(0, math.floor(height * 0.14)),
			SortOrder = Enum.SortOrder.LayoutOrder,
			VerticalAlignment = Enum.VerticalAlignment.Center,
			Parent = root,
		})
		local iconSize = props.IconSize or math.floor(height * 1.2)
		icon = icons().view(root, iconName, {
			Size = UDim2.fromOffset(iconSize, iconSize),
			LayoutOrder = 1,
			ZIndex = 3,
			Spin = props.IconSpin,
		})
	end

	root.Parent = props.Parent
	return { Root = root, Label = label, Icon = icon }
end

-- 딱지 아이콘 보이기/숨기기 (숨기면 왼쪽 여백도 글자만 있는 딱지와 같게)
function Ui.showChipIcon(chip: Chip, visible: boolean)
	local icon = chip.Icon
	local padding = chip.Root:FindFirstChildOfClass("UIPadding")
	if not icon or not padding or icon.Visible == visible then
		return
	end
	icon.Visible = visible
	local height = chip.Root.Size.Y.Offset
	padding.PaddingLeft = UDim.new(0, math.floor(height * (if visible then CHIP_ICON_PAD else CHIP_PAD)))
end

-- 화면 크기 자동 스케일 -------------------------------------------------------

-- 화면 크기에 맞춰 크기를 조절하는 UIScale 을 붙임 (AnchorPoint 기준으로 커지고 작아짐)
local scalers: { UIScale } = {}

-- 화면(카메라 ViewportSize) 전체 크기 = 로블록스 상단바까지 포함. 카메라가 없으면 기준 해상도
function Ui.viewport(): Vector2
	local camera = workspace.CurrentCamera
	return if camera then camera.ViewportSize else DESIGN_SIZE
end

-- 터치 전용 기기(휴대폰·태블릿)인지. 이런 기기에서는 로블록스가 조이스틱(왼쪽 아래)·점프 버튼(오른쪽 아래)을 띄움.
-- 키보드가 붙어 있으면(터치 노트북 등) PC 로 봄 — 키캡(Ui.keyCap)을 보이는 기준과 같음
function Ui.touchOnly(): boolean
	return UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
end

local function currentScale(): number
	local viewport = Ui.viewport()
	return math.clamp(math.min(viewport.X / DESIGN_SIZE.X, viewport.Y / DESIGN_SIZE.Y), MIN_SCALE, MAX_SCALE)
end

function Ui.autoScale(object: GuiObject)
	local scale = Ui.new("UIScale", { Scale = currentScale(), Parent = object })
	table.insert(scalers, scale)
end

-- 지금 자동 스케일 배율 (0.55~0.9)
function Ui.scale(): number
	return currentScale()
end

-- 화면 크기가 바뀌어 배율을 다시 잰 뒤 부를 함수 (배율에 따라 자리를 다시 잡는 HUD 용)
local rescaleCallbacks: { (number) -> () } = {}
function Ui.onRescale(callback: (number) -> ())
	table.insert(rescaleCallbacks, callback)
end

local function refreshScales()
	local value = currentScale()
	for _, scale in scalers do
		scale.Scale = value
	end
	for _, callback in rescaleCallbacks do
		task.spawn(callback, value)
	end
end

local cameraConnection: RBXScriptConnection? = nil
local function watchCamera()
	if cameraConnection then
		cameraConnection:Disconnect()
	end
	local camera = workspace.CurrentCamera
	if camera then
		cameraConnection = camera:GetPropertyChangedSignal("ViewportSize"):Connect(refreshScales)
	end
	refreshScales()
end
workspace:GetPropertyChangedSignal("CurrentCamera"):Connect(watchCamera)
watchCamera()

return Ui
