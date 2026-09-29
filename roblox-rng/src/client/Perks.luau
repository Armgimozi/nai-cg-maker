-- 환생 · 게임패스 · 개발자 상품 · 시간 부스트 · 서버 행운을 화면용으로 읽는 헬퍼 (DESIGN.md v3).
-- Snapshot/Config 를 방어적으로 읽습니다: 필드가 없거나 형식이 조금 달라도(숫자/표) 화면이 깨지지 않게.
--   Snapshot: Rebirths, NextRebirth = { Coins, Landmarks }, Discovered, Boosts = { [id] = 남은 초 },
--             Passes = { [passKey] = true }, ServerLuck (남은 초 / 끝나는 유닉스 시각 / 표 / true)
--   Config:   REBIRTH_LUCK_BONUS, REBIRTH_INCOME_BONUS, REBIRTHS, GamePasses, Products
--             (상품 항목은 숫자 Id 또는 { Id = 숫자, ... } 둘 다 받음. Id 가 0 이면 화면에 안 나옴)

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config) :: any
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState) :: any

local Perks = {}

local function number(value: any, default: number): number
	return if type(value) == "number" and value == value then value else default
end

-- 처음 나오는 숫자 필드 (없으면 nil)
local function pick(entry: any, keys: { string }): number?
	if type(entry) ~= "table" then
		return nil
	end
	for _, key in keys do
		local value = tonumber(entry[key])
		if value then
			return value
		end
	end
	return nil
end

Perks.REBIRTH_LUCK = number(Config.REBIRTH_LUCK_BONUS, 0.2)
Perks.REBIRTH_INCOME = number(Config.REBIRTH_INCOME_BONUS, 0.5)

-- 서버 행운 이벤트/스냅샷의 시각이 이보다 크면 유닉스 시각(초), 작으면 남은 초로 봄
local EPOCH_MIN = 1e8

-- 상품 ------------------------------------------------------------------------

export type Item = {
	Key: string,
	Kind: string, -- "Pass" | "Product"
	Id: number,
	Name: string,
	Icon: string, -- 카드 큰 아이콘
	Color: string, -- 카드 띠 색 (Ui 색 이름)
	EffectIcon: string,
	Mult: number?, -- 배율 (×2, 굴림 간격 ×0.7)
	Seconds: number?, -- 시간 부스트 길이
}

-- 화면에 보여 줄 순서와 모양. 효과 숫자는 Config 항목에 있으면 그 값을 씀
local PASS_INFO = {
	{ Key = "LuckVIP", Name = "행운 VIP", Icon = "clover", Color = "Grape", EffectIcon = "clover", Mult = 2 },
	{ Key = "FastRoll", Name = "빠른 굴림", Icon = "plane", Color = "Sky", EffectIcon = "dice", Mult = 0.7 },
	{ Key = "DoubleIncome", Name = "수입 2배", Icon = "coin", Color = "Sun", EffectIcon = "arrow_up", Mult = 2 },
}
local PRODUCT_INFO = {
	{
		Key = "LuckBoost",
		Name = "행운 부스트",
		Icon = "clover",
		Color = "Grass",
		EffectIcon = "clover",
		Mult = 2,
		Seconds = 900,
	},
	{
		Key = "ServerLuck",
		Name = "서버 행운",
		Icon = "globe",
		Color = "Coral",
		EffectIcon = "clover",
		Mult = 2,
		Seconds = 900,
	},
	{ Key = "CoinPack", Name = "코인 팩", Icon = "coin", Color = "Sun", EffectIcon = "coin" },
}

-- Config.GamePasses / Products 에서 key 항목 찾기: { LuckVIP = 123 } / { LuckVIP = { Id = 123 } } / { { Key = "LuckVIP", Id = 123 } }
local function lookup(group: any, key: string): any
	if type(group) ~= "table" then
		return nil
	end
	local entry = group[key]
	if entry ~= nil then
		return entry
	end
	for _, value in group do
		if type(value) == "table" and value.Key == key then
			return value
		end
	end
	return nil
end

local function idOf(entry: any): number
	if type(entry) == "number" then
		return entry
	end
	return pick(entry, { "Id", "PassId", "ProductId", "AssetId" }) or 0
end

