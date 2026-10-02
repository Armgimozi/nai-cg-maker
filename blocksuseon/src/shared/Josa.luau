-- 받침에 맞춰 조사를 붙인다. ("결단기" → "결단기를", "영력 1.2만" → "영력 1.2만을")

local Josa = {}

-- 숫자로 끝나면 읽는 소리로 받침을 정한다: 영 일 이 삼 사 오 육 칠 팔 구
local DIGIT_FINAL = {
	["0"] = "ㅇ",
	["1"] = "ㄹ",
	["2"] = "",
	["3"] = "ㅁ",
	["4"] = "",
	["5"] = "",
	["6"] = "ㄱ",
	["7"] = "ㄹ",
	["8"] = "ㄹ",
	["9"] = "",
}

-- 마지막 글자의 받침. "" 이면 받침 없음, "ㄹ" 은 따로 구분한다.
local function final(word: string): string
	local last: number? = nil
	for _, code in utf8.codes(word) do
		last = code
	end
	if not last then
		return ""
	end
	if last >= 0xAC00 and last <= 0xD7A3 then
		local jong = (last - 0xAC00) % 28
		if jong == 0 then
			return ""
		end
		return if jong == 8 then "ㄹ" else "받침"
	end
	return DIGIT_FINAL[utf8.char(last)] or ""
end

function Josa.eul(word: string): string -- 을/를
	return word .. (if final(word) == "" then "를" else "을")
end

function Josa.i(word: string): string -- 이/가
	return word .. (if final(word) == "" then "가" else "이")
end

function Josa.eun(word: string): string -- 은/는
	return word .. (if final(word) == "" then "는" else "은")
end

function Josa.ro(word: string): string -- 으로/로 (ㄹ 받침은 "로")
	local f = final(word)
	return word .. (if f == "" or f == "ㄹ" then "로" else "으로")
end

return Josa
