-- 로벅스 상품: 종족 다시 뽑기 (Races.REROLL_PRODUCT_ID, 49 로벅스)와 영석 묶음 (Currency.PACKS).
--
-- ProcessReceipt 는 같은 구매를 여러 번 보낼 수 있다. 구매 id 를 기록(data.receipts)에 남겨 두 번 주지 않고,
-- 기록을 저장소에 쓴 뒤에만 PurchaseGranted 를 돌려준다. 저장에 실패하거나 아직 기록을 못 불러왔으면
-- NotProcessedYet 을 돌려줘 Roblox 가 다음에 다시 보내게 한다.

local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Progression = require(Shared.Progression)
local Races = require(Shared.Races)
local Currency = require(Shared.Currency)
local Josa = require(Shared.Josa)
local PlayerData = require(script.Parent.PlayerData)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)

local Shop = {}

local rng = Random.new()

-- 처음 들어온 사람에게 종족을 뽑아 준다. 새로 뽑았으면 true
function Shop.assignRace(player: Player): boolean
	local data = PlayerData.get(player)
	if not data or data.race then
		return false
	end
	local race = Races.get(Progression.rollRace(data, rng:NextNumber()))
	Sync.notify(
		player,
		string.format(
			"%s 태어났다 (%.0f%%). %s 상태창(C)에서 다시 뽑을 수 있다.",
			Josa.ro(race.name),
			Races.chance(race.id),
			race.summary
		),
		"good"
	)
	Sync.markDirty(player)
	return true
end

local function reroll(player: Player, data)
	local before = Races.get(data.race)
	local after = Races.get(Progression.rollRace(data, rng:NextNumber(), true))
	Characters.applyStats(player, false)
	Sync.notify(
		player,
		string.format(
			"종족을 다시 뽑았다. %s에서 %s 바뀌었다. %s",
			before.name,
			Josa.ro(after.name),
			after.summary
		),
		"good"
	)
	if after.weight <= 4 then
		Sync.broadcast(
			string.format("%s님이 %s 다시 태어났다.", player.DisplayName, Josa.ro(after.name)),
			"world"
		)
	end
	Sync.markDirty(player)
end

-- 영석 묶음 (상품 id 가 0 인 묶음은 아직 팔지 않는다)
local function grantStones(player: Player, data, pack: Currency.Pack)
	Progression.addStones(data, pack.stones)
	Sync.notify(
		player,
		string.format(
			"영석 %s개를 받았다. (지닌 영석 %s)",
			Currency.format(pack.stones),
			Currency.format(data.stones)
		),
		"good"
	)
	Sync.markDirty(player)
end

function Shop.processReceipt(receipt): Enum.ProductPurchaseDecision
	local player = Players:GetPlayerByUserId(receipt.PlayerId)
	if not player then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local data = PlayerData.get(player)
	if not data or not PlayerData.canSave(player) then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local isReroll = Races.REROLL_PRODUCT_ID ~= 0 and receipt.ProductId == Races.REROLL_PRODUCT_ID
	local pack = if isReroll then nil else Currency.packByProduct(receipt.ProductId)
	if not isReroll and not pack then
		warn("[블록수선전] 모르는 상품:", receipt.ProductId)
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	-- 같은 구매가 다시 와도 한 번만 준다
	if Progression.claimReceipt(data, tostring(receipt.PurchaseId)) then
		if pack then
			grantStones(player, data, pack)
		else
			reroll(player, data)
		end
	end
	if PlayerData.save(player) then
		return Enum.ProductPurchaseDecision.PurchaseGranted
	end
	return Enum.ProductPurchaseDecision.NotProcessedYet
end

function Shop.start()
	MarketplaceService.ProcessReceipt = Shop.processReceipt
end

return Shop
