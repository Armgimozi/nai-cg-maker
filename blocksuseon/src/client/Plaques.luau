-- 맵의 현판과 비석에 글자를 새긴다.
--
-- 서버 맵(World.luau)은 판자에 Plaque 태그와 Text 속성만 달아 둔다. 글자는 여기서
-- 붓글씨 글자판(BitmapText)으로 판자 겉면에 붙인다. 공중에 뜨는 이름표는 쓰지 않는다.
--   Text      새길 글
--   Vertical  true 면 세로쓰기 (비석)
--   Faces     새길 면, 쉼표로 (기본 "Front")
--   Ink       글자 색 "gold" | "ink" | "cream" (기본 gold)

local CollectionService = game:GetService("CollectionService")

local BitmapText = require(script.Parent.BitmapText)

local Plaques = {}

local PIXELS_PER_STUD = 40
local MAX_DISTANCE = 220
local FILL = 0.82 -- 판자 너비(세로쓰기면 높이) 가운데 글자가 차지하는 몫

local INKS = {
	gold = Color3.fromRGB(236, 196, 112),
	ink = Color3.fromRGB(34, 26, 22),
	cream = Color3.fromRGB(246, 234, 206),
}

-- 면의 가로·세로 길이 (스터드)
local function faceSize(part: BasePart, face: Enum.NormalId): Vector2
	local size = part.Size
	if face == Enum.NormalId.Front or face == Enum.NormalId.Back then
		return Vector2.new(size.X, size.Y)
	elseif face == Enum.NormalId.Left or face == Enum.NormalId.Right then
		return Vector2.new(size.Z, size.Y)
	end
	return Vector2.new(size.X, size.Z)
end

local function engrave(part: BasePart, face: Enum.NormalId, text: string, vertical: boolean, color: Color3)
	local studs = faceSize(part, face)
	local gui = Instance.new("SurfaceGui")
	gui.Name = "Engraving_" .. face.Name
	gui.Face = face
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = PIXELS_PER_STUD
	gui.LightInfluence = 0.7
	gui.MaxDistance = MAX_DISTANCE
	gui.Parent = part

	local width, height = studs.X * PIXELS_PER_STUD, studs.Y * PIXELS_PER_STUD
	local holder = Instance.new("Frame")
	holder.Name = "Text"
	holder.BackgroundTransparency = 1
	holder.AnchorPoint = Vector2.new(0.5, 0.5)
	holder.Position = UDim2.fromScale(0.5, 0.5)
	holder.Parent = gui

	local chars = {}
	for _, code in utf8.codes(text) do
		table.insert(chars, utf8.char(code))
	end
	if #chars == 0 then
		return
	end

	if vertical then
		-- 한 글자씩 아래로 쌓는다. 글자 칸은 정사각형으로 보고 너비와 높이 중 좁은 쪽에 맞춘다
		local cell = math.min(width * FILL, height * FILL / #chars)
		local size = math.floor(cell * 0.9)
		holder.Size = UDim2.fromOffset(cell, cell * #chars)
		for i, ch in chars do
			local glyph = BitmapText.new({ font = "title", size = size, color = color, text = ch })
			local measured = glyph.frame.Size
			glyph.frame.Position =
				UDim2.fromOffset((cell - measured.X.Offset) / 2, (i - 1) * cell + (cell - measured.Y.Offset) / 2)
			glyph.frame.Parent = holder
		end
	else
		-- 한 줄로. 판자 너비에 맞추되 높이를 넘지 않게
		local probe = BitmapText.measure("title", 100, text)
		local size = math.floor(math.min(100 * width * FILL / probe.X, 100 * height * FILL / probe.Y))
		local label = BitmapText.new({ font = "title", size = math.max(size, 8), color = color, text = text })
		holder.Size = label.frame.Size
		label.frame.Parent = holder
	end
end

local function decorate(part: Instance)
	if not part:IsA("BasePart") or part:FindFirstChildOfClass("SurfaceGui") then
		return
	end
	local text = part:GetAttribute("Text")
	if type(text) ~= "string" or text == "" then
		return
	end
	local vertical = part:GetAttribute("Vertical") == true
	local color = INKS[part:GetAttribute("Ink") or "gold"] or INKS.gold
	local faces = part:GetAttribute("Faces")
	for name in string.gmatch(if type(faces) == "string" then faces else "Front", "[^,%s]+") do
		local ok, face = pcall(function()
			return (Enum.NormalId :: any)[name]
		end)
		if ok and face then
			engrave(part, face, text, vertical, color)
		end
	end
end

function Plaques.start()
	-- 맵이 스트리밍으로 들어오고 나가도 들어올 때마다 다시 새긴다
	CollectionService:GetInstanceAddedSignal("Plaque"):Connect(decorate)
	for _, part in CollectionService:GetTagged("Plaque") do
		decorate(part)
	end
end

-- 테스트용
Plaques.decorate = decorate

return Plaques
