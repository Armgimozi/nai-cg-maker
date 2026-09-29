--!strict
-- 플레이어 데이터와 그 데이터를 바꾸는 규칙(순수 함수). 서버가 유일한 진실의 원천이고,
-- 클라이언트는 Snapshot 만 받아서 화면에 그립니다. Roblox 서비스에 의존하지 않아 테스트 가능.
-- 읽기 전용 함수(luck, park, stars, incomePerSecond 등)는 Data 대신 Snapshot 을 넘겨도 됩니다.

local Config = require(script.Parent.Config)
local Landmarks = require(script.Parent.Landmarks)

type Landmark = Landmarks.Landmark

export type Settings = {
	AutoFeature: boolean, -- 더 희귀한 명소를 발견하면 자동으로 대표 명소로 지정
}

export type Data = {
	Rolls: number,
	Coins: number, -- 관광 수입이 초 단위로 쌓이므로 소수일 수 있음(표시할 때 버림)
	Inventory: { [string]: number }, -- 명소 Id -> 발견 횟수
	Featured: string?, -- 대표 명소(캐릭터 옆에 떠 다님)
	Upgrades: { [string]: number }, -- 업그레이드 Id -> 레벨
	Settings: Settings,
}

export type Snapshot = {
	Revision: number,
	Rolls: number,
	Coins: number,
	Inventory: { [string]: number },
	Featured: string?,
	Upgrades: { [string]: number },
	Settings: Settings,
	Luck: number,
	Cooldown: number,
	Income: number, -- 초당 관광 수입
}

export type Upgrade = typeof(Config.Upgrades[1])

local PlayerState = {}

PlayerState.UpgradesById = {} :: { [string]: Upgrade }
for _, upgrade in Config.Upgrades do
	PlayerState.UpgradesById[upgrade.Id] = upgrade
end

function PlayerState.new(): Data
	local upgrades = {}
	for _, upgrade in Config.Upgrades do
		upgrades[upgrade.Id] = 0
	end
	return {
		Rolls = 0,
		Coins = 0,
		Inventory = {},
		Featured = nil,
		Upgrades = upgrades,
		Settings = { AutoFeature = true },
	}
end

local function nonNegativeInt(value: any): number?
	if type(value) == "number" and value == value and value >= 0 and value < math.huge then
		return math.floor(value)
	end
	return nil
end

-- DataStore 에서 읽은 값(형식 보장 없음)을 안전한 Data 로 정리합니다.
-- 모르는 명소 Id 의 발견 횟수는 지우지 않고 보존합니다(명소를 잠시 뺐다가 다시 넣어도 안전).
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

	if type(raw.Featured) == "string" and Landmarks.ById[raw.Featured] and data.Inventory[raw.Featured] then
		data.Featured = raw.Featured
	end

	if type(raw.Upgrades) == "table" then
		for _, upgrade in Config.Upgrades do
			local level = nonNegativeInt(raw.Upgrades[upgrade.Id])
			if level then
				data.Upgrades[upgrade.Id] = math.min(level, upgrade.MaxLevel)
			end
		end
	end

	if type(raw.Settings) == "table" and type(raw.Settings.AutoFeature) == "boolean" then
		data.Settings.AutoFeature = raw.Settings.AutoFeature
	end

	return data
end

-- 업그레이드 ---------------------------------------------------------------

function PlayerState.upgradeLevel(data: Data | Snapshot, upgradeId: string): number
	return data.Upgrades[upgradeId] or 0
end

-- 현재 레벨에서 다음 레벨로 가는 가격. 최대 레벨이면 nil.
function PlayerState.upgradePrice(upgradeId: string, level: number): number?
	local upgrade = PlayerState.UpgradesById[upgradeId]
	if not upgrade or level >= upgrade.MaxLevel then
		return nil
	end
	return math.floor(upgrade.BasePrice * upgrade.Growth ^ level)
end

-- 반환: 성공 여부, 실패 사유(표시용)
function PlayerState.buyUpgrade(data: Data, upgradeId: any): (boolean, string?)
	local upgrade = if type(upgradeId) == "string" then PlayerState.UpgradesById[upgradeId] else nil
	if not upgrade then
		return false, "존재하지 않는 업그레이드입니다"
	end
	local level = PlayerState.upgradeLevel(data, upgrade.Id)
	local price = PlayerState.upgradePrice(upgrade.Id, level)
	if not price then
		return false, "이미 최대 레벨입니다"
	end
	if data.Coins < price then
		return false, "코인이 부족합니다"
	end
	data.Coins -= price
	data.Upgrades[upgrade.Id] = level + 1
	return true, nil
end

-- 여권 도장 / 행운 / 속도 ----------------------------------------------------

-- 이 명소가 여권 도장 조건에 들어가는지 (전설급은 보너스 수집이라 제외)
function PlayerState.countsForStamp(landmark: Landmark): boolean
	return landmark.Tier.Rank <= Config.STAMP_MAX_RANK
end

-- 대륙의 도장 진행도: 발견한 수, 필요한 수 (도장 조건에 드는 명소만 셈)
function PlayerState.regionProgress(data: Data | Snapshot, regionId: string): (number, number)
	local found, required = 0, 0
	for _, landmark in Landmarks.ByRegion[regionId] or {} do
		if PlayerState.countsForStamp(landmark) then
			required += 1
			if (data.Inventory[landmark.Id] or 0) > 0 then
				found += 1
			end
		end
	end
	return found, required
