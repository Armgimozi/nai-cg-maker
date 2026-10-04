-- 화면 UI 를 Lune 의 Roblox 인스턴스로 실제로 만들어 본다.   실행: lune run tests/hud
--
-- Lune 은 속성 이름·타입을 Roblox 반영 DB 로 검사하므로, 잘못된 속성이 있으면 여기서 터진다.
-- 이벤트·트윈·입력 서비스는 Lune 에 없어서 가짜로 넣는다 (tests/hud_env.luau, tools/gui_snapshot 과 함께 쓴다).

local roblox = require("@lune/roblox") :: any
local task = require("@lune/task")
local HudEnv = require("./hud_env")

local hudEnv = HudEnv.new()
local fire, wrap = hudEnv.fire, hudEnv.wrap
local real, playerGui = hudEnv.real, hudEnv.playerGui
local tagged, purchases, chatMessages = hudEnv.tagged, hudEnv.purchases, hudEnv.chatMessages
local heartbeatKey = hudEnv.heartbeatKey
local sharedFolder = hudEnv.sharedFolder

-- 실제로 만들고 갱신해 본다 ----------------------------------------------------------

local loader = hudEnv.loader
local Hud = loader.require(loader.folder("src/client").Hud)

local noop = function() end
local sent: { [string]: any } = {}
local function record(name: string)
	return function(...)
		sent[name] = { ... }
	end
end
Hud.build({
	meditate = noop,
	breakthrough = noop,
	useSlot = noop,
	equip = record("equip"),
	assign = record("assign"),
	startTask = record("startTask"),
	skipTask = record("skipTask"),
	choose = record("choose"),
	eat = record("eat"),
	trialResult = record("trialResult"),
	trialCancel = record("trialCancel"),
	travel = record("travel"),
	buy = record("buy"),
	upgrade = record("upgrade"),
	craft = record("craft"),
	equipGuard = record("equipGuard"),
})

local function state(overrides)
	local s = {
		step = 5,
		qi = 120,
		req = 300,
		gain = 4.5,
		meditating = false,
		veinId = nil,
		needsBreak = false,
		ready = false,
		tasksDone = false,
		entry = nil,
		tasks = {},
		root = nil,
		choice = {},
		items = {},
		inTrial = false,
		skills = {},
		equipped = {},
		hotbar = { "", "", "", "" },
		keys = { "Q", "E", "Z", "X" },
		slots = 1,
		stats = { tribulations = 0, herbs = 0, manuals = 0 },
		inFormation = false,
		maxHealth = 125,
		tribulation = nil,
		canSave = true,
		stones = 30,
		weapons = { { kind = "sword", grade = 1 } },
		guards = {},
		guard = nil,
	}
	for k, v in overrides or {} do
		s[k] = v
	end
	return s
end

local Tasks0 = loader.require(sharedFolder.Tasks)
local Progression0 = loader.require(sharedFolder.Progression)
local Roots0 = loader.require(sharedFolder.Roots)
local function tasksFor(step: number, root)
	local data = Progression0.newData()
	data.step = step
	data.root = root
	return Tasks0.snapshot(data)
end

local cases = {
	{ "기본", state() },
	{ "범인 과업", state({ step = 1, tasks = tasksFor(1, nil) }) },
	{
		"단수기 과업",
		state({
			step = 2,
			root = Roots0.make({ "wood", "fire" }),
			tasks = tasksFor(2, Roots0.make({ "wood", "fire" })),
			items = { herb = 3, lingzhi = 1 },
		}),
	},
	{
		"돌파 준비 끝",
		state({
			step = 16,
			qi = 999,
			req = 999,
			ready = true,
			tasksDone = true,
			entry = { kind = "trial", title = "무극영운" },
		}),
	},
	{ "과업 남음", state({ step = 3, qi = 999, req = 999, tasksDone = false }) },
	{ "운기 중 + 영맥", state({ meditating = true, veinId = "low" }) },
	{
		"병목 천겁",
		state({
			step = 48,
			qi = 999,
			req = 999,
			ready = true,
			entry = { kind = "tribulation", title = "천겁 맞기" },
		}),
	},
	{
		"천겁 모이는 중",
		state({ step = 44, qi = 999, req = 999, tribulation = { name = "천겁", wave = 0, waves = 9 } }),
	},
	{
		"천겁 진행",
		state({ step = 44, qi = 999, req = 999, tribulation = { name = "천겁", wave = 3, waves = 9 } }),
	},
	{ "천겁 끝", state({ step = 45 }) },
	{
		"술법·공법 익힘",
		state({
			skills = { gyeongsin = true, yeongan = true, tonap = true, baekcho = true },
			equipped = { "tonap" },
			hotbar = { "gyeongsin", "", "yeongan", "" },
			keys = { "Q", "T", "Z", "X" },
		}),
	},
	{
		"공법 칸 가득",
		state({
			step = 45,
			slots = 3,
			skills = { tonap = true, baekcho = true, geumgang = true, piroe = true },
			equipped = { "tonap", "baekcho", "geumgang" },
			inFormation = true,
			veinId = "high",
		}),
	},
	{ "최고 경지", state({ step = 56, qi = 1e12, req = 1e12 }) },
	{
		"법구 가득",
		state({
			weapons = {
				{ kind = "sword", grade = 5 },
				{ kind = "saber", grade = 4 },
				{ kind = "spear", grade = 3 },
				{ kind = "fan", grade = 1 },
			},
			guards = {
				{ kind = "okpae", grade = 5 },
				{ kind = "palchi", grade = 1 },
				{ kind = "gabui", grade = 2 },
				{ kind = "jam", grade = 3 },
				{ kind = "bangul", grade = 4 },
				{ kind = "hwan", grade = 5 },
				{ kind = "gyeong", grade = 1 },
				{ kind = "tti", grade = 2 },
			},
			guard = "gabui",
		}),
	},
	-- 예전 서버처럼 법구 칸이 없는 상태도 견딘다
	{ "법구 칸 없음", state({ weapons = nil, guards = nil }) },
}
for _, case in cases do
	local ok, err = pcall(Hud.update, case[2])
	if not ok then
		error(`갱신 실패 [{case[1]}]: {err}`)
	end
end

Hud.toggleStatus()
Hud.toggleStatus(false)

