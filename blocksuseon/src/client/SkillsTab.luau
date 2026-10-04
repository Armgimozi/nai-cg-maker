-- 상태창 술법·공법 갈래.
--
-- 술법: 위에 단축칸 넷(그림, 키, 쿨타임), 아래에 술법 카드 (익힌 것 먼저, 못 익힌 것은 흐리게 얻는 곳과 함께).
--   넣기: 카드를 누르고 칸을 누른다. 칸을 먼저 누르고 카드를 눌러도 된다
--   (화면 아래 단축칸의 빈 칸을 누르면 그 칸이 골라진 채 열린다, SkillsTab.pickSlot).
--   이미 다른 칸에 있던 술법을 넣으면 서버가 두 칸을 맞바꾼다 (Progression.assignSkill). 고른 뒤 "칸 비우기"로 뺀다.
--   칸의 키 표를 누르면 다음에 누르는 키로 바꾼다 (Hud.startBinding → Main.client 가 BindKey 를 보낸다).
-- 공법: 위에 공법 칸 (경지마다 열린다, Skills.SLOT_REALMS), 아래에 공법 카드와 장착·해제 (Equip / Unequip).

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Skills = require(Shared.Skills)
local Realms = require(Shared.Realms)
local Progression = require(Shared.Progression)
local Ui = require(script.Parent.Ui)
local Kit = require(script.Parent.StatusKit)

local C = Ui.C
local new, text, setImage = Ui.new, Ui.text, Ui.setImage

local SkillsTab = {}

local HOTBAR = Progression.HOTBAR_SIZE
local COLUMNS = 3
local SLOT_H = 80
local HINT_Y = 88
local GRID_Y = 120
local ICON, TEXT_X = 44, 62 -- 카드 그림 크기, 글 시작
SkillsTab.CELL_W = math.floor((Kit.W - 4 - (COLUMNS - 1) * Kit.GAP_X) / COLUMNS)
SkillsTab.TEXT_W = SkillsTab.CELL_W - TEXT_X - 8 -- 카드 설명 줄 너비 (두 줄까지)
SkillsTab.SLOT_W = math.floor((Kit.W - 4 - (HOTBAR - 1) * 10) / HOTBAR)
SkillsTab.SLOT_TEXT_W = SkillsTab.SLOT_W - 74 - 6

export type Tab = {
	update: (state: { [string]: any }) -> (),
	tick: (() -> ())?,
	reset: () -> (),
}

-- 못 익힌 술법·공법을 얻는 곳
local function lockedLine(def, state): string
	if state.step >= Realms.firstStepById[def.minRealm] then
		return "비급을 찾으면 익힐 수 있다"
	end
	return string.format("%s부터 익힐 수 있다", Realms.byId[def.minRealm].name)
end

-- 카드 하나: 그림 칸, 이름, 오른쪽 위 작은 글, 설명 두 줄
local function skillCard(list: Instance, def, clickable: boolean)
	local card, stroke = Kit.card(list, {
		Name = "Card_" .. def.id,
		Size = UDim2.fromOffset(SkillsTab.CELL_W, Kit.CARD_H),
	}, clickable)
	local frame, icon = Kit.slot(card, ICON, UDim2.fromOffset(9, 10), def.icon)
	local key, keyText = Kit.key(card, 22, 20, 14)
	key.Position = UDim2.fromOffset(3, 3)
	key.Visible = false
	local name = text("title", 19, { color = C.cream, text = def.name, name = "Name" })
	name.frame.Position = UDim2.fromOffset(TEXT_X - 4, 6)
	name.frame.Parent = card
	local corner = text("body", 14, { color = C.dim, name = "Corner" })
	corner.frame.AnchorPoint = Vector2.new(1, 0)
	corner.frame.Position = UDim2.new(1, -6, 0, 9)
	corner.frame.Parent = card
	local summary, setSummary = Ui.paragraph("body", 14, SkillsTab.TEXT_W, 2, C.dim, card)
	summary.Name = "Summary"
	summary.Position = UDim2.fromOffset(TEXT_X - 3, 33)
	return {
		card = card,
		stroke = stroke,
		frame = frame,
		icon = icon,
		key = key,
		keyText = keyText,
		name = name,
		corner = corner,
		setSummary = setSummary,
	}
