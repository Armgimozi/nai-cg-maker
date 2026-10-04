-- 상태창 주머니 갈래: 물건마다 카드 (개수, 쓰임, 먹기). 먹기는 서버에 "Eat" 로 보낸다.
-- 축기단은 먹는 버튼이 없다 (무극영운을 시작할 때 저절로 먹는다). 나머지는 가진 것이 있을 때만 먹기를 띄우고,
-- 먹을 수 없는 것(별씨)은 서버가 왜 안 되는지 알려 준다.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Balance = require(Shared.Balance)
local Guards = require(Shared.Guards)
local Ui = require(script.Parent.Ui)
local Kit = require(script.Parent.StatusKit)

local C = Ui.C
local text = Ui.text

local PouchTab = {}

local COLUMNS = 2
local GRID_Y = 34
PouchTab.CELL_W = math.floor((Kit.W - 4 - (COLUMNS - 1) * Kit.GAP_X) / COLUMNS)
PouchTab.TEXT_W = PouchTab.CELL_W - 74 - 10

-- 대장간에서 방어 법구 재료로 쓰는 물건
local MATERIAL: { [string]: boolean } = {}
for _, cost in Guards.CRAFT do
	for id in cost.items do
		MATERIAL[id] = true
	end
end

-- 물건 쓰임 (두 줄까지)
function PouchTab.describe(id: string): string
	local def = Balance.ITEMS[id]
	local line
	if id == "pill" then
		line = "무극영운을 시작할 때 저절로 먹는다."
	elseif id == "starSeed" then
		line = "먹는 것이 아니라 단전에 별로 응결한다."
	elseif id == "hongsam" then
		line = "먹으면 몸이 홍령수지체로 바뀐다. 결단기에 이르면 듣지 않는다."
	elseif def.qi then
		line = string.format("먹으면 지금 단계 영력의 %d%%가 찬다.", math.round(def.qi * 100))
	else
		line = ""
	end
	if MATERIAL[id] then
		line ..= " 대장간 재료로도 쓴다."
	end
	return line
end

function PouchTab.build(parent: Frame, ctx: Kit.Context)
	local cards: { [string]: { [string]: any } } = {}

	local hint = text("body", 15, {
		color = C.dim,
		name = "Hint",
		text = "영력이 가득 찬 채 먹으면 흩어진다.",
	})
	hint.frame.Position = UDim2.fromOffset(2, 3)
	hint.frame.Parent = parent

	local list = Kit.grid(parent, {
		Name = "Cards",
		Position = UDim2.fromOffset(0, GRID_Y),
		Size = UDim2.fromOffset(Kit.W + Kit.GUTTER, Kit.H - GRID_Y),
	}, COLUMNS, Kit.CARD_H, ctx.touchOnly)

	for index, id in Balance.ITEM_ORDER do
		local def = Balance.ITEMS[id]
		local card, stroke = Kit.card(list, {
			Name = "Item_" .. id,
			LayoutOrder = index,
			Size = UDim2.fromOffset(PouchTab.CELL_W, Kit.CARD_H),
		})
		local seal, glyph = Kit.seal(card, 52, UDim2.fromOffset(10, 14))
		glyph:set(string.sub(def.name, 1, utf8.offset(def.name, 2) - 1))
		local nameRow = Ui.row({
			Position = UDim2.fromOffset(70, 6),
			Size = UDim2.fromOffset(PouchTab.CELL_W - 150, 28),
			Parent = card,
		}, Enum.HorizontalAlignment.Left, 8)
		local name = text("title", 19, { color = C.cream, text = def.name, name = "Name", parent = nameRow })
		name.frame.LayoutOrder = 1
		local count = text("body", 16, { color = C.gold, name = "Count", parent = nameRow })
		count.frame.LayoutOrder = 2
		local about, setAbout = Ui.paragraph("body", 14, PouchTab.TEXT_W, 2, C.dim, card)
		about.Name = "About"
		about.Position = UDim2.fromOffset(71, 34)
		setAbout(PouchTab.describe(id))
		local button = nil
		if id ~= "pill" then
			button = Ui.pill("먹기", 62, 28, 14, card, function()
				ctx.actions.eat(id)
			end)
			button.Name = "Button"
			button.AnchorPoint = Vector2.new(1, 0)
			button.Position = UDim2.new(1, -8, 0, 7)
		end
		cards[id] = {
			card = card,
			stroke = stroke,
			seal = seal,
			glyph = glyph,
			name = name,
			count = count,
			button = button,
			setAbout = setAbout,
		}
	end

	local function update(state)
		local items = state.items or {}
		for id, entry in cards do
			local have = items[id] or 0
			entry.count:set(string.format("%d개", have))
			entry.count:setColor(if have > 0 then C.gold else C.dim)
			entry.name:setColor(if have > 0 then C.cream else C.dim)
			entry.glyph:setColor(if have > 0 then C.cream else C.dim)
			entry.seal.ImageColor3 = if have > 0 then Color3.new(1, 1, 1) else Color3.fromRGB(120, 114, 104)
			if entry.button then
				entry.button.Visible = have > 0
			end
			Kit.look(entry.card, entry.stroke, if have > 0 then "normal" else "dim")
		end
	end

	return {
		update = update,
		reset = function() end,
	}
end

return PouchTab
