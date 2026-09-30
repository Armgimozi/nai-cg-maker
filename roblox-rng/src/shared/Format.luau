--!strict
-- 숫자/시간 표시용 포맷 함수

local Format = {}

-- 1234567 -> "1,234,567"
function Format.commas(n: number): string
	local negative = n < 0
	local digits = tostring(math.floor(math.abs(n)))
	local out = digits:reverse():gsub("(%d%d%d)", "%1,"):reverse()
	if out:sub(1, 1) == "," then
		out = out:sub(2)
	end
	return if negative then "-" .. out else out
end

local SUFFIXES = {
	{ 1e12, "T" },
	{ 1e9, "B" },
	{ 1e6, "M" },
	{ 1e3, "K" },
}

-- 2500000 -> "2.5M", 404040 -> "404K". 반올림 대신 버림(999.95K 가 "1000K" 가 되지 않도록).
function Format.short(n: number): string
	for _, entry in SUFFIXES do
		local unit = entry[1] :: number
		if n >= unit then
			local value = n / unit
			local text
			if value >= 100 then
				text = tostring(math.floor(value))
			else
				text = string.format("%.1f", math.floor(value * 10) / 10):gsub("%.0$", "")
			end
			return text .. (entry[2] :: string)
		end
	end
	return Format.commas(n)
end

-- 확률 표기: 항상 콤마 자연수 ("1 in 2,500", "1 in 40,000,000")
function Format.oneIn(n: number): string
	return "1 in " .. Format.commas(n) -- 백만 넘어도 줄이지 않고 그대로(1 in 40,000,000)
end

-- 1.5 -> "x1.5", 2 -> "x2", 1.25 -> "x1.25"
function Format.multiplier(x: number): string
	local text = string.format("%.2f", x):gsub("0+$", ""):gsub("%.$", "")
	return "x" .. text
end

-- 초 -> "4:05" / "1:02:03"
function Format.duration(seconds: number): string
	local total = math.max(0, math.ceil(seconds))
	local h = total // 3600
	local m = (total % 3600) // 60
	local s = total % 60
	if h > 0 then
		return string.format("%d:%02d:%02d", h, m, s)
	end
	return string.format("%d:%02d", m, s)
end

-- Color3 -> "#rrggbb" (RichText 용)
function Format.hex(color: Color3): string
	return string.format(
		"#%02x%02x%02x",
		math.floor(color.R * 255 + 0.5),
		math.floor(color.G * 255 + 0.5),
		math.floor(color.B * 255 + 0.5)
	)
end

-- RichText 에 넣을 문자열 이스케이프
function Format.escape(text: string): string
	return (text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"))
end

return Format
