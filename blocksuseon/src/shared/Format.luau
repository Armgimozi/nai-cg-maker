-- 화면 표시용 숫자 포맷.

local Format = {}

local UNITS = {
	{ 1e16, "경" },
	{ 1e12, "조" },
	{ 1e8, "억" },
	{ 1e4, "만" },
}

local function trim(value: number): string
	if value >= 100 then
		return tostring(math.floor(value))
	end
	local text = string.format("%.1f", math.floor(value * 10) / 10)
	return (string.gsub(text, "%.0$", ""))
end

-- 12345 → "1.2만", 340000000 → "3.4억"
function Format.qi(value: number): string
	value = math.floor(value)
	for _, unit in UNITS do
		if value >= unit[1] then
			return trim(value / unit[1]) .. unit[2]
		end
	end
	return tostring(value)
end

function Format.rate(value: number): string
	if value < 10 then
		return trim(value)
	end
	return Format.qi(value)
end

function Format.percent(value: number): string
	return string.format("%d%%", math.floor(value * 100 + 0.5))
end

return Format
