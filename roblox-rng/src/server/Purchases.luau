-- 유료 상품(Robux) 서버 규칙: 개발자 상품 영수증(ProcessReceipt) 판정·지급, 게임패스 소유 확인, 구매 창 조건.
-- 세션 표·저장·이벤트 같은 서버 일은 init.server 가 deps 로 넘김 → 테스트(tests/run.luau)가 가짜 deps 로 그대로 돌림.
--
-- 영수증 규칙:
--   · 지급 + 저장 성공 뒤에만 PurchaseGranted. 저장이 실패하면 NotProcessedYet → Roblox 가 나중에 다시 부름
--   · 같은 PurchaseId 는 Data.Receipts 로 한 번만 지급(다시 불리면 저장만 다시 시도)
--   · 접속 직후 데이터를 불러오는 중이면 세션이 생길 때까지 기다림. 여기서 바로 NotProcessedYet 을 돌려주면
--     접속 때 다시 온 영수증이 다음 구매나 다음 접속 때까지 지급되지 않음
--   · 코인 팩(초당 수입 기준)은 접속 시 게임패스(수입 2배) 확인이 끝날 때까지 잠깐 기다린 뒤 지급

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local PlayerState = require(Shared.PlayerState)

local Purchases = {}

-- 데이터를 불러오는 동안 영수증이 기다리는 최대 초 (DataService.load 는 세션 잠금 대기까지 약 25~30초)
Purchases.SESSION_WAIT = 60
-- 코인 팩이 접속 시 게임패스 확인(다시 확인 포함)을 기다리는 최대 초
Purchases.PASS_WAIT = 15
Purchases.POLL = 0.25
-- 게임패스 확인이 오류 나면 이만큼(초) 기다렸다가 오류 난 패스만 다시 확인. 모두 실패하면 이번 접속은 포기
Purchases.PASS_RETRY = { 1, 2, 4 }

export type Session = {
	Data: PlayerState.Data,
	LockId: string?, -- nil 이면 저장하지 않음(Studio)
	Passes: { [string]: boolean },
}

export type Deps = {
	findPlayer: (userId: number) -> Player?, -- Players:GetPlayerByUserId
	session: (player: Player) -> Session?, -- 데이터를 다 불러온 세션(아직이면 nil)
	inGame: (player: Player) -> boolean, -- 아직 이 서버에 있는지(나가거나 Kick 되면 false)
	passesReady: (player: Player) -> boolean, -- 접속 시 게임패스 확인(다시 확인 포함)이 끝났는지
	mods: (session: Session) -> PlayerState.Mods,
	save: (player: Player, session: Session) -> boolean, -- 저장(잠금 유지). 성공하면 true
	serverLuck: (player: Player, seconds: number) -> (), -- 서버 행운 타이머에 더하고 모두에게 알림
	pushState: (player: Player) -> (),
	-- 영수증을 처음 지급했을 때(분석: 구매 퍼널·코인 팩 경제 이벤트). 없어도 됨, 오류가 나도 지급·저장은 그대로
	granted: ((player: Player, session: Session, grant: PlayerState.Grant) -> ())?,
	ownsPass: (player: Player, passId: number) -> boolean, -- UserOwnsGamePassAsync (오류는 그대로 던짐)
	passesChanged: (player: Player) -> (), -- 가진 게임패스가 늘었음(상태 + 공원 간판 갱신)
	wait: (seconds: number) -> (),
	clock: () -> number,
}

function Purchases.productByProductId(productId: any): Config.Product?
	local id = tonumber(productId)
	if not id then
		return nil
	end
	for _, product in Config.Products do
		if product.ProductId > 0 and product.ProductId == id then
			return product
		end
	end
	return nil
end

function Purchases.passByPassId(passId: any): Config.GamePass?
	local id = tonumber(passId)
	if not id then
		return nil
	end
	for _, pass in Config.GamePasses do
		if pass.PassId > 0 and pass.PassId == id then
			return pass
		end
	end
	return nil
end

-- ready() 가 true 가 될 때까지 기다림. 플레이어가 나가거나 seconds 초가 지나면 그만. 반환: ready() 결과
local function waitFor(deps: Deps, player: Player, seconds: number, ready: () -> boolean): boolean
	local deadline = deps.clock() + seconds
	while not ready() do
		if not deps.inGame(player) or deps.clock() >= deadline then
			return false
		end
		deps.wait(Purchases.POLL)
	end
	return true
end

