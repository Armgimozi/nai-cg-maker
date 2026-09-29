--!strict
-- 플레이어 데이터와 그 데이터를 바꾸는 규칙(순수 함수). 서버가 유일한 진실의 원천이고,
-- 클라이언트는 Snapshot 만 받아서 화면에 그립니다. Roblox 서비스에 의존하지 않아 테스트 가능.
-- 읽기 전용 함수(luck, park, stars, incomePerSecond 등)는 Data 대신 Snapshot 을 넘겨도 됩니다.
-- luck / cooldown / incomePerSecond / addIncome / snapshot 은 선택 인자 mods(게임패스·서버 행운)를 받습니다.
-- mods 가 없으면 게임패스·서버 행운 없이 계산합니다. Snapshot 은 Passes/ServerLuck 필드가 있어서
-- PlayerState.luck(snapshot, snapshot) 처럼 mods 자리에 그대로 넘겨도 됩니다.

local Config = require(script.Parent.Config)
local Landmarks = require(script.Parent.Landmarks)

type Landmark = Landmarks.Landmark
type GamePass = Config.GamePass
type Product = Config.Product

export type Settings = {
	AutoFeature: boolean, -- 더 희귀한 명소를 발견하면 자동으로 대표 명소로 지정
}

-- 세션에만 있는 효과(저장 안 함). 서버가 만들어서 넘김
export type Mods = {
	Passes: { [string]: boolean }?, -- 가진 게임패스 Id -> true
	ServerLuck: boolean?, -- 서버 전체 행운 부스트 중인지
}

export type RebirthRequirement = {
	Coins: number,
	Landmarks: { string }, -- 이번 판에 보유해야 하는 명소 Id
}

-- 상품 지급 결과(grantProduct)
export type Grant = {
	Product: string, -- 상품 Id (Config.Products 의 Id)
	Coins: number, -- 더해진 코인(코인 팩)
	Seconds: number, -- 더해진 부스트 시간(초)
	ServerWide: boolean, -- true 면 서버가 서버 행운 타이머에 Seconds 를 더해야 함(Data 는 안 바뀜)
}

export type Data = {
	Rolls: number,
	Coins: number, -- 관광 수입이 초 단위로 쌓이므로 소수일 수 있음(표시할 때 버림)
	Inventory: { [string]: number }, -- 이번 판에 보유한 명소 Id -> 발견 횟수 (환생하면 비움)
	Discovered: { [string]: boolean }, -- 한 번이라도 발견한 명소 Id -> true (환생해도 유지. 도감·여권 기준)
	Featured: string?, -- 대표 명소(캐릭터 옆에 떠 다님)
	Upgrades: { [string]: number }, -- 업그레이드 Id -> 레벨
	Settings: Settings,
	Rebirths: number, -- 환생 횟수
	Boosts: { [string]: number }, -- 개인 시간 부스트 상품 Id -> 남은 초(접속 중에만 줄어듦)
	Receipts: { string }, -- 최근에 지급한 구매 영수증 PurchaseId (중복 지급 방지, 최근 MAX_RECEIPTS 개)
}

export type Snapshot = {
	Revision: number,
	Rolls: number,
	Coins: number,
	Inventory: { [string]: number },
	Discovered: { [string]: boolean },
	Featured: string?,
	Upgrades: { [string]: number },
	Settings: Settings,
	Rebirths: number,
	Boosts: { [string]: number }, -- 개인 부스트 남은 초
	Passes: { [string]: boolean }, -- 가진 게임패스
	ServerLuck: boolean, -- 서버 행운 부스트 중인지
	NextRebirth: RebirthRequirement, -- 다음 환생 조건
	Luck: number, -- mods 반영
	Cooldown: number, -- mods 반영
	Income: number, -- 초당 관광 수입(mods 반영)
}

export type Upgrade = typeof(Config.Upgrades[1])

local PlayerState = {}

PlayerState.UpgradesById = {} :: { [string]: Upgrade }
for _, upgrade in Config.Upgrades do
	PlayerState.UpgradesById[upgrade.Id] = upgrade
end

PlayerState.PassesById = {} :: { [string]: GamePass }
for _, pass in Config.GamePasses do
	PlayerState.PassesById[pass.Id] = pass
end

PlayerState.ProductsById = {} :: { [string]: Product }
for _, product in Config.Products do
	PlayerState.ProductsById[product.Id] = product
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
		Discovered = {},
		Featured = nil,
		Upgrades = upgrades,
		Settings = { AutoFeature = true },
		Rebirths = 0,
		Boosts = {},
		Receipts = {},
	}
end

local function nonNegativeInt(value: any): number?
	if type(value) == "number" and value == value and value >= 0 and value < math.huge then
		return math.floor(value)
	end
	return nil
end

