-- 상태창 법구 갈래.
--   왼쪽 공격 법구: Roblox 도구 칸에 든 순서대로 (키보드는 숫자 키, 터치는 아래 도구 칸). 이름, 등급, 위력·간격·거리.
--     손에 든 법구(캐릭터에 붙은 도구의 WeaponIndex)는 금테로 보인다.
--   오른쪽 방어 법구: 위에 지닌 하나(효과와 내려놓기), 아래에 가진 나머지와 지니기.
--     나머지 카드에는 지금 지닌 것 대신 지니면 효과가 어떻게 바뀌는지 보인다 (좋아지면 옥빛, 나빠지면 붉게).
--     방어 법구는 부위와 상관없이 하나만 지닌다 (서버 Progression.equipGuard 가 하나만 남긴다).

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Combat = require(Shared.Combat)
local Guards = require(Shared.Guards)
local Ui = require(script.Parent.Ui)
local Kit = require(script.Parent.StatusKit)

local C = Ui.C
local new, text, setImage = Ui.new, Ui.text, Ui.setImage

local BeopguTab = {}

BeopguTab.LEFT_W = 300
BeopguTab.RIGHT_W = Kit.W - BeopguTab.LEFT_W - 14
local LIST_Y = 38
local CARD_H = 76
local WORN_H = 96
local MAX_DIFF = 4 -- 바뀌는 효과 칸 수 (두 법구의 효과 칸을 합쳐도 넷을 넘지 않는다)
local LINE = 20
BeopguTab.TEXT_X = 64
local DIFF_W = BeopguTab.RIGHT_W - BeopguTab.TEXT_X - 6

-- 조각들을 왼쪽부터 놓고 줄이 넘치면 다음 줄로. 반환: 줄 수
local function flow(pieces: { any }): number
	local x, lines = 0, 1
	for _, piece in pieces do
		if not piece.frame.Visible then
			continue
		end
		local width = piece.frame.Size.X.Offset
		if x > 0 and x + width > DIFF_W then
			x, lines = 0, lines + 1
		end
		piece.frame.Position = UDim2.fromOffset(x, (lines - 1) * LINE)
		x += width + 4
	end
	return lines
end

-- 공격 법구 한 줄: "위력 ×1.3  간격 0.45초  거리 8"
function BeopguTab.weaponStats(weapon: Combat.Weapon): string
	local kind = Combat.KINDS[weapon.kind]
	local grade = Combat.GRADES[weapon.grade]
	return string.format(
		"위력 ×%s  간격 %s  거리 %d",
		Kit.number(kind.damage * grade.mult),
		Kit.seconds(kind.cooldown),
		kind.range
	)
end

-- 지닌 것(worn) 대신 이것(guard)을 지니면 바뀌는 효과. { 글, 좋아지는가 }
function BeopguTab.changes(guard: Guards.Guard, worn: Guards.Guard?): { { text: string, good: boolean } }
	local out = {}
	for _, entry in Guards.LABELS do
		local key, label, sign = entry[1], entry[2], entry[3]
		local delta = Guards.value(guard, key) - Guards.value(worn, key)
		if math.abs(delta) > 1e-9 then
			local percent = math.round(delta * 1000 * sign) / 10
			local shown = math.abs(percent)
			local number = if shown % 1 == 0 then string.format("%d", shown) else string.format("%.1f", shown)
			table.insert(out, {
				text = string.format("%s %s%s%%", label, if percent > 0 then "+" else "-", number),
				good = delta > 0,
			})
		end
	end
	return out
end

-- 방어 법구 겉말: 설명의 첫 문장 ("몸을 지키는 옥패.")
local function flavor(kind: string): string
	local summary = Guards.byId[kind].summary
	return string.match(summary, "^(.-%.)%s") or summary
end

local function guardSeal(seal, glyph, guard: Guards.Guard?)
	if guard then
		glyph:set(string.sub(Guards.byId[guard.kind].name, 1, utf8.offset(Guards.byId[guard.kind].name, 2) - 1))
		glyph:setColor(Kit.GRADE[guard.grade] or C.cream)
		seal.ImageColor3 = Color3.new(1, 1, 1)
	else
		glyph:set("")
		seal.ImageColor3 = Color3.fromRGB(120, 114, 104)
	end
end

