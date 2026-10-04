-- 마을 상점과 대장간 (영석을 쓰는 곳). 상인·대장장이 곁에서만 사고, 공격 법구를 강화하고, 방어 법구를 만든다.
-- 방어 법구를 바꿔 지니는 일(equipGuard)은 어디서나 한다.
--
-- 맵(World.luau)이 만물상 판대와 대장간 모루에 MarketSpot 태그(속성 Shop = "market" | "smith")와 F 버튼을 달아 둔다.
-- 버튼은 클라이언트에서 창만 연다. 사고 강화하는 요청이 오면 여기서 그 자리 곁에 섰는지 다시 본다.
-- 가격과 데이터 처리는 Currency.luau, Guards.luau, Progression.buy/upgradeWeapon/craftGuard/equipGuard.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Progression = require(Shared.Progression)
local Currency = require(Shared.Currency)
local Combat = require(Shared.Combat)
local Guards = require(Shared.Guards)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Weapons = require(script.Parent.Weapons)
local Villagers = require(script.Parent.Villagers)

local Market = {}

Market.TAG = "MarketSpot"
Market.RADIUS = 16 -- 상점 자리에서 이 거리(수평, 스터드) 안에 서야 사고 강화한다
local COOLDOWN = 0.25
local MERCHANT = "merchant" -- 만물상 주인 (Npcs.luau)

local lastRequest: { [Player]: number } = {}

-- 그 종류(market, smith)의 상점 자리 곁에 섰는가
local function nearShop(player: Player, kind: string): boolean
	local root = Characters.root(player)
	if not root or not Characters.humanoid(player) then
		return false
	end
	for _, spot in CollectionService:GetTagged(Market.TAG) do
		if spot:IsA("BasePart") and spot:GetAttribute("Shop") == kind then
			local offset = root.Position - spot.Position
			if Vector3.new(offset.X, 0, offset.Z).Magnitude <= Market.RADIUS then
				return true
			end
		end
	end
	return false
end

-- 너무 잦은 요청은 버린다
local function ready(player: Player): boolean
	local now = os.clock()
	if now - (lastRequest[player] or -math.huge) < COOLDOWN then
		return false
	end
	lastRequest[player] = now
	return true
end

-- guardChanged: 지닌 방어 법구가 바뀌었거나 더 좋아졌다 (체력·걸음을 다시 맞춘다)
local function finish(player: Player, ok: boolean, message: string, weaponChanged: boolean, guardChanged: boolean?)
	Sync.notify(player, message, if ok then "good" else "bad")
	if not ok then
		return
	end
	if guardChanged then
		Characters.applyStats(player, false, true)
	end
	Sync.markDirty(player)
	Sync.state(player)
	if weaponChanged then
		-- 가방의 공격 법구 도구를 새것에 맞춘다 (들고 있던 칸은 그대로 든다)
		Weapons.give(player)
	end
end

-- 만물상에서 산다 (wareId: Currency.WARES 의 id)
function Market.buy(player: Player, wareId: any)
	if type(wareId) ~= "string" or #wareId > 40 then
		return
	end
	local data = PlayerData.get(player)
	if not data or not ready(player) then
		return
	end
	if not nearShop(player, "market") then
		Sync.notify(player, "만물상 곁에서만 살 수 있다.", "bad")
		return
	end
	local ware = Currency.wareById[wareId]
	local ok, message = Progression.buy(data, wareId)
	local guard = ware and ware.guard
	finish(player, ok, message, ware ~= nil and ware.weapon ~= nil, guard ~= nil and data.guard == guard.kind)
end

-- 대장간에서 index 칸 공격 법구를 한 등급 올린다
function Market.upgrade(player: Player, index: any)
	if type(index) ~= "number" or index ~= index or index % 1 ~= 0 then
		return
	end
	if index < 1 or index > Combat.MAX_WEAPONS then
		return
	end
	local data = PlayerData.get(player)
	if not data or not ready(player) then
		return
	end
	if not nearShop(player, "smith") then
		Sync.notify(player, "대장간 모루 곁에서만 공격 법구를 벼릴 수 있다.", "bad")
		return
	end
	local ok, message = Progression.upgradeWeapon(data, index)
	finish(player, ok, message, true)
end

-- 대장간에서 방어 법구를 만든다 (arg: { kind = Guards 종류 id, grade = 1~5 }). 처음 만든 것은 바로 지닌다
function Market.craft(player: Player, arg: any)
	if type(arg) ~= "table" then
		return
	end
	local kind, grade = arg.kind, arg.grade
	if type(kind) ~= "string" or not Guards.byId[kind] then
		return
	end
	if type(grade) ~= "number" or grade ~= grade or grade % 1 ~= 0 or grade < 1 or grade > #Guards.GRADES then
		return
	end
	local data = PlayerData.get(player)
	if not data or not ready(player) then
		return
	end
	if not nearShop(player, "smith") then
		Sync.notify(player, "대장간 모루 곁에서만 법구를 만들 수 있다.", "bad")
		return
	end
	local ok, message = Progression.craftGuard(data, kind, grade)
	-- 지닌 종류를 더 좋게 만들었거나, 처음 만들어 바로 지녔으면 몸에 맞춘다
	finish(player, ok, message, false, data.guard == kind)
end

-- 방어 법구를 바꿔 지닌다 (kind: 종류 id, "" 이면 내려놓는다). 어디서나 한다
function Market.equipGuard(player: Player, kind: any)
	if type(kind) ~= "string" or #kind > 40 then
		return
	end
	local data = PlayerData.get(player)
	if not data or not ready(player) then
		return
	end
	local session = Session.get(player)
	if session and session.tribulation then
		Sync.notify(player, "천겁을 맞는 중에는 법구를 바꿀 수 없다.", "bad")
		return
	end
	local ok, message = Progression.equipGuard(data, kind)
	Sync.notify(player, message, if ok then "info" else "bad")
	if not ok then
		return
	end
	Characters.applyStats(player, false, true)
	Sync.markDirty(player)
	Sync.state(player)
end

function Market.start()
	-- 만물상 버튼을 누르면 주인이 말을 건넨다 (창은 클라이언트가 연다. 사고파는 일과는 상관없다)
	local function hook(spot: Instance)
		if spot:GetAttribute("Shop") ~= "market" then
			return
		end
		for _, prompt in spot:GetDescendants() do
			if prompt:IsA("ProximityPrompt") then
				prompt.Triggered:Connect(function(player)
					Villagers.talk(player, MERCHANT)
				end)
			end
		end
	end
	for _, spot in CollectionService:GetTagged(Market.TAG) do
		hook(spot)
	end
	CollectionService:GetInstanceAddedSignal(Market.TAG):Connect(hook)
	Players.PlayerRemoving:Connect(function(player)
		lastRequest[player] = nil
	end)
end

return Market