-- 개인 시간 부스트 상품인지(Data.Boosts 에 남은 시간이 쌓이는 상품)
local function isPersonalBoost(product: Product): boolean
	return product.Seconds ~= nil and not product.ServerWide
end

local function trimReceipts(receipts: { string })
	while #receipts > Config.MAX_RECEIPTS do
		table.remove(receipts, 1)
	end
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
	data.Rebirths = nonNegativeInt(raw.Rebirths) or 0

	if type(raw.Inventory) == "table" then
		for id, count in raw.Inventory do
			local n = nonNegativeInt(count)
			if type(id) == "string" and n and n > 0 then
				data.Inventory[id] = n
			end
		end
	end

	if type(raw.Discovered) == "table" then
		for id, flag in raw.Discovered do
			if type(id) == "string" and flag == true then
				data.Discovered[id] = true
			end
		end
	end
	-- 보유한 명소는 항상 발견한 명소(Discovered 가 없던 예전 저장도 여기서 채워짐)
	for id in data.Inventory do
		data.Discovered[id] = true
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

	if type(raw.Boosts) == "table" then
		for _, product in Config.Products do
			local left = raw.Boosts[product.Id]
			if isPersonalBoost(product) and type(left) == "number" and left == left and left > 0 then
				data.Boosts[product.Id] = math.min(left, Config.MAX_BOOST_SECONDS)
			end
		end
	end

	if type(raw.Receipts) == "table" then
		for _, purchaseId in ipairs(raw.Receipts) do
			if type(purchaseId) == "string" then
				table.insert(data.Receipts, purchaseId)
			end
		end
		trimReceipts(data.Receipts)
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

-- 발견 기록 / 여권 도장 -------------------------------------------------------

-- 한 번이라도 발견한 명소인지(환생해도 유지). 도감의 발견/미발견과 여권은 이것 기준.
function PlayerState.isDiscovered(data: Data | Snapshot, landmarkId: string): boolean
	local discovered = data.Discovered
	if discovered and discovered[landmarkId] then
		return true
	end
	return (data.Inventory[landmarkId] or 0) > 0
end

-- 이 명소가 여권 도장 조건에 들어가는지 (전설급은 보너스 수집이라 제외)
function PlayerState.countsForStamp(landmark: Landmark): boolean
	return landmark.Tier.Rank <= Config.STAMP_MAX_RANK
end

-- 대륙의 도장 진행도: 발견한 수, 필요한 수 (도장 조건에 드는 명소만, 역대 발견 기록 기준)
function PlayerState.regionProgress(data: Data | Snapshot, regionId: string): (number, number)
	local found, required = 0, 0
	for _, landmark in Landmarks.ByRegion[regionId] or {} do
		if PlayerState.countsForStamp(landmark) then
			required += 1
			if PlayerState.isDiscovered(data, landmark.Id) then
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

-- 부스트 / 게임패스 -----------------------------------------------------------

local function rebirthsOf(data: Data | Snapshot): number
	return data.Rebirths or 0
end

-- mods 에 있는 게임패스 목록(Config.GamePasses 순서)
local function ownedPasses(mods: Mods?): { GamePass }
	local list = {}
	local passes = if mods then mods.Passes else nil
	if passes then
		for _, pass in Config.GamePasses do
			if passes[pass.Id] == true then
				table.insert(list, pass)
			end
		end
	end
	return list
end

-- 개인 부스트 남은 초(없으면 0)
function PlayerState.boostLeft(data: Data | Snapshot, productKey: string): number
	local boosts = data.Boosts
	return if boosts then boosts[productKey] or 0 else 0
end

-- 개인 시간 부스트(예: LuckBoost)의 남은 시간을 더함(MAX_BOOST_SECONDS 까지). 개인 부스트 상품이 아니면 false.
function PlayerState.addBoost(data: Data, productKey: any): boolean
	local product = if type(productKey) == "string" then PlayerState.ProductsById[productKey] else nil
	if not product or not isPersonalBoost(product) then
		return false
	end
	local left = data.Boosts[product.Id] or 0
	data.Boosts[product.Id] = math.min(Config.MAX_BOOST_SECONDS, left + (product.Seconds or 0))
	return true
end

-- 접속 중 dt 초만큼 부스트 시간을 줄임. 끝난 부스트가 있으면 true.
function PlayerState.tickBoosts(data: Data, dt: number): boolean
	if not (dt > 0) then
		return false
	end
	local expired = false
	for id, left in data.Boosts do
		local after = left - dt
		if after > 0 then
			data.Boosts[id] = after
		else
			data.Boosts[id] = nil
			expired = true
		end
	end
	return expired
end

-- 행운 / 속도 -----------------------------------------------------------------

