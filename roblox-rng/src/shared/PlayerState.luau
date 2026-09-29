--!strict
-- 플레이어 데이터와 그 데이터를 바꾸는 규칙(순수 함수). 서버가 유일한 진실의 원천이고,
-- 클라이언트는 Snapshot 만 받아서 화면에 그립니다. Roblox 서비스에 의존하지 않아 테스트 가능.

local Auras = require(script.Parent.Auras)
local Config = require(script.Parent.Config)

type Aura = Auras.Aura

export type Settings = {
	AutoEquip: boolean,
}

export type Data = {
	Rolls: number,
	Coins: number,
	Inventory: { [string]: number }, -- 오라 Id -> 보유 개수
	Equipped: string?,
	Potions: { [string]: number }, -- 물약 Id -> 남은 초 (접속 중에만 줄어듦)
	Settings: Settings,
}

export type Snapshot = {
	Revision: number,
	Rolls: number,
	Coins: number,
	Inventory: { [string]: number },
	Equipped: string?,
	Potions: { [string]: number },
	Settings: Settings,
	Luck: number,
	Cooldown: number,
}

export type Potion = typeof(Config.Potions[1])

local PlayerState = {}

PlayerState.PotionsById = {} :: { [string]: Potion }
for _, potion in Config.Potions do
	PlayerState.PotionsById[potion.Id] = potion
end

function PlayerState.new(): Data
	return {
		Rolls = 0,
		Coins = 0,
		Inventory = {},
		Equipped = nil,
		Potions = {},
		Settings = { AutoEquip = true },
	}
end

local function nonNegativeInt(value: any): number?
	if type(value) == "number" and value == value and value >= 0 and value < math.huge then
		return math.floor(value)
	end
	return nil
end

-- DataStore 에서 읽은 값(형식 보장 없음)을 안전한 Data 로 정리합니다.
-- 모르는 오라 Id 의 보유 개수는 지우지 않고 보존합니다(오라를 잠시 뺐다가 다시 넣어도 안전).
function PlayerState.reconcile(raw: any): Data
	local data = PlayerState.new()
	if type(raw) ~= "table" then
		return data
	end

	data.Rolls = nonNegativeInt(raw.Rolls) or 0
	data.Coins = nonNegativeInt(raw.Coins) or 0

	if type(raw.Inventory) == "table" then
		for id, count in raw.Inventory do
			local n = nonNegativeInt(count)
			if type(id) == "string" and n and n > 0 then
				data.Inventory[id] = n
			end
		end
	end

	if type(raw.Equipped) == "string" and Auras.ById[raw.Equipped] and data.Inventory[raw.Equipped] then
		data.Equipped = raw.Equipped
	end

	if type(raw.Potions) == "table" then
		for id, seconds in raw.Potions do
			if type(id) == "string" and PlayerState.PotionsById[id] and type(seconds) == "number" and seconds > 0 then
				data.Potions[id] = math.min(seconds, Config.MAX_POTION_SECONDS)
			end
		end
	end

	if type(raw.Settings) == "table" and type(raw.Settings.AutoEquip) == "boolean" then
		data.Settings.AutoEquip = raw.Settings.AutoEquip
	end

	return data
end

-- 물약 효과를 반영한 현재 행운 (행운 굴림 보너스 제외)
function PlayerState.luck(data: Data): number
	local luck = Config.BASE_LUCK
	for id in data.Potions do
		local potion = PlayerState.PotionsById[id]
		if potion then
			luck *= potion.LuckMult
		end
	end
	return luck
end

-- 굴림 번호(1부터)가 행운 굴림인지
function PlayerState.isLuckyRoll(rollNumber: number): boolean
	return rollNumber % Config.LUCKY_ROLL_EVERY == 0
end

-- 다음 행운 굴림까지 남은 굴림 수 (1 = 바로 다음 굴림)
function PlayerState.rollsUntilLucky(rolls: number): number
	return Config.LUCKY_ROLL_EVERY - (rolls % Config.LUCKY_ROLL_EVERY)
end

-- 이번 굴림에 실제로 적용할 행운과 행운 굴림 여부
function PlayerState.rollLuck(data: Data): (number, boolean)
	local lucky = PlayerState.isLuckyRoll(data.Rolls + 1)
	local luck = PlayerState.luck(data)
	if lucky then
		luck *= Config.LUCKY_ROLL_MULT
	end
	return luck, lucky
end

function PlayerState.cooldown(data: Data): number
	local cooldown = Config.ROLL_COOLDOWN
	for id in data.Potions do
		local potion = PlayerState.PotionsById[id]
		if potion then
			cooldown *= potion.CooldownMult
		end
	end
	return cooldown
end

function PlayerState.coinsFor(aura: Aura): number
	return math.ceil(aura.OneIn ^ Config.COIN_EXPONENT)
end

-- 굴림 결과 반영. 반환: 얻은 코인, 처음 얻은 오라인지
function PlayerState.applyRoll(data: Data, aura: Aura): (number, boolean)
	local owned = data.Inventory[aura.Id] or 0
	data.Inventory[aura.Id] = owned + 1
	data.Rolls += 1
	local coins = PlayerState.coinsFor(aura)
	data.Coins += coins
	return coins, owned == 0
end

-- 가장 희귀한 보유 오라
function PlayerState.best(data: Data): Aura?
	for _, aura in Auras.RarestFirst do
		if (data.Inventory[aura.Id] or 0) > 0 then
			return aura
		end
	end
	return nil
end

-- auraId 가 nil 이면 해제. 보유한 오라만 장착 가능.
function PlayerState.equip(data: Data, auraId: any): boolean
	if auraId == nil then
		data.Equipped = nil
		return true
	end
	if type(auraId) == "string" and Auras.ById[auraId] and (data.Inventory[auraId] or 0) > 0 then
		data.Equipped = auraId
		return true
	end
	return false
end

-- 반환: 성공 여부, 실패 사유(표시용)
function PlayerState.buyPotion(data: Data, potionId: any): (boolean, string?)
	local potion = if type(potionId) == "string" then PlayerState.PotionsById[potionId] else nil
	if not potion then
		return false, "존재하지 않는 물약입니다"
	end
	if data.Coins < potion.Price then
		return false, "코인이 부족합니다"
	end
	local current = data.Potions[potion.Id] or 0
	if current + potion.Duration > Config.MAX_POTION_SECONDS then
		return false, string.format("최대 %d분까지만 쌓을 수 있습니다", Config.MAX_POTION_SECONDS // 60)
	end
	data.Coins -= potion.Price
	data.Potions[potion.Id] = current + potion.Duration
	return true, nil
end

-- 물약 시간 감소. 끝난 물약이 있으면 true.
function PlayerState.tickPotions(data: Data, dt: number): boolean
	local expired = false
	for id, remaining in data.Potions do
		local left = remaining - dt
		if left <= 0 then
			data.Potions[id] = nil
			expired = true
		else
			data.Potions[id] = left
		end
	end
	return expired
end

function PlayerState.setSetting(data: Data, key: any, value: any): boolean
	if key == "AutoEquip" and type(value) == "boolean" then
		data.Settings.AutoEquip = value
		return true
	end
	return false
end

function PlayerState.snapshot(data: Data, revision: number): Snapshot
	return {
		Revision = revision,
		Rolls = data.Rolls,
		Coins = data.Coins,
		Inventory = table.clone(data.Inventory),
		Equipped = data.Equipped,
		Potions = table.clone(data.Potions),
		Settings = table.clone(data.Settings),
		Luck = PlayerState.luck(data),
		Cooldown = PlayerState.cooldown(data),
	}
end

return PlayerState