-- MarketplaceService.ProcessReceipt 본체(오류는 부르는 쪽 pcall 이 NotProcessedYet 으로 바꿈)
function Purchases.processReceipt(receiptInfo: { [string]: any }, deps: Deps): Enum.ProductPurchaseDecision
	local notYet = Enum.ProductPurchaseDecision.NotProcessedYet
	local player = deps.findPlayer(receiptInfo.PlayerId)
	if not player then
		return notYet -- 이 서버에 없음: 다음 접속 때 다시 옴
	end
	local purchaseId = tostring(receiptInfo.PurchaseId)
	local product = Purchases.productByProductId(receiptInfo.ProductId)

	-- 데이터를 불러오는 중: 세션이 생길 때까지 기다림(불러오기 실패 = Kick, 도중에 나감 → 바로 그만)
	local loaded = waitFor(deps, player, Purchases.SESSION_WAIT, function()
		return deps.session(player) ~= nil
	end)
	if not loaded then
		return notYet
	end
	-- 코인 팩은 초당 수입(수입 2배 게임패스 포함)으로 정하므로 접속 시 게임패스 확인을 잠깐 기다림.
	-- 확인이 끝나지 않아도 PASS_WAIT 가 지나면 지금 아는 대로 지급(무한정 미루지 않음)
	if product and product.IncomeSeconds then
		local session = deps.session(player)
		if session and not PlayerState.hasReceipt(session.Data, purchaseId) then
			waitFor(deps, player, Purchases.PASS_WAIT, function()
				return deps.passesReady(player)
			end)
		end
	end

	-- 기다리는 동안 나갔을 수 있으니 세션을 다시 읽음. 여기서 지급·영수증 기록까지는 멈추지 않음(같은 영수증이
	-- 동시에 불려도 한쪽만 지급)
	local session = deps.session(player)
	if not session then
		return notYet
	end
	if not PlayerState.hasReceipt(session.Data, purchaseId) then
		if not product then
			warn("[LandmarkRNG] 모르는 개발자 상품: " .. tostring(receiptInfo.ProductId))
			return notYet
		end
		local ok, grant = PlayerState.grantProduct(session.Data, product.Id, deps.mods(session))
		if not ok or not grant then
			return notYet
		end
		PlayerState.addReceipt(session.Data, purchaseId)
		if grant.ServerWide then
			deps.serverLuck(player, grant.Seconds)
		else
			deps.pushState(player)
		end
		local granted = deps.granted
		if granted then
			local ok, err = pcall(granted, player, session, grant)
			if not ok then
				warn("[LandmarkRNG] 구매 분석 기록 실패: " .. tostring(err))
			end
		end
	end

	-- Studio(저장 안 함)에서는 효과만 적용되고 완료 처리는 되지 않음
	if not session.LockId then
		return notYet
	end
	if deps.save(player, session) then
		return Enum.ProductPurchaseDecision.PurchaseGranted
	end
	return notYet
end

-- 서버 행운 타이머 늘리기: (지금 끝나는 시각, 지금 시각, 더할 초) -> (새 끝나는 시각, 실제로 더한 초).
-- 결제된 시간이라 구매 창 상한(MAX_BOOST_SECONDS)으로 자르지 않음(PlayerState.stackSeconds)
function Purchases.extendUntil(untilTime: number, now: number, seconds: number): (number, number)
	local left = math.max(0, untilTime - now)
	local after = PlayerState.stackSeconds(left, seconds)
	return now + after, after - left
end

-- BuyProduct 원격: 구매 창을 띄워도 되는지. 반환: (상품, nil) 이면 띄움, 아니면 (nil, 이유)
--   이유 "loading" = 데이터를 불러오는 중, "max" = 남은 부스트 시간 + 이번 시간이 MAX_BOOST_SECONDS 를 넘음, nil = 모르는 상품
-- serverLuckLeft: 지금 서버 행운 남은 초
function Purchases.promptCheck(productKey: any, session: Session?, serverLuckLeft: number): (Config.Product?, string?)
	local product = if type(productKey) == "string" then PlayerState.ProductsById[productKey] else nil
	if not product or product.ProductId <= 0 then
		return nil, nil
	end
	if not session then
		return nil, "loading"
	end
	local seconds = product.Seconds
	if seconds then
		local left = if product.ServerWide then serverLuckLeft else PlayerState.boostLeft(session.Data, product.Id)
		if left + seconds > Config.MAX_BOOST_SECONDS then
			return nil, "max"
		end
	end
	return product, nil
end

-- 게임패스 ----------------------------------------------------------------

-- 접속 시 게임패스 소유 확인. owned 는 세션과 같은 표라서 확인되는 대로 반영됨.
-- 오류 난 패스만 PASS_RETRY 간격으로 다시 확인하고(나가면 그만), 새로 찾은 패스가 있으면 그때마다 passesChanged.
-- 반환: 끝까지 확인하지 못한 패스 수(0 = 모두 확인)
function Purchases.checkPasses(player: Player, owned: { [string]: boolean }, deps: Deps): number
	local pending: { Config.GamePass } = {}
	for _, pass in Config.GamePasses do
		if pass.PassId > 0 then
			table.insert(pending, pass)
		end
	end
	local tries = #Purchases.PASS_RETRY + 1
	for attempt = 1, tries do
		local failed = {}
		local found = false
		for _, pass in pending do
			if owned[pass.Id] then
				continue -- 그사이 구매 완료 이벤트로 받음
			end
			local ok, result = pcall(deps.ownsPass, player, pass.PassId)
			if not ok then
				table.insert(failed, pass)
				warn(
					string.format(
						"[LandmarkRNG] %s 게임패스(%s) 확인 실패(%d/%d): %s",
						player.Name,
						pass.Id,
						attempt,
						tries,
						tostring(result)
					)
				)
			elseif result == true then
				owned[pass.Id] = true
				found = true
			end
		end
		if found then
			deps.passesChanged(player)
		end
		pending = failed
		if #pending == 0 or attempt == tries then
			break
		end
		deps.wait(Purchases.PASS_RETRY[attempt])
		if not deps.inGame(player) then
			break
		end
	end
	return #pending
end

-- BuyPass 원격: 구매 창을 띄우기 전에 한 번 더 확인(접속 때 확인이 오류였거나 웹사이트에서 산 경우).
-- 새로 가진 걸 알게 되면 passesChanged. 반환: 가졌는지(true 면 구매 창을 띄우지 않음)
function Purchases.recheckPass(player: Player, owned: { [string]: boolean }, pass: Config.GamePass, deps: Deps): boolean
	if owned[pass.Id] then
		return true
	end
	local ok, result = pcall(deps.ownsPass, player, pass.PassId)
	if not ok then
		warn(
			string.format(
				"[LandmarkRNG] %s 게임패스(%s) 다시 확인 실패: %s",
				player.Name,
				pass.Id,
				tostring(result)
			)
		)
		return false
	end
	if result == true then
		owned[pass.Id] = true
		deps.passesChanged(player)
		return true
	end
	return false
end

return Purchases
