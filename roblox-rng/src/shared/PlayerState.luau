--!strict
-- 플레이어 데이터와 그 데이터를 바꾸는 규칙(순수 함수). 서버가 유일한 진실의 원천이고,
-- 클라이언트는 Snapshot 만 받아서 화면에 그립니다. Roblox 서비스에 의존하지 않아 테스트 가능.
-- 읽기 전용 함수(luck, permanentLuck, park, parkSlots, stars, incomePerSecond 등)는 Data 대신 Snapshot 을 넘겨도 됩니다.
-- luck / permanentLuck / autoDiscover / cooldown / incomePerSecond / addIncome / snapshot 은 선택 인자 mods(게임패스·서버 행운)를 받습니다.
-- mods 가 없으면 게임패스·서버 행운 없이 계산합니다. Snapshot 은 Passes/ServerLuck 필드가 있어서
-- PlayerState.luck(snapshot, snapshot) 처럼 mods 자리에 그대로 넘겨도 됩니다.

local Config = require(script.Parent.Config)
local Landmarks = require(script.Parent.Landmarks)

type Landmark = Landmarks.Landmark
type GamePass = Config.GamePass
type Product = Config.Product

export type Settings = {
	AutoFeature: boolean, -- 더 희귀한 명소를 발견하면 자동으로 대표 명소로 지정
	AutoPark: boolean, -- true: 공원 전시를 희귀한 순서로 자동 배치 / false: 플레이어가 고른 배치(Data.Display)
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
	-- 직접 고른 공원 배치(AutoPark = false 일 때만 씀): 전시 칸 번호 -> 명소 Id, 빈 칸은 "".
	-- 구멍 없는 배열(DataStore 안전), 길이 ≤ PARK_GRID². 보유하지 않거나 겹치는 Id 는 전시할 때 건너뜀
	Display: { string },
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
	Display: { string }, -- 직접 고른 공원 배치(복사본). 전시 칸은 PlayerState.parkSlots(snapshot) 로 계산
	Rebirths: number,
	Boosts: { [string]: number }, -- 개인 부스트 남은 초
	Passes: { [string]: boolean }, -- 가진 게임패스
	ServerLuck: boolean, -- 서버 행운 부스트 중인지
	NextRebirth: RebirthRequirement?, -- 다음 환생 조건(최대까지 했으면 nil)
	Luck: number, -- mods 반영
	-- 영구 행운 = Luck 에서 시간 부스트·서버 행운을 뺀 값(PlayerState.permanentLuck). 확률(OneIn)이 이 값 이하인
	-- 명소는 자동 발견(Discovered 에 이미 들어 있음)이고 부스트 없이는 굴림에서 다시 안 나옴
	PermanentLuck: number,
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

-- 공원 전시 칸 최대 수(격자 칸 수) = Data.Display 최대 길이
PlayerState.MAX_SLOTS = Config.PARK_GRID * Config.PARK_GRID
-- 별 최대 개수(★5). 처음 발견 = 별 0, 같은 명소를 또 뽑을 때마다 +1
PlayerState.MAX_STARS = #Config.STAR_THRESHOLDS

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
		Settings = { AutoFeature = true, AutoPark = true },
		Display = {},
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

-- 배치 끝의 빈 칸("")은 저장할 필요가 없으므로 잘라 냄
local function trimDisplay(display: { string })
	while #display > 0 and display[#display] == "" do
		table.remove(display)
	end
end

-- 저장된 배치(형식 보장 없음) -> 구멍 없는 문자열 배열. 문자열이 아니거나 앞 칸과 겹치는 Id 는 빈 칸("").
-- 모르는 명소 Id 는 보존(보유 명소처럼 명소를 잠시 뺐다가 다시 넣어도 안전, 전시할 때만 건너뜀)
local function cleanDisplay(raw: any): { string }
	local display = {}
	if type(raw) ~= "table" then
		return display
	end
	local seen = {}
	for slot = 1, PlayerState.MAX_SLOTS do
		local id = raw[slot]
		if type(id) == "string" and id ~= "" and not seen[id] then
			seen[id] = true
			display[slot] = id
		else
			display[slot] = ""
		end
	end
	trimDisplay(display)
	return display
end

-- display[slot] = id. 사이에 빈 자리가 생기면 ""로 채워서 구멍 없는 배열을 유지
local function setEntry(display: { string }, slot: number, id: string)
	for i = #display + 1, slot - 1 do
		display[i] = ""
	end
	display[slot] = id
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

	if type(raw.Settings) == "table" then
		if type(raw.Settings.AutoFeature) == "boolean" then
			data.Settings.AutoFeature = raw.Settings.AutoFeature
		end
		-- 예전 저장에는 없음 -> 기본값(자동 배치) = 예전과 같은 공원
		if type(raw.Settings.AutoPark) == "boolean" then
			data.Settings.AutoPark = raw.Settings.AutoPark
		end
	end
	data.Display = cleanDisplay(raw.Display)

	if type(raw.Boosts) == "table" then
		for _, product in Config.Products do
			local left = raw.Boosts[product.Id]
			if isPersonalBoost(product) and type(left) == "number" and left == left and left > 0 then
				data.Boosts[product.Id] = math.min(left, Config.MAX_BOOST_STORED_SECONDS)
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

-- 직접 배치 중 공원 확장으로 새로 열린 칸 채우기 (아래 "관광 공원" 에서 정의)
local fillSlots: (data: Data, from: number, to: number) -> ()

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
	local slotsBefore = PlayerState.slots(data)
	data.Coins -= price
	data.Upgrades[upgrade.Id] = level + 1
	if upgrade.Id == "Park" then
		fillSlots(data, slotsBefore + 1, PlayerState.slots(data))
	end
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

-- 환생 rebirths 번의 행운 배율 = REBIRTH_LUCK_MULT ^ 환생 수 (1, 2, 4, … 10번 = 1,024). MAX_REBIRTHS 에서 멈춤
function PlayerState.rebirthLuckMult(rebirths: number): number
	local n = math.clamp(math.floor(rebirths), 0, Config.MAX_REBIRTHS)
	return Config.REBIRTH_LUCK_MULT ^ n
end

-- 환생 rebirths 번의 관광 수입 배율 = 1 + REBIRTH_INCOME_BONUS × 환생 수 (MAX_REBIRTHS 에서 멈춤)
function PlayerState.rebirthIncomeMult(rebirths: number): number
	local n = math.clamp(math.floor(rebirths), 0, Config.MAX_REBIRTHS)
	return 1 + Config.REBIRTH_INCOME_BONUS * n
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

-- 남은 시간 left 에 seconds 를 더한 값. 이미 결제된 시간이라 구매 창 상한(MAX_BOOST_SECONDS)으로 자르지 않고,
-- 데이터 손상 방지용 상한(MAX_BOOST_STORED_SECONDS)까지만 막음. 개인 부스트와 서버 행운이 같이 씀
function PlayerState.stackSeconds(left: number, seconds: number): number
	return math.min(Config.MAX_BOOST_STORED_SECONDS, math.max(0, left) + math.max(0, seconds))
end

-- 개인 시간 부스트(예: LuckBoost)의 남은 시간을 더함(stackSeconds). 개인 부스트 상품이 아니면 false.
function PlayerState.addBoost(data: Data, productKey: any): boolean
	local product = if type(productKey) == "string" then PlayerState.ProductsById[productKey] else nil
	if not product or not isPersonalBoost(product) then
		return false
	end
	local left = data.Boosts[product.Id] or 0
	data.Boosts[product.Id] = PlayerState.stackSeconds(left, product.Seconds or 0)
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

-- 영구 행운 = 기본 × 지구본 × 여권 도장 × 환생(2^환생 수) × 행운 VIP (시간 부스트·서버 행운 제외).
-- 자동 발견(autoDiscover) 기준. 지구본은 환생하면 0 레벨로 돌아가므로 "영구"는 부스트가 아니라는 뜻
function PlayerState.permanentLuck(data: Data | Snapshot, mods: Mods?): number
	local globe = PlayerState.UpgradesById.Globe
	local globeMult = 1 + globe.PerLevel * PlayerState.upgradeLevel(data, "Globe")
	local regionMult = 1 + Config.REGION_LUCK_BONUS * #PlayerState.completedRegions(data)
	local luck = Config.BASE_LUCK * globeMult * regionMult * PlayerState.rebirthLuckMult(rebirthsOf(data))
	for _, pass in ownedPasses(mods) do
		luck *= pass.LuckMult or 1
	end
	return luck
end

-- 이번 굴림에 적용할 행운 = 영구 행운 × 행운 부스트 × 서버 행운
function PlayerState.luck(data: Data | Snapshot, mods: Mods?): number
	local luck = PlayerState.permanentLuck(data, mods)
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

-- 자동 발견: 굴림은 희귀한 것부터 "행운 / N" 판정이라 행운 ≥ N 이면 그보다 흔한 명소는 다시는 안 나옴(RollLogic).
-- 그래서 아직 발견하지 않은 명소 중 확률(OneIn)이 영구 행운(permanentLuck) 이하인 것은 발견한 것으로 칩니다
-- (도감·여권 도장 기준인 Discovered 에 기록 — 행운이 나중에 내려가도 유지). 보유(Inventory)·공원 수입·
-- 환생 조건·발견 보너스 코인은 그대로. 새로 채운 도장이 행운을 올리면 한 번 더 확인합니다.
-- 서버가 상태를 보내기 전(접속·굴림·업그레이드·환생·게임패스)에 부름.
-- 반환: 이번에 새로 발견 처리한 명소 Id 목록(흔한 것 → 희귀한 것)
function PlayerState.autoDiscover(data: Data, mods: Mods?): { string }
	local added = {}
	while true do
		local luck = PlayerState.permanentLuck(data, mods)
		local changed = false
		for _, landmark in Landmarks.List do
			if landmark.OneIn > luck then
				break -- List 는 흔한 것 → 희귀한 것
			end
			if not PlayerState.isDiscovered(data, landmark.Id) then
				data.Discovered[landmark.Id] = true
				table.insert(added, landmark.Id)
				changed = true
			end
		end
		if not changed then
			return added
		end
	end
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

-- 이번 판 발견 횟수(보유 수) -> 별 개수(0~MAX_STARS). 가챠 중복처럼 처음 발견 = 별 0, 또 뽑을 때마다 +1
-- (STAR_THRESHOLDS = { 2, 3, 4, 5, 6 }: 2번째 ★1 … 6번째 ★5). 보유하지 않았어도(0) 별 0 이므로 보유 여부는
-- 개수(count > 0)로 판단. 별은 개수로 계산하고 따로 저장하지 않음
function PlayerState.stars(count: number): number
	local stars = 0
	for i, threshold in Config.STAR_THRESHOLDS do
		if count >= threshold then
			stars = i
		end
	end
	return stars
end

-- 전시 칸 번호 -> 격자 자리. 칸 번호는 입구 쪽 줄부터, 한 줄 안에서는 가운데에 가까운 칸부터
-- (입구에서 공원 안쪽을 볼 때 가운데 오른쪽 → 가운데 왼쪽 → 그 바깥 오른쪽 → …)라서 자동 배치에서는
-- 가장 희귀한 명소가 입구 정면에 옴. 월드 받침대(ParkService)와 공원 배치 창(Panels)이 같은 표를 씀.
local SLOT_CELLS: { { number } } = {}
do
	local grid = Config.PARK_GRID
	local middle = (grid + 1) / 2
	-- 부지 좌표 열 c(1..grid, x = (c - middle) 칸). 가운데에 가까운 열부터, 같으면 x 가 작은 열부터
	local columns = {}
	for c = 1, grid do
		table.insert(columns, c)
	end
	table.sort(columns, function(a: number, b: number): boolean
		local da, db = math.abs(a - middle), math.abs(b - middle)
		if da ~= db then
			return da < db
		end
		return a < b
	end)
	for row = 1, grid do
		for _, c in columns do
			-- 입구에서 공원 안쪽(부지 +Z)을 보면 오른쪽이 -X 라서, 보이는 대로의 열 번호는 좌우가 뒤집힘
			table.insert(SLOT_CELLS, { row, grid + 1 - c })
		end
	end
end

-- 반환: row(1 = 입구 쪽 줄 … PARK_GRID = 맨 안쪽 줄), column(1 = 입구에서 공원 안쪽을 볼 때 왼쪽 끝)
function PlayerState.slotCell(slot: number): (number, number)
	local cell = SLOT_CELLS[slot]
	return cell[1], cell[2]
end

-- 열린 전시 칸 수(격자 칸 수까지)
local function unlockedSlots(data: Data | Snapshot): number
	return math.clamp(PlayerState.slots(data), 0, PlayerState.MAX_SLOTS)
end

local function autoParkOn(data: Data | Snapshot): boolean
	return data.Settings.AutoPark ~= false -- 설정이 없던 예전 데이터/스냅샷은 자동 배치
end

-- 전시 칸마다 전시되는 명소. 반환: 칸 번호 -> 명소 Id(빈 칸은 nil), 열린 칸 수.
-- 자동 배치: 이번 판에 가진 명소를 희귀한 순서로 1번 칸부터.
-- 직접 배치: Display 에서 열린 칸만, 보유한 명소만, 같은 명소는 앞 칸 하나만.
function PlayerState.parkSlots(data: Data | Snapshot): ({ [number]: string }, number)
	local unlocked = unlockedSlots(data)
	local result: { [number]: string } = {}
	if autoParkOn(data) then
		local slot = 0
		for _, landmark in Landmarks.RarestFirst do
			if slot >= unlocked then
				break
			end
			if (data.Inventory[landmark.Id] or 0) > 0 then
				slot += 1
				result[slot] = landmark.Id
			end
		end
	else
		local display = data.Display or {}
		local seen = {}
		for slot = 1, unlocked do
			local id = display[slot]
			if type(id) == "string" and not seen[id] and Landmarks.ById[id] and (data.Inventory[id] or 0) > 0 then
				seen[id] = true
				result[slot] = id
			end
		end
	end
	return result, unlocked
end

-- 공원에 전시되는 명소 Id 목록(칸 번호 순서). 자동 배치면 희귀한 순서로 전시 칸 수만큼
function PlayerState.park(data: Data | Snapshot): { string }
	local slots, unlocked = PlayerState.parkSlots(data)
	local result = {}
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			table.insert(result, id)
		end
	end
	return result
end

-- 지금 보이는 전시 그대로 Display 에 옮겨 적음: 자동 배치를 끌 때 시작 배치,
-- 직접 배치 편집 전 정리(보유하지 않거나 겹치거나 잠긴 칸의 Id 는 빠짐)
local function freezeDisplay(data: Data)
	local slots, unlocked = PlayerState.parkSlots(data)
	local display = {}
	for slot = 1, unlocked do
		display[slot] = slots[slot] or ""
	end
	trimDisplay(display)
	data.Display = display
end

-- 칸 하나에 명소를 놓거나(landmarkId) 비움(nil). 이미 다른 칸에 있는 명소면 그 칸과 자리를 바꿈
-- (그 칸에는 이 칸에 있던 명소가 가거나 빈 칸이 됨). 자동 배치 중이면 지금 자동 배치에서 시작하고 자동 배치를 끔.
-- slot: 1..열린 칸 수 정수, landmarkId: 보유한 명소 Id 또는 nil.
-- expected(선택): 요청한 쪽이 본 그 칸의 명소 Id(빈 칸은 ""). 지금 그 칸에 보이는 것과 다르면 아무것도 바꾸지 않고
--   "stale" — 클라이언트 화면이 늦은 사이(예: 자동 굴림이 빈 칸에 새 명소를 놓음) 그 명소를 모르고 덮어쓰지 않게.
--   nil 이면 확인하지 않음(서버 내부 · 옛 클라이언트).
-- 반환: 성공 여부, 실패 사유(표시용 문장, 또는 "stale")
function PlayerState.setDisplay(
	data: Data,
	slot: any,
	landmarkId: any,
	expected: any?,
	expectedFrom: any?
): (boolean, string?)
	if type(slot) ~= "number" or slot ~= slot or slot % 1 ~= 0 or slot < 1 or slot > PlayerState.MAX_SLOTS then
		return false, "잘못된 칸입니다"
	end
	if slot > unlockedSlots(data) then
		return false, "잠긴 칸입니다"
	end
	if landmarkId ~= nil then
		local known = type(landmarkId) == "string" and Landmarks.ById[landmarkId] ~= nil
		if not known or (data.Inventory[landmarkId] or 0) <= 0 then
			return false, "보유하지 않은 명소입니다"
		end
	end
	if expected ~= nil or (landmarkId ~= nil and expectedFrom ~= nil) then
		local shown, unlocked = PlayerState.parkSlots(data)
		if expected ~= nil and (type(expected) ~= "string" or (shown[slot] or "") ~= expected) then
			return false, "stale"
		end
		-- 옮기는 명소가 클라이언트가 본 칸(0 = 전시 안 됨)에 그대로 있는지. 자동 배치에서 새로 뽑은 명소가
		-- 옮기던 명소를 밀어냈는데 그대로 옮기면, 자리 바꿀 상대가 옮겨지지 않고 빠져 버림
		if landmarkId ~= nil and expectedFrom ~= nil then
			local current = 0
			for s = 1, unlocked do
				if shown[s] == landmarkId then
					current = s
					break
				end
			end
			if type(expectedFrom) ~= "number" or expectedFrom ~= current then
				return false, "stale"
			end
		end
	end
	freezeDisplay(data)
	data.Settings.AutoPark = false
	local display = data.Display
	local id: string = landmarkId or ""
	if id ~= "" then
		local from = table.find(display, id)
		if from and from ~= slot then
			display[from] = display[slot] or ""
		end
	end
	setEntry(display, slot, id)
	trimDisplay(display)
	return true, nil
end

-- 자동 배치 켜기/끄기. 켜면 희귀한 순서로 다시 채움(직접 배치는 지움),
-- 끄면 지금 자동 배치 그대로에서 시작(화면은 안 바뀜)
function PlayerState.setAutoPark(data: Data, on: boolean)
	if on then
		data.Settings.AutoPark = true
		table.clear(data.Display)
	elseif autoParkOn(data) then
		freezeDisplay(data)
		data.Settings.AutoPark = false
	end
end

-- 자동 배치로 되돌림(가장 희귀한 명소들로 다시 채움)
function PlayerState.autoPark(data: Data)
	PlayerState.setAutoPark(data, true)
end

-- 직접 배치 중 이번 판에 처음 얻은 명소: 첫 빈 칸(칸 번호 순서)에 전시. 빈 칸이 없으면 전시 안 함
local function placeNew(data: Data, id: string)
	if autoParkOn(data) then
		return
	end
	local slots, unlocked = PlayerState.parkSlots(data)
	local empty: number? = nil
	for slot = 1, unlocked do
		local shown = slots[slot]
		if shown == id then
			return -- 이미 전시 중
		elseif not shown and not empty then
			empty = slot
		end
	end
	if empty then
		setEntry(data.Display, empty, id)
	end
end

-- 직접 배치 중 새로 열린 칸(from..to 중 빈 칸)을 아직 전시하지 않은 보유 명소로 희귀한 순서대로 채움
function fillSlots(data: Data, from: number, to: number)
	if autoParkOn(data) then
		return
	end
	local slots, unlocked = PlayerState.parkSlots(data)
	local shown = {}
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			shown[id] = true
		end
	end
	local rarest = Landmarks.RarestFirst
	local index = 1
	for slot = math.max(1, from), math.min(to, unlocked) do
		if not slots[slot] then
			while index <= #rarest do
				local landmark = rarest[index]
				index += 1
				if not shown[landmark.Id] and (data.Inventory[landmark.Id] or 0) > 0 then
					shown[landmark.Id] = true
					setEntry(data.Display, slot, landmark.Id)
					break
				end
			end
		end
	end
end

-- 명소 1개의 초당 수입 (입장료 업그레이드 제외) = 등급 수입 × (1 + 별 보너스 × 별 수). 보유하지 않으면 0
function PlayerState.landmarkIncome(landmark: Landmark, count: number): number
	if not (count > 0) then
		return 0
	end
	local base = Config.TIER_INCOME[landmark.Tier.Rank] or 0
	return base * (1 + Config.STAR_INCOME_BONUS * PlayerState.stars(count))
end

-- 직접 배치 중 "전시하면 수입이 느는데 전시 안 된" 보유 명소 Id 목록(희귀한 순서): 전시 칸에 있는 명소 중
-- 가장 수입이 적은 것보다 수입이 큰 것. 전시된 명소가 하나도 없으면 수입이 있는 보유 명소 전부.
-- 자동 배치면 빈 목록(자동 배치가 알아서 채움). 배치 버튼 숫자 배지 · "공원 꽉 참" 알림 기준
function PlayerState.betterHidden(data: Data | Snapshot): { string }
	local result = {}
	if autoParkOn(data) then
		return result
	end
	local slots, unlocked = PlayerState.parkSlots(data)
	if unlocked <= 0 then
		return result
	end
	local shown: { [string]: boolean } = {}
	local weakest: number? = nil
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			shown[id] = true
			local income = PlayerState.landmarkIncome(Landmarks.ById[id], data.Inventory[id] or 0)
			weakest = if weakest then math.min(weakest, income) else income
		end
	end
	local floor = weakest or 0
	for _, landmark in Landmarks.RarestFirst do
		local count = data.Inventory[landmark.Id] or 0
		if count > 0 and not shown[landmark.Id] and PlayerState.landmarkIncome(landmark, count) > floor then
			table.insert(result, landmark.Id)
		end
	end
	return result
end

-- 직접 배치 중 이번 판에 처음 얻은 명소(보유 1개)가 공원이 꽉 차서(빈 열린 칸이 없어서) 전시되지 못했는지.
-- 굴림 연출이 끝난 뒤 "공원 꽉 참" 알림 기준(자동 배치면 늘 false — 자동 배치가 알아서 채움)
function PlayerState.missedByFullPark(data: Data | Snapshot, landmarkId: string): boolean
	if autoParkOn(data) or (data.Inventory[landmarkId] or 0) ~= 1 then
		return false
	end
	local slots, unlocked = PlayerState.parkSlots(data)
	for slot = 1, unlocked do
		local id = slots[slot]
		if id == landmarkId or id == nil then
			return false -- 전시 중이거나, 빈 칸이 있음(꽉 차서 못 놓인 게 아님)
		end
	end
	return true
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
		* PlayerState.rebirthIncomeMult(rebirthsOf(data))
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
-- (이번 판에 이미 보유한 명소를 또 뽑으면 별 +1(★5 까지). 환생 뒤 예전에 발견했던 명소를 다시 얻으면
-- 처음 발견도 별 상승도 아님 — 별 0 부터 다시)
-- 직접 배치 중 이번 판에 처음 얻은 명소는 첫 빈 전시 칸에 놓임(빈 칸이 없으면 안 놓임)
function PlayerState.applyRoll(data: Data, landmark: Landmark): (number, boolean, boolean)
	local before = data.Inventory[landmark.Id] or 0
	local after = before + 1
	local isNew = not PlayerState.isDiscovered(data, landmark.Id)
	data.Inventory[landmark.Id] = after
	data.Discovered[landmark.Id] = true
	data.Rolls += 1
	if before == 0 then
		placeNew(data, landmark.Id)
	end
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
	elseif key == "AutoPark" and type(value) == "boolean" then
		PlayerState.setAutoPark(data, value)
		return true
	end
	return false
end

-- 환생 --------------------------------------------------------------------

-- rebirths 번 환생한 플레이어의 다음 환생 조건(복사본). 최대(Config.MAX_REBIRTHS)까지 했으면 nil
function PlayerState.rebirthRequirement(rebirths: number): RebirthRequirement?
	local n = math.max(0, math.floor(rebirths)) + 1
	local step = if n <= Config.MAX_REBIRTHS then Config.REBIRTHS[n] else nil
	if not step then
		return nil
	end
	return { Coins = step.Coins, Landmarks = table.clone(step.Landmarks) }
end

-- 환생을 최대까지 했는지
function PlayerState.rebirthMaxed(data: Data | Snapshot): boolean
	return rebirthsOf(data) >= Config.MAX_REBIRTHS
end

-- 반환: 환생 가능 여부, 이번 판에 없는 요구 명소 Id 목록, 모자란 코인(0 이상). 최대까지 했으면 false, {}, 0
function PlayerState.canRebirth(data: Data | Snapshot): (boolean, { string }, number)
	local requirement = PlayerState.rebirthRequirement(rebirthsOf(data))
	if not requirement then
		return false, {}, 0
	end
	local missing = {}
	for _, id in requirement.Landmarks do
		if (data.Inventory[id] or 0) <= 0 then
			table.insert(missing, id)
		end
	end
	local coinsShort = math.max(0, math.ceil(requirement.Coins - data.Coins))
	return #missing == 0 and coinsShort == 0, missing, coinsShort
end

-- 환생: 코인·업그레이드·보유 명소·대표 명소·직접 배치(Display) 초기화, 환생 수 +1.
-- 공원은 자동 배치로 되돌림(AutoPark = true): 빈 공원에서 직접 배치로 다시 시작하면 새로 얻는 명소가
-- 첫 빈 칸부터 차고 공원이 꽉 찬 뒤에는 더 좋은 명소를 얻어도 전시가 안 되기 때문.
-- 유지: 발견 기록(Discovered = 도감·여권 도장), 그 밖의 설정(AutoFeature), 굴림 수, 부스트, 영수증.
-- 반환: 성공 여부, 실패 사유(표시용)
function PlayerState.rebirth(data: Data): (boolean, string?)
	if PlayerState.rebirthMaxed(data) then
		return false, "최대 환생입니다"
	end
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
	table.clear(data.Display)
	data.Settings.AutoPark = true
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

-- 지급한 영수증을 기록(이미 있으면 그대로). 최근 MAX_RECEIPTS 개만 보관(오래된 것부터 지움).
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
		Display = table.clone(data.Display),
		Rebirths = data.Rebirths,
		Boosts = table.clone(data.Boosts),
		Passes = passes,
		ServerLuck = mods ~= nil and mods.ServerLuck == true,
		NextRebirth = PlayerState.rebirthRequirement(data.Rebirths),
		Luck = PlayerState.luck(data, mods),
		PermanentLuck = PlayerState.permanentLuck(data, mods),
		Cooldown = PlayerState.cooldown(data, mods),
		Income = PlayerState.incomePerSecond(data, mods),
	}
end

return PlayerState