-- 이번 굴림에 적용할 행운 = 기본 × 지구본 × 여권 도장 × 환생 × VIP × 행운 부스트 × 서버 행운
function PlayerState.luck(data: Data | Snapshot, mods: Mods?): number
	local globe = PlayerState.UpgradesById.Globe
	local globeMult = 1 + globe.PerLevel * PlayerState.upgradeLevel(data, "Globe")
	local regionMult = 1 + Config.REGION_LUCK_BONUS * #PlayerState.completedRegions(data)
	local rebirthMult = 1 + Config.REBIRTH_LUCK_BONUS * rebirthsOf(data)
	local luck = Config.BASE_LUCK * globeMult * regionMult * rebirthMult
	for _, pass in ownedPasses(mods) do
		luck *= pass.LuckMult or 1
	end
	local serverLuck = mods ~= nil and mods.ServerLuck == true
	for _, product in Config.Products do
		if product.ServerWide then
			if serverLuck then
				luck *= product.LuckMult or 1
			end
		elseif product.Seconds and PlayerState.boostLeft(data, product.Id) > 0 then
			luck *= product.LuckMult or 1
		end
	end
	return luck
end

function PlayerState.cooldown(data: Data | Snapshot, mods: Mods?): number
	local agency = PlayerState.UpgradesById.Agency
	local cooldown = Config.ROLL_COOLDOWN * (1 - agency.PerLevel * PlayerState.upgradeLevel(data, "Agency"))
	for _, pass in ownedPasses(mods) do
		cooldown *= pass.CooldownMult or 1
	end
	return cooldown
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

-- 공원에 전시되는 명소 Id 목록: 이번 판에 가진 것 중 희귀한 순서로 전시 칸 수만큼
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

-- 초당 관광 수입 = 전시 명소 합 × 입장료 × 환생 × 수입 2배 게임패스
function PlayerState.incomePerSecond(data: Data | Snapshot, mods: Mods?): number
	local total = 0
	for _, id in PlayerState.park(data) do
		total += PlayerState.landmarkIncome(Landmarks.ById[id], data.Inventory[id])
	end
	local ticket = PlayerState.UpgradesById.Ticket
	local income = total
		* (1 + ticket.PerLevel * PlayerState.upgradeLevel(data, "Ticket"))
		* (1 + Config.REBIRTH_INCOME_BONUS * rebirthsOf(data))
	for _, pass in ownedPasses(mods) do
		income *= pass.IncomeMult or 1
	end
	return income
end

-- dt 초 동안의 관광 수입을 더하고, 더한 양을 반환
function PlayerState.addIncome(data: Data, dt: number, mods: Mods?): number
	local amount = PlayerState.incomePerSecond(data, mods) * math.max(0, dt)
	data.Coins += amount
	return amount
end

-- 굴림 --------------------------------------------------------------------

function PlayerState.discoveryBonus(landmark: Landmark): number
	return math.ceil(Config.DISCOVERY_BONUS_MULT * landmark.OneIn ^ 0.5)
end

-- 굴림 결과 반영. 반환: 보너스 코인, 역대 처음 발견인지(보너스는 이때만), 별이 올랐는지
-- (환생 뒤 예전에 발견했던 명소를 다시 얻으면 처음 발견도 별 상승도 아님)
function PlayerState.applyRoll(data: Data, landmark: Landmark): (number, boolean, boolean)
	local before = data.Inventory[landmark.Id] or 0
	local after = before + 1
	local isNew = not PlayerState.isDiscovered(data, landmark.Id)
	data.Inventory[landmark.Id] = after
	data.Discovered[landmark.Id] = true
	data.Rolls += 1
	local bonus = if isNew then PlayerState.discoveryBonus(landmark) else 0
	data.Coins += bonus
	local starUp = before > 0 and PlayerState.stars(after) > PlayerState.stars(before)
	return bonus, isNew, starUp
end

-- 가장 희귀한 보유 명소(이번 판)
function PlayerState.best(data: Data | Snapshot): Landmark?
	for _, landmark in Landmarks.RarestFirst do
		if (data.Inventory[landmark.Id] or 0) > 0 then
			return landmark
		end
	end
	return nil
end

-- landmarkId 가 nil 이면 해제. 보유한 명소만 대표로 지정 가능.
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

-- 환생 --------------------------------------------------------------------