end

-- 술법 갈래 -------------------------------------------------------------------------

function SkillsTab.buildActive(parent: Frame, ctx: Kit.Context): Tab
	local state: { [string]: any }? = nil
	-- 고른 것: 술법 카드({ kind = "skill", id }) 또는 단축칸({ kind = "slot", slot })
	local selected: { kind: string, id: string?, slot: number? }? = nil
	local slots: { { [string]: any } } = {}
	local cards: { [string]: { [string]: any } } = {}
	local hint, clearButton, clearText, cancelButton

	local function keyOf(slot: number): string
		if not state then
			return tostring(slot)
		end
		return if ctx.keyboard then state.keys[slot] else tostring(slot)
	end

	local function assign(slot: number, id: string)
		selected = nil
		ctx.actions.assign(slot, id)
		ctx.refresh()
	end

	local function clickSlot(slot: number)
		if not state then
			return
		end
		local current = state.hotbar[slot]
		if selected and selected.kind == "skill" then
			if current ~= selected.id then
				assign(slot, selected.id :: string)
				return
			end
			selected = nil
		elseif selected and selected.kind == "slot" and selected.slot == slot then
			selected = nil
		else
			selected = { kind = "slot", slot = slot }
		end
		ctx.refresh()
	end

	local function clickCard(id: string)
		if not state then
			return
		end
		local def = Skills.byId[id]
		if state.skills[id] ~= true then
			ctx.toast(string.format("%s: %s.", def.name, lockedLine(def, state)), "info")
			return
		end
		if selected and selected.kind == "slot" then
			local slot = selected.slot :: number
			if state.hotbar[slot] ~= id then
				assign(slot, id)
				return
			end
			selected = nil
		elseif selected and selected.kind == "skill" and selected.id == id then
			selected = nil
		else
			selected = { kind = "skill", id = id }
		end
		ctx.refresh()
	end

	-- 고른 술법이 든 칸, 또는 고른 칸 (비우기 버튼이 비울 칸)
	local function clearTarget(): number?
		if not state or not selected then
			return nil
		end
		if selected.kind == "slot" then
			local slot = selected.slot :: number
			local id = state.hotbar[slot]
			return if id and id ~= "" then slot else nil
		end
		return table.find(state.hotbar, selected.id)
	end

	-- 단축칸
	for slot = 1, HOTBAR do
		local card, stroke = Kit.card(parent, {
			Name = "Hotbar" .. slot,
			Position = UDim2.fromOffset(2 + (slot - 1) * (SkillsTab.SLOT_W + 10), 2),
			Size = UDim2.fromOffset(SkillsTab.SLOT_W, SLOT_H),
		}, true)
		local _, icon = Kit.slot(card, 56, UDim2.fromOffset(10, 12))
		local key, keyText = Kit.key(card, 30, 24, 15, ctx.keyboard)
		key.Position = UDim2.fromOffset(3, 3)
		local name = text("title", 18, { color = C.dim, name = "Name" })
		name.frame.Position = UDim2.fromOffset(72, 12)
		name.frame.Parent = card
		local cool = text("body", 14, { color = C.dim, name = "Cool" })
		cool.frame.Position = UDim2.fromOffset(73, 44)
		cool.frame.Parent = card
		card.Activated:Connect(function()
			clickSlot(slot)
		end)
		if ctx.keyboard then
			-- 키 표: 누르면 다음에 누르는 키를 이 칸에 묶는다
			key.Activated:Connect(function()
				selected = nil
				ctx.startBinding(slot)
			end)
		end
		slots[slot] =
			{ card = card, stroke = stroke, icon = icon, key = key, keyText = keyText, name = name, cool = cool }
	end

	-- 안내 줄과 고른 뒤 쓰는 버튼
	local hintRow = new("Frame", {
		Name = "Hint",
		Position = UDim2.fromOffset(2, HINT_Y),
		Size = UDim2.fromOffset(Kit.W - 4, 26),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	hint = text("body", 15, { color = C.dim, name = "Text" })
	hint.frame.Position = UDim2.fromOffset(0, 3)
	hint.frame.Parent = hintRow
	cancelButton = Ui.pill("취소", 62, 26, 14, hintRow, function()
		selected = nil
		ctx.refresh()
	end)
	cancelButton.Name = "Cancel"
	cancelButton.AnchorPoint = Vector2.new(1, 0)
	cancelButton.Position = UDim2.fromScale(1, 0)
	setImage(cancelButton, "pillStone")
	clearButton, clearText = Ui.pill("칸 비우기", 100, 26, 14, hintRow, function()
		local slot = clearTarget()
		if slot then
			assign(slot, "")
		end
	end)
	clearButton.Name = "Clear"
	clearButton.AnchorPoint = Vector2.new(1, 0)
	clearButton.Position = UDim2.new(1, -70, 0, 0)

	-- 술법 카드
	local list = Kit.grid(parent, {
		Name = "Cards",
		Position = UDim2.fromOffset(0, GRID_Y),
		Size = UDim2.fromOffset(Kit.W + Kit.GUTTER, Kit.H - GRID_Y),
	}, COLUMNS, Kit.CARD_H, ctx.touchOnly)
	for _, def in Skills.actives do
		local entry = skillCard(list, def, true)
		entry.corner:set(Kit.seconds(def.cooldown or 0))
		entry.card.Activated:Connect(function()
			clickCard(def.id)
		end)
		cards[def.id] = entry
	end

	local function update(newState)
		state = newState
		local binding = ctx.bindingSlot()
		-- 고른 술법을 잊었거나(되돌림) 칸이 없어졌으면 고르기를 푼다
		if selected and selected.kind == "skill" and newState.skills[selected.id] ~= true then
			selected = nil
		end
		local pickedSkill = if selected and selected.kind == "skill" then selected.id else nil
		local pickedSlot = if selected and selected.kind == "slot" then selected.slot else nil

		for slot, entry in slots do
			local id = newState.hotbar[slot]
			local def = if id and id ~= "" then Skills.byId[id] else nil
			entry.icon.Visible = def ~= nil
			if def then
				setImage(entry.icon, def.icon)
				entry.name:set(def.name)
			else
				entry.name:set("빈 칸")
			end
			entry.name:setColor(if def then C.cream else C.dim)
			entry.def = def
			local look: Kit.Look = if pickedSlot == slot
				then "on"
				elseif pickedSkill and newState.hotbar[slot] ~= pickedSkill then "target"
				else "normal"
			Kit.look(entry.card, entry.stroke, look)
			-- 키 표: 바꾸는 중이면 "?" (옥빛)
			local rebinding = binding == slot
			entry.keyText:set(if rebinding then "?" else keyOf(slot))
			entry.key.BackgroundColor3 = if rebinding then C.jade else C.keyBack
		end

		local known = 0
		local order = 0
		for _, def in Skills.actives do
			if newState.skills[def.id] == true then
				known += 1
			end
		end
		for _, pass in { true, false } do
			for _, def in Skills.actives do
				local isKnown = newState.skills[def.id] == true
				if isKnown ~= pass then
					continue
				end
				order += 1
				local entry = cards[def.id]
				entry.card.LayoutOrder = order
				local slot = table.find(newState.hotbar, def.id)
				entry.key.Visible = slot ~= nil and isKnown
				if slot then
					entry.keyText:set(keyOf(slot))
				end
				entry.icon.ImageColor3 = if isKnown then Color3.new(1, 1, 1) else Color3.fromRGB(70, 66, 60)
				entry.name:setColor(if pickedSkill == def.id then C.gold elseif isKnown then C.cream else C.dim)
				entry.setSummary(
					if isKnown then def.summary else lockedLine(def, newState),
					if isKnown then C.dim else Color3.fromRGB(150, 140, 118)
				)
				Kit.look(
					entry.card,
					entry.stroke,
					if pickedSkill == def.id
						then "on"
						elseif pickedSlot and isKnown and newState.hotbar[pickedSlot] ~= def.id then "target"
						elseif isKnown then "normal"
						else "dim"
				)
			end
		end

		-- 안내 줄
		local message, color = nil, C.dim
		if binding then
			message, color = string.format("%s 칸: 바꿀 키를 누른다", newState.keys[binding]), C.gold
		elseif pickedSkill then
			message, color = string.format("%s: 넣을 칸을 누른다", Skills.byId[pickedSkill].name), C.gold
		elseif pickedSlot then
			local label = if ctx.keyboard then keyOf(pickedSlot) .. " 칸" else string.format("%d번 칸", pickedSlot)
			message, color = string.format("%s: 넣을 술법을 누른다", label), C.gold
		elseif known == 0 then
			message, color = "아직 익힌 술법이 없다. 맵 곳곳에서 빛나는 비급을 찾는다.", C.cream
		elseif ctx.keyboard then
			message = "술법을 누르고 넣을 칸을 누른다. 키 표를 누르면 키를 바꾼다."
		else
			message = "술법을 누르고 넣을 칸을 누른다."
		end
		hint:set(message)
		hint:setColor(color)
		cancelButton.Visible = selected ~= nil
		local target = clearTarget()
		clearButton.Visible = target ~= nil
		clearText:set(if pickedSkill then "칸에서 빼기" else "칸 비우기")
	end

	-- 쿨타임: 단축칸에 남은 초 (열려 있을 때 Hud 가 프레임마다 부른다)
	local function tick()
		for _, entry in slots do
			local def = entry.def
			if not def then
				entry.cool:set("")
				continue
			end
			local left = ctx.cooldownLeft(def.id)
			if left > 0 then
				entry.cool:set(string.format("%d초 남음", math.ceil(left)))
				entry.cool:setColor(C.jade)
			else
				entry.cool:set("재사용 " .. Kit.seconds(def.cooldown or 0))
				entry.cool:setColor(C.dim)
			end
		end
	end

	return {
		update = function(newState)
			update(newState)
			tick()
		end,
		tick = tick,
		reset = function()
			selected = nil
		end,
		-- 이 칸을 고른 채로 (화면 아래 빈 단축칸을 눌렀을 때)
		pickSlot = function(slot: number)
			selected = { kind = "slot", slot = slot }
		end,
	} :: any
end

-- 공법 갈래 -------------------------------------------------------------------------

function SkillsTab.buildPassive(parent: Frame, ctx: Kit.Context): Tab
	local slots: { { [string]: any } } = {}
	local cards: { [string]: { [string]: any } } = {}
	local lastState: { [string]: any }? = nil

	-- 공법 칸 (처음 1칸, 경지에 따라 늘어난다)
	for index = 1, #Skills.SLOT_REALMS do
		local card, stroke = Kit.card(parent, {
			Name = "PassiveSlot" .. index,
			Position = UDim2.fromOffset(2 + (index - 1) * (SkillsTab.CELL_W + Kit.GAP_X), 2),
			Size = UDim2.fromOffset(SkillsTab.CELL_W, SLOT_H),
		})
		local frame, icon = Kit.slot(card, 52, UDim2.fromOffset(10, 14))
		local name = text("title", 19, { color = C.dim, name = "Name" })
		name.frame.Position = UDim2.fromOffset(70, 8)
		name.frame.Parent = card
		local sub, setSub = Ui.paragraph("body", 14, SkillsTab.CELL_W - 80, 2, C.dim, card)
		sub.Name = "Sub"
		sub.Position = UDim2.fromOffset(71, 35)
		slots[index] = { card = card, stroke = stroke, frame = frame, icon = icon, name = name, setSub = setSub }
	end

	local hintRow = new("Frame", {
		Name = "Hint",
		Position = UDim2.fromOffset(2, HINT_Y),
		Size = UDim2.fromOffset(Kit.W - 4, 26),
		BackgroundTransparency = 1,
		Parent = parent,
	})
	local count = text("body", 15, { color = C.gold, name = "Count" })
	count.frame.Position = UDim2.fromOffset(0, 3)
	count.frame.Parent = hintRow
	local hint = text("body", 15, { color = C.dim, name = "Text" })
	hint.frame.Position = UDim2.fromOffset(100, 3)
	hint.frame.Parent = hintRow

	local list = Kit.grid(parent, {
		Name = "Cards",
		Position = UDim2.fromOffset(0, GRID_Y),
		Size = UDim2.fromOffset(Kit.W + Kit.GUTTER, Kit.H - GRID_Y - 28),
	}, COLUMNS, Kit.CARD_H, ctx.touchOnly)
	-- 칸이 늘어나는 경지 (맨 아래 작은 글)
	local realmNames = {}
	for index = 2, #Skills.SLOT_REALMS do
		table.insert(realmNames, Realms.byId[Skills.SLOT_REALMS[index]].name)
	end
	local footer = text("body", 14, {
		color = Color3.fromRGB(150, 140, 118),
		name = "Footer",
		text = string.format(
			"공법 칸은 처음 한 칸이고, %s에 이르면 한 칸씩 늘어난다.",
			table.concat(realmNames, "와 ")
		),
	})
	footer.frame.Position = UDim2.fromOffset(2, Kit.H - 22)
	footer.frame.Parent = parent
	for _, def in Skills.passives do
		local entry = skillCard(list, def, false)
		local button, caption = Ui.pill("장착", 58, 28, 14, entry.card, function()
			local equipped = lastState ~= nil and table.find(lastState.equipped, def.id) ~= nil
			ctx.actions.equip(def.id, not equipped)
		end)
		button.Name = "Button"
		button.AnchorPoint = Vector2.new(1, 0)
		button.Position = UDim2.new(1, -7, 0, 6)
		entry.button, entry.buttonText = button, caption
		cards[def.id] = entry
	end

	local function update(state)
		lastState = state
		local free = #state.equipped < state.slots
		for index, entry in slots do
			local open = index <= state.slots
			local id = state.equipped[index]
			local def = if id then Skills.byId[id] else nil
			entry.icon.Visible = def ~= nil
			entry.frame.ImageColor3 = if open then Color3.new(1, 1, 1) else Color3.fromRGB(110, 104, 96)
			if def then
				setImage(entry.icon, def.icon)
				entry.name:set(def.name)
				entry.name:setColor(C.gold)
				entry.setSub(def.summary, C.jade)
			elseif open then
				entry.name:set("빈 칸")
				entry.name:setColor(C.cream)
				entry.setSub("아래에서 공법을 장착한다", C.dim)
			else
				entry.name:set("잠긴 칸")
				entry.name:setColor(C.dim)
				entry.setSub(
					string.format("%s부터 열린다", Realms.byId[Skills.SLOT_REALMS[index]].name),
					Color3.fromRGB(150, 140, 118)
				)
			end
			Kit.look(entry.card, entry.stroke, if def then "worn" elseif open then "normal" else "dim")
		end

		count:set(string.format("장착 %d / %d", #state.equipped, state.slots))
		local known = 0
		for _, def in Skills.passives do
			if state.skills[def.id] == true then
				known += 1
			end
		end
		hint:set(
			if known == 0
				then "아직 익힌 공법이 없다. 맵 곳곳에서 빛나는 비급을 찾는다."
				elseif not free then "칸이 모두 찼다. 바꾸려면 먼저 하나를 해제한다."
				else "장착한 공법은 늘 효과가 걸린다."
		)
		hint:setColor(if known == 0 then C.cream else C.dim)
		hint.frame.Position = UDim2.fromOffset(count.frame.Size.X.Offset + 10, 3)

		local order = 0
		for _, pass in { true, false } do
			for _, def in Skills.passives do
				local isKnown = state.skills[def.id] == true
				if isKnown ~= pass then
					continue
				end
				order += 1
				local entry = cards[def.id]
				local equipped = table.find(state.equipped, def.id) ~= nil
				entry.card.LayoutOrder = order
				entry.icon.ImageColor3 = if isKnown then Color3.new(1, 1, 1) else Color3.fromRGB(70, 66, 60)
				entry.name:setColor(if equipped then C.gold elseif isKnown then C.cream else C.dim)
				entry.setSummary(
					if isKnown then def.summary else lockedLine(def, state),
					if equipped then C.jade elseif isKnown then C.dim else Color3.fromRGB(150, 140, 118)
				)
				entry.button.Visible = isKnown
				if isKnown then
					setImage(entry.button, if equipped or not free then "pillStone" else "pillJade")
					entry.buttonText:set(if equipped then "해제" else "장착")
					entry.buttonText:setColor(if equipped or free then C.cream else C.dim)
				end
				Kit.look(entry.card, entry.stroke, if equipped then "worn" elseif isKnown then "normal" else "dim")
			end
		end
	end

	return {
		update = update,
		reset = function() end,
	}
end

return SkillsTab