end

-- 도장을 받은 대륙 Id 목록 (Landmarks.Regions 순서)
function PlayerState.completedRegions(data: Data | Snapshot): { string }
	local completed = {}
	for _, region in Landmarks.Regions do
		local found, required = PlayerState.regionProgress(data, region.Id)
		if required > 0 and found >= required then
			table.insert(completed, region.Id)
		end
	end
	return completed
end

-- 이번 굴림에 적용할 행운 = 기본 × 지구본 업그레이드 × 여권 도장
function PlayerState.luck(data: Data | Snapshot): number
	local globe = PlayerState.UpgradesById.Globe
	local globeMult = 1 + globe.PerLevel * PlayerState.upgradeLevel(data, "Globe")
	local regionMult = 1 + Config.REGION_LUCK_BONUS * #PlayerState.completedRegions(data)
	return Config.BASE_LUCK * globeMult * regionMult
end

function PlayerState.cooldown(data: Data | Snapshot): number
	local agency = PlayerState.UpgradesById.Agency
	return Config.ROLL_COOLDOWN * (1 - agency.PerLevel * PlayerState.upgradeLevel(data, "Agency"))
end

-- 관광 공원 ---------------------------------------------------------------

function PlayerState.slots(data: Data | Snapshot): number
	local park = PlayerState.UpgradesById.Park
	return Config.BASE_SLOTS + park.PerLevel * PlayerState.upgradeLevel(data, "Park")
end

-- 발견 횟수 -> 별 개수(0~5). 0 이면 미발견.
function PlayerState.stars(count: number): number
	local stars = 0
	for i, threshold in Config.STAR_THRESHOLDS do
		if count >= threshold then
			stars = i
		end
	end
	return stars
end

-- 공원에 전시되는 명소 Id 목록: 가진 것 중 희귀한 순서로 전시 칸 수만큼
function PlayerState.park(data: Data | Snapshot): { string }
	local result = {}
	local slots = PlayerState.slots(data)
	for _, landmark in Landmarks.RarestFirst do
		if #result >= slots then
			break
		end
		if (data.Inventory[landmark.Id] or 0) > 0 then
			table.insert(result, landmark.Id)
		end
	end
	return result
end

-- 명소 1개의 초당 수입 (입장료 업그레이드 제외)
function PlayerState.landmarkIncome(landmark: Landmark, count: number): number
	local stars = PlayerState.stars(count)
	if stars == 0 then
		return 0
	end
	local base = Config.TIER_INCOME[landmark.Tier.Rank] or 0
	return base * (1 + Config.STAR_INCOME_BONUS * (stars - 1))
end

function PlayerState.incomePerSecond(data: Data | Snapshot): number
	local total = 0
	for _, id in PlayerState.park(data) do
		total += PlayerState.landmarkIncome(Landmarks.ById[id], data.Inventory[id])
	end
	local ticket = PlayerState.UpgradesById.Ticket
	return total * (1 + ticket.PerLevel * PlayerState.upgradeLevel(data, "Ticket"))
end

-- dt 초 동안의 관광 수입을 더하고, 더한 양을 반환
function PlayerState.addIncome(data: Data, dt: number): number
	local amount = PlayerState.incomePerSecond(data) * math.max(0, dt)
	data.Coins += amount
	return amount
end

-- 굴림 --------------------------------------------------------------------

function PlayerState.discoveryBonus(landmark: Landmark): number
	return math.ceil(Config.DISCOVERY_BONUS_MULT * landmark.OneIn ^ 0.5)
end

-- 굴림 결과 반영. 반환: 보너스 코인(처음 발견일 때만), 처음 발견인지, 별이 올랐는지
function PlayerState.applyRoll(data: Data, landmark: Landmark): (number, boolean, boolean)
	local before = data.Inventory[landmark.Id] or 0
	local after = before + 1
	data.Inventory[landmark.Id] = after
	data.Rolls += 1
	local isNew = before == 0
	local bonus = if isNew then PlayerState.discoveryBonus(landmark) else 0
	data.Coins += bonus
	local starUp = not isNew and PlayerState.stars(after) > PlayerState.stars(before)
	return bonus, isNew, starUp
end

-- 가장 희귀한 보유 명소
function PlayerState.best(data: Data | Snapshot): Landmark?
	for _, landmark in Landmarks.RarestFirst do
		if (data.Inventory[landmark.Id] or 0) > 0 then
			return landmark
		end
	end
	return nil
end

-- landmarkId 가 nil 이면 해제. 발견한 명소만 대표로 지정 가능.
function PlayerState.feature(data: Data, landmarkId: any): boolean
	if landmarkId == nil then
		data.Featured = nil
		return true
	end
	if type(landmarkId) == "string" and Landmarks.ById[landmarkId] and (data.Inventory[landmarkId] or 0) > 0 then
		data.Featured = landmarkId
		return true
	end
	return false
end

function PlayerState.setSetting(data: Data, key: any, value: any): boolean
	if key == "AutoFeature" and type(value) == "boolean" then
		data.Settings.AutoFeature = value
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
		Featured = data.Featured,
		Upgrades = table.clone(data.Upgrades),
		Settings = table.clone(data.Settings),
		Luck = PlayerState.luck(data),
		Cooldown = PlayerState.cooldown(data),
		Income = PlayerState.incomePerSecond(data),
	}
end

return PlayerState
