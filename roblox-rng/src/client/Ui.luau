-- UI 생성 헬퍼와 테마. 모든 화면은 코드로 만들어서 .rbxm 없이도 동작합니다.

local CollectionService = game:GetService("CollectionService")

local Ui = {}

Ui.Theme = {
	Panel = Color3.fromRGB(24, 26, 38),
	PanelLight = Color3.fromRGB(40, 44, 64),
	Stroke = Color3.fromRGB(90, 96, 140),
	Text = Color3.fromRGB(240, 240, 250),
	SubText = Color3.fromRGB(165, 170, 200),
	Accent = Color3.fromRGB(125, 95, 255),
	Good = Color3.fromRGB(90, 220, 120),
	Bad = Color3.fromRGB(255, 95, 95),
	Gold = Color3.fromRGB(255, 205, 70),
	Font = Enum.Font.GothamBold,
	FontHeavy = Enum.Font.GothamBlack,
}

-- 화면 크기 기준 해상도. 이보다 작으면(휴대폰) 줄이고, 크면 조금 키웁니다.
local DESIGN_SIZE = Vector2.new(1280, 720)

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

function Ui.stroke(color: Color3?, thickness: number?, transparency: number?): UIStroke
	return Ui.new("UIStroke", {
		Color = color or Ui.Theme.Stroke,
		Thickness = thickness or 2,
		Transparency = transparency or 0.3,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
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

-- 글자 크기 자동(TextScaled) + 최대 크기 제한
function Ui.label(props: { [string]: any }, maxTextSize: number?): TextLabel
	local label = Ui.new("TextLabel", {
		Text = "",
		BackgroundTransparency = 1,
		Font = Ui.Theme.Font,
		TextColor3 = Ui.Theme.Text,
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

function Ui.button(props: { [string]: any }, maxTextSize: number?): TextButton
	local button = Ui.new("TextButton", {
		Text = "",
		AutoButtonColor = true,
		BackgroundColor3 = Ui.Theme.PanelLight,
		Font = Ui.Theme.FontHeavy,
		TextColor3 = Ui.Theme.Text,
		TextScaled = true,
		RichText = true,
	})
	for key, value in props do
		if key ~= "Parent" then
			(button :: any)[key] = value
		end
	end
	Ui.corner(12).Parent = button
	Ui.stroke().Parent = button
	Ui.new("UITextSizeConstraint", { MaxTextSize = maxTextSize or 26, Parent = button })
	Ui.padding(6).Parent = button
	button.Parent = props.Parent
	return button
end

function Ui.colorSequence(colors: { Color3 }): ColorSequence
	if #colors == 1 then
		return ColorSequence.new(colors[1])
	end
	local keypoints = {}
	for i, color in colors do
		table.insert(keypoints, ColorSequenceKeypoint.new((i - 1) / (#colors - 1), color))
	end
	return ColorSequence.new(keypoints)
end

-- 텍스트에 오라 색(단색 또는 회전하는 그라데이션)을 입힘
function Ui.paintAura(label: TextLabel | TextButton, aura: any)
	local old = label:FindFirstChild("AuraGradient")
	if old then
		old:Destroy()
	end
	if aura.Gradient then
		label.TextColor3 = Color3.new(1, 1, 1)
		local gradient = Ui.new("UIGradient", {
			Name = "AuraGradient",
			Color = Ui.colorSequence(aura.Gradient),
			Parent = label,
		})
		CollectionService:AddTag(gradient, "AuraGradient")
	else
		label.TextColor3 = aura.Color
	end
end

-- 화면 크기에 맞춰 크기를 조절하는 UIScale 을 붙임 (AnchorPoint 기준으로 커지고 작아짐)
local scalers: { UIScale } = {}

local function currentScale(): number
	local camera = workspace.CurrentCamera
	local viewport = if camera then camera.ViewportSize else DESIGN_SIZE
	return math.clamp(math.min(viewport.X / DESIGN_SIZE.X, viewport.Y / DESIGN_SIZE.Y), 0.6, 1.3)
end

function Ui.autoScale(object: GuiObject)
	local scale = Ui.new("UIScale", { Scale = currentScale(), Parent = object })
	table.insert(scalers, scale)
end

local function refreshScales()
	local value = currentScale()
	for _, scale in scalers do
		scale.Scale = value
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