local function buildItems(group: any, infos: { any }, kind: string): { Item }
	local items = {}
	for _, info in infos do
		local entry = lookup(group, info.Key)
		local id = idOf(entry)
		if id ~= 0 then
			table.insert(items, {
				Key = info.Key,
				Kind = kind,
				Id = id,
				Name = info.Name,
				Icon = info.Icon,
				Color = info.Color,
				EffectIcon = info.EffectIcon,
				Mult = pick(entry, { "Mult", "Multiplier", "Factor" }) or info.Mult,
				Seconds = pick(entry, { "Seconds", "Duration" }) or info.Seconds,
			})
		end
	end
	return items
end

-- Id 가 0 이 아닌 것만 (Config 는 바뀌지 않으므로 한 번만 만듦)
Perks.Passes = buildItems(Config.GamePasses, PASS_INFO, "Pass")
Perks.Products = buildItems(Config.Products, PRODUCT_INFO, "Product")

local itemsByKey: { [string]: Item } = {}
for _, item in Perks.Passes do
	itemsByKey[item.Key] = item
end
for _, item in Perks.Products do
	itemsByKey[item.Key] = item
end

-- 팔 상품이 하나라도 있는지 (없으면 상점 버튼을 숨김)
function Perks.anyForSale(): boolean
	return #Perks.Passes > 0 or #Perks.Products > 0
end

-- 구매 완료 이벤트(숫자 Id) -> 상품
function Perks.itemById(kind: string, id: number): Item?
	local list = if kind == "Pass" then Perks.Passes else Perks.Products
	for _, item in list do
		if item.Id == id then
			return item
		end
	end
	return nil
end

-- 설정에 없는(Id 0) 상품이어도 기본 배율/시간은 알려 줌 (서버 행운 띠, 부스트 딱지에서 씀)
local function infoFor(key: string): any
	local item = itemsByKey[key]
	if item then
		return item
	end
	for _, info in PRODUCT_INFO do
		if info.Key == key then
			return info
		end
	end
	return nil
end

function Perks.mult(key: string, default: number): number
	local info = infoFor(key)
	return if info and info.Mult then info.Mult else default
end

-- 게임패스 보유 여부. Passes 의 키가 패스 이름이든 숫자 Id 든 받아 줌
function Perks.ownsPass(state: any, key: string): boolean
	local passes = if type(state) == "table" then state.Passes else nil
	if type(passes) ~= "table" then
		return false
	end
	if passes[key] then
		return true
	end
	local item = itemsByKey[key]
	return item ~= nil and (passes[item.Id] or passes[tostring(item.Id)]) and true or false
end

-- 코인 팩으로 받을 코인 = max(1000, 초당 수입 × 1800)
function Perks.coinPackAmount(income: number): number
	local entry = lookup(Config.Products, "CoinPack")
	local minimum = pick(entry, { "MinCoins", "Min" }) or 1000
	local seconds = pick(entry, { "IncomeSeconds", "Seconds" }) or 1800
	return math.max(minimum, math.floor(number(income, 0) * seconds))
end

-- 시간 부스트 ------------------------------------------------------------------

export type Boost = { Key: string, Seconds: number, Mult: number, Icon: string }

local BOOST_ICONS = { LuckBoost = "clover" }

-- 스냅샷을 받은 순간의 남은 시간 목록 (0 초 이하는 뺌). 키 이름 순서
function Perks.boosts(state: any): { Boost }
	local list = {}
	local boosts = if type(state) == "table" then state.Boosts else nil
	if type(boosts) ~= "table" then
		return list
	end
	for key, value in boosts do
		local seconds = if type(value) == "number" then value else pick(value, { "Remaining", "Seconds" })
		if type(key) == "string" and seconds and seconds > 0 then
			table.insert(list, {
				Key = key,
				Seconds = seconds,
				Mult = Perks.mult(key, 2),
				Icon = BOOST_ICONS[key] or "clover",
			})
		end
	end
	table.sort(list, function(a, b)
		return a.Key < b.Key
	end)
	return list
end

-- 서버 행운 -------------------------------------------------------------------

-- 시각 값 -> 끝나는 유닉스 시각. 큰 값은 그대로(유닉스 시각), 작은 값은 nowEpoch 기준 남은 초
function Perks.toEpoch(value: number, nowEpoch: number): number
	if value >= EPOCH_MIN then
		return value
	end
	return nowEpoch + value
end

