-- 붓글씨·명조 비트맵 글꼴로 글자를 찍는다.
--
-- Roblox 에는 한글 명조·붓글씨 글꼴이 없어서, tools/build_glyphs.mjs 로 만든 글자판(Art.fonts)에서
-- 글자를 하나씩 잘라 ImageLabel 로 놓는다. 글자판은 흰 글자 + 어두운 테두리라서
-- ImageColor3 나 UIGradient 로 곱하면 글자만 원하는 색이 된다.
-- 글자판 그림을 못 받아 오면(검수 중, 내려받기 실패) 그 글자판을 쓰는 글줄은 Roblox 글꼴로 대신 찍는다.

local ContentProvider = game:GetService("ContentProvider")

local Art = require(script.Parent.Art)

local FALLBACK_FONT = { body = Enum.Font.GothamBold, title = Enum.Font.GothamBlack }

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

-- 못 뜬 글자판과, 다시 찍어야 할 글줄
local badPages: { [string]: boolean } = {}
local live = setmetatable({}, { __mode = "k" }) :: { [any]: boolean }
local checking = false

local function checkPages()
	if checking then
		return
	end
	checking = true
	task.spawn(function()
		local list = {}
		for _, font in Art.fonts do
			for _, page in font.pages do
				table.insert(list, page)
			end
		end
		pcall(function()
			ContentProvider:PreloadAsync(list, function(content: string, status: Enum.AssetFetchStatus)
				if status ~= Enum.AssetFetchStatus.Success then
					badPages[content] = true
					warn(
						"[블록수선전] 글자판을 못 받아 왔다:",
						content,
						status,
						"— Roblox 글꼴로 찍는다"
					)
				end
			end)
		end)
		if next(badPages) then
			for text in live do
				text:_refresh()
			end
		end
	end)
end

-- 이 글줄이 못 뜬 글자판을 쓰는가
local function usesBadPage(font, text: string): boolean
	if not next(badPages) then
		return false
	end
	for _, code in utf8.codes(text) do
		local glyph = font.glyphs[utf8.char(code)]
		if glyph and glyph[4] > 0 and badPages[font.pages[glyph[1]]] then
			return true
		end
	end
	return false
end

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
	self.fallback = nil :: TextLabel?

	local frame = Instance.new("Frame")
	frame.Name = options.name or "Text"
	frame.BackgroundTransparency = 1
	frame.Size = UDim2.fromOffset(0, 0)
	self.frame = frame

	self:set(options.text or "")
	if options.parent then
		frame.Parent = options.parent
	end
	live[self] = true
	checkPages()
	return self
end

-- 글자판 상태가 바뀌었을 때 다시 찍는다
function BitmapText:_refresh()
	local text = self.text
	self.text = nil
	self:set(text or "")
end

-- Roblox 글꼴로 찍는 글줄
function BitmapText:_paintFallback(label: TextLabel)
	label.TextColor3 = if self.gradient then Color3.new(1, 1, 1) else self.color
	label.TextTransparency = self.transparency
	label.TextStrokeTransparency = 0.35 + self.transparency * 0.65
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
	if self.fallback then
		self.fallback:Destroy()
		self.fallback = nil
	end

	local font = self.font
	local scale = self.size / font.size
	if usesBadPage(font, text) then
		local size = BitmapText.measure(self.fontName, self.size, text)
		local label = Instance.new("TextLabel")
		label.Name = "fallback"
		label.BackgroundTransparency = 1
		label.Font = FALLBACK_FONT[self.fontName] or Enum.Font.GothamBold
		label.TextSize = math.floor(self.size * 0.86)
		label.TextXAlignment = Enum.TextXAlignment.Left
		label.TextStrokeColor3 = Color3.fromRGB(27, 21, 13)
		label.Text = text
		label.Size = UDim2.fromScale(1, 1)
		label.Position = UDim2.fromOffset(font.pad * scale, 0)
		self:_paintFallback(label)
		label.Parent = self.frame
		self.fallback = label
		self.frame.Size = UDim2.fromOffset(math.ceil(size.X), math.ceil(size.Y))
		return
	end
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
	if self.fallback then
		self:_paintFallback(self.fallback)
	end
end

function BitmapText:setGradient(gradient: ColorSequence)
	self.gradient = gradient
	for _, label in self.glyphs do
		self:_paint(label)
	end
	if self.fallback then
		self:_paintFallback(self.fallback)
	end
end

function BitmapText:setTransparency(transparency: number)
	self.transparency = transparency
	for _, label in self.glyphs do
		label.ImageTransparency = transparency
	end
	if self.fallback then
		self:_paintFallback(self.fallback)
	end
end

return BitmapText