-- rebirths 번 환생한 플레이어의 다음 환생 조건(복사본)
function PlayerState.rebirthRequirement(rebirths: number): RebirthRequirement
	local steps = Config.REBIRTHS
	local n = math.max(0, math.floor(rebirths)) + 1
	local step = steps[math.min(n, #steps)]
	local coins = step.Coins
	if n > #steps then
		coins *= Config.REBIRTH_COIN_GROWTH ^ (n - #steps)
	end
	return { Coins = coins, Landmarks = table.clone(step.Landmarks) }
end

-- 반환: 환생 가능 여부, 이번 판에 없는 요구 명소 Id 목록, 모자란 코인(0 이상)
function PlayerState.canRebirth(data: Data | Snapshot): (boolean, { string }, number)
	local requirement = PlayerState.rebirthRequirement(rebirthsOf(data))
	local missing = {}
	for _, id in requirement.Landmarks do
		if (data.Inventory[id] or 0) <= 0 then
			table.insert(missing, id)
		end
	end
	local coinsShort = math.max(0, math.ceil(requirement.Coins - data.Coins))
	return #missing == 0 and coinsShort == 0, missing, coinsShort
end

-- 환생: 코인·업그레이드·보유 명소·대표 명소 초기화, 환생 수 +1.
-- 유지: 발견 기록(Discovered = 도감·여권 도장), 설정, 굴림 수, 부스트, 영수증.
-- 반환: 성공 여부, 실패 사유(표시용)
function PlayerState.rebirth(data: Data): (boolean, string?)
	local ok, missing = PlayerState.canRebirth(data)
	if not ok then
		if #missing > 0 then
			return false, "필요한 명소가 없습니다"
		end
		return false, "코인이 부족합니다"
	end
	for id in data.Inventory do
		data.Discovered[id] = true
	end
	table.clear(data.Inventory)
	data.Featured = nil
	data.Coins = 0
	for _, upgrade in Config.Upgrades do
		data.Upgrades[upgrade.Id] = 0
	end
	data.Rebirths = rebirthsOf(data) + 1
	return true, nil
end

-- 구매 영수증 / 상품 지급 --------------------------------------------------------

function PlayerState.hasReceipt(data: Data, purchaseId: any): boolean
	return table.find(data.Receipts, tostring(purchaseId)) ~= nil
end

-- 지급한 영수증을 기록(이미 있으면 그대로). 최근 MAX_RECEIPTS 개만 보관.
function PlayerState.addReceipt(data: Data, purchaseId: any)
	local key = tostring(purchaseId)
	if table.find(data.Receipts, key) then
		return
	end
	table.insert(data.Receipts, key)
	trimReceipts(data.Receipts)
end

-- 개발자 상품 효과를 data 에 적용. productKey 는 Config.Products 의 Id.
-- 개인 부스트는 남은 시간 추가, 코인 팩은 max(MinCoins, 초당 수입(mods 반영) × IncomeSeconds) 코인,
-- 서버 전체 부스트는 data 를 바꾸지 않고 Grant.ServerWide 로 알려 줌(서버가 서버 변수에 반영).
-- 영수증 기록(addReceipt)은 따로 해야 함.
function PlayerState.grantProduct(data: Data, productKey: any, mods: Mods?): (boolean, Grant?)
	local product = if type(productKey) == "string" then PlayerState.ProductsById[productKey] else nil
	if not product then
		return false, nil
	end
	if product.ServerWide then
		return true, { Product = product.Id, Coins = 0, Seconds = product.Seconds or 0, ServerWide = true }
	end
	if isPersonalBoost(product) then
		local before = PlayerState.boostLeft(data, product.Id)
		PlayerState.addBoost(data, product.Id)
		local added = PlayerState.boostLeft(data, product.Id) - before
		return true, { Product = product.Id, Coins = 0, Seconds = added, ServerWide = false }
	end
	if product.IncomeSeconds or product.MinCoins then
		local fromIncome = PlayerState.incomePerSecond(data, mods) * (product.IncomeSeconds or 0)
		local amount = math.floor(math.max(product.MinCoins or 0, fromIncome))
		data.Coins += amount
		return true, { Product = product.Id, Coins = amount, Seconds = 0, ServerWide = false }
	end
	return false, nil
end

-- 스냅샷 --------------------------------------------------------------------

function PlayerState.snapshot(data: Data, revision: number, mods: Mods?): Snapshot
	local passes = {}
	for _, pass in ownedPasses(mods) do
		passes[pass.Id] = true
	end
	return {
		Revision = revision,
		Rolls = data.Rolls,
		Coins = data.Coins,
		Inventory = table.clone(data.Inventory),
		Discovered = table.clone(data.Discovered),
		Featured = data.Featured,
		Upgrades = table.clone(data.Upgrades),
		Settings = table.clone(data.Settings),
		Rebirths = data.Rebirths,
		Boosts = table.clone(data.Boosts),
		Passes = passes,
		ServerLuck = mods ~= nil and mods.ServerLuck == true,
		NextRebirth = PlayerState.rebirthRequirement(data.Rebirths),
		Luck = PlayerState.luck(data, mods),
		Cooldown = PlayerState.cooldown(data, mods),
		Income = PlayerState.incomePerSecond(data, mods),
	}
end

return PlayerState
