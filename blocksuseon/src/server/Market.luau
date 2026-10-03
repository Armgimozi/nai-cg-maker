-- 마을 상점과 대장간 (영석을 쓰는 곳). 상인·대장장이 곁에서만 사고 강화한다.
-- (뼈대: 이 파일은 Market 담당이 채운다. 가격과 데이터 처리는 Currency.luau, Progression.buy/upgradeWeapon)

local Market = {}

function Market.buy(_player: Player, _wareId: any) end

function Market.upgrade(_player: Player, _index: any) end

function Market.start() end

return Market