function BeopguTab.build(parent: Frame, ctx: Kit.Context)
	local weaponCards: { { [string]: any } } = {}
	local guardCards: { [string]: { [string]: any } } = {}
	local lastState: { [string]: any }? = nil

	-- 공격 법구 ---------------------------------------------------------------------
	local left = new("Frame", {
		Name = "Weapons",
		Position = UDim2.fromOffset(2, 0),
		Size = UDim2.fromOffset(BeopguTab.LEFT_W, Kit.H),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	local _, weaponSub = Kit.header(left, "공격 법구", UDim2.fromOffset(0, 0), BeopguTab.LEFT_W)
	weaponSub:set(if ctx.keyboard then "숫자 키로 든다" else "아래 도구 칸에서 든다")
	local weaponList = new("ScrollingFrame", {
		Name = "List",
		Position = UDim2.fromOffset(-2, LIST_Y),
		Size = UDim2.fromOffset(BeopguTab.LEFT_W + 12, Kit.H - LIST_Y),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 4,
		ScrollBarImageColor3 = C.gold,
		ScrollingDirection = Enum.ScrollingDirection.Y,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = left,
	}, {
		new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder, Padding = UDim.new(0, Kit.GAP_Y) }),
		new("UIPadding", {
			PaddingLeft = UDim.new(0, 2),
			PaddingTop = UDim.new(0, 2),
			PaddingBottom = UDim.new(0, if ctx.touchOnly then 70 else 2),
		}),
	})
	for index = 1, Combat.MAX_WEAPONS do
		local card, stroke = Kit.card(weaponList, {
			Name = "Weapon" .. index,
			LayoutOrder = index,
			Size = UDim2.fromOffset(BeopguTab.LEFT_W, CARD_H),
			Visible = false,
		})
		local seal, glyph = Kit.seal(card, 46, UDim2.fromOffset(9, 15))
		-- 드는 키 (도구 칸 번호)
		local key, keyText = Kit.key(card, 22, 20, 14)
		key.Position = UDim2.fromOffset(3, 6)
		keyText:set(tostring(index))
		local name = text("title", 19, { color = C.cream, name = "Name" })
		name.frame.Position = UDim2.fromOffset(BeopguTab.TEXT_X - 4, 6)
		name.frame.Parent = card
		local tag = text("body", 14, { color = C.dim, name = "Tag" })
		tag.frame.AnchorPoint = Vector2.new(1, 0)
		tag.frame.Position = UDim2.new(1, -8, 0, 9)
		tag.frame.Parent = card
		local stats = text("body", 14, { color = C.cream, name = "Stats" })
		stats.frame.Position = UDim2.fromOffset(BeopguTab.TEXT_X - 3, 32)
		stats.frame.Parent = card
		local summary = text("body", 14, { color = C.dim, name = "Sub" })
		summary.frame.Position = UDim2.fromOffset(BeopguTab.TEXT_X - 3, 52)
		summary.frame.Parent = card
		weaponCards[index] = {
			card = card,
			stroke = stroke,
			seal = seal,
			glyph = glyph,
			name = name,
			tag = tag,
			stats = stats,
			summary = summary,
		}
	end
	local weaponEmpty, setWeaponEmpty =
		Kit.note(left, "WeaponEmpty", BeopguTab.LEFT_W - 8, 2, UDim2.fromOffset(4, LIST_Y + 8))
	setWeaponEmpty("지닌 공격 법구가 없다. 만물상에서 산다.")

	-- 방어 법구 ---------------------------------------------------------------------
	local right = new("Frame", {
		Name = "Guards",
		Position = UDim2.fromOffset(2 + BeopguTab.LEFT_W + 14, 0),
		Size = UDim2.fromOffset(BeopguTab.RIGHT_W, Kit.H),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	local _, guardCount = Kit.header(right, "방어 법구", UDim2.fromOffset(0, 0), BeopguTab.RIGHT_W)

	-- 지닌 방어 법구 (큰 칸)
	local worn, wornStroke = Kit.card(right, {
		Name = "Worn",
		Position = UDim2.fromOffset(0, LIST_Y + 2),
		Size = UDim2.fromOffset(BeopguTab.RIGHT_W, WORN_H),
	})
	local wornSeal, wornGlyph = Kit.seal(worn, 62, UDim2.fromOffset(12, 17))
	local wornName = text("title", 22, { color = C.gold, name = "Name" })
	wornName.frame.Position = UDim2.fromOffset(84, 8)
	wornName.frame.Parent = worn
	local wornEffects = text("body", 15, { color = C.jade, name = "Sub" })
	wornEffects.frame.Position = UDim2.fromOffset(86, 42)
	wornEffects.frame.Parent = worn
	local wornFlavor = text("body", 14, { color = C.dim, name = "Flavor" })
	wornFlavor.frame.Position = UDim2.fromOffset(86, 66)
	wornFlavor.frame.Parent = worn
	local wornButton = Ui.pill("내려놓기", 84, 28, 14, worn, function()
		ctx.actions.equipGuard("")
	end)
	wornButton.Name = "Button"
	wornButton.AnchorPoint = Vector2.new(1, 0)
	wornButton.Position = UDim2.new(1, -8, 0, 8)
	setImage(wornButton, "pillStone")

	-- 하나만 지닌다는 규칙 (작게)
	local rule = text("body", 14, {
		color = Color3.fromRGB(150, 140, 118),
		name = "GuardRule",
		text = "방어 법구는 부위와 상관없이 하나만 지닐 수 있다.",
	})
	rule.frame.Position = UDim2.fromOffset(2, LIST_Y + WORN_H + 8)
	rule.frame.Parent = right

	local guardListY = LIST_Y + WORN_H + 34
	local guardList = new("ScrollingFrame", {
		Name = "List",
		Position = UDim2.fromOffset(-2, guardListY),
		Size = UDim2.fromOffset(BeopguTab.RIGHT_W + 12, Kit.H - guardListY),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ScrollBarThickness = 4,
		ScrollBarImageColor3 = C.gold,
		ScrollingDirection = Enum.ScrollingDirection.Y,
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		Parent = right,
	}, {
		new("UIListLayout", { SortOrder = Enum.SortOrder.LayoutOrder, Padding = UDim.new(0, Kit.GAP_Y) }),
		new("UIPadding", {
			PaddingLeft = UDim.new(0, 2),
			PaddingTop = UDim.new(0, 2),
			PaddingBottom = UDim.new(0, if ctx.touchOnly then 70 else 2),
		}),
	})
	for index, id in Guards.ORDER do
		local card, stroke = Kit.card(guardList, {
			Name = "Guard_" .. id,
			LayoutOrder = index,
			Size = UDim2.fromOffset(BeopguTab.RIGHT_W, CARD_H),
			Visible = false,
		})
		local seal, glyph = Kit.seal(card, 46, UDim2.fromOffset(9, 15))
		local name = text("title", 19, { color = C.cream, name = "Name" })
		name.frame.Position = UDim2.fromOffset(BeopguTab.TEXT_X - 4, 6)
		name.frame.Parent = card
		local effects = text("body", 14, { color = C.cream, name = "Sub" })
		effects.frame.Position = UDim2.fromOffset(BeopguTab.TEXT_X - 3, 32)
		effects.frame.Parent = card
		-- 바꾸면 달라지는 것: "바꾸면" + 효과마다 한 조각 (색이 달라서 조각마다 따로 찍고, 넘치면 다음 줄로)
		local diff = new("Frame", {
			Name = "Diff",
			Position = UDim2.fromOffset(BeopguTab.TEXT_X - 3, 52),
			Size = UDim2.fromOffset(DIFF_W, 20),
			BackgroundTransparency = 1,
			Parent = card,
		})
		local lead = text("body", 14, { color = C.dim, text = "바꾸면", name = "Lead", parent = diff })
		local parts = {}
		for part = 1, MAX_DIFF do
			parts[part] = text("body", 14, { color = C.jade, name = "Part" .. part, parent = diff })
		end
		local button, caption = Ui.pill("지니기", 70, 28, 14, card, function()
			local wearing = lastState ~= nil and lastState.guard == id
			ctx.actions.equipGuard(if wearing then "" else id)
		end)
		button.Name = "Button"
		button.AnchorPoint = Vector2.new(1, 0)
		button.Position = UDim2.new(1, -8, 0, 6)
		guardCards[id] = {
			card = card,
			stroke = stroke,
			seal = seal,
			glyph = glyph,
			name = name,
			effects = effects,
			diff = diff,
			lead = lead,
			parts = parts,
			button = button,
			caption = caption,
		}
	end
	local guardEmpty, setGuardEmpty =
		Kit.note(right, "GuardEmpty", BeopguTab.RIGHT_W - 8, 2, UDim2.fromOffset(4, guardListY + 4))
	setGuardEmpty(
		"아직 방어 법구가 없다. 요수를 쓰러뜨리거나, 대장간에서 만들거나, 만물상에서 산다."
	)

	-- 손에 든 법구 표시. 프레임마다 불려서 든 칸이 바뀌었을 때만 다시 칠한다 (force 는 상태가 바뀌었을 때)
	local paintedHeld: number? | false = false
	local function paintHeld(force: boolean?)
		local held = ctx.heldWeapon()
		if not force and held == paintedHeld then
			return
		end
		paintedHeld = held
		local weapons = if lastState then lastState.weapons or {} else {}
		for index, entry in weaponCards do
			local weapon = weapons[index]
			if not weapon or not Combat.isWeapon(weapon) then
				continue
			end
			local holding = held == index
			Kit.look(entry.card, entry.stroke, if holding then "worn" else "normal")
			entry.name:setColor(if holding then C.gold else C.cream)
			entry.tag:set(if holding then "손에 들었다" else Combat.GRADES[weapon.grade].prefix .. " 등급")
			entry.tag:setColor(if holding then C.jade else C.dim)
		end
	end

	local function update(state)
		lastState = state
		local weapons = state.weapons or {}
		local shown = 0
		for index, entry in weaponCards do
			local weapon = weapons[index]
			local ok = weapon ~= nil and Combat.isWeapon(weapon)
			entry.card.Visible = ok
			if not ok then
				continue
			end
			shown += 1
			local kind = Combat.KINDS[weapon.kind]
			entry.name:set(Combat.weaponName(weapon))
			entry.glyph:set(kind.suffix)
			entry.glyph:setColor(Kit.GRADE[weapon.grade] or C.cream)
			entry.stats:set(BeopguTab.weaponStats(weapon))
			entry.summary:set(kind.summary)
		end
		weaponEmpty.Visible = shown == 0
		paintHeld(true)

		local owned: { [string]: Guards.Guard } = {}
		local any = false
		for _, guard in state.guards or {} do
			if Guards.isGuard(guard) then
				owned[guard.kind] = guard
				any = true
			end
		end
		local wornGuard = if state.guard then owned[state.guard] else nil
		guardCount:set(if wornGuard then "지님 1 / 1" else "지님 0 / 1")

		-- 지닌 것
		guardSeal(wornSeal, wornGlyph, wornGuard)
		wornButton.Visible = wornGuard ~= nil
		if wornGuard then
			wornName:set(Guards.name(wornGuard))
			wornName:setColor(C.gold)
			wornEffects:set(Guards.effects(wornGuard))
			wornEffects:setColor(C.jade)
			wornFlavor:set(flavor(wornGuard.kind))
			Kit.look(worn, wornStroke, "worn")
		else
			wornName:set("지닌 방어 법구가 없다")
			wornName:setColor(C.dim)
			wornEffects:set(if any then "아래에서 지니기를 누른다" else "")
			wornEffects:setColor(C.cream)
			wornFlavor:set("")
			Kit.look(worn, wornStroke, "dim")
		end

		-- 나머지
		local others = 0
		for _, id in Guards.ORDER do
			local entry = guardCards[id]
			local guard = owned[id]
			local visible = guard ~= nil and guard ~= wornGuard
			entry.card.Visible = visible
			if not guard or not visible then
				continue
			end
			others += 1
			guardSeal(entry.seal, entry.glyph, guard)
			entry.name:set(Guards.name(guard))
			entry.effects:set(Guards.effects(guard))
			entry.caption:set("지니기")
			setImage(entry.button, "pillJade")
			Kit.look(entry.card, entry.stroke, "normal")
			-- 지닌 것이 있으면 바꿨을 때 달라지는 것
			local list = if wornGuard then BeopguTab.changes(guard, wornGuard) else {}
			entry.diff.Visible = wornGuard ~= nil
			for part, piece in entry.parts do
				local change = list[part]
				piece.frame.Visible = change ~= nil
				if change then
					piece:set(change.text .. (if part < #list then "," else ""))
					piece:setColor(if change.good then C.jade else C.red)
				end
			end
			if wornGuard and #list == 0 then
				entry.parts[1].frame.Visible = true
				entry.parts[1]:set("효과가 같다")
				entry.parts[1]:setColor(C.dim)
			end
			local lines = if wornGuard then flow({ entry.lead, table.unpack(entry.parts) }) else 1
			entry.diff.Size = UDim2.fromOffset(DIFF_W, lines * LINE)
			entry.card.Size = UDim2.fromOffset(BeopguTab.RIGHT_W, CARD_H + (lines - 1) * LINE)
		end
		guardEmpty.Visible = not any
		guardList.Visible = others > 0
	end

	return {
		update = update,
		tick = function()
			paintHeld(false)
		end,
		reset = function() end,
	}
end

return BeopguTab
