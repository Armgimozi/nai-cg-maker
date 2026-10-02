-- 붓글씨·명조 비트맵 글꼴로 글자를 찍는다.
--
-- Roblox 에는 한글 명조·붓글씨 글꼴이 없어서, tools/build_glyphs.mjs 로 만든 글자판(Art.fonts)에서
-- 글자를 하나씩 잘라 ImageLabel 로 놓는다. 글자판은 흰 글자 + 어두운 테두리라서
-- ImageColor3 나 UIGradient 로 곱하면 글자만 원하는 색이 된다.

local Art = require(script.Parent.Art)

export type Options = {
	font: string, -- "body" | "title"
	size: number, -- 글자 크기(px)
	color: Color3?,
	gradient: ColorSequence?, -- 위→아래 그라데이션 (color 대신)
	text: string?,
	name: string?,
	parent: Instance?,
}

local BitmapText = {}
BitmapText.__index = BitmapText

local warned: { [string]: boolean } = {}

local function glyphOf(font, ch: string)
	local glyph = font.glyphs[ch]
	if not glyph and not warned[ch] then
		warned[ch] = true
		warn("[블록수선전] 글자판에 없는 글자:", ch, "— tools/fetch_fonts.py 부터 다시 돌릴 것")
	end
	return glyph
end

-- 글자 줄의 픽셀 너비·높이
function BitmapText.measure(fontName: string, size: number, text: string): Vector2
	local font = Art.fonts[fontName]
	local scale = size / font.size
	local width = 0
	for _, code in utf8.codes(text) do
		local glyph = font.glyphs[utf8.char(code)]
		if glyph then
			width += glyph[6]
		end
	end
	return Vector2.new((width + font.pad * 2) * scale, (font.lineHeight + font.pad * 2) * scale)
end

function BitmapText.new(options: Options)
	local self = setmetatable({}, BitmapText)
	self.font = Art.fonts[options.font]
	self.fontName = options.font
	self.size = options.size
	self.color = options.color or Color3.new(1, 1, 1)
	self.gradient = options.gradient
	self.transparency = 0
	self.text = nil :: string?
	self.glyphs = {} :: { ImageLabel }

	local frame = Instance.new("Frame")
	frame.Name = options.name or "Text"
	frame.BackgroundTransparency = 1
	frame.Size = UDim2.fromOffset(0, 0)
	self.frame = frame

	self:set(options.text or "")
	if options.parent then
		frame.Parent = options.parent
	end
	return self
end

function BitmapText:_paint(label: ImageLabel)
	label.ImageColor3 = if self.gradient then Color3.new(1, 1, 1) else self.color
	label.ImageTransparency = self.transparency
	local gradient = label:FindFirstChildOfClass("UIGradient")
	if self.gradient then
		if not gradient then
			gradient = Instance.new("UIGradient")
			gradient.Rotation = 90
			gradient.Parent = label
		end
		gradient.Color = self.gradient
	elseif gradient then
		gradient:Destroy()
	end
end

function BitmapText:set(text: string)
	if text == self.text then
		return
	end
	self.text = text
	for _, label in self.glyphs do
		label:Destroy()
	end
	table.clear(self.glyphs)

	local font = self.font
	local scale = self.size / font.size
	local pen = 0
	for _, code in utf8.codes(text) do
		local glyph = glyphOf(font, utf8.char(code))
		if glyph then
			local page, x, y, w, h, advance = glyph[1], glyph[2], glyph[3], glyph[4], glyph[5], glyph[6]
			if w > 0 then
				local label = Instance.new("ImageLabel")
				label.Name = "g"
				label.BackgroundTransparency = 1
				label.Image = font.pages[page]
				label.ImageRectOffset = Vector2.new(x, y)
				label.ImageRectSize = Vector2.new(w, h)
				label.Size = UDim2.fromOffset(w * scale, h * scale)
				label.Position = UDim2.fromOffset(pen * scale, 0)
				self:_paint(label)
				label.Parent = self.frame
				table.insert(self.glyphs, label)
			end
			pen += advance
		end
	end

	self.frame.Size =
		UDim2.fromOffset(math.ceil((pen + font.pad * 2) * scale), math.ceil((font.lineHeight + font.pad * 2) * scale))
end

function BitmapText:setColor(color: Color3)
	if self.color == color and not self.gradient then
		return
	end
	self.color = color
	self.gradient = nil
	for _, label in self.glyphs do
		self:_paint(label)
	end
end

function BitmapText:setGradient(gradient: ColorSequence)
	self.gradient = gradient
	for _, label in self.glyphs do
		self:_paint(label)
	end
end

function BitmapText:setTransparency(transparency: number)
	self.transparency = transparency
	for _, label in self.glyphs do
		label.ImageTransparency = transparency
	end
end

return BitmapText