-- 전송진 창: 열린 진만 고를 수 있고, 고르면 서버에 보낸다
Hud.update(state({
	waypoints = {
		{ id = "wp_home", name = "송계 마을", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = false },
	},
}))
-- 맵의 전송진(WorldSites 의 16 곳)이 모두 창에 들어가고, 이름이 칸 안에 들며, 창이 화면(1280×720 기준) 안에 든다
do
	local fs = require("@lune/fs")
	local many = {}
	for id, name in string.gmatch(fs.readFile("src/server/WorldSites.luau"), 'add%("wp", "([%w_]+)", "([^"]+)"') do
		table.insert(many, { id = id, name = name, open = true })
	end
	assert(#many == 16, `WorldSites 의 전송진 {#many}곳 (16)`)
	Hud.update(state({ waypoints = many }))
	Hud.openTravel(many[2].id)
	local menu = playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("TravelMenu")
	local shown, cellWidth = 0, nil
	for _, item in menu:GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			shown += 1
		elseif item:IsA("UIGridLayout") then
			cellWidth = item.CellSize.X.Offset
		end
	end
	assert(shown == #many, `전송진 {shown}개만 보인다 ({#many})`)
	local BitmapTextForMenu = loader.require(loader.folder("src/client").BitmapText)
	for _, point in many do
		local width = BitmapTextForMenu.measure("title", 19, point.name).X
		assert(width < cellWidth - 12, `{point.name} 이 칸({cellWidth})보다 넓다 ({width})`)
	end
	assert(BitmapTextForMenu.measure("title", 19, "가 보지 못한 곳").X < cellWidth - 12, "가 보지 못한 곳")
	assert(menu.Size.X.Offset <= 1280 - 80 and menu.Size.Y.Offset <= 720 - 80, `전송진 창이 크다 ({menu.Size})`)
	-- 진이 더 늘어도 스물까지는 들어간다
	local more = table.clone(many)
	for i = #many + 1, 20 do
		table.insert(more, { id = "wp_more" .. i, name = "청허경", open = true })
	end
	Hud.update(state({ waypoints = more }))
	Hud.openTravel(many[2].id)
	shown = 0
	for _, item in menu:GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			shown += 1
		end
	end
	assert(shown == 20, `전송진 {shown}개만 보인다 (20)`)
	Hud.closeTravel()
end
Hud.update(state({
	waypoints = {
		{ id = "wp_home", name = "송계 마을", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = false },
	},
}))
Hud.openTravel("wp_home")
assert(Hud.travelOpen(), "전송진 창이 열리지 않았다")
do
	local menu = playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("TravelMenu")
	local buttons = {}
	for _, item in menu:GetDescendants() do
		if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
			buttons[item.LayoutOrder] = item
		end
	end
	assert(buttons[1] and buttons[2] and buttons[3] and not buttons[4], "진 셋만 보여야 한다")
	fire(buttons[3], "Activated")
	assert(sent.travel == nil and Hud.travelOpen(), "닫힌 진은 고를 수 없다")
	fire(buttons[1], "Activated")
	assert(sent.travel == nil, "지금 선 진은 고를 수 없다")
	fire(buttons[2], "Activated")
	assert(sent.travel and sent.travel[1] == "wp_two", "고른 진을 보내야 한다")
	assert(not Hud.travelOpen(), "고르면 창이 닫힌다")
end

-- 영석 ------------------------------------------------------------------------------

-- BitmapText 틀에 찍힌 글자를 다시 읽는다 (빈칸은 그림이 없어서 빠진다)
local ArtGlyphs = loader.require(loader.folder("src/client").Art)
local glyphChars: { [string]: string } = {}
for _, font in ArtGlyphs.fonts do
	for ch, glyph in font.glyphs do
		glyphChars[`{font.pages[glyph[1]]}:{glyph[2]}:{glyph[3]}`] = ch
	end
end
local function readText(frame): string
	assert(frame, "글자 틀이 없다")
	local labels = {}
	for _, child in frame:GetChildren() do
		if child:IsA("ImageLabel") then
			table.insert(labels, child)
		end
	end
	table.sort(labels, function(a, b)
		return a.Position.X.Offset < b.Position.X.Offset
	end)
	local out = {}
	for _, label in labels do
		table.insert(out, glyphChars[`{label.Image}:{label.ImageRectOffset.X}:{label.ImageRectOffset.Y}`] or "?")
	end
	return table.concat(out)
end
-- 글자판에 있는 글자만 찍히므로, 기대하는 글에서도 빈칸과 글자판에 없는 글자는 빼고 견준다
-- (새 글자가 들어가 글자판을 다시 굽기 전에도 통과하게)
local function shows(frame, fontName: string, expected: string): boolean
	local out = {}
	for _, code in utf8.codes(expected) do
		local ch = utf8.char(code)
		local glyph = ArtGlyphs.fonts[fontName].glyphs[ch]
		if glyph and glyph[4] > 0 then
			table.insert(out, ch)
		end
	end
	return readText(frame) == table.concat(out)
end
local function find(root, name: string)
	for _, item in root:GetDescendants() do
		if item.Name == name then
			return item
		end
	end
	return nil
end
local UiForTest = loader.require(loader.folder("src/client").Ui)

do
	local hudGui = playerGui:FindFirstChild("BlockSuseonHud")
	-- 늘 보이는 영석 칸: 쉼표로 끊어 보이고, 늘면 잠깐 옥빛이 된다
	Hud.update(state({ stones = 1250 }))
	local counter = find(hudGui:FindFirstChild("Status"), "StoneText")
	assert(shows(counter, "body", "1,250"), `영석 칸 {readText(counter)} (1,250)`)
	-- 앞 상태(30)보다 늘어서 잠깐 빛났다가 금빛으로 돌아온다
	task.wait(1)
	local first = counter:FindFirstChildOfClass("ImageLabel")
	assert(first.ImageColor3 == UiForTest.C.gold, "영석 칸은 금빛이다")
	Hud.update(state({ stones = 1265 }))
	assert(shows(counter, "body", "1,265"), "영석이 늘면 숫자를 바꾼다")
	first = counter:FindFirstChildOfClass("ImageLabel")
	assert(first.ImageColor3 == UiForTest.C.jade, "영석이 늘면 잠깐 빛난다")
	-- 상태창 능력치에도 보인다
	local statShown = false
	for _, item in hudGui:FindFirstChild("StatusWindow"):GetDescendants() do
		if item.ClassName == "Frame" and shows(item, "body", "1,265개") then
			statShown = true
		end
	end
	assert(statShown, "상태창에 영석이 없다")

	-- 만물상: 물건, 무기, 영석 사기
	Hud.update(state({
		stones = 100,
		items = { herb = 3 },
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
	}))
	Hud.openShop("market")
	assert(Hud.shopOpen(), "상점 창이 열리지 않았다")
	local shop = hudGui:FindFirstChild("ShopWindow")
	local function shown(): { [number]: any }
		local out = {}
		for _, item in shop:GetDescendants() do
			if item.Name == "Row" and item.Visible then
				out[item.LayoutOrder] = item
			end
		end
		return out
	end
	local function count(list): number
		local n = 0
		for _ in list do
			n += 1
		end
		return n
	end
	local function buttonOf(rowFrame)
		return find(rowFrame, "Button")
	end
	local pillStone = ArtGlyphs.images.pillStone.id
	local Combat = loader.require(sharedFolder.Combat)
	local function weaponName(kind: string, grade: number): string
		return Combat.weaponName({ kind = kind, grade = grade })
	end
	assert(shows(find(shop, "Stones"), "body", "100"), "상점 창 머리에 지닌 영석이 보여야 한다")
	local rows = shown()
	assert(count(rows) == 4, `물건 {count(rows)}줄 (4)`)
	assert(shows(find(rows[1], "Name"), "title", "영초"), "첫 물건은 영초")
	assert(shows(find(rows[1], "Sub"), "body", "1개, 주머니에 3개"), readText(find(rows[1], "Sub")))
	assert(shows(find(rows[1], "Price"), "body", "15"), "영초 값")
	fire(buttonOf(rows[1]), "Activated")
	assert(sent.buy and sent.buy[1] == "herb1", "사기를 누르면 서버에 보낸다")
	sent.buy = nil
	-- 모자라면 버튼을 흐리게 하고 보내지 않는다
	assert(buttonOf(rows[2]).Image == pillStone, "못 사는 물건은 흐려야 한다")
	fire(buttonOf(rows[2]), "Activated")
	assert(sent.buy == nil, "영석이 모자라면 보내지 않는다")

	-- 법구 갈래: 공격 법구(도·창·선) 다음에 방어 법구 범품 여덟
	local Guards = loader.require(sharedFolder.Guards)
	assert(
		shows(find(shop, "Tab2"):FindFirstChild("Text", true), "body", "법구"),
		"만물상 둘째 갈래는 법구"
	)
	Hud.update(state({
		stones = 100,
		items = { herb = 3 },
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
		guards = { { kind = "jam", grade = 3 } },
		guard = "jam",
	}))
	fire(find(shop, "Tab2"), "Activated")
	rows = shown()
	assert(count(rows) == 3 + #Guards.KINDS, `법구 {count(rows)}줄 ({3 + #Guards.KINDS})`)
	assert(shows(find(rows[1], "Name"), "title", weaponName("saber", 1)), readText(find(rows[1], "Name")))
	assert(
		shows(find(rows[1], "Sub"), "body", "공격 법구, " .. Combat.KINDS.saber.summary),
		readText(find(rows[1], "Sub"))
	)
	assert(shows(find(buttonOf(rows[1]), "Text"), "body", "지님"), "지닌 종류는 지님")
	fire(buttonOf(rows[1]), "Activated")
	assert(sent.buy == nil, "지닌 종류는 다시 사지 않는다")
	fire(buttonOf(rows[2]), "Activated")
	assert(sent.buy and sent.buy[1] == "spear", "창을 산다")
	sent.buy = nil
	for index, id in Guards.ORDER do
		local guardRow = rows[3 + index]
		local ware = { kind = id, grade = 1 }
		assert(shows(find(guardRow, "Name"), "title", Guards.name(ware)), readText(find(guardRow, "Name")))
		assert(
			shows(find(guardRow, "Sub"), "body", "방어 법구, " .. Guards.effects(ware)),
			readText(find(guardRow, "Sub"))
		)
		assert(shows(find(guardRow, "Price"), "body", tostring(Guards.SHOP_PRICE)), "방어 법구 값")
	end
	-- 청운잠은 이미 지녔다 (더 높은 등급이어도): 흐린 "지님", 보내지 않는다
	local jamRow = rows[3 + table.find(Guards.ORDER, "jam")]
	assert(shows(find(buttonOf(jamRow), "Text"), "body", "지님"), "지닌 방어 법구는 지님")
	assert(buttonOf(jamRow).Image == pillStone, "지닌 방어 법구는 흐리다")
	fire(buttonOf(jamRow), "Activated")
	assert(sent.buy == nil, "지닌 방어 법구는 다시 사지 않는다")
	local okpaeRow = rows[3 + table.find(Guards.ORDER, "okpae")]
	assert(shows(find(buttonOf(okpaeRow), "Text"), "body", "사기"), "지니지 않은 방어 법구는 사기")
	fire(buttonOf(okpaeRow), "Activated")
	assert(sent.buy and sent.buy[1] == "guard_okpae", "방어 법구를 산다")
	sent.buy = nil
	-- 안내 글이 창 안에 들고, 설명 줄이 값(오른쪽)과 겹치지 않는다
	assert(
		shows(
			find(shop, "Hint"),
			"body",
			"법구는 종류마다 하나씩 지닌다. 방어 법구는 한 번에 하나만 지닌다."
		),
		"법구 안내"
	)
	assert(
		find(shop, "Hint").Size.X.Offset < 600,
		`법구 안내가 창보다 넓다 ({find(shop, "Hint").Size.X.Offset})`
	)
	local SUB_MAX = 560 - 96 - 70
	for _, guardRow in rows do
		local sub = find(guardRow, "Sub")
		assert(sub.Size.X.Offset < SUB_MAX, `{readText(find(guardRow, "Name"))} 설명이 값과 겹친다`)
	end

	fire(find(shop, "Tab3"), "Activated")
	rows = shown()
	assert(count(rows) == 3, `영석 묶음 {count(rows)}줄 (3)`)
	assert(shows(find(rows[1], "Name"), "title", "영석 한 줌"), "묶음 이름")
	assert(shows(find(rows[1], "Sub"), "body", "영석 120개"), "묶음 영석")
	assert(shows(find(buttonOf(rows[1]), "Text"), "body", "25 로벅스"), "묶음 값")
	fire(buttonOf(rows[2]), "Activated")
	local Currency = loader.require(sharedFolder.Currency)
	assert(purchases[1] == Currency.PACKS[2].productId, "로벅스 상품 창을 띄워야 한다")

	-- 열려 있는 동안 상태가 오면 다시 그린다
	fire(find(shop, "Tab2"), "Activated")
	Hud.update(state({ stones = 10, weapons = { { kind = "sword", grade = 1 } } }))
	assert(shows(find(shop, "Stones"), "body", "10"), "상태가 오면 머리 영석을 바꾼다")
	rows = shown()
	assert(shows(find(buttonOf(rows[1]), "Text"), "body", "사기"), "지니지 않은 종류는 사기")
	assert(buttonOf(rows[1]).Image == pillStone, "모자라면 흐려진다")

	-- 대장간: 지닌 무기마다 다음 등급과 값. 최고 등급은 버튼이 없다
	Hud.update(state({
		stones = 100,
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
	}))
	Hud.openShop("smith")
	assert(Hud.shopOpen(), "대장간 창이 열리지 않았다")
	-- 대장간 갈래는 강화와 제작 둘. 처음에는 강화
	assert(find(shop, "Tab1").Visible and find(shop, "Tab2").Visible, "대장간 갈래 둘")
	assert(not find(shop, "Tab3").Visible, "대장간에는 셋째 갈래가 없다")
	assert(shows(find(shop, "Tab1"):FindFirstChild("Text", true), "body", "강화"), "대장간 첫 갈래는 강화")
	assert(
		shows(find(shop, "Tab2"):FindFirstChild("Text", true), "body", "제작"),
		"대장간 둘째 갈래는 제작"
	)
	rows = shown()
	assert(count(rows) == 3, `대장간 {count(rows)}줄 (3)`)
	assert(shows(find(rows[1], "Name"), "title", weaponName("sword", 1)), "첫 무기")
	assert(
		shows(
			find(rows[1], "Sub"),
			"body",
			string.format("%s 등급, 강화하면 %s", Combat.GRADES[1].prefix, weaponName("sword", 2))
		),
		readText(find(rows[1], "Sub"))
	)
	assert(shows(find(rows[1], "Price"), "body", "120"), "목→철 값")
	assert(shows(find(rows[3], "Name"), "title", weaponName("fan", 5)), "부채 최고 등급")
	assert(shows(find(rows[3], "Price"), "body", "최고 등급"), "최고 등급은 값 대신")
	assert(not buttonOf(rows[3]).Visible, "최고 등급은 강화 버튼이 없다")
	fire(buttonOf(rows[1]), "Activated")
	assert(sent.upgrade == nil, "영석이 모자라면 강화를 보내지 않는다")
	Hud.update(state({
		stones = 500,
		weapons = { { kind = "sword", grade = 1 }, { kind = "saber", grade = 2 }, { kind = "fan", grade = 5 } },
	}))
	fire(buttonOf(rows[2]), "Activated")
	assert(sent.upgrade and sent.upgrade[1] == 2, "그 칸 공격 법구를 강화한다")
	-- 공격 법구가 없으면 빈 글
	Hud.update(state({ stones = 500, weapons = {} }))
	assert(count(shown()) == 0 and find(shop, "Empty").Visible, "공격 법구가 없으면 빈 글")
	assert(shows(find(shop, "Empty"), "body", "지닌 공격 법구가 없다."), readText(find(shop, "Empty")))

	-- 제작: 종류마다 다음 등급 (없으면 범품), 극품이면 최고 등급. 영석과 재료(지닌 수/드는 수)
	local Balance = loader.require(sharedFolder.Balance)
	Hud.update(state({
		stones = 600,
		items = { yodan = 20, lingzhi = 0, herb = 2 },
		guards = { { kind = "okpae", grade = 2 }, { kind = "palchi", grade = 1 }, { kind = "hwan", grade = 5 } },
		guard = "okpae",
	}))
	fire(find(shop, "Tab2"), "Activated")
	assert(not find(shop, "Empty").Visible, "제작 갈래에는 빈 글이 없다")
	rows = shown()
	assert(count(rows) == #Guards.KINDS, `제작 {count(rows)}줄 ({#Guards.KINDS})`)
	local function craftRow(id: string)
		return rows[table.find(Guards.ORDER, id)]
	end
	-- 호신옥패 하품 → 중품: 영석 500, 요단 16, 천년영지 1 (천년영지가 모자라다)
	local okpaeCraft = craftRow("okpae")
	assert(shows(find(okpaeCraft, "Name"), "title", Guards.name({ kind = "okpae", grade = 3 })), "다음 등급")
	assert(
		shows(
			find(okpaeCraft, "Sub"),
			"body",
			Guards.effects({ kind = "okpae", grade = 3 }) .. " (지금 " .. Guards.GRADES[2] .. ")"
		),
		readText(find(okpaeCraft, "Sub"))
	)
	assert(shows(find(okpaeCraft, "Price"), "body", tostring(Guards.CRAFT[3].stones)), "제작 영석")
	assert(find(okpaeCraft, "Cost").Visible, "재료 줄이 보여야 한다")
	-- 재료는 주머니 순서(Balance.ITEM_ORDER)로, 지닌 수/드는 수
	assert(
		shows(
			find(okpaeCraft, "Cost"),
			"body",
			string.format("재료 %s 0/1, %s 20/16", Balance.ITEMS.lingzhi.name, Balance.ITEMS.yodan.name)
		),
		readText(find(okpaeCraft, "Cost"))
	)
	assert(
		find(okpaeCraft, "Cost"):FindFirstChildOfClass("ImageLabel").ImageColor3 == UiForTest.C.red,
		"재료가 모자라면 붉다"
	)
	assert(buttonOf(okpaeCraft).Image == pillStone, "재료가 모자라면 흐리다")
	fire(buttonOf(okpaeCraft), "Activated")
	assert(sent.craft == nil, "재료가 모자라면 보내지 않는다")
	-- 금강팔찌 범품 → 하품: 영석 160, 요단 8, 영초 4 (영초가 모자라다)
	local palchiCraft = craftRow("palchi")
	assert(
		shows(find(palchiCraft, "Name"), "title", Guards.name({ kind = "palchi", grade = 2 })),
		"팔찌 다음 등급"
	)
	fire(buttonOf(palchiCraft), "Activated")
	assert(sent.craft == nil, "영초가 모자라면 보내지 않는다")
	-- 현무갑의는 없으니 범품: 영석 40, 요단 3 → 만들 수 있다
	local gabuiCraft = craftRow("gabui")
	assert(shows(find(gabuiCraft, "Name"), "title", Guards.name({ kind = "gabui", grade = 1 })), "없으면 범품")
	assert(
		shows(find(gabuiCraft, "Sub"), "body", Guards.effects({ kind = "gabui", grade = 1 })),
		readText(find(gabuiCraft, "Sub"))
	)
	assert(
		shows(find(gabuiCraft, "Cost"), "body", string.format("재료 %s 20/3", Balance.ITEMS.yodan.name)),
		readText(find(gabuiCraft, "Cost"))
	)
	assert(
		find(gabuiCraft, "Cost"):FindFirstChildOfClass("ImageLabel").ImageColor3 == UiForTest.C.jade,
		"넉넉하면 옥빛"
	)
	assert(shows(find(buttonOf(gabuiCraft), "Text"), "body", "만들기"), "만들기 버튼")
	assert(buttonOf(gabuiCraft).Image ~= pillStone, "만들 수 있으면 밝다")
	fire(buttonOf(gabuiCraft), "Activated")
	assert(sent.craft and sent.craft[1] == "gabui" and sent.craft[2] == 1, "현무갑의 범품을 만든다")
	sent.craft = nil
	-- 회춘환은 극품: 최고 등급, 버튼 없음
	local hwanCraft = craftRow("hwan")
	assert(shows(find(hwanCraft, "Name"), "title", Guards.name({ kind = "hwan", grade = 5 })), "극품 이름")
	assert(shows(find(hwanCraft, "Price"), "body", "최고 등급"), "극품은 최고 등급")
	assert(
		not buttonOf(hwanCraft).Visible and not find(hwanCraft, "Cost").Visible,
		"극품은 만들기와 재료가 없다"
	)
	assert(
		shows(
			find(shop, "Hint"),
			"body",
			"방어 법구를 만든다. 같은 종류는 더 높은 등급으로 바뀐다."
		),
		"제작 안내"
	)
	-- 어느 등급이든 설명 줄은 값과 겹치지 않고, 재료 줄은 줄 안에 든다
	for grade = 0, #Guards.GRADES - 1 do
		local all = {}
		for _, id in Guards.ORDER do
			if grade > 0 then
				table.insert(all, { kind = id, grade = grade })
			end
		end
		Hud.update(state({ stones = 0, guards = all }))
		for _, craft in shown() do
			local label = readText(find(craft, "Name"))
			assert(find(craft, "Sub").Size.X.Offset < SUB_MAX, `{label} 설명이 값과 겹친다`)
			assert(find(craft, "Cost").Size.X.Offset < 560 - 96, `{label} 재료 줄이 넓다`)
			assert(
				craft.Size.Y.Offset >= 51 + find(craft, "Cost").Size.Y.Offset,
				`{label} 재료 줄이 줄 밖으로 나간다`
			)
		end
	end
	-- 영석이 모자라면 보내지 않는다
	Hud.update(state({ stones = 10, items = { yodan = 20 } }))
	assert(shows(find(craftRow("gabui"), "Price"), "body", "40"), "범품 영석 40")
	fire(buttonOf(craftRow("gabui")), "Activated")
	assert(sent.craft == nil, "영석이 모자라면 만들지 않는다")
	-- 다시 열면 강화부터
	Hud.closeShop()
	Hud.openShop("smith")
	assert(shows(find(shown()[1], "Name"), "title", weaponName("sword", 1)), "다시 열면 강화 갈래")
	-- 대장간 뒤에 만물상을 열면 물건 갈래와 셋째 갈래가 돌아온다
	Hud.openShop("market")
	assert(find(shop, "Tab3").Visible, "만물상 갈래 셋")
	assert(shows(find(shown()[1], "Name"), "title", "영초"), "만물상은 물건부터")

	-- 상태창을 열면 상점 창은 닫힌다
	Hud.toggleStatus(true)
	assert(not Hud.shopOpen(), "상태창을 열면 상점 창을 닫는다")
	assert(Hud.statusOpen(), "상태창이 열려야 한다")

	-- 상태창 ---------------------------------------------------------------------------
	-- 왼쪽 인물 칸(늘 보인다)과 갈래 넷: 술법(단축칸), 공법, 법구, 주머니
	local window = hudGui:FindFirstChild("StatusWindow")
	local client = loader.folder("src/client")
	local StatusWindow = loader.require(client.StatusWindow)
	local SkillsTab = loader.require(client.SkillsTab)
	local BeopguTab = loader.require(client.BeopguTab)
	local PouchTab = loader.require(client.PouchTab)
	local Kit = loader.require(client.StatusKit)
	local SkillsShared = loader.require(sharedFolder.Skills)
	local RealmsShared = loader.require(sharedFolder.Realms)
	local Balance = loader.require(sharedFolder.Balance)
	local C = UiForTest.C
	local function page(key: string)
		return window:FindFirstChild("Page_" .. key)
	end
	local function anyText(root, fontName: string, expected: string): boolean
		for _, item in root:GetDescendants() do
			if item.ClassName == "Frame" and shows(item, fontName, expected) then
				return true
			end
		end
		return false
	end
	-- 글 조각이 들어 있는 글줄이 있는가 (여러 줄로 나뉜 설명의 앞부분 따위)
	local function hasText(root, fontName: string, fragment: string): boolean
		local out = {}
		for _, code in utf8.codes(fragment) do
			local ch = utf8.char(code)
			local glyph = ArtGlyphs.fonts[fontName].glyphs[ch]
			if glyph and glyph[4] > 0 then
				table.insert(out, ch)
			end
		end
		local wanted = table.concat(out)
		for _, item in root:GetDescendants() do
			if item.ClassName == "Frame" and item:FindFirstChild("g") then
				if string.find(readText(item), wanted, 1, true) then
					return true
				end
			end
		end
		return false
	end
	local function text(root, name: string): string
		return readText(find(root, name))
	end
	local function color(frame)
		local glyph = frame:FindFirstChildOfClass("ImageLabel")
		return glyph and glyph.ImageColor3
	end

	-- 창 크기: Hud 배율(폰 가로 844×390 은 0.6)로 줄이면 위쪽 막대(58px) 아래에 든다
	local scale = math.clamp(math.min(844 / 1280, 390 / 720), 0.6, 1)
	assert(window.Size.X.Offset * scale <= 844 - 16, "상태창이 폰 화면보다 넓다")
	assert(
		window.Size.Y.Offset * scale <= 390 - 58,
		`상태창이 폰 화면보다 높다 ({window.Size.Y.Offset * scale})`
	)
	assert(
		window.Size.X.Offset <= 1280 - 80 and window.Size.Y.Offset <= 720 - 58 - 40,
		"상태창이 1280×720 에 크다"
	)
	assert(window:FindFirstChildOfClass("UIScale"), "상태창은 Hud 배율을 따른다")
	-- 더 작은 폰(667×375)에서는 위쪽 막대 아래에 들게 조금 더 줄이고, 큰 화면에서는 Hud 배율 그대로
	StatusWindow.fit(roblox.Vector2.new(667, 375), 0.6)
	local small = window:FindFirstChildOfClass("UIScale").Scale
	assert(small < 0.6 and window.Size.Y.Offset * small <= 375 - 58 - 8 + 0.01, `작은 폰 배율 {small}`)
	StatusWindow.fit(roblox.Vector2.new(844, 390), 0.6)
	assert(
		math.abs(window:FindFirstChildOfClass("UIScale").Scale - 0.6) < 1e-6,
		"폰 가로는 Hud 배율 0.6 그대로"
	)
	StatusWindow.fit(roblox.Vector2.new(1920, 1080), 1)
	assert(window:FindFirstChildOfClass("UIScale").Scale == 1, "큰 화면은 Hud 배율 그대로")

	-- 갈래 단추: 누르면 그 갈래만 보이고, 닫았다 열어도 마지막 갈래를 기억한다
	Hud.update(state({ stones = 1265, race = "human" }))
	for index, def in StatusWindow.TABS do
		local button = window:FindFirstChild("Tab_" .. def.key, true)
		assert(button and shows(find(button, "Text"), "body", def.label), `갈래 단추 {def.label}`)
		fire(button, "Activated")
		assert(Hud.statusTab() == def.key, `갈래 {def.key} 로 바뀌어야 한다`)
		for _, other in StatusWindow.TABS do
			assert(
				page(other.key).Visible == (other.key == def.key),
				`{def.key} 갈래에서 {other.key} 쪽이 보인다`
			)
		end
		assert(button.Image == ArtGlyphs.images.pillJade.id, "고른 갈래는 옥빛")
		Hud.setStatusTab(index)
		assert(Hud.statusTab() == def.key, "번호로도 갈래를 고른다")
	end
	Hud.setStatusTab("법구")
	assert(Hud.statusTab() == "gear", "글자로도 갈래를 고른다")
	Hud.toggleStatus(false)
	Hud.toggleStatus(true)
	assert(Hud.statusTab() == "gear" and page("gear").Visible, "다시 열면 마지막 갈래")
	fire(find(window, "Close"), "Activated")
	assert(not Hud.statusOpen(), "닫기 단추")
	Hud.toggleStatus(true)

	-- 인물 칸: 능력치, 종족 효과, 확률 창, 다시 뽑기 (확률 창은 갈래와 상관없이)
	local character = find(window, "Character")
	assert(anyText(character, "body", "1,265개"), "인물 칸에 영석이 없다")
	assert(anyText(character, "body", "125"), "인물 칸에 체력이 없다")
	assert(find(character, "PlayerName").Text == "", "이름 (가짜 환경은 빈 이름)")
	local oddsPanel = find(window, "OddsPanel")
	assert(not oddsPanel.Visible, "확률 창은 접혀 있다")
	fire(find(character, "Odds"), "Activated")
	assert(oddsPanel.Visible and oddsPanel.Active, "확률 보기를 누르면 확률 창 (뒤를 누르지 못하게)")
	local shade = find(window, "OddsShade")
	assert(shade.Visible, "확률 창 뒤 갈래 자리는 그늘로 덮는다")
	assert(anyText(oddsPanel, "body", "지금 종족"), "지금 종족은 다시 뽑아도 나오지 않는다")
	fire(shade, "Activated")
	assert(not oddsPanel.Visible and not shade.Visible, "그늘을 누르면 확률 창을 닫는다")
	fire(find(character, "Odds"), "Activated")
	Hud.toggleStatus(false)
	assert(not oddsPanel.Visible and not shade.Visible, "상태창을 닫으면 확률 창도 접는다")
	Hud.toggleStatus(true)
	local RacesShared = loader.require(sharedFolder.Races)
	local before = #purchases
	fire(find(character, "Reroll"), "Activated")
	if RacesShared.REROLL_PRODUCT_ID ~= 0 then
		assert(purchases[#purchases] == RacesShared.REROLL_PRODUCT_ID, "다시 뽑기는 로벅스 상품 창")
	else
		assert(#purchases == before, "상품이 없으면 사지 않는다")
	end

	-- 술법 갈래 ----------------------------------------------------------------------
	Hud.setStatusTab("skills")
	local skills = page("skills")
	local learned = {
		skills = { gyeongsin = true, yeongan = true, chwiryeong = true },
		hotbar = { "gyeongsin", "", "", "" },
		keys = { "Q", "E", "Z", "X" },
	}
	Hud.update(state(learned))
	local slot1, slot2 = find(skills, "Hotbar1"), find(skills, "Hotbar2")
	assert(
		shows(find(slot1, "Name"), "title", "경신술") and shows(find(slot2, "Name"), "title", "빈 칸"),
		"단축칸 이름"
	)
	assert(shows(find(find(slot1, "Key"), "Text"), "body", "Q"), "단축칸 키")
	assert(shows(find(slot1, "Cool"), "body", "재사용 5초"), text(slot1, "Cool"))
	assert(find(slot1, "Icon").Visible and not find(slot2, "Icon").Visible, "빈 칸은 그림이 없다")
	-- 카드: 익힌 것 먼저, 못 익힌 것은 얻는 곳
	local cardYeongan, cardHosin = find(skills, "Card_yeongan"), find(skills, "Card_hosin")
	assert(cardYeongan.LayoutOrder < cardHosin.LayoutOrder, "익힌 술법이 앞에")
	assert(hasText(cardYeongan, "body", "영초와 비급이"), "술법 카드 설명")
	assert(shows(find(cardYeongan, "Corner"), "body", "30초"), "술법 카드 쿨타임")
	local hosinDef = SkillsShared.byId.hosin
	assert(
		hasText(cardHosin, "body", string.format("%s부터", RealmsShared.byId[hosinDef.minRealm].name)),
		"못 익힌 술법은 얻는 곳"
	)
	assert(find(find(skills, "Card_gyeongsin"), "Key").Visible, "단축칸에 든 술법 카드에 키 표")
	assert(not find(cardYeongan, "Key").Visible, "단축칸에 없는 술법은 키 표가 없다")
	-- 카드를 누르고 칸을 누르면 넣는다
	sent.assign = nil
	fire(cardYeongan, "Activated")
	assert(sent.assign == nil, "카드만 누르면 아직 보내지 않는다")
	assert(find(cardYeongan, "UIStroke").Thickness == 2, "고른 카드는 금테")
	assert(anyText(find(skills, "Hint"), "body", "영안: 넣을 칸을 누른다"), "고르면 안내")
	assert(find(slot2, "UIStroke").Color == C.jade, "넣을 수 있는 칸은 옥테")
	fire(slot2, "Activated")
	assert(sent.assign and sent.assign[1] == 2 and sent.assign[2] == "yeongan", "고른 술법을 누른 칸에")
	assert(find(cardYeongan, "UIStroke").Thickness == 1, "넣으면 고르기를 푼다")
	-- 칸을 먼저 누르고 카드를 눌러도 된다
	sent.assign = nil
	fire(find(skills, "Hotbar3"), "Activated")
	assert(anyText(find(skills, "Hint"), "body", "Z 칸: 넣을 술법을 누른다"), "칸을 고르면 안내")
	fire(find(skills, "Card_chwiryeong"), "Activated")
	assert(sent.assign and sent.assign[1] == 3 and sent.assign[2] == "chwiryeong", "고른 칸에 누른 술법을")
	-- 이미 그 칸에 있으면 보내지 않고 고르기만 푼다
	sent.assign = nil
	fire(find(skills, "Card_gyeongsin"), "Activated")
	fire(slot1, "Activated")
	assert(sent.assign == nil, "같은 칸이면 보내지 않는다")
	-- 칸 비우기 / 칸에서 빼기 / 취소
	fire(slot1, "Activated")
	local clear, cancel = find(skills, "Clear"), find(skills, "Cancel")
	assert(clear.Visible and cancel.Visible, "칸을 고르면 비우기·취소")
	fire(clear, "Activated")
	assert(sent.assign and sent.assign[1] == 1 and sent.assign[2] == "", "칸 비우기")
	sent.assign = nil
	fire(find(skills, "Card_gyeongsin"), "Activated")
	assert(shows(find(clear, "Text"), "body", "칸에서 빼기"), "단축칸에 든 술법을 고르면 빼기")
	fire(cancel, "Activated")
	assert(not clear.Visible and not cancel.Visible and sent.assign == nil, "취소")
	-- 못 익힌 술법은 고르지 못한다
	fire(cardHosin, "Activated")
	fire(slot2, "Activated")
	assert(sent.assign == nil or sent.assign[2] ~= "hosin", "못 익힌 술법은 넣지 않는다")
	fire(slot2, "Activated")
	sent.assign = nil
	-- 키 표를 누르면 키 바꾸기 (다음에 누르는 키, Main.client 가 BindKey 를 보낸다)
	fire(find(slot2, "Key"), "Activated")
	assert(Hud.bindingSlot() == 2, "키 표를 누르면 그 칸 키 바꾸기")
	assert(shows(find(find(slot2, "Key"), "Text"), "body", "?"), "바꾸는 칸은 ?")
	assert(anyText(find(skills, "Hint"), "body", "E 칸: 바꿀 키를 누른다"), "키 바꾸기 안내")
	Hud.stopBinding()
	assert(shows(find(find(slot2, "Key"), "Text"), "body", "E"), "키 바꾸기가 끝나면 키")
	-- 쿨타임: 열려 있으면 단축칸에 남은 초
	Hud.skillUsed({ id = "gyeongsin", cooldown = 5 })
	fire(heartbeatKey, "Heartbeat", 0.016)
	assert(shows(find(slot1, "Cool"), "body", "5초 남음"), text(slot1, "Cool"))
	assert(color(find(slot1, "Cool")) == C.jade, "쿨타임 중은 옥빛")
	-- 익힌 술법이 없으면 안내
	Hud.update(state())
	assert(hasText(find(skills, "Hint"), "body", "아직 익힌 술법이 없다"), "빈 술법 안내")
	-- 화면 아래 빈 단축칸을 누르면 상태창 술법 갈래가 그 칸을 고른 채 열린다
	Hud.update(state(learned))
	Hud.setStatusTab("pouch")
	Hud.toggleStatus(false)
	local hotbarGui = hudGui:FindFirstChild("Hotbar")
	local hotbarButtons = {}
	for _, item in hotbarGui:GetDescendants() do
		if item:IsA("ImageButton") then
			hotbarButtons[item.Parent.LayoutOrder] = item
		end
	end
	fire(hotbarButtons[4], "Activated")
	assert(Hud.statusOpen() and Hud.statusTab() == "skills", "빈 단축칸을 누르면 술법 갈래")
	assert(anyText(find(skills, "Hint"), "body", "X 칸: 넣을 술법을 누른다"), "그 칸이 골라져 있다")
	fire(find(skills, "Card_yeongan"), "Activated")
	assert(sent.assign and sent.assign[1] == 4 and sent.assign[2] == "yeongan", "카드를 누르면 바로 그 칸에")
	sent.assign = nil

	-- 공법 갈래 ----------------------------------------------------------------------
	Hud.setStatusTab("passives")
	local passives = page("passives")
	Hud.update(state({
		step = 20,
		slots = 2,
		skills = { tonap = true, baekcho = true, geumgang = true },
		equipped = { "tonap" },
	}))
	assert(shows(find(find(passives, "PassiveSlot1"), "Name"), "title", "토납법"), "장착한 공법 칸")
	assert(shows(find(find(passives, "PassiveSlot2"), "Name"), "title", "빈 칸"), "빈 공법 칸")
	local lockedSlot = find(passives, "PassiveSlot3")
	assert(shows(find(lockedSlot, "Name"), "title", "잠긴 칸"), "잠긴 공법 칸")
	local lastRealm = RealmsShared.byId[SkillsShared.SLOT_REALMS[3]].name
	assert(hasText(lockedSlot, "body", lastRealm .. "부터 열린다"), "왜 잠겼는지")
	assert(anyText(find(passives, "Hint"), "body", "장착 1 / 2"), "장착 수")
	local tonap, baekcho, piroe =
		find(passives, "Card_tonap"), find(passives, "Card_baekcho"), find(passives, "Card_piroe")
	assert(shows(find(buttonOf(tonap), "Text"), "body", "해제"), "장착한 공법은 해제")
	assert(shows(find(buttonOf(baekcho), "Text"), "body", "장착"), "나머지는 장착")
	assert(not buttonOf(piroe).Visible, "못 익힌 공법은 단추가 없다")
	sent.equip = nil
	fire(buttonOf(tonap), "Activated")
	assert(sent.equip and sent.equip[1] == "tonap" and sent.equip[2] == false, "해제를 보낸다 (Unequip)")
	fire(buttonOf(baekcho), "Activated")
	assert(sent.equip and sent.equip[1] == "baekcho" and sent.equip[2] == true, "장착을 보낸다 (Equip)")
	Hud.update(state({ slots = 1, skills = { tonap = true, baekcho = true }, equipped = { "tonap" } }))
	assert(buttonOf(baekcho).Image == pillStone, "칸이 다 차면 장착 단추가 흐리다")
	assert(hasText(find(passives, "Hint"), "body", "칸이 모두 찼다"), "칸이 다 찬 안내")

	-- 법구 갈래 ----------------------------------------------------------------------
	Hud.setStatusTab("gear")
	local gear = page("gear")
	Hud.update(state({
		weapons = { { kind = "sword", grade = 2 }, { kind = "fan", grade = 1 } },
		guards = { { kind = "okpae", grade = 2 }, { kind = "jam", grade = 1 } },
		guard = "okpae",
	}))
	assert(anyText(gear, "title", "공격 법구") and anyText(gear, "title", "방어 법구"), "법구 갈래 제목")
	local weapon1, weapon2, weapon3 = find(gear, "Weapon1"), find(gear, "Weapon2"), find(gear, "Weapon3")
	assert(weapon1.Visible and weapon2.Visible and not weapon3.Visible, "지닌 공격 법구만 보인다")
	assert(shows(find(weapon1, "Name"), "title", weaponName("sword", 2)), text(weapon1, "Name"))
	assert(
		shows(find(weapon1, "Stats"), "body", BeopguTab.weaponStats({ kind = "sword", grade = 2 })),
		text(weapon1, "Stats")
	)
	assert(shows(find(weapon1, "Sub"), "body", Combat.KINDS.sword.summary), text(weapon1, "Sub"))
	assert(shows(find(weapon1, "Tag"), "body", Combat.GRADES[2].prefix .. " 등급"), text(weapon1, "Tag"))
	assert(shows(find(find(weapon2, "Key"), "Text"), "body", "2"), "둘째 공격 법구는 숫자 키 2")
	assert(shows(find(weapon2, "Name"), "title", weaponName("fan", 1)), "죽선")
	assert(not find(gear, "WeaponEmpty").Visible, "공격 법구가 있으면 빈 글이 없다")
	-- 손에 든 법구 (캐릭터의 도구 WeaponIndex) 는 금테와 "손에 들었다"
	local body = roblox.Instance.new("Model")
	local tool = roblox.Instance.new("Tool")
	tool:SetAttribute("WeaponIndex", 2)
	tool.Parent = body
	hudEnv.services.Players.LocalPlayer.Character = wrap(body)
	fire(heartbeatKey, "Heartbeat", 0.016)
	assert(shows(find(weapon2, "Tag"), "body", "손에 들었다"), text(weapon2, "Tag"))
	assert(color(find(weapon2, "Name")) == C.gold, "손에 든 법구는 금빛")
	assert(shows(find(weapon1, "Tag"), "body", Combat.GRADES[2].prefix .. " 등급"), "든 것만")
	hudEnv.services.Players.LocalPlayer.Character = nil
	fire(heartbeatKey, "Heartbeat", 0.016)
	assert(not anyText(gear, "body", "손에 들었다"), "내려놓으면 표시가 없다")
	-- 방어 법구: 지닌 하나는 위 큰 칸, 나머지는 아래 (지니면 바뀌는 것과 함께)
	local worn = find(gear, "Worn")
	local okpaeGuard = { kind = "okpae", grade = 2 }
	assert(shows(find(worn, "Name"), "title", Guards.name(okpaeGuard)), text(worn, "Name"))
	assert(shows(find(worn, "Sub"), "body", Guards.effects(okpaeGuard)), text(worn, "Sub"))
	assert(anyText(gear, "body", "지님 1 / 1"), "지님 수")
	assert(find(gear, "GuardRule").Visible, "방어 법구는 하나만이라는 글")
	local okpae, jam, gabui = find(gear, "Guard_okpae"), find(gear, "Guard_jam"), find(gear, "Guard_gabui")
	assert(
		not okpae.Visible and jam.Visible and not gabui.Visible,
		"지닌 것은 위에, 가진 나머지만 아래에"
	)
	assert(not find(gear, "GuardEmpty").Visible, "방어 법구가 있으면 빈 글이 없다")
	assert(shows(find(jam, "Name"), "title", Guards.name({ kind = "jam", grade = 1 })), text(jam, "Name"))
	assert(shows(find(buttonOf(jam), "Text"), "body", "지니기"), "나머지는 지니기")
	-- 청운잠으로 바꾸면 옥패의 피해 감소가 빠지고(붉게) 천겁 피해가 준다(옥빛)
	local changes = BeopguTab.changes({ kind = "jam", grade = 1 }, okpaeGuard)
	assert(#changes == 2, `바뀌는 효과 {#changes}개 (2)`)
	local diff = find(jam, "Diff")
	assert(diff.Visible, "바꾸면 달라지는 것")
	assert(shows(find(diff, "Part1"), "body", changes[1].text .. ","), text(diff, "Part1"))
	assert(
		color(find(diff, "Part1")) == (if changes[1].good then C.jade else C.red),
		"좋아지면 옥빛, 나빠지면 붉게"
	)
	assert(not changes[1].good and changes[2].good, "피해 감소를 잃고 천겁 피해가 준다")
	assert(color(find(diff, "Part2")) == C.jade, "좋아지는 것은 옥빛")
	sent.equipGuard = nil
	fire(buttonOf(jam), "Activated")
	assert(sent.equipGuard and sent.equipGuard[1] == "jam", "지니기를 누르면 그 종류를 보낸다")
	fire(buttonOf(worn), "Activated")
	assert(sent.equipGuard and sent.equipGuard[1] == "", "내려놓기는 빈 글을 보낸다")
	sent.equipGuard = nil
	-- 서버가 바꿔 지니면 위아래가 바뀐다
	Hud.update(state({
		weapons = { { kind = "sword", grade = 2 } },
		guards = { okpaeGuard, { kind = "jam", grade = 1 } },
		guard = "jam",
	}))
	assert(okpae.Visible and not jam.Visible, "지님이 옮겨 간다")
	assert(shows(find(worn, "Name"), "title", Guards.name({ kind = "jam", grade = 1 })), "위 칸은 새로 지닌 것")
	assert(not weapon2.Visible, "공격 법구가 줄면 칸을 숨긴다")
	-- 아무것도 지니지 않았으면 위 칸이 비고, 아래 카드에 바뀌는 것 줄이 없다
	Hud.update(state({ guards = { okpaeGuard }, guard = nil }))
	assert(shows(find(worn, "Name"), "title", "지닌 방어 법구가 없다"), "빈 큰 칸")
	assert(not buttonOf(worn).Visible, "지닌 것이 없으면 내려놓기가 없다")
	assert(okpae.Visible and not find(okpae, "Diff").Visible, "지닌 것이 없으면 바뀌는 것 줄이 없다")
	-- 방어 법구가 없으면 얻는 곳을 알려 준다
	Hud.update(state({ guards = {}, guard = nil }))
	assert(find(gear, "GuardEmpty").Visible, "방어 법구가 없으면 얻는 곳 안내")
	assert(not okpae.Visible and not jam.Visible, "방어 법구가 없으면 카드가 없다")
	Hud.update(state({ weapons = {} }))
	assert(find(gear, "WeaponEmpty").Visible, "공격 법구가 없으면 빈 글")

	-- 주머니 갈래 --------------------------------------------------------------------
	Hud.setStatusTab("pouch")
	local pouch = page("pouch")
	Hud.update(state({ items = { herb = 3, pill = 1 } }))
	local herb, pill, lingzhi = find(pouch, "Item_herb"), find(pouch, "Item_pill"), find(pouch, "Item_lingzhi")
	assert(shows(find(herb, "Count"), "body", "3개") and shows(find(lingzhi, "Count"), "body", "0개"), "물건 수")
	assert(buttonOf(herb).Visible and not buttonOf(lingzhi).Visible, "가진 것만 먹기")
	assert(buttonOf(pill) == nil, "축기단은 먹기 단추가 없다")
	assert(hasText(herb, "body", "대장간 재료로도"), "재료로 쓰는 물건")
	sent.eat = nil
	fire(buttonOf(herb), "Activated")
	assert(sent.eat and sent.eat[1] == "herb", "먹기를 보낸다 (Eat)")

	-- 글이 칸에 드는지 ------------------------------------------------------------------
	-- Lune 은 배치를 하지 않으므로 카드의 바로 아래 자식 오프셋으로 센다: 카드 밖으로 나가지 않고, 글끼리 또는 글과
	-- 단추·그림이 겹치지 않는다 (가로 목록은 자식 너비를 더한다, 여러 줄 글은 줄마다)
	local function isTextFrame(item): boolean
		if item.ClassName ~= "Frame" then
			return false
		end
		for _, child in item:GetChildren() do
			if child.ClassName == "ImageLabel" and child.Name == "g" then
				return true
			end
		end
		return false
	end
	local function boxOf(item, parentW: number, parentH: number): { [string]: any }?
		if not item:IsA("GuiObject") or not item.Visible then
			return nil
		end
		local w = item.Size.X.Scale * parentW + item.Size.X.Offset
		local h = item.Size.Y.Scale * parentH + item.Size.Y.Offset
		local kind = "image"
		local inner = { x = 0, y = 0 }
		if item:IsA("GuiButton") then
			kind = "button"
		elseif isTextFrame(item) then
			kind = "text"
		elseif item.ClassName == "Frame" then
			local layout = item:FindFirstChildOfClass("UIListLayout")
			local texts = {}
			for _, child in item:GetChildren() do
				if child:IsA("GuiObject") and child.Visible and isTextFrame(child) then
					table.insert(texts, child)
				end
			end
			if #texts == 0 then
				return nil
			end
			kind = "text"
			if layout and layout.FillDirection == roblox.Enum.FillDirection.Horizontal then
				local total = 0
				for index, child in texts do
					total += child.Size.X.Offset + (if index > 1 then layout.Padding.Offset else 0)
				end
				assert(total <= w + 0.5, `{item:GetFullName()} 줄이 틀보다 넓다 ({total} > {w})`)
				if layout.HorizontalAlignment ~= roblox.Enum.HorizontalAlignment.Left then
					return nil
				end
				w = total
			else
				local right, bottom = 0, 0
				for _, child in texts do
					right = math.max(right, child.Position.X.Offset + child.Size.X.Offset)
					bottom = math.max(bottom, child.Position.Y.Offset + child.Size.Y.Offset)
				end
				w, h = right, bottom
			end
		end
		local x = item.Position.X.Scale * parentW + item.Position.X.Offset - item.AnchorPoint.X * w
		local y = item.Position.Y.Scale * parentH + item.Position.Y.Offset - item.AnchorPoint.Y * h
		return { item = item, kind = kind, x = x + inner.x, y = y + inner.y, w = w, h = h }
	end
	local checked = 0
	local function fits(card)
		local cardW, cardH = card.Size.X.Offset, card.Size.Y.Offset
		local boxes = {}
		for _, child in card:GetChildren() do
			local box = boxOf(child, cardW, cardH)
			if box then
				table.insert(boxes, box)
			end
		end
		local function labelOf(item): string
			if isTextFrame(item) then
				return readText(item)
			end
			for _, child in item:GetDescendants() do
				if isTextFrame(child) then
					return readText(child)
				end
			end
			return item.Name
		end
		for _, box in boxes do
			if box.kind == "text" then
				local label = labelOf(box.item)
				assert(
					box.x >= -1 and box.x + box.w <= cardW + 1 and box.y >= -1 and box.y + box.h <= cardH + 1,
					`{card:GetFullName()} 의 글 "{label}" 이 칸 밖으로 나간다 ({box.x},{box.y} {box.w}×{box.h} / {cardW}×{cardH})`
				)
			end
		end
		for i = 1, #boxes do
			for j = i + 1, #boxes do
				local a, b = boxes[i], boxes[j]
				if a.kind ~= "text" and b.kind ~= "text" then
					continue
				end
				local overlapW = math.min(a.x + a.w, b.x + b.w) - math.max(a.x, b.x)
				local overlapH = math.min(a.y + a.h, b.y + b.h) - math.max(a.y, b.y)
				assert(
					overlapW <= 1 or overlapH <= 1,
					`{card:GetFullName()}: {a.item.Name} 와 {b.item.Name} 이 겹친다 ({overlapW}×{overlapH})`
				)
			end
		end
		checked += 1
	end
	local CARD_NAMES = {
		"^Card_",
		"^Hotbar%d",
		"^PassiveSlot%d",
		"^Weapon%d",
		"^Guard_",
		"^Worn$",
		"^Item_",
		"^Hint$",
		"^Header$",
		"^Character$",
	}
	local function fitAll()
		for _, item in window:GetDescendants() do
			if item:IsA("GuiObject") and item.Visible then
				for _, pattern in CARD_NAMES do
					if string.match(item.Name, pattern) then
						fits(item)
						break
					end
				end
			end
		end
	end
	-- 설명 줄은 두 줄 안에 든다 (Ui.paragraph 는 넘치는 줄을 버린다)
	for _, def in SkillsShared.list do
		local lines = UiForTest.wrap("body", 14, def.summary, SkillsTab.TEXT_W)
		assert(#lines <= 2, `{def.name} 설명이 카드에서 {#lines}줄이다`)
		local slotLines = UiForTest.wrap("body", 14, def.summary, SkillsTab.CELL_W - 80)
		assert(def.kind ~= "passive" or #slotLines <= 2, `{def.name} 설명이 공법 칸에서 {#slotLines}줄이다`)
	end
	for _, id in Balance.ITEM_ORDER do
		local lines = UiForTest.wrap("body", 14, PouchTab.describe(id), PouchTab.TEXT_W)
		assert(#lines <= 2, `{id} 쓰임이 {#lines}줄이다`)
	end
	-- 여러 상태에서: 다 익힘·못 익힘, 고르는 중, 키 바꾸는 중, 법구 등급마다, 방어 법구 짝마다, 많은 물건
	local everything = {}
	for _, def in SkillsShared.list do
		everything[def.id] = true
	end
	local allWeapons = {}
	for _, kind in Combat.KIND_ORDER do
		table.insert(allWeapons, { kind = kind, grade = 1 })
	end
	local scenarios = {
		state({ skills = everything, hotbar = { "yeongchul", "heogong", "hosin", "yudo" }, step = 56 }),
		state({ skills = {}, step = 1 }),
		state({ stones = 9999999, maxHealth = 99999999, qi = 1e15, req = 1e15, race = "human", step = 56 }),
	}
	for grade = 1, #Combat.GRADES do
		local list = {}
		for _, weapon in allWeapons do
			table.insert(list, { kind = weapon.kind, grade = grade })
		end
		table.insert(
			scenarios,
			state({
				weapons = list,
				items = { herb = 999, lingzhi = 999, yodan = 999, hongsam = 99, pill = 99, starSeed = 99 },
			})
		)
	end
	for _, wornKind in Guards.ORDER do
		for _, grade in { 1, 5 } do
			local list = {}
			for _, kind in Guards.ORDER do
				table.insert(list, { kind = kind, grade = if kind == wornKind then 6 - grade else grade })
			end
			table.insert(scenarios, state({ guards = list, guard = wornKind }))
		end
	end
	for _, tabDef in StatusWindow.TABS do
		Hud.setStatusTab(tabDef.key)
		for _, scenario in scenarios do
			Hud.update(scenario)
			fitAll()
		end
	end
	-- 경지 이름마다 인물 칸에 든다
	for step = 1, RealmsShared.maxStep do
		Hud.update(state({ step = step, qi = 5e14, req = 9e14 }))
		fits(character)
	end
	-- 술법 고르는 중·키 바꾸는 중의 안내 줄 (가장 긴 이름)
	Hud.setStatusTab("skills")
	Hud.update(scenarios[1])
	fire(find(skills, "Card_yeongchul"), "Activated")
	fitAll()
	fire(find(skills, "Hotbar1"), "Activated")
	fire(find(skills, "Hotbar1"), "Activated")
	fitAll()
	Hud.startBinding(3)
	fitAll()
	Hud.stopBinding()
	assert(checked > 500, `글 자리 검사가 너무 적다 ({checked})`)
	-- 갈래 쪽 크기: 카드 줄이 갈래 너비 안에 든다
	assert(
		SkillsTab.SLOT_W * 4 + 30 <= Kit.W and SkillsTab.CELL_W * 3 + Kit.GAP_X * 2 <= Kit.W,
		"술법 카드 줄이 넓다"
	)
	assert(BeopguTab.LEFT_W + BeopguTab.RIGHT_W + 14 <= Kit.W, "법구 두 쪽이 넓다")
	assert(PouchTab.CELL_W * 2 + Kit.GAP_X <= Kit.W, "주머니 카드 줄이 넓다")
	assert(page("skills").Size.X.Offset + 314 <= window.Size.X.Offset - 24, "갈래가 창 밖으로 나간다")
	Hud.update(state())
	Hud.toggleStatus(false)

	-- 전송진 삯: 선 진과 갈 진 바닥 사이 거리로 센다. 송계 마을(Places.HOME_WAYPOINT)로는 공짜
	local function pad(id: string, x: number, z: number)
		local part = roblox.Instance.new("Part")
		part.Position = roblox.Vector3.new(x, 0, z)
		part:SetAttribute("WaypointId", id)
		return wrap(part)
	end
	tagged.Waypoint = { pad("wp_home", 0, 0), pad("wp_two", 600, 0), pad("wp_three", 0, 5000) }
	local points = {
		{ id = "wp_home", name = "송계 마을", open = true },
		{ id = "wp_two", name = "영산", open = true },
		{ id = "wp_three", name = "천겁대", open = true },
	}
	Hud.update(state({ stones = 5, waypoints = points }))
	Hud.openTravel("wp_two")
	local menu = hudGui:FindFirstChild("TravelMenu")
	local function entries()
		local out = {}
		for _, item in menu:GetDescendants() do
			if item:IsA("ImageButton") and item.Visible and item.LayoutOrder > 0 then
				out[item.LayoutOrder] = item
			end
		end
		return out
	end
	local buttons = entries()
	assert(shows(find(menu, "Stones"), "body", "5"), "전송진 창에 지닌 영석")
	assert(shows(find(buttons[1], "Fee"), "body", "공짜"), "송계 마을로 가는 길은 공짜")
	assert(not find(buttons[2], "Fee").Visible, "지금 선 진에는 삯이 없다")
	local far = Currency.travelFee(math.sqrt(600 ^ 2 + 5000 ^ 2), false)
	assert(shows(find(buttons[3], "Fee"), "body", "영석 " .. far), readText(find(buttons[3], "Fee")))
	sent.travel = nil
	fire(buttons[3], "Activated")
	assert(sent.travel == nil, "삯이 모자라면 보내지 않는다")
	assert(Hud.travelOpen(), "삯이 모자라면 창을 닫지 않는다")
	fire(buttons[1], "Activated")
	assert(sent.travel[1] == "wp_home", "공짜 길은 바로 간다")
	Hud.openTravel("wp_home")
	buttons = entries()
	local near = Currency.travelFee(600, false)
	assert(shows(find(buttons[2], "Fee"), "body", "영석 " .. near), "가까운 진 삯")
	fire(buttons[2], "Activated")
	assert(sent.travel[1] == "wp_two", "삯이 넉넉하면 간다")
	tagged.Waypoint = nil
end

-- 싸움: 대상 창과 맞은 느낌
do
	local mob = roblox.Instance.new("Model")
	mob:SetAttribute("Hp", 40)
	mob:SetAttribute("MaxHp", 60)
	mob:SetAttribute("Tier", 1)
	mob.Parent = real:GetService("Workspace")
	Hud.combat({ kind = "hit", mob = wrap(mob), name = "잿빛이리", tier = 1, hp = 40, maxHp = 60 })
	local frame = playerGui:FindFirstChild("BlockSuseonHud"):FindFirstChild("Target")
	assert(frame and frame.Visible, "대상 창이 떠야 한다")
	Hud.combat({ kind = "hurt", amount = 8, name = "잿빛이리", mob = wrap(mob) })
	Hud.combat({ kind = "blocked", name = "잿빛이리" })
	Hud.combat({ kind = "hit", mob = wrap(mob), name = "잿빛이리", tier = 1, hp = 0, maxHp = 60, killed = true })
	assert(not frame.Visible, "쓰러뜨리면 대상 창이 닫힌다")
end

-- 땅 이름 띄우기
loader.require(loader.folder("src/client").PlaceBanner).show("청송림", "다리 건너 영초가 돋는 솔숲")

-- 현판: 판자 겉면에 붓글씨 글자를 붙인다 (가로, 세로)
do
	local Plaques = loader.require(loader.folder("src/client").Plaques)
	for _, case in
		{ { "송계", false, roblox.Vector3.new(8, 3, 0.6) }, { "관성대", true, roblox.Vector3.new(3, 10, 1.2) } }
	do
		local board = roblox.Instance.new("Part")
		board.Size = case[3]
		board:SetAttribute("Text", case[1])
		board:SetAttribute("Vertical", case[2])
		board:SetAttribute("Faces", "Front,Back")
		Plaques.decorate(wrap(board))
		local guis = 0
		for _, child in board:GetChildren() do
			if child:IsA("SurfaceGui") then
				guis += 1
				local glyphs = 0
				for _, item in child:GetDescendants() do
					if item:IsA("ImageLabel") then
						glyphs += 1
					end
				end
				assert(glyphs == utf8.len(case[1]), `현판 글자 수 {glyphs} ({case[1]})`)
			end
		end
		assert(guis == 2, "앞뒤 두 면에 새겨야 한다")
		Plaques.decorate(wrap(board))
		assert(#board:GetChildren() == 2, "두 번 새기면 안 된다")
	end
end

-- 내관 창: 박자와 균형
Hud.openTrial({
	id = 1,
	mode = "rhythm",
	seed = 9,
	params = { beats = 2, interval = 0.9, band = 1 },
	title = "음양지의",
	hint = "박자에 맞춰 누른다.",
})
for _ = 1, 30 do
	fire(heartbeatKey, "Heartbeat", 0.05)
end
Hud.openTrial({ close = true })
Hud.openTrial({
	id = 2,
	mode = "balance",
	seed = 3,
	params = { bars = 3, target = 1, band = 1.3, turbulence = 1 },
	title = "혼원지의",
})
for _ = 1, 10 do
	fire(heartbeatKey, "Heartbeat", 0.05)
end
Hud.openTrial({ close = true })
for id, case in
	{
		{ "sequence", { nodes = 9, lengths = { 3, 3 }, style = "dots" } },
		{ "sequence", { nodes = 9, lengths = { 4 }, style = "cheongang" } },
		{ "ring", { hits = 3, band = 1 } },
		{ "arrange", { band = 1 } },
		{ "strands", { count = 9, time = 17, speed = 1, band = 1 } },
		{
			"order",
			{ items = { "금단이 맺힌 날", "영근이 깨어난 날", "송계 마을에 처음 온 날" } },
		},
	}
do
	Hud.openTrial({ id = 10 + id, mode = case[1], seed = 42, params = case[2], title = "내관" })
	for _ = 1, 20 do
		fire(heartbeatKey, "Heartbeat", 0.05)
	end
	Hud.openTrial({ close = true })
end
-- 술법 쿨타임이 단축칸에 그려지는지
-- 단축키 바꾸기 모드
Hud.startBinding(2)
assert(Hud.bindingSlot() == 2, "단축키 바꾸기 모드가 아니다")
Hud.stopBinding()
assert(Hud.bindingSlot() == nil, "단축키 바꾸기 모드가 안 끝났다")
Hud.skillUsed({ id = "gyeongsin", cooldown = 5 })
fire(heartbeatKey, "Heartbeat", 0.016)
assert(Hud.cooldownReady("gyeongsin") == false, "쿨타임 중인데 바로 쓸 수 있다")
for i = 1, 6 do
	Hud.toast("알림 " .. i, if i % 2 == 0 then "good" else "bad")
end
Hud.cinematic({ kind = "intro", realm = "범인", returning = false })
Hud.cinematic({ kind = "ascend", step = 45, realm = "결단기 초기", blurb = "금단을 맺는다." })
Hud.cinematic({ kind = "ascend", step = 49, realm = "원영기 초기", blurb = "" })
Hud.cinematic({ kind = "down" })

-- 미뤄 둔 연출(task.delay)까지 돌게 잠깐 기다린다
task.wait(4)

local hud = playerGui:FindFirstChild("BlockSuseonHud")
assert(hud, "HUD ScreenGui 가 없다")
-- 알림은 화면 위 가운데 띠로 뜬다. 한 번에 넷까지, 넘치면 줄을 세운다 (버리지 않는다)
local Art = loader.require(loader.folder("src/client").Art)
local Notice = loader.require(loader.folder("src/client").Notice)
local notices = hud:FindFirstChild("Notices")
assert(notices, "화면 알림 틀이 없다")
assert(#chatMessages == 0, "알림을 채팅으로 보내면 안 된다")
-- 앞의 상태 검사에서 열린 고르기 창을 닫고 보통 자리로
loader.require(loader.folder("src/client").Choice).close()
Notice.setCompact(false)
Notice.clear()
task.wait(0.5)
for i = 1, 6 do
	Hud.toast("몰린 알림 " .. i, "good")
end
assert(Notice.count() == 4, `화면 알림 {Notice.count()}개 (넷)`)
assert(Notice.pendingCount() == 2, "넘친 알림은 기다린다")
Hud.toast("몰린 알림 6", "good")
assert(Notice.pendingCount() == 2, "기다리는 알림과 같으면 겹쳐 쌓지 않는다")
Hud.toast("몰린 알림 1", "good")
assert(Notice.count() == 4 and Notice.pendingCount() == 2, "떠 있는 알림과 같으면 시간만 늘린다")
Notice.clear()
task.wait(0.5)

-- 연출 중에는 멈췄다가 걷힌 뒤 띄운다
Notice.hold(0.6)
Hud.toast("연출 뒤 알림", "info")
assert(Notice.count() == 0 and Notice.pendingCount() == 1, "연출 중에는 띄우지 않는다")
task.wait(0.8)
assert(Notice.count() == 1 and Notice.pendingCount() == 0, "연출이 끝나면 띄운다")
Notice.clear()
task.wait(0.5)

-- 창이 열려 있으면 맨 위로 올리고 둘만
Notice.setCompact(true)
for i = 1, 3 do
	Hud.toast("창 열림 알림 " .. i, "info")
end
assert(Notice.count() == 2, "창이 열려 있으면 둘만 띄운다")
Notice.setCompact(false)
assert(Notice.count() == 3, "창을 닫으면 기다리던 것을 띄운다")
Notice.clear()
task.wait(0.5)

-- 글자판에 없는 글자가 있으면 그 알림만 Roblox 글꼴로
Hud.toast("Ωmega님이 결단기에 올랐다.", "world")
Hud.toast("영력이 가득 찼다. 남은 과업을 마치면 오른다.", "info")
local fallbacks = 0
for _, item in notices:GetDescendants() do
	if item:IsA("TextLabel") then
		assert(
			string.find(item.Text, "Ωmega", 1, true),
			"글자판으로 찍을 수 있는 알림이 Roblox 글꼴로 갔다"
		)
		fallbacks += 1
	end
end
assert(fallbacks == 1, "글자판에 없는 글자가 있으면 Roblox 글꼴로 찍어야 한다")
-- 도움말처럼 긴 알림도 글자판으로
local Commands = loader.require(sharedFolder.Commands)
for _, line in Commands.HELP do
	for _, code in utf8.codes("[검수] " .. line) do
		local ch = utf8.char(code)
		assert(ch == " " or Art.fonts.body.glyphs[ch], "도움말 글자가 글자판에 없다: " .. ch)
	end
end
local cinematicGui = playerGui:FindFirstChild("BlockSuseonCinematic")
assert(cinematicGui, "연출 ScreenGui 가 없다")
-- 연출이 끝나면 화면에서 사라져야 한다 (지난번에 계속 남아 있던 문제)
task.wait(1.5)
local stage = cinematicGui:FindFirstChild("Stage")
assert(stage, "연출 Stage 가 없다")
assert(stage.Visible == false, "연출이 끝났는데 화면에 남아 있다")
for _, child in cinematicGui:GetChildren() do
	if child:IsA("Frame") and child.Name ~= "Stage" then
		assert(child.BackgroundTransparency == 1, "연출 배경이 어둡게 남아 있다")
	end
end

task.wait(10)
assert(Notice.count() == 0 and Notice.pendingCount() == 0, "알림이 사라지지 않았다")

local count = 0
for _, _ in hud:GetDescendants() do
	count += 1
end
print(`HUD 통과 · 인스턴스 {count}개 · 트윈 {hudEnv.counts.tweens}회 · 상태 {#cases}가지`)

-- 화면에 나올 수 있는 글자가 모두 글자판에 있는지 -----------------------------------------
local Realms = loader.require(sharedFolder.Realms)
local Skills = loader.require(sharedFolder.Skills)
local missing = {}
local function need(fontName: string, text: string)
	for _, code in utf8.codes(text) do
		local ch = utf8.char(code)
		if not Art.fonts[fontName].glyphs[ch] then
			missing[`{fontName}:{ch}`] = text
		end
	end
end
for step = 1, Realms.maxStep do
	local s = Realms.get(step)
	need("title", Realms.label(step))
	need("title", s.realm.name)
	need("title", s.sub)
	need("body", s.realm.blurb)
	if s.realm.tribulation then
		need("title", s.realm.tribulation.name)
	end
end
for _, def in Skills.list do
	need("title", def.name)
	need("body", def.summary)
	need("body", string.format("%s부터 익힐 수 있다", Realms.byId[def.minRealm].name))
end
local Tasks = loader.require(sharedFolder.Tasks)
local Roots = loader.require(sharedFolder.Roots)
local Progression = loader.require(sharedFolder.Progression)
local Clock = loader.require(sharedFolder.Clock)
Tasks.LIVE_UNTIL = Realms.maxStep
for step = 1, Realms.maxStep do
	for _, combo in { { "wood" }, { "wood", "fire", "earth", "metal", "water" } } do
		local data = Progression.newData()
		data.step = step
		data.root = Roots.make(combo)
		for _, choice in { { chilsu = "baek", element = combo[1] }, {} } do
			data.choice = choice
			for _, job in Tasks.list(data) do
				need("title", job.label)
				need("body", job.hint)
			end
		end
	end
	if Realms.get(step).realm.entry then
		need("title", Realms.get(step).realm.entry.title)
		need("body", "B 로 " .. Realms.get(step).realm.entry.title)
	end
end
for _, element in Roots.ELEMENTS do
	need("title", Roots.ELEMENT[element].name .. " 속성")
	need("body", Roots.ELEMENT[element].place .. "에서 닦는다")
end
for _, kind in Roots.KIND do
	need("title", kind.name)
	need("body", kind.summary)
end
for _, def in Tasks.CHILSU do
	need("title", def.name)
	need("body", def.summary)
end
for _, name in Clock.PHASE_NAME do
	need("body", name)
end
local Trials = loader.require(sharedFolder.Trials)
for _, memory in Trials.MEMORIES do
	need("body", memory)
end
need("body", Trials.BIRTH)
for _, def in Tasks.DOSIM do
	need("title", def.name)
	need("body", def.summary)
end
for mansion = 1, 4 do
	for _, name in Tasks.mansionStars(mansion) do
		need("title", name)
	end
	need("title", Tasks.MANSIONS[mansion].name)
end
need("title", "천지인")
-- 종족 (상태창)
local RacesForGlyphs = loader.require(sharedFolder.Races)
for _, race in RacesForGlyphs.list do
	need("body", race.name)
	need("body", race.summary)
	need("body", RacesForGlyphs.effects(race.id))
end
need("body", "종족 다시 뽑기 49 로벅스")
-- 땅 이름 (들어설 때 화면에 띄운다)
for _, region in loader.require(sharedFolder.Places).REGIONS do
	need("title", region.name)
	need("body", region.name)
	if region.sub then
		need("body", region.sub)
	end
end
need("body", "별씨 12")
for _, name in Trials.CHEONGANG do
	need("title", name)
end
for i, name in Trials.GUGUNG do
	need("body", name)
	need("title", tostring(i))
end
for _, def in Tasks.CHILSU do
	need("body", string.format("%s 시운, 3분 12초 남았다 %s 시운까지 40초", def.name, def.name))
end
need("body", "주머니  영초 3  천년영지 1  홍령삼 1  축기단 1 주머니 비었다 끝 12 / 30초")
-- 서버가 보내는 알림 문구 (화면에 글자판으로 찍는다).
-- 맵 짓는 World*.luau 의 글은 부품 이름과 현판 글(붓글씨, tests/run 이 본다)이라 빼고, 전송진 이름만 창에 나온다
local fs = require("@lune/fs")
for id, name in string.gmatch(fs.readFile("src/server/WorldSites.luau"), 'add%("wp", "([%w_]+)", "([^"]+)"') do
	need("title", name)
end
for _, file in fs.readDir("src/server") do
	if string.match(file, "^World") then
		continue
	end
	local source = fs.readFile("src/server/" .. file)
	source = string.gsub(source, "%-%-[^\n]*", "")
	for literal in string.gmatch(source, '"([^"\n]*)"') do
		if string.find(literal, "[\234-\237]") then
			need("body", (string.gsub(literal, "%%[%a%.%d]+", "")))
		end
	end
end
-- 영석: 영석 칸, 상점·대장간 창, 전송진 삯
local CurrencyForGlyphs = loader.require(sharedFolder.Currency)
local CombatForGlyphs = loader.require(sharedFolder.Combat)
local BalanceForGlyphs = loader.require(sharedFolder.Balance)
need("body", "1,250 1,265개 영석 25 공짜")
need("title", "만물상 대장간")
for _, ware in CurrencyForGlyphs.WARES do
	if ware.item then
		need("title", BalanceForGlyphs.ITEMS[ware.item].name)
	end
end
for _, pack in CurrencyForGlyphs.PACKS do
	need("title", pack.name)
	need("body", string.format("영석 %s개 %d 로벅스", CurrencyForGlyphs.format(pack.stones), pack.robux))
end
for _, kind in CombatForGlyphs.KIND_ORDER do
	need("body", CombatForGlyphs.KINDS[kind].summary)
	for grade = 1, #CombatForGlyphs.GRADES do
		local weapon = { kind = kind, grade = grade }
		need("title", CombatForGlyphs.weaponName(weapon))
		need("body", CombatForGlyphs.weaponName(weapon) .. " " .. CombatForGlyphs.GRADES[grade].prefix .. " 등급")
	end
end
-- 법구: 방어 법구 이름(제목 글꼴)과 효과 줄, 제작 재료
local GuardsForGlyphs = loader.require(sharedFolder.Guards)
for _, kind in GuardsForGlyphs.KINDS do
	for grade = 1, #GuardsForGlyphs.GRADES do
		local guard = { kind = kind.id, grade = grade }
		need("title", GuardsForGlyphs.name(guard))
		need("body", GuardsForGlyphs.effects(guard) .. " 지금 " .. GuardsForGlyphs.GRADES[grade])
	end
end
for _, id in BalanceForGlyphs.ITEM_ORDER do
	need("body", "재료 " .. BalanceForGlyphs.ITEMS[id].name .. " 0/1234567890")
end
need("title", "공격 법구 방어 법구 지님 0 / 1")
-- 상태창: 제목 글꼴로 찍는 칸 이름, 글자 도장 (법구 종류 끝 글자, 방어 법구·물건 첫 글자)
need("title", "빈 칸 잠긴 칸 지닌 방어 법구가 없다")
for _, kind in CombatForGlyphs.KINDS do
	need("title", kind.suffix)
end
for _, kind in GuardsForGlyphs.KINDS do
	need("title", kind.name)
end
for _, id in BalanceForGlyphs.ITEM_ORDER do
	need("title", BalanceForGlyphs.ITEMS[id].name)
end
local PouchForGlyphs = loader.require(loader.folder("src/client").PouchTab)
for _, id in BalanceForGlyphs.ITEM_ORDER do
	need("body", PouchForGlyphs.describe(id))
end
local BeopguForGlyphs = loader.require(loader.folder("src/client").BeopguTab)
for _, kind in CombatForGlyphs.KIND_ORDER do
	for grade = 1, #CombatForGlyphs.GRADES do
		need("body", BeopguForGlyphs.weaponStats({ kind = kind, grade = grade }))
	end
end
for _, entry in GuardsForGlyphs.LABELS do
	need("body", entry[2] .. " +-%,")
end
for _, def in loader.require(sharedFolder.Skills).list do
	need("body", string.format("%s: 넣을 칸을 누른다 재사용 %s", def.name, tostring(def.cooldown or 0)))
end
for _, file in
	{
		"src/client/ShopWindow.luau",
		"src/client/TravelMenu.luau",
		"src/client/Hud.luau",
		"src/client/Main.client.luau",
		"src/client/StatusWindow.luau",
		"src/client/StatusKit.luau",
		"src/client/SkillsTab.luau",
		"src/client/BeopguTab.luau",
		"src/client/PouchTab.luau",
	}
do
	local source = string.gsub(fs.readFile(file), "%-%-[^\n]*", "")
	for literal in string.gmatch(source, '"([^"\n]*)"') do
		if string.find(literal, "[\234-\237]") then
			need("body", (string.gsub(literal, "%%[%a%.%d]+", "")))
		end
	end
end
for key, text in missing do
	print(`  글자판에 없음 {key} ← "{text}"`)
end
assert(next(missing) == nil, "글자판에 없는 글자가 있다 — tools/fetch_fonts.py 부터 다시")
print("글자판 검사 통과")
