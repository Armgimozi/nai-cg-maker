-- 상점 창: 마을 만물상(물건, 법구, 영석 사기)과 대장간(공격 법구 강화, 방어 법구 제작).
-- 상점 자리의 F 버튼을 누르면 열린다 (Main.client). 사고 강화하고 만드는 요청은 서버에 "Buy"·"Upgrade"·"Craft" 로 보내고,
-- 서버(Market.luau)가 상점 곁에 섰는지와 영석·재료가 넉넉한지 다시 본다. 열려 있는 동안 상태가 올 때마다 다시 그린다.
-- 법구: 공격 법구는 Combat(검·도·창·선, 숫자 키 도구), 방어 법구는 Guards(하나만 지닌다).
-- 영석 묶음은 로벅스 개발자 상품이다 (Currency.PACKS, 지급은 server/Shop.luau).

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Balance = require(Shared.Balance)
local Combat = require(Shared.Combat)
local Currency = require(Shared.Currency)
local Guards = require(Shared.Guards)
local Ui = require(script.Parent.Ui)
local Notice = require(script.Parent.Notice)

local C = Ui.C
local new, image, setImage, text, row = Ui.new, Ui.image, Ui.setImage, Ui.text, Ui.row

local ShopWindow = {}

export type Handlers = {
	buy: (wareId: string) -> (),
	upgrade: (index: number) -> (),
	craft: (kind: string, grade: number) -> (),
}

