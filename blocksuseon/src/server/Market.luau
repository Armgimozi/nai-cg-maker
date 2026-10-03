-- 마을 상점과 대장간 (영석을 쓰는 곳). 상인·대장장이 곁에서만 사고 강화한다.
--
-- 맵(World.luau)이 만물상 판대와 대장간 모루에 MarketSpot 태그(속성 Shop = "market" | "smith")와 F 버튼을 달아 둔다.
-- 버튼은 클라이언트에서 창만 연다. 사고 강화하는 요청이 오면 여기서 그 자리 곁에 섰는지 다시 본다.
-- 가격과 데이터 처리는 Currency.luau, Progression.buy/upgradeWeapon.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Progression = require(Shared.Progression)
local Currency = require(Shared.Currency)
local Combat = require(Shared.Combat)
local PlayerData = require(script.Parent.PlayerData)
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

local function finish(player: Player, ok: boolean, message: string, weaponChanged: boolean)
	Sync.notify(player, message, if ok then "good" else "bad")
	if not ok then
		return
	end
	Sync.markDirty(player)
	Sync.state(player)
	if weaponChanged then
		-- 가방의 무기 도구를 새 무기에 맞춘다 (들고 있던 칸은 그대로 든다)
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
	finish(player, ok, message, ware ~= nil and ware.weapon ~= nil)
end

-- 대장간에서 index 칸 무기를 한 등급 올린다
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
		Sync.notify(player, "대장간 모루 곁에서만 무기를 벼릴 수 있다.", "bad")
		return
	end
	local ok, message = Progression.upgradeWeapon(data, index)
	finish(player, ok, message, true)
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