-- 스냅샷의 ServerLuck -> (끝나는 유닉스 시각?, 시각 없이 "켜짐"만 알면 true)
-- receivedEpoch: 스냅샷을 받은 순간의 서버 시계(workspace:GetServerTimeNow 기준)
function Perks.serverLuck(value: any, receivedEpoch: number): (number?, boolean)
	if type(value) == "number" then
		if value <= 0 then
			return nil, false
		end
		return Perks.toEpoch(value, receivedEpoch), false
	elseif type(value) == "table" then
		local untilTime = pick(value, { "Until", "EndsAt" })
		if untilTime then
			return Perks.toEpoch(untilTime, receivedEpoch), false
		end
		local remaining = pick(value, { "Remaining", "Seconds" })
		if remaining then
			return receivedEpoch + remaining, false
		end
		return nil, value.Active == true
	elseif value == true then
		return nil, true
	end
	return nil, false
end

-- 환생 -----------------------------------------------------------------------

export type Need = { Coins: number, Landmarks: { string } }

function Perks.rebirths(state: any): number
	return if type(state) == "table" then math.max(0, math.floor(number(state.Rebirths, 0))) else 0
end

-- 환생 수 -> 지금 받는 (행운 배율, 수입 배율)
function Perks.rebirthMults(rebirths: number): (number, number)
	return 1 + Perks.REBIRTH_LUCK * rebirths, 1 + Perks.REBIRTH_INCOME * rebirths
end

-- 요구 명소 목록: 배열 { id, ... } 또는 { [id] = true } 둘 다 받음. 모르는 Id 는 뺌
local function landmarkList(value: any): { string }
	local list = {}
	if type(value) ~= "table" then
		return list
	end
	if #value > 0 then
		for _, id in value do
			if type(id) == "string" and Landmarks.ById[id] then
				table.insert(list, id)
			end
		end
	else
		for id, flag in value do
			if type(id) == "string" and flag and Landmarks.ById[id] then
				table.insert(list, id)
			end
		end
		-- 순서가 없는 표면 흔한 것부터
		table.sort(list, function(a, b)
			return Landmarks.ById[a].OneIn < Landmarks.ById[b].OneIn
		end)
	end
	return list
end

local function need(raw: any): Need?
	if type(raw) ~= "table" then
		return nil
	end
	return { Coins = math.max(0, number(tonumber(raw.Coins), 0)), Landmarks = landmarkList(raw.Landmarks) }
end

-- 다음 환생 조건: 스냅샷 NextRebirth -> PlayerState.rebirthRequirement -> Config.REBIRTHS 순서로 찾음
function Perks.rebirthNeed(state: any): Need?
	if type(state) ~= "table" then
		return nil
	end
	local fromSnapshot = need(state.NextRebirth)
	if fromSnapshot then
		return fromSnapshot
	end
	local rebirths = Perks.rebirths(state)
	if type(PlayerState.rebirthRequirement) == "function" then
		local ok, result = pcall(PlayerState.rebirthRequirement, rebirths)
		local parsed = if ok then need(result) else nil
		if parsed then
			return parsed
		end
	end
	local steps = Config.REBIRTHS
	if type(steps) == "table" and #steps > 0 then
		local nextNumber = rebirths + 1
		local step = steps[math.min(nextNumber, #steps)]
		local coins = number(if type(step) == "table" then tonumber(step.Coins) else nil, 0)
		local extra = math.max(0, nextNumber - #steps)
		return {
			Coins = coins * 4 ^ extra,
			Landmarks = landmarkList(if type(step) == "table" then step.Landmarks else nil),
		}
	end
	return nil
end

-- 이번 판에 보유한 수 (공원·별·환생 조건 기준)
function Perks.owned(state: any, id: string): number
	local inventory = if type(state) == "table" then state.Inventory else nil
	return if type(inventory) == "table" then number(inventory[id], 0) else 0
end

-- 역대 발견 여부 (도감·여권 기준). 스냅샷에 Discovered 가 없으면 보유 기준
function Perks.discovered(state: any, id: string): boolean
	local discovered = if type(state) == "table" then state.Discovered else nil
	if type(discovered) == "table" and discovered[id] then
		return true
	end
	return Perks.owned(state, id) > 0
end

-- 지금 환생할 수 있는지. 반환: 가능 여부, 없는 명소 Id 목록, 모자란 코인, 조건
function Perks.rebirthCheck(state: any, coins: number): (boolean, { string }, number, Need?)
	local nextNeed = Perks.rebirthNeed(state)
	if not nextNeed then
		return false, {}, 0, nil
	end
	local missing = {}
	for _, id in nextNeed.Landmarks do
		if Perks.owned(state, id) <= 0 then
			table.insert(missing, id)
		end
	end
	local short = math.max(0, nextNeed.Coins - math.floor(coins))
	return #missing == 0 and short <= 0, missing, short, nextNeed
end

return Perks