local PANEL_W, PANEL_H = 640, 540
local LIST_W = 560
local ROW_H, ROW_H_TALL = 56, 74 -- 재료 줄이 있으면 높인다
local BUTTON_W, PACK_BUTTON_W = 80, 112
local MAX_ROWS = math.max(#Currency.WARES, #Currency.PACKS, Combat.MAX_WEAPONS, #Guards.KINDS)

local TITLES = { market = "만물상", smith = "대장간" }
-- 상점마다 갈래. 첫 갈래가 처음 열릴 때 보인다
local TABS = {
	market = {
		{ key = "goods", label = "물건" },
		{ key = "gear", label = "법구" },
		{ key = "packs", label = "영석 사기" },
	},
	smith = {
		{ key = "upgrade", label = "강화" },
		{ key = "craft", label = "제작" },
	},
}
local MAX_TABS = 3
local HINTS = {
	goods = "산 물건은 주머니에 들어간다.",
	gear = "법구는 종류마다 하나씩 지닌다. 방어 법구는 한 번에 하나만 지닌다.",
	packs = "로벅스로 영석을 산다.",
	upgrade = "공격 법구 강화는 반드시 성공한다. 한 번에 한 등급씩 오른다.",
	craft = "방어 법구를 만든다. 같은 종류는 더 높은 등급으로 바뀐다.",
}
local EMPTY = {
	upgrade = "지닌 공격 법구가 없다.",
}

local player = Players.LocalPlayer
local ui: { [string]: any } = {}
local rows: { { [string]: any } } = {}
local tabs: { { [string]: any } } = {}
local handlers: Handlers
local kind: string? = nil
local tab = "goods"
local lastState: { [string]: any }? = nil

local function short(price: number)
	Notice.show(string.format("영석이 모자라다. (%s 필요)", Currency.format(price)), "bad")
end

-- 줄 하나 채우기
type Spec = {
	name: string,
	sub: string,
	price: number?, -- 영석 값 (보석과 함께)
	note: string?, -- 값 대신 쓰는 말 ("최고 등급")
	cost: string?, -- 셋째 줄: 재료 ("재료 요단 2/3")
	costShort: boolean?, -- 재료가 모자라면 붉게
	label: string?, -- 버튼 글자 (없으면 버튼을 숨긴다)
	width: number?,
	enabled: boolean,
	affordable: boolean,
	onClick: () -> (),
}

local function fill(entry: { [string]: any }, spec: Spec)
	entry.frame.Visible = true
	entry.frame.Size = UDim2.new(1, -8, 0, if spec.cost then ROW_H_TALL else ROW_H)
	entry.name:set(spec.name)
	entry.sub:set(spec.sub)
	entry.cost.frame.Visible = spec.cost ~= nil
	if spec.cost then
		entry.cost:set(spec.cost)
		entry.cost:setColor(if spec.costShort then C.red else C.jade)
	end
	entry.priceRow.Visible = spec.price ~= nil or spec.note ~= nil
	entry.gem.Visible = spec.price ~= nil
	if spec.price then
		entry.price:set(Currency.format(spec.price))
		entry.price:setColor(if spec.affordable then C.gold else C.red)
	elseif spec.note then
		entry.price:set(spec.note)
		entry.price:setColor(C.dim)
	end
	entry.button.Visible = spec.label ~= nil
	if spec.label then
		entry.button.Size = UDim2.fromOffset(spec.width or BUTTON_W, 32)
		entry.buttonText:set(spec.label)
		entry.buttonText:setColor(if spec.enabled then C.cream else C.dim)
		setImage(entry.button, if spec.enabled then "pillJade" else "pillStone")
	end
	entry.name:setColor(if spec.enabled or spec.label == nil then C.cream else C.dim)
	entry.onClick = spec.onClick
end

local function owns(state: { [string]: any }, weaponKind: string): boolean
	for _, weapon in state.weapons or {} do
		if weapon.kind == weaponKind then
			return true
		end
	end
	return false
end

-- 지닌 그 종류 방어 법구 (Progression.guardOf 와 같다, 상태 스냅숏에서)
local function guardOf(state: { [string]: any }, guardKind: string): Guards.Guard?
	for _, guard in state.guards or {} do
		if guard.kind == guardKind then
			return guard
		end
	end
	return nil
end

local function goodsSpecs(state: { [string]: any }, stones: number): { Spec }
	local out = {}
	for _, ware in Currency.WARES do
		local item = ware.item
		if not item then
			continue
		end
		local count = ware.count or 1
		local have = (state.items or {})[item] or 0
		local affordable = stones >= ware.price
		table.insert(out, {
			name = Balance.ITEMS[item].name,
			sub = string.format("%d개, 주머니에 %d개", count, have),
			price = ware.price,
			label = "사기",
			enabled = affordable,
			affordable = affordable,
			onClick = function()
				if affordable then
					handlers.buy(ware.id)
				else
					short(ware.price)
				end
			end,
		})
	end
	return out
end

-- 만물상 법구 갈래: 공격 법구 다음에 방어 법구 (범품)
local function gearSpecs(state: { [string]: any }, stones: number): { Spec }
	local out = {}
	for _, ware in Currency.WARES do
		local weapon = ware.weapon
		if not weapon then
			continue
		end
		local owned = owns(state, weapon.kind)
		local affordable = stones >= ware.price
		table.insert(out, {
			name = Combat.weaponName(weapon),
			sub = "공격 법구, " .. Combat.KINDS[weapon.kind].summary,
			price = ware.price,
			label = if owned then "지님" else "사기",
			enabled = affordable and not owned,
			affordable = affordable or owned,
			onClick = function()
				if owned then
					Notice.show(
						"이미 지닌 종류의 공격 법구다. 대장간에서 강화할 수 있다.",
						"info"
					)
				elseif affordable then
					handlers.buy(ware.id)
				else
					short(ware.price)
				end
			end,
		})
	end
	for _, ware in Currency.WARES do
		local guard = ware.guard
		if not guard then
			continue
		end
		local owned = guardOf(state, guard.kind) ~= nil
		local affordable = stones >= ware.price
		table.insert(out, {
			name = Guards.name(guard),
			sub = "방어 법구, " .. Guards.effects(guard),
			price = ware.price,
			label = if owned then "지님" else "사기",
			enabled = affordable and not owned,
			affordable = affordable or owned,
			onClick = function()
				if owned then
					Notice.show(
						"이미 지닌 종류의 방어 법구다. 대장간에서 더 좋은 것을 만들 수 있다.",
						"info"
					)
				elseif affordable then
					handlers.buy(ware.id)
				else
					short(ware.price)
				end
			end,
		})
	end
	return out
end

local function packSpecs(): { Spec }
	local out = {}
	for _, pack in Currency.PACKS do
		table.insert(out, {
			name = pack.name,
			sub = string.format("영석 %s개", Currency.format(pack.stones)),
			label = string.format("%d 로벅스", pack.robux),
			width = PACK_BUTTON_W,
			enabled = true,
			affordable = true,
			onClick = function()
				if pack.productId > 0 then
					MarketplaceService:PromptProductPurchase(player, pack.productId)
				else
					Notice.show("이 영석 묶음은 아직 준비 중이다.", "info")
				end
			end,
		})
	end
	return out
end

-- 대장간 강화 갈래: 지닌 공격 법구마다 다음 등급과 값
local function upgradeSpecs(state: { [string]: any }, stones: number): { Spec }
	local out = {}
	for index, weapon in state.weapons or {} do
		local grade = Combat.GRADES[weapon.grade]
		local cost = Currency.upgradeCost(weapon.grade)
		if not grade then
			continue
		end
		if cost then
			local after = { kind = weapon.kind, grade = weapon.grade + 1 }
			local affordable = stones >= cost
			table.insert(out, {
				name = Combat.weaponName(weapon),
				sub = string.format("%s 등급, 강화하면 %s", grade.prefix, Combat.weaponName(after)),
				price = cost,
				label = "강화",
				enabled = affordable,
				affordable = affordable,
				onClick = function()
					if affordable then
						handlers.upgrade(index)
					else
						short(cost)
					end
				end,
			})
		else
			table.insert(out, {
				name = Combat.weaponName(weapon),
				sub = string.format("%s 등급", grade.prefix),
				note = "최고 등급",
				enabled = false,
				affordable = true,
				onClick = function() end,
			})
		end
	end
	return out
end

-- 제작 재료 줄 ("재료 요단 2/3, 영초 0/4": 지닌 수 / 드는 수). 반환: 글, 모자란 재료 이름과 수 (넉넉하면 nil)
local function costLine(cost: Guards.Cost, items: { [string]: number }): (string, string?, number?)
	local parts = {}
	local shortName, shortCount = nil, nil
	for _, id in Balance.ITEM_ORDER do
		local need = cost.items[id]
		if need then
			local have = items[id] or 0
			table.insert(parts, string.format("%s %d/%d", Balance.ITEMS[id].name, have, need))
			if have < need and not shortName then
				shortName, shortCount = Balance.ITEMS[id].name, need - have
			end
		end
	end
	return "재료 " .. table.concat(parts, ", "), shortName, shortCount
end

-- 대장간 제작 갈래: 방어 법구 종류마다 만들 수 있는 다음 등급 (없으면 범품)
local function craftSpecs(state: { [string]: any }, stones: number): { Spec }
	local out = {}
	local items = state.items or {}
	for _, id in Guards.ORDER do
		local owned = guardOf(state, id)
		local grade = if owned then owned.grade + 1 else 1
		local cost = Guards.CRAFT[grade]
		if owned and not cost then
			table.insert(out, {
				name = Guards.name(owned),
				sub = Guards.effects(owned),
				note = "최고 등급",
				enabled = false,
				affordable = true,
				onClick = function() end,
			})
			continue
		end
		local made = { kind = id, grade = grade }
		local line, shortName, shortCount = costLine(cost, items)
		local enough = stones >= cost.stones
		local affordable = enough and shortName == nil
		table.insert(out, {
			name = Guards.name(made),
			sub = if owned
				then string.format("%s (지금 %s)", Guards.effects(made), Guards.GRADES[owned.grade])
				else Guards.effects(made),
			price = cost.stones,
			cost = line,
			costShort = shortName ~= nil,
			label = "만들기",
			enabled = affordable,
			affordable = enough,
			onClick = function()
				if affordable then
					handlers.craft(id, grade)
				elseif not enough then
					short(cost.stones)
				else
					Notice.show(string.format("%s %d개가 모자라다.", shortName, shortCount), "bad")
				end
			end,
		})
	end
	return out
end

local function draw()
	local state = lastState
	if not kind or not state then
		return
	end
	local stones = state.stones or 0
	ui.stones:set(Currency.format(stones))
	for _, entry in tabs do
		local on = entry.key == tab
		setImage(entry.button, if on then "pillJade" else "pillStone")
		entry.text:setColor(if on then C.cream else C.dim)
	end
	local specs
	if tab == "upgrade" then
		specs = upgradeSpecs(state, stones)
	elseif tab == "craft" then
		specs = craftSpecs(state, stones)
	elseif tab == "gear" then
		specs = gearSpecs(state, stones)
	elseif tab == "packs" then
		specs = packSpecs()
	else
		specs = goodsSpecs(state, stones)
	end
	ui.hint:set(HINTS[tab] or "")
	ui.empty:set(EMPTY[tab] or "")
	for index, entry in rows do
		local spec = specs[index]
		if spec then
			fill(entry, spec)
		else
			entry.frame.Visible = false
			entry.onClick = nil
		end
	end
	ui.empty.frame.Visible = #specs == 0
end

-- 상점에 맞게 갈래 버튼 글자를 바꾸고 남는 버튼은 숨긴다
local function layout()
	local defs = TABS[kind or "market"]
	for index, entry in tabs do
		local def = defs[index]
		entry.button.Visible = def ~= nil
		entry.key = if def then def.key else nil
		if def then
			entry.text:set(def.label)
		end
	end
end

function ShopWindow.build(gui: ScreenGui, newHandlers: Handlers)
	handlers = newHandlers
	local panel = image("panel", {
		Name = "ShopWindow",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(PANEL_W, PANEL_H),
		SliceScale = 0.8,
		Visible = false,
		Active = true,
		ZIndex = 5,
		Parent = gui,
	})
	new("UIScale", { Parent = panel })
	ui.panel = panel
	local titleRow = row({ Position = UDim2.fromOffset(0, 22), Size = UDim2.new(1, 0, 0, 56), Parent = panel })
	ui.title = text("title", 38, { gradient = Ui.GOLD_TEXT, parent = titleRow })
	image("divider", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 74),
		Size = UDim2.fromOffset(540, 22),
		Parent = panel,
	})
	local closeButton = image("iconClose", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -24, 0, 24),
		Size = UDim2.fromOffset(32, 32),
		Parent = panel,
	}, "ImageButton")
	closeButton.Activated:Connect(function()
		ShopWindow.close()
	end)

	-- 지닌 영석 (왼쪽 위)
	local stoneRow = row({
		Position = UDim2.fromOffset(40, 30),
		Size = UDim2.fromOffset(200, 30),
		Parent = panel,
	}, Enum.HorizontalAlignment.Left, 6)
	stoneRow:FindFirstChildOfClass("UIListLayout").VerticalAlignment = Enum.VerticalAlignment.Center
	image("gem", { LayoutOrder = 1, Size = UDim2.fromOffset(20, 20), Parent = stoneRow })
	ui.stones = text("body", 19, { color = C.gold, name = "Stones", parent = stoneRow })
	ui.stones.frame.LayoutOrder = 2

	-- 갈래 (만물상: 물건·법구·영석 사기, 대장간: 강화·제작)
	local tabRow = row({ Position = UDim2.fromOffset(0, 98), Size = UDim2.new(1, 0, 0, 36), Parent = panel }, nil, 10)
	for index = 1, MAX_TABS do
		local entry: { [string]: any } = {}
		local button, caption = Ui.pill(TABS.market[index].label, 112, 34, 16, tabRow, function()
			if entry.key then
				tab = entry.key
				draw()
			end
		end)
		button.Name = "Tab" .. index
		button.LayoutOrder = index
		entry.key, entry.button, entry.text = TABS.market[index].key, button, caption
		tabs[index] = entry
	end

	local hintRow = row({ Position = UDim2.fromOffset(0, 140), Size = UDim2.new(1, 0, 0, 22), Parent = panel })
	ui.hint = text("body", 14, { color = C.dim, name = "Hint", parent = hintRow })

	local list = new("ScrollingFrame", {
		Position = UDim2.fromOffset((PANEL_W - LIST_W) / 2, 170),
		Size = UDim2.fromOffset(LIST_W, PANEL_H - 210),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 4,
		ScrollBarImageColor3 = C.gold,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = panel,
	}, { new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder }) })

	for index = 1, MAX_ROWS do
		local frame = new("Frame", {
			Name = "Row",
			LayoutOrder = index,
			Size = UDim2.new(1, -8, 0, ROW_H),
			BackgroundTransparency = 1,
			Visible = false,
			Parent = list,
		})
		new("Frame", {
			Position = UDim2.new(0, 0, 1, -1),
			Size = UDim2.new(1, 0, 0, 1),
			BackgroundColor3 = C.gold,
			BackgroundTransparency = 0.85,
			BorderSizePixel = 0,
			Parent = frame,
		})
		local name = text("title", 21, { color = C.cream, name = "Name" })
		name.frame.Position = UDim2.fromOffset(4, 2)
		name.frame.Parent = frame
		local sub = text("body", 13, { color = C.dim, name = "Sub" })
		sub.frame.Position = UDim2.fromOffset(6, 32)
		sub.frame.Parent = frame
		local cost = text("body", 13, { color = C.jade, name = "Cost" })
		cost.frame.Position = UDim2.fromOffset(6, 51)
		cost.frame.Visible = false
		cost.frame.Parent = frame

		local priceRow = row({
			AnchorPoint = Vector2.new(1, 0),
			Position = UDim2.new(1, -(BUTTON_W + 16), 0, 0),
			Size = UDim2.new(0, 160, 1, 0),
			Parent = frame,
		}, Enum.HorizontalAlignment.Right, 5)
		priceRow:FindFirstChildOfClass("UIListLayout").VerticalAlignment = Enum.VerticalAlignment.Center
		local gem = image("gem", { LayoutOrder = 1, Size = UDim2.fromOffset(18, 18), Parent = priceRow })
		local price = text("body", 17, { color = C.gold, name = "Price", parent = priceRow })
		price.frame.LayoutOrder = 2

		local entry: { [string]: any } = {}
		local button, caption = Ui.pill("사기", BUTTON_W, 32, 15, frame, function()
			if entry.onClick then
				entry.onClick()
			end
		end)
		button.Name = "Button"
		button.AnchorPoint = Vector2.new(1, 0.5)
		button.Position = UDim2.new(1, -4, 0.5, 0)

		entry.frame, entry.name, entry.sub, entry.cost = frame, name, sub, cost
		entry.priceRow, entry.gem, entry.price = priceRow, gem, price
		entry.button, entry.buttonText = button, caption
		rows[index] = entry
	end

	ui.empty = text("body", 16, { color = C.dim, name = "Empty", parent = panel })
	ui.empty.frame.Position = UDim2.fromOffset((PANEL_W - LIST_W) / 2 + 8, 182)
	ui.empty.frame.Visible = false
end

function ShopWindow.isOpen(): boolean
	return ui.panel ~= nil and ui.panel.Visible
end

function ShopWindow.close()
	if ui.panel then
		ui.panel.Visible = false
	end
	kind = nil
end

-- shopKind: "market" (만물상) | "smith" (대장간). 처음 열면 첫 갈래 (물건, 강화)
function ShopWindow.open(shopKind: string, state: { [string]: any })
	if not ui.panel or not TITLES[shopKind] then
		return
	end
	if kind ~= shopKind then
		tab = TABS[shopKind][1].key
	end
	kind = shopKind
	lastState = state
	ui.title:set(TITLES[shopKind])
	layout()
	draw()
	ui.panel.Visible = true
end

-- 열려 있을 때 새 상태로 다시 그린다
function ShopWindow.refresh(state: { [string]: any })
	lastState = state
	if ShopWindow.isOpen() then
		draw()
	end
end

return ShopWindow
