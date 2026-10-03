-- 검수용 채팅 명령 (플레이스 주인만). 글을 읽어 무엇을 할지만 정하는 순수 로직이다.
--
--   /경지 연기기 7   경지와 단계로 옮긴다 (단계를 빼면 그 경지의 첫 단계)
--   /단계 23         단계 번호로 옮긴다 (1 범인 ~ 56 천인 천원)
--   /영력            지금 단계 영력을 채운다
--   /과업            지금 단계 과업을 끝낸다 (고르기는 직접)
--   /주머니 영초 10  주머니에 넣는다
--   /시간 밤         낮, 해질녘, 밤, 새벽으로 넘긴다
--   /초기화 확인     기록을 지우고 범인부터
--   /복구 확인       검수 명령을 처음 쓰기 전의 기록으로 되돌린다
--   /검수            명령 목록

local Realms = require(script.Parent.Realms)
local Balance = require(script.Parent.Balance)

local Commands = {}

-- 한글 이름, 영어 이름
Commands.ALIASES = {
	{ "경지", "realm" },
	{ "단계", "step" },
	{ "영력", "qi" },
	{ "과업", "tasks" },
	{ "주머니", "item" },
	{ "시간", "time" },
	{ "초기화", "reset" },
	{ "복구", "restore" },
	{ "검수", "devhelp" },
}

Commands.HELP = table.concat({
	"/경지 연기기 7, /단계 23, /영력, /과업, /주머니 영초 10, /시간 밤, /초기화 확인, /복구 확인",
	"경지 이름: 범인 단수기 연기기 축기기 결단기 원영기 천인기. 시간: 낮 해질녘 밤 새벽",
}, "\n")

local PHASES = { ["낮"] = "day", ["해질녘"] = "dusk", ["밤"] = "night", ["새벽"] = "dawn" }
for _, phase in { "day", "dusk", "night", "dawn" } do
	PHASES[phase] = phase
end

local NAME_OF: { [string]: string } = {}
for _, alias in Commands.ALIASES do
	NAME_OF[alias[1]] = alias[1]
	NAME_OF[alias[2]] = alias[1]
end

export type Parsed = {
	command: string, -- 한글 이름
	step: number?,
	item: string?,
	count: number?,
	phase: string?,
	confirmed: boolean?,
	error: string?,
}

local function words(text: string): { string }
	local out = {}
	for word in string.gmatch(text, "%S+") do
		table.insert(out, word)
	end
	return out
end

-- 경지 이름(또는 id)과 단계 → 단계 번호
function Commands.stepOf(realmName: string, sub: number?): number?
	for _, realm in Realms.list do
		if realm.name == realmName or realm.id == realmName then
			local index = math.clamp(math.floor(sub or 1), 1, #realm.subs)
			return Realms.firstStepById[realm.id] + index - 1
		end
	end
	return nil
end

function Commands.itemOf(name: string): string?
	for id, def in Balance.ITEMS do
		if def.name == name or string.lower(id) == string.lower(name) then
			return id
		end
	end
	return nil
end

-- "/경지 연기기 7" 같은 글을 읽는다. 명령이 아니면 nil
function Commands.parse(text: any): Parsed?
	if type(text) ~= "string" or string.sub(text, 1, 1) ~= "/" then
		return nil
	end
	-- 채팅 명령 별칭은 대소문자를 가리지 않으므로 여기서도 소문자로 맞춘다 (한글은 그대로)
	local list = words(string.lower(string.sub(text, 2)))
	local command = NAME_OF[list[1] or ""]
	if not command then
		return nil
	end
	local parsed: Parsed = { command = command }
	if command == "경지" then
		local sub = tonumber(list[3] or "1")
		local validSub = sub ~= nil and sub == sub and sub % 1 == 0 and sub >= 1 and sub < 1000
		local step = if list[2] then Commands.stepOf(list[2], 1) else nil
		if step and not validSub then
			parsed.error = "단계 번호는 1 이상의 정수다. 예: /경지 연기기 7"
		elseif step then
			parsed.step = Commands.stepOf(list[2], sub)
		else
			parsed.error =
				"경지 이름을 모르겠다. 범인 단수기 연기기 축기기 결단기 원영기 천인기 중에서."
		end
	elseif command == "단계" then
		local step = tonumber(list[2])
		if step and step == step and step % 1 == 0 and step >= 1 and step <= Realms.maxStep then
			parsed.step = step
		else
			parsed.error = string.format("단계는 1부터 %d까지의 수다.", Realms.maxStep)
		end
	elseif command == "주머니" then
		local item = list[2] and Commands.itemOf(list[2])
		local count = tonumber(list[3] or "1")
		if item and count and count == count and count >= 1 and count <= 999 then
			parsed.item = item
			parsed.count = math.floor(count)
		else
			parsed.error = "예: /주머니 영초 10 (영초, 천년영지, 홍령삼, 축기단, 별씨)"
		end
	elseif command == "시간" then
		local phase = PHASES[list[2] or ""]
		if phase then
			parsed.phase = phase
		else
			parsed.error = "예: /시간 밤 (낮, 해질녘, 밤, 새벽)"
		end
	elseif command == "초기화" or command == "복구" then
		parsed.confirmed = list[2] == "확인" or list[2] == "confirm"
	end
	return parsed
end

return Commands
