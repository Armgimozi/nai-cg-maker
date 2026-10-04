--[[
GUI 스냅숏: Roblox 없이 HUD 배치를 본다.

tests/hud.luau 와 같은 가짜 환경(tests/hud_env.luau)으로 진짜 HUD 를 짓고, 중반 플레이어 상태(경지, 능력치,
익힌 술법·공법, 단축칸, 공격·방어 법구, 주머니, 영석)를 넣고, 창을 하나 연 뒤 ScreenGui 나무를 Roblox 처럼
배치해서(절대 좌표) JSON 으로 쓴다. 그림은 tools/gui_render.py 가 PNG 로 그린다.

    lune run tools/gui_snapshot status 1920 1080 && python3 tools/gui_render.py build/gui_status.json build/gui_status.png
    lune run tools/gui_snapshot status 844 390 --touch --out build/gui_status_phone.json
    lune run tools/gui_snapshot shop-market 1920 1080 법구      (갈래: 번호, 글자, 또는 goods/gear/packs)
    lune run tools/gui_snapshot shop-smith 1920 1080 craft
    lune run tools/gui_snapshot travel 1920 1080
    lune run tools/gui_snapshot hud 1920 1080

인자: <창> [너비 높이] [갈래]
  창      status | shop-market | shop-smith | travel | choice | hud (아무 창도 열지 않음)
  너비 높이 화면(뷰포트) 픽셀. 기본 1920 1080. 폰 가로는 844 390 (--touch 와 함께)
  갈래    status 는 Hud 의 공개 함수(setStatusTab·openStatusTab·showStatusTab·selectStatusTab·statusTab)가 있으면
          그것으로, 없으면 상태창 안에서 이름(Tab<n>, Tab_<갈래>)이나 글자가 맞는 버튼을 눌러 연다.
          지금 상태창 갈래: skills·passives·gear·pouch (또는 술법·공법·법구·주머니, 1~4)
          상점도 같은 식으로 갈래 버튼을 누른다. choice 는 고르기 열쇠 (root, chilsu, element, center, dosim)
선택:
  --out <경로>        JSON 경로 (기본 build/gui_<창>[_<갈래>].json)
  --state <경로>      상태를 덮어쓸 JSON (기본 상태 위에 맨 윗단 키 단위로 덮는다, null 은 그 키를 지운다)
  --name <이름>       플레이어 DisplayName (기본 수선객)
  --touch             터치 전용 기기 (키 표시 없음, 오른쪽 아래 버튼을 위로)
  --inset <px>        Roblox 위쪽 막대 높이 (기본 58). IgnoreGuiInset 이 아닌 ScreenGui 는 그만큼 내려온다
  --scroll <px>       열린 창 목록(ScrollingFrame)을 그만큼 내린 상태로 (기본 0)
  --click <이름|글자> 보이는 버튼 하나를 누른다 (여러 번 쓸 수 있다). 예: --click "확률 보기"
  --toasts            화면 알림(과업 안내 등)을 지우지 않고 둔다
  --no-core           Roblox 기본 UI 자리(위쪽 막대, 도구 칸, 점프 버튼)를 넣지 않는다

배치 규칙 (화면 UI 가 실제로 쓰는 것): UDim2 위치·크기, AnchorPoint, UIScale (그 물체를 AnchorPoint 둘레로 키우고
자손의 오프셋에 곱한다), UIPadding, UIListLayout (FillDirection, Padding, 정렬, SortOrder, Wraps), UIGridLayout
(CellSize, CellPadding, FillDirectionMaxCells, 정렬), AutomaticSize, ScrollingFrame (CanvasPosition, 창에 자르기,
AutomaticCanvasSize, 스크롤 막대), Visible 상속, ClipsDescendants, ZIndexBehavior (Sibling/Global), DisplayOrder.
UISizeConstraint 와 UIAspectRatioConstraint 는 간단히만 본다. Rotation 은 값만 적고 배치에는 넣지 않는다.

JSON: { screen, assets (rbxassetid → art/out 파일), core (Roblox 기본 UI 자리), guis: [ScreenGui 나무] }.
나무의 마디마다 class, name, path, rect [x, y, w, h] (화면 픽셀), order (그리는 차례), zIndex, scale (누적 UIScale),
clip (자르는 영역), bg, border, image, text, glyph (글자판 글자), bitmapText (BitmapText 틀의 글줄)와 ink (글자 자리),
gradient, stroke, corner, scroll, children.
]]

local fs = require("@lune/fs")
local process = require("@lune/process")
local serde = require("@lune/serde")
local task = require("@lune/task")
local roblox = require("@lune/roblox") :: any

local HudEnv = require("../tests/hud_env")

local Enum = roblox.Enum
local Vector2 = roblox.Vector2

-- 인자 ---------------------------------------------------------------------------

local args = {
	which = "status",
	width = 1920,
	height = 1080,
	tab = nil :: string?,
	out = nil :: string?,
	state = nil :: string?,
	touch = false,
	name = "수선객",
	inset = 58,
	scroll = 0,
	clicks = {} :: { string },
	toasts = false,
	core = true,
}

do
	local positional = {}
	local i = 1
	local argv = process.args
	while i <= #argv do
		local a = argv[i]
		if a == "--out" then
			i += 1
			args.out = argv[i]
		elseif a == "--state" then
			i += 1
			args.state = argv[i]
		elseif a == "--touch" then
			args.touch = true
		elseif a == "--name" then
			i += 1
			args.name = argv[i]
		elseif a == "--inset" then
			i += 1
			args.inset = assert(tonumber(argv[i]), "--inset 숫자")
		elseif a == "--scroll" then
			i += 1
			args.scroll = assert(tonumber(argv[i]), "--scroll 숫자")
		elseif a == "--click" then
			i += 1
			table.insert(args.clicks, argv[i])
		elseif a == "--toasts" then
			args.toasts = true
		elseif a == "--no-core" then
			args.core = false
		elseif a == "--help" or a == "-h" then
			print("사용법은 tools/gui_snapshot.luau 맨 위 주석을 본다.")
			process.exit(0)
		else
			table.insert(positional, a)
		end
		i += 1
	end
	args.which = positional[1] or args.which
	-- 둘째 자리가 숫자면 너비 높이, 아니면 바로 갈래
	local rest = 2
	if positional[2] and tonumber(positional[2]) then
		args.width = tonumber(positional[2]) :: number
		args.height = assert(tonumber(positional[3]), "너비 다음에 높이를 준다") :: number
		rest = 4
	end
	args.tab = positional[rest]
	local valid =
		{ status = true, ["shop-market"] = true, ["shop-smith"] = true, travel = true, choice = true, hud = true }
	if not valid[args.which] then
		error(`모르는 창: {args.which} (status | shop-market | shop-smith | travel | choice | hud)`)
	end
end

-- HUD 짓기 -----------------------------------------------------------------------

local env = HudEnv.new({
	viewport = Vector2.new(args.width, args.height),
	keyboard = not args.touch,
	touch = args.touch,
	displayName = args.name,
})
local loader = env.loader
local client = env.clientFolder
local shared = env.sharedFolder
local Hud = loader.require(client.Hud)
local Art = loader.require(client.Art)
local Notice = loader.require(client.Notice)

local noop = function() end
Hud.build(setmetatable({}, {
	__index = function()
		return noop
	end,
}) :: any)

-- 대표 상태: 축기기 중반, 술법 넷·공법 넷, 공격 법구 넷, 방어 법구 셋 (하나 지님), 주머니, 영석
local Progression = loader.require(shared.Progression)
local Realms = loader.require(shared.Realms)
local Roots = loader.require(shared.Roots)
local Tasks = loader.require(shared.Tasks)
local Currency = loader.require(shared.Currency)

local function baseState(): { [string]: any }
	local data = Progression.newData()
	data.step = (Realms.firstStepById.chukgi or 17) + 5
	data.root = Roots.make({ "fire" })
	data.race = "human"
	data.skills = {
		gyeongsin = true,
		yeongan = true,
		chwiryeong = true,
		hosin = true,
		tonap = true,
		baekcho = true,
		cheongsim = true,
		geumgang = true,
	}
	data.equipped = { "tonap", "geumgang" }
	data.hotbar = { "gyeongsin", "yeongan", "chwiryeong", "hosin" }
	data.keys = { "Q", "E", "Z", "X" }
	data.items = { herb = 7, lingzhi = 1, yodan = 4, starSeed = 2 }
	data.weapons = {
		{ kind = "sword", grade = 2 },
		{ kind = "saber", grade = 3 },
		{ kind = "spear", grade = 1 },
		{ kind = "fan", grade = 1 },
	}
	data.guards = {
		{ kind = "okpae", grade = 2 },
		{ kind = "palchi", grade = 1 },
		{ kind = "jam", grade = 3 },
	}
	data.guard = "okpae"
	data.stones = 1250
	data.stats.tribulations = 0
	data.stats.herbs = 86
	data.stats.manuals = 5
	data.stats.breakthroughs = 21

	local function try(f, fallback)
		local ok, value = pcall(f)
		return if ok then value else fallback
	end
	local req = try(function()
		return Progression.requiredQi(data)
	end, 5000)
	data.qi = math.floor(req * 0.62)
	local tasks = try(function()
		return Tasks.snapshot(data)
	end, {})
	return {
		step = data.step,
		qi = data.qi,
		req = req,
		debt = 0,
		gain = try(function()
			return Progression.qiPerSecond(data, 1.5, 1, true)
		end, 12),
		race = data.race,
		stones = data.stones,
		weapons = data.weapons,
		guards = data.guards,
		guard = data.guard,
		meditating = true,
		veinId = "low",
		needsBreak = false,
		ready = false,
		tasksDone = try(function()
			return Tasks.allDone(data)
		end, false),
		entry = try(function()
			return Progression.nextEntry(data)
		end, nil),
		tasks = tasks,
		root = data.root,
		choice = data.choice,
		items = data.items,
		inTrial = false,
		skills = data.skills,
		equipped = data.equipped,
		hotbar = data.hotbar,
		keys = data.keys,
		slots = try(function()
			return Progression.slots(data)
		end, 2),
		stats = data.stats,
		inFormation = false,
		maxHealth = try(function()
			return Progression.maxHealth(data)
		end, 150),
		tribulation = nil,
		canSave = true,
		waypoints = {},
	}
end

-- 전송진: WorldSites 의 16 곳, 앞쪽 아홉은 밟아 보았다. 삯을 셀 수 있게 바닥(Waypoint 태그)도 둔다
local function waypoints(): { { [string]: any } }
	local list, pads = {}, {}
	local source = fs.readFile("src/server/WorldSites.luau")
	for id, name, x, z in string.gmatch(source, 'add%("wp", "([%w_]+)", "([^"]+)", (%-?[%d%.]+), (%-?[%d%.]+)') do
		table.insert(list, { id = id, name = name, open = #list < 9 })
		local part = roblox.Instance.new("Part")
		part.Position = roblox.Vector3.new(tonumber(x), 0, tonumber(z))
		part:SetAttribute("WaypointId", id)
		table.insert(pads, env.wrap(part))
	end
	env.tagged.Waypoint = pads
	return list
end

local state = baseState()
state.waypoints = waypoints()
if args.state then
	local source = fs.readFile(args.state)
	for key, value in serde.decode("json", source) do
		state[key] = value
	end
	-- JSON 의 null 은 그 키를 지운다 (serde 는 null 을 빼 버리므로 맨 윗단 키만 글에서 찾는다)
	for key in string.gmatch(source, '"([%w_]+)"%s*:%s*null') do
		state[key] = nil
	end
end
Hud.update(state)
-- 영석이 처음 들어올 때의 빛남(task.delay 0.8)이 끝나게
task.wait(0.9)
-- 한 프레임 돌린다 (RenderStepped: 다치지 않았으면 내 체력 막대를 숨긴다 따위)
env.fire(env.heartbeatKey, "Heartbeat", 1 / 60)
-- 고르기 과업이 열려 있으면 Hud 가 고르기 창을 저절로 띄우므로 닫아 둔다 (choice 창이면 아래에서 다시 연다)
local Choice = loader.require(client.Choice)
Choice.close()

-- 창 열기 ------------------------------------------------------------------------

local hudGui = env.playerGui:FindFirstChild("BlockSuseonHud")

-- 글자판 글자를 다시 읽는다: "page:x:y" → { 글자, 글꼴 }
local glyphAt: { [string]: { ch: string, font: string } } = {}
for fontName, font in Art.fonts do
	for ch, glyph in font.glyphs do
		if glyph[4] > 0 then
			glyphAt[`{font.pages[glyph[1]]}:{glyph[2]}:{glyph[3]}`] = { ch = ch, font = fontName }
		end
	end
end

local function prop(inst: any, name: string, default: any?): any
	local ok, value = pcall(function()
		return inst[name]
	end)
	if ok and value ~= nil then
		return value
	end
	return default
end

-- BitmapText 틀(글자 ImageLabel 들을 담은 Frame)의 글줄. 빈칸은 글자 사이 틈으로 되살린다
local function bitmapTextOf(frame: any): (string?, string?, number?)
	local glyphs = {}
	for _, child in frame:GetChildren() do
		if child.ClassName == "ImageLabel" and child.Name == "g" then
			local found = glyphAt[`{prop(child, "Image", "")}:{child.ImageRectOffset.X}:{child.ImageRectOffset.Y}`]
			if found then
				table.insert(glyphs, { label = child, ch = found.ch, font = found.font })
			end
		end
	end
	if #glyphs == 0 then
		return nil
	end
	table.sort(glyphs, function(a, b)
		return a.label.Position.X.Offset < b.label.Position.X.Offset
	end)
	local fontName = glyphs[1].font
	local font = Art.fonts[fontName]
	local first = glyphs[1].label
	local scale = first.Size.X.Offset / math.max(first.ImageRectSize.X, 1)
	local space = (font.glyphs[" "] or { 0, 0, 0, 0, 0, font.size * 0.3 })[6]
	local out = {}
	local pen = nil
	for _, g in glyphs do
		local x = g.label.Position.X.Offset / scale
		if pen and x - pen > space * 0.5 then
			table.insert(out, string.rep(" ", math.max(1, math.floor((x - pen) / space + 0.5))))
		end
		table.insert(out, g.ch)
		pen = x + font.glyphs[g.ch][6]
	end
	return table.concat(out), fontName, scale * font.size
end

local function isVisibleChain(inst: any): boolean
	local node = inst
	while node and node:IsA("GuiObject") do
		if not node.Visible then
			return false
		end
		node = node.Parent
	end
	return true
end

-- 이름이나 글자로 보이는 버튼을 찾는다
local function findButton(root: any, wanted: string): any?
	local plain = string.gsub(wanted, "%s", "")
	for _, item in root:GetDescendants() do
		if item:IsA("GuiButton") and isVisibleChain(item) then
			if item.Name == wanted or item.Name == "Tab_" .. wanted then
				return item
			end
			for _, sub in item:GetDescendants() do
				if sub.ClassName == "Frame" then
					local line = bitmapTextOf(sub)
					if line and string.gsub(line, "%s", "") == plain then
						return item
					end
				elseif (sub.ClassName == "TextLabel") and string.gsub(prop(sub, "Text", ""), "%s", "") == plain then
					return item
				end
			end
			if
				item:IsA("TextButton")
				and prop(item, "Text", "") ~= ""
				and string.gsub(item.Text, "%s", "") == plain
			then
				return item
			end
		end
	end
	return nil
end

local function click(button: any)
	env.fire(button, "MouseButton1Down")
	env.fire(button, "MouseButton1Up")
	env.fire(button, "MouseButton1Click")
	env.fire(button, "Activated")
end

local TAB_ALIASES = {
	goods = "물건",
	gear = "법구",
	packs = "영석 사기",
	upgrade = "강화",
	craft = "제작",
}

-- 창 안의 갈래 버튼: 번호(Tab<n>), 이름, 글자
local function openTab(window: any, tab: string): boolean
	local button = nil
	if tonumber(tab) then
		button = window:FindFirstChild("Tab" .. tab, true)
	end
	button = button or findButton(window, tab)
	if not button and TAB_ALIASES[tab] then
		button = findButton(window, TAB_ALIASES[tab])
	end
	if button then
		click(button)
		return true
	end
	return false
end

local opened: any = nil
if args.which == "status" then
	Hud.toggleStatus(true)
	opened = hudGui:FindFirstChild("StatusWindow")
	if args.tab then
		local done = false
		for _, name in { "setStatusTab", "openStatusTab", "showStatusTab", "selectStatusTab", "statusTab" } do
			if type(Hud[name]) == "function" then
				Hud[name](args.tab)
				done = true
				break
			end
		end
		if not done and opened then
			done = openTab(opened, args.tab)
		end
		if not done then
			warn(
				`상태창 갈래 "{args.tab}" 를 열 방법이 없다 (Hud 공개 함수도, 맞는 버튼도 없다). 그냥 연다`
			)
		end
	end
elseif args.which == "shop-market" or args.which == "shop-smith" then
	Hud.openShop(if args.which == "shop-market" then "market" else "smith")
	opened = hudGui:FindFirstChild("ShopWindow")
	if args.tab and opened and not openTab(opened, args.tab) then
		warn(`상점 갈래 "{args.tab}" 를 못 찾았다`)
	end
elseif args.which == "travel" then
	Hud.openTravel(state.waypoints[1] and state.waypoints[1].id or "wp_home")
	opened = hudGui:FindFirstChild("TravelMenu")
elseif args.which == "choice" then
	-- 갈래 = 고르기 열쇠 (root, chilsu, element, center, dosim). 없으면 지금 열린 고르기 과업
	local key = args.tab
	if not key then
		for _, job in state.tasks or {} do
			if job.kind == "choose" and job.open and not job.done then
				key = job.key
				break
			end
		end
	end
	Choice.open(key or "root", state)
	opened = hudGui:FindFirstChild("Choice")
end

for _, wanted in args.clicks do
	local button = findButton(opened or hudGui, wanted) or findButton(env.playerGui, wanted)
	if button then
		click(button)
	else
		warn(`누를 버튼 "{wanted}" 를 못 찾았다`)
	end
end

if not args.toasts then
	pcall(Notice.clear)
	-- 알림은 흐려진 뒤(0.35초) 지워진다
	task.wait(0.5)
end
task.wait(0.05)

-- 배치 ---------------------------------------------------------------------------

local function round(x: number): number
	return math.floor(x * 100 + 0.5) / 100
end

local function rgb(c: any): { number }
	return { math.floor(c.R * 255 + 0.5), math.floor(c.G * 255 + 0.5), math.floor(c.B * 255 + 0.5) }
end

local function childOfClass(inst: any, className: string): any?
	for _, child in inst:GetChildren() do
		if child.ClassName == className then
			return child
		end
	end
	return nil
end

local function guiChildren(inst: any): { any }
	local out = {}
	for _, child in inst:GetChildren() do
		if child:IsA("GuiObject") then
			table.insert(out, child)
		end
	end
	return out
end

local function ownScale(inst: any): number
	local s = childOfClass(inst, "UIScale")
	return if s then s.Scale else 1
end

local function udim(u: any, basis: number, s: number): number
	return basis * u.Scale + u.Offset * s
end

local function isText(inst: any): boolean
	return inst.ClassName == "TextLabel" or inst.ClassName == "TextButton" or inst.ClassName == "TextBox"
end

-- 글자 상자 어림 (AutomaticSize 글자용). 한글은 글자 크기만큼, 나머지는 0.55 배
local function textBounds(inst: any, s: number): (number, number)
	local str = prop(inst, "Text", "")
	local size = prop(inst, "TextSize", 14) * s
	local width = 0
	for _, code in utf8.codes(str) do
		width += if code >= 0x1100 then size else size * 0.55
	end
	return width, size * 1.2
end

type Box = { x: number, y: number, w: number, h: number }
type Placement = { inst: any, x: number, y: number, w: number, h: number }

local measure: (inst: any, basisW: number, basisH: number, s: number) -> (number, number)
local placeChildren: (inst: any, box: Box, s: number) -> ({ Placement }, number, number)

local function padding(inst: any, w: number, h: number, s: number): (number, number, number, number)
	local p = childOfClass(inst, "UIPadding")
	if not p then
		return 0, 0, 0, 0
	end
	return udim(p.PaddingLeft, w, s), udim(p.PaddingTop, h, s), udim(p.PaddingRight, w, s), udim(p.PaddingBottom, h, s)
end

local function constrain(inst: any, w: number, h: number, s: number): (number, number)
	local size = childOfClass(inst, "UISizeConstraint")
	if size then
		w = math.clamp(w, size.MinSize.X * s, math.max(size.MinSize.X * s, size.MaxSize.X * s))
		h = math.clamp(h, size.MinSize.Y * s, math.max(size.MinSize.Y * s, size.MaxSize.Y * s))
	end
	local aspect = childOfClass(inst, "UIAspectRatioConstraint")
	if aspect and aspect.AspectRatio > 0 then
		local ratio = aspect.AspectRatio
		if aspect.AspectType == Enum.AspectType.ScaleWithParentSize then
			if aspect.DominantAxis == Enum.DominantAxis.Width then
				h = w / ratio
			else
				w = h * ratio
			end
		else
			-- FitWithinMaxSize: 지금 상자 안에 드는 가장 큰 크기
			if w / ratio <= h then
				h = w / ratio
			else
				w = h * ratio
			end
		end
	end
	return w, h
end

-- 부모 상자(basisW × basisH, 자손 오프셋 배율 s) 안에서의 크기. UIScale·AutomaticSize 까지
function measure(inst: any, basisW: number, basisH: number, s: number): (number, number)
	local k = ownScale(inst)
	local size = inst.Size
	local w = udim(size.X, basisW, s)
	local h = udim(size.Y, basisH, s)
	w, h = constrain(inst, w, h, s)
	local auto = prop(inst, "AutomaticSize", Enum.AutomaticSize.None)
	if auto ~= Enum.AutomaticSize.None then
		local inner = s * k
		local ew, eh = 0, 0
		if isText(inst) then
			ew, eh = textBounds(inst, inner)
		end
		local pl, pt, pr, pb = padding(inst, w, h, inner)
		local placements, layoutW, layoutH =
			placeChildren(inst, { x = 0, y = 0, w = w - pl - pr, h = h - pt - pb }, inner)
		ew = math.max(ew, layoutW)
		eh = math.max(eh, layoutH)
		for _, p in placements do
			ew = math.max(ew, p.x + p.w)
			eh = math.max(eh, p.y + p.h)
		end
		ew += pl + pr
		eh += pt + pb
		if auto == Enum.AutomaticSize.X or auto == Enum.AutomaticSize.XY then
			w = math.max(w, ew)
		end
		if auto == Enum.AutomaticSize.Y or auto == Enum.AutomaticSize.XY then
			h = math.max(h, eh)
		end
	end
	return w * k, h * k
end

local function sortedForLayout(inst: any, layout: any): { any }
	local list = {}
	for index, child in guiChildren(inst) do
		if child.Visible then
			table.insert(list, { child = child, index = index })
		end
	end
	local order = layout.SortOrder
	table.sort(list, function(a, b)
		if order == Enum.SortOrder.LayoutOrder then
			if a.child.LayoutOrder ~= b.child.LayoutOrder then
				return a.child.LayoutOrder < b.child.LayoutOrder
			end
		elseif order == Enum.SortOrder.Name then
			if a.child.Name ~= b.child.Name then
				return a.child.Name < b.child.Name
			end
		end
		return a.index < b.index
	end)
	local out = {}
	for _, entry in list do
		table.insert(out, entry.child)
	end
	return out
end

local function alignOffset(free: number, align: any, startItem: any, centerItem: any): number
	if align == centerItem then
		return free / 2
	elseif align == startItem then
		return 0
	end
	return free
end

local H, V = Enum.HorizontalAlignment, Enum.VerticalAlignment

local function listLayout(inst: any, layout: any, box: Box, s: number): ({ Placement }, number, number)
	local children = sortedForLayout(inst, layout)
	local horizontal = layout.FillDirection == Enum.FillDirection.Horizontal
	local mainSize = if horizontal then box.w else box.h
	local gap = udim(layout.Padding, mainSize, s)
	local wraps = prop(layout, "Wraps", false)
	-- 줄 나누기 (Wraps 일 때만 여러 줄)
	local lines = { { items = {}, main = 0, cross = 0 } }
	for _, child in children do
		local w, h = measure(child, box.w, box.h, s)
		local main, cross = if horizontal then w else h, if horizontal then h else w
		local line = lines[#lines]
		local extra = if #line.items > 0 then gap else 0
		if wraps and #line.items > 0 and line.main + extra + main > mainSize + 0.01 then
			line = { items = {}, main = 0, cross = 0 }
			table.insert(lines, line)
			extra = 0
		end
		table.insert(line.items, { child = child, w = w, h = h, main = main, cross = cross })
		line.main += extra + main
		line.cross = math.max(line.cross, cross)
	end
	local out = {}
	local totalMain, totalCross = 0, 0
	for i, line in lines do
		totalMain = math.max(totalMain, line.main)
		totalCross += line.cross + (if i > 1 then gap else 0)
	end
	local crossSize = if horizontal then box.h else box.w
	local crossStart = 0
	if wraps and #lines > 1 then
		crossStart = if horizontal
			then alignOffset(crossSize - totalCross, layout.VerticalAlignment, V.Top, V.Center)
			else alignOffset(crossSize - totalCross, layout.HorizontalAlignment, H.Left, H.Center)
	end
	local crossPen = crossStart
	for _, line in lines do
		local lineCross = if wraps and #lines > 1 then line.cross else crossSize
		local pen = if horizontal
			then alignOffset(mainSize - line.main, layout.HorizontalAlignment, H.Left, H.Center)
			else alignOffset(mainSize - line.main, layout.VerticalAlignment, V.Top, V.Center)
		for _, item in line.items do
			local crossOffset = if horizontal
				then alignOffset(lineCross - item.cross, layout.VerticalAlignment, V.Top, V.Center)
				else alignOffset(lineCross - item.cross, layout.HorizontalAlignment, H.Left, H.Center)
			local x, y
			if horizontal then
				x, y = box.x + pen, box.y + crossPen + crossOffset
			else
				x, y = box.x + crossPen + crossOffset, box.y + pen
			end
			table.insert(out, { inst = item.child, x = x, y = y, w = item.w, h = item.h })
			pen += item.main + gap
		end
		crossPen += line.cross + gap
	end
	if horizontal then
		return out, totalMain, totalCross
	end
	return out, totalCross, totalMain
end

local function gridLayout(inst: any, layout: any, box: Box, s: number): ({ Placement }, number, number)
	local children = sortedForLayout(inst, layout)
	local cw, ch = udim(layout.CellSize.X, box.w, s), udim(layout.CellSize.Y, box.h, s)
	local px, py = udim(layout.CellPadding.X, box.w, s), udim(layout.CellPadding.Y, box.h, s)
	local horizontal = layout.FillDirection == Enum.FillDirection.Horizontal
	local fit = if horizontal
		then math.max(1, math.floor((box.w + px) / (cw + px) + 1e-6))
		else math.max(1, math.floor((box.h + py) / (ch + py) + 1e-6))
	local maxCells = layout.FillDirectionMaxCells
	local perLine = if maxCells > 0 then math.min(maxCells, fit) else fit
	local n = #children
	local lineCount = math.ceil(n / perLine)
	local out = {}
	local usedW = if horizontal then math.min(n, perLine) * (cw + px) - px else lineCount * (cw + px) - px
	local usedH = if horizontal then lineCount * (ch + py) - py else math.min(n, perLine) * (ch + py) - py
	for i, child in children do
		local line = (i - 1) // perLine
		local cell = (i - 1) % perLine
		local inLine = math.min(perLine, n - line * perLine)
		local x, y
		if horizontal then
			local lineW = inLine * (cw + px) - px
			x = alignOffset(box.w - lineW, layout.HorizontalAlignment, H.Left, H.Center) + cell * (cw + px)
			y = alignOffset(box.h - usedH, layout.VerticalAlignment, V.Top, V.Center) + line * (ch + py)
		else
			local lineH = inLine * (ch + py) - py
			x = alignOffset(box.w - usedW, layout.HorizontalAlignment, H.Left, H.Center) + line * (cw + px)
			y = alignOffset(box.h - lineH, layout.VerticalAlignment, V.Top, V.Center) + cell * (ch + py)
		end
		local corner = layout.StartCorner
		if corner == Enum.StartCorner.TopRight or corner == Enum.StartCorner.BottomRight then
			x = box.w - x - cw
		end
		if corner == Enum.StartCorner.BottomLeft or corner == Enum.StartCorner.BottomRight then
			y = box.h - y - ch
		end
		local k = ownScale(child)
		table.insert(out, { inst = child, x = box.x + x, y = box.y + y, w = cw * k, h = ch * k })
	end
	return out, math.max(usedW, 0), math.max(usedH, 0)
end

-- 상자 안에 자식을 놓는다. 반환: 놓은 자리들, 레이아웃 내용 너비·높이 (레이아웃이 없으면 0)
function placeChildren(inst: any, box: Box, s: number): ({ Placement }, number, number)
	local layout = nil
	for _, child in inst:GetChildren() do
		if child.ClassName == "UIListLayout" or child.ClassName == "UIGridLayout" then
			layout = child
			break
		end
	end
	if layout and layout.ClassName == "UIListLayout" then
		return listLayout(inst, layout, box, s)
	elseif layout then
		return gridLayout(inst, layout, box, s)
	end
	local out = {}
	for _, child in guiChildren(inst) do
		if child.Visible then
			local w, h = measure(child, box.w, box.h, s)
			local pos, anchor = child.Position, child.AnchorPoint
			local ax = box.x + udim(pos.X, box.w, s)
			local ay = box.y + udim(pos.Y, box.h, s)
			table.insert(out, { inst = child, x = ax - anchor.X * w, y = ay - anchor.Y * h, w = w, h = h })
		end
	end
	return out, 0, 0
end

-- 마디 만들기 ----------------------------------------------------------------------

local assets: { [string]: string } = {}
do
	for name, def in Art.images do
		local file = `art/out/{name}.png`
		if fs.isFile(file) then
			assets[def.id] = file
		end
	end
	local ok, glyphJson = pcall(function()
		return serde.decode("json", fs.readFile("art/out/glyphs.json"))
	end)
	if ok then
		for fontName, font in Art.fonts do
			local local_ = glyphJson[fontName]
			for index, id in font.pages do
				local file = local_ and local_.pages and local_.pages[index]
				if file and fs.isFile("art/out/" .. file) then
					assets[id] = "art/out/" .. file
				end
			end
		end
	end
	local okUp, uploaded = pcall(function()
		return serde.decode("json", fs.readFile("art/uploaded.json"))
	end)
	if okUp then
		for file, info in uploaded do
			local id = "rbxassetid://" .. tostring(info.assetId)
			if not assets[id] and fs.isFile("art/out/" .. file) then
				assets[id] = "art/out/" .. file
			end
		end
	end
end

local function intersect(a: Box?, b: Box): Box
	if not a then
		return b
	end
	local x0, y0 = math.max(a.x, b.x), math.max(a.y, b.y)
	local x1, y1 = math.min(a.x + a.w, b.x + b.w), math.min(a.y + a.h, b.y + b.h)
	return { x = x0, y = y0, w = math.max(0, x1 - x0), h = math.max(0, y1 - y0) }
end

local function boxArray(b: Box): { number }
	return { round(b.x), round(b.y), round(b.w), round(b.h) }
end

local function enumName(value: any): string
	return if typeof(value) == "EnumItem" then value.Name else tostring(value)
end

local function colorSequence(seq: any): { { number } }
	local out = {}
	for _, key in seq.Keypoints do
		local c = rgb(key.Value)
		table.insert(out, { round(key.Time), c[1], c[2], c[3] })
	end
	return out
end

local function numberSequence(seq: any): { { number } }
	local out = {}
	for _, key in seq.Keypoints do
		table.insert(out, { round(key.Time), round(key.Value) })
	end
	return out
end

local function fontName(inst: any): string
	local ok, font = pcall(function()
		return inst.Font
	end)
	if ok and font then
		return font.Name
	end
	local face = prop(inst, "FontFace")
	if face then
		return string.match(face.Family, "([^/]+)%.json$") or face.Family
	end
	return "Legacy"
end

local function describe(inst: any, rect: Box, s: number, clip: Box?, path: string): { [string]: any }
	local node: { [string]: any } = {
		class = inst.ClassName,
		name = inst.Name,
		path = path,
		rect = boxArray(rect),
		zIndex = inst.ZIndex,
		layoutOrder = inst.LayoutOrder,
		scale = round(s),
		pos = {
			round(inst.Position.X.Scale),
			inst.Position.X.Offset,
			round(inst.Position.Y.Scale),
			inst.Position.Y.Offset,
		},
		size = { round(inst.Size.X.Scale), inst.Size.X.Offset, round(inst.Size.Y.Scale), inst.Size.Y.Offset },
		anchor = { round(inst.AnchorPoint.X), round(inst.AnchorPoint.Y) },
	}
	if clip then
		node.clip = boxArray(clip)
	end
	if inst.Rotation ~= 0 then
		node.rotation = round(inst.Rotation)
	end
	if inst.ClipsDescendants then
		node.clipsDescendants = true
	end
	if inst.BackgroundTransparency < 1 then
		node.bg = { color = rgb(inst.BackgroundColor3), transparency = round(inst.BackgroundTransparency) }
		if inst.BorderSizePixel > 0 then
			node.border = {
				size = inst.BorderSizePixel,
				color = rgb(inst.BorderColor3),
				mode = enumName(inst.BorderMode),
			}
		end
	end
	local className = inst.ClassName
	if className == "ImageLabel" or className == "ImageButton" then
		local image = prop(inst, "Image", "")
		if image ~= "" then
			local slice = inst.SliceCenter
			node.image = {
				id = image,
				file = assets[image],
				rectOffset = { inst.ImageRectOffset.X, inst.ImageRectOffset.Y },
				rectSize = { inst.ImageRectSize.X, inst.ImageRectSize.Y },
				color = rgb(inst.ImageColor3),
				transparency = round(inst.ImageTransparency),
				scaleType = enumName(inst.ScaleType),
				sliceCenter = { slice.Min.X, slice.Min.Y, slice.Max.X, slice.Max.Y },
				sliceScale = round(inst.SliceScale),
				tileSize = {
					round(inst.TileSize.X.Scale),
					inst.TileSize.X.Offset,
					round(inst.TileSize.Y.Scale),
					inst.TileSize.Y.Offset,
				},
			}
			local glyph = glyphAt[`{image}:{inst.ImageRectOffset.X}:{inst.ImageRectOffset.Y}`]
			if glyph and inst.Name == "g" then
				node.glyph = glyph.ch
				node.font = glyph.font
			end
		end
	elseif isText(inst) then
		local str = prop(inst, "Text", "")
		if str ~= "" then
			node.text = {
				text = str,
				color = rgb(inst.TextColor3),
				size = round(inst.TextSize * s),
				font = fontName(inst),
				xAlign = enumName(inst.TextXAlignment),
				yAlign = enumName(inst.TextYAlignment),
				transparency = round(inst.TextTransparency),
				strokeColor = rgb(inst.TextStrokeColor3),
				strokeTransparency = round(inst.TextStrokeTransparency),
				wrapped = inst.TextWrapped,
				scaled = inst.TextScaled,
			}
		end
	end
	if className == "Frame" then
		local line, glyphFont, glyphSize = bitmapTextOf(inst)
		if line then
			node.bitmapText = line
			node.font = glyphFont
			node.fontSize = round((glyphSize :: number) * s)
			-- 글자가 실제로 차지하는 곳 (틀에서 글자판 여백을 뺀 곳). 겹침 검사(gui_render --report)에 쓴다
			local pad = Art.fonts[glyphFont].pad * (glyphSize :: number) / Art.fonts[glyphFont].size * s
			node.ink = boxArray({
				x = rect.x + pad,
				y = rect.y + pad,
				w = math.max(0, rect.w - pad * 2),
				h = math.max(0, rect.h - pad * 2),
			})
		end
	end
	for _, child in inst:GetChildren() do
		local cls = child.ClassName
		if cls == "UIGradient" and child.Enabled then
			node.gradient = {
				color = colorSequence(child.Color),
				transparency = numberSequence(child.Transparency),
				rotation = round(child.Rotation),
				offset = { round(child.Offset.X), round(child.Offset.Y) },
			}
		elseif cls == "UIStroke" and child.Enabled then
			node.stroke = {
				color = rgb(child.Color),
				thickness = round(child.Thickness * s),
				transparency = round(child.Transparency),
				mode = enumName(child.ApplyStrokeMode),
			}
		elseif cls == "UICorner" then
			local radius = prop(child, "CornerRadius", roblox.UDim.new(0, 8))
			node.corner = { radius = round(radius.Scale * math.min(rect.w, rect.h) + radius.Offset * s) }
		end
	end
	return node
end

-- 열린 창 목록을 --scroll 만큼 내린다 (열린 창 안의 ScrollingFrame)
local function scrollFor(inst: any): number
	if args.scroll ~= 0 and opened and inst:IsDescendantOf(opened) then
		return args.scroll
	end
	return inst.CanvasPosition.Y
end

-- rect 는 이미 놓은 자리 (부모 배율과 이 물체의 UIScale 까지 들어갔다).
-- 이 물체의 글자·테두리와 자식 오프셋에는 inner = 부모 배율 × 이 물체의 UIScale 을 곱한다
local function build(inst: any, rect: Box, s: number, clip: Box?, path: string): { [string]: any }
	local inner = s * ownScale(inst)
	local node = describe(inst, rect, inner, clip, path)
	local pl, pt, pr, pb = padding(inst, rect.w, rect.h, inner)
	local childClip = clip
	if inst.ClipsDescendants or inst.ClassName == "ScrollingFrame" then
		childClip = intersect(clip, rect)
	end
	local placements
	if inst.ClassName == "ScrollingFrame" then
		-- 캔버스: CanvasSize (창 크기 기준) 와 창 크기 중 큰 쪽, AutomaticCanvasSize 면 내용까지
		local canvasW = math.max(rect.w, udim(inst.CanvasSize.X, rect.w, inner))
		local canvasH = math.max(rect.h, udim(inst.CanvasSize.Y, rect.h, inner))
		local automatic = inst.AutomaticCanvasSize
		local first, layoutW, layoutH =
			placeChildren(inst, { x = 0, y = 0, w = canvasW - pl - pr, h = canvasH - pt - pb }, inner)
		local contentW, contentH = layoutW + pl + pr, layoutH + pt + pb
		for _, p in first do
			contentW = math.max(contentW, p.x + p.w + pl + pr)
			contentH = math.max(contentH, p.y + p.h + pt + pb)
		end
		if automatic == Enum.AutomaticSize.X or automatic == Enum.AutomaticSize.XY then
			canvasW = math.max(canvasW, contentW)
		end
		if automatic == Enum.AutomaticSize.Y or automatic == Enum.AutomaticSize.XY then
			canvasH = math.max(canvasH, contentH)
		end
		local scrollY = math.clamp(scrollFor(inst) * inner, 0, math.max(0, canvasH - rect.h))
		local scrollX = math.clamp(inst.CanvasPosition.X * inner, 0, math.max(0, canvasW - rect.w))
		placements = placeChildren(inst, {
			x = rect.x + pl - scrollX,
			y = rect.y + pt - scrollY,
			w = canvasW - pl - pr,
			h = canvasH - pt - pb,
		}, inner)
		local scroll: { [string]: any } = {
			canvas = { round(canvasW), round(canvasH) },
			position = { round(scrollX), round(scrollY) },
		}
		local canY = inst.ScrollingDirection ~= Enum.ScrollingDirection.X
		local thickness = inst.ScrollBarThickness * inner
		if canY and canvasH > rect.h + 0.5 and thickness > 0 then
			local thumbH = math.max(thickness, rect.h * rect.h / canvasH)
			local travel = rect.h - thumbH
			local left = inst.VerticalScrollBarPosition == Enum.VerticalScrollBarPosition.Left
			local barX = if left then rect.x else rect.x + rect.w - thickness
			scroll.bar = {
				rect = boxArray({
					x = barX,
					y = rect.y + travel * scrollY / math.max(1, canvasH - rect.h),
					w = thickness,
					h = thumbH,
				}),
				color = rgb(inst.ScrollBarImageColor3),
				transparency = round(inst.ScrollBarImageTransparency),
			}
		end
		node.scroll = scroll
	else
		placements =
			placeChildren(inst, { x = rect.x + pl, y = rect.y + pt, w = rect.w - pl - pr, h = rect.h - pt - pb }, inner)
	end
	local children = {}
	for _, p in placements do
		local child = p.inst
		table.insert(
			children,
			build(child, { x = p.x, y = p.y, w = p.w, h = p.h }, inner, childClip, path .. "/" .. child.Name)
		)
	end
	if #children > 0 then
		node.children = children
	end
	return node
end

-- ScreenGui 하나: 화면(뷰포트)에서 위쪽 막대를 뺀 자리
local function buildScreen(gui: any): { [string]: any }?
	if not prop(gui, "Enabled", true) then
		return nil
	end
	local ignore = prop(gui, "IgnoreGuiInset", false)
	local insets = prop(gui, "ScreenInsets", Enum.ScreenInsets.CoreUISafeInsets)
	local top = 0
	if
		not ignore and (insets == Enum.ScreenInsets.CoreUISafeInsets or insets == Enum.ScreenInsets.TopbarSafeInsets)
	then
		top = args.inset
	end
	local rect = { x = 0, y = top, w = args.width, h = args.height - top }
	local placements = placeChildren(gui, rect, 1)
	local children = {}
	for _, p in placements do
		table.insert(
			children,
			build(p.inst, { x = p.x, y = p.y, w = p.w, h = p.h }, 1, nil, gui.Name .. "/" .. p.inst.Name)
		)
	end
	return {
		class = "ScreenGui",
		name = gui.Name,
		path = gui.Name,
		rect = boxArray(rect),
		displayOrder = gui.DisplayOrder,
		zIndexBehavior = enumName(gui.ZIndexBehavior),
		ignoreGuiInset = ignore,
		children = children,
	}
end

-- 그리는 차례: Sibling 은 형제끼리 ZIndex 순 (자손은 부모 바로 위), Global 은 화면 전체를 ZIndex 순
local order = 0
local function stableSort(list: { any }, key: (any) -> number)
	local indexed = {}
	for i, item in list do
		indexed[i] = { item = item, i = i }
	end
	table.sort(indexed, function(a, b)
		local ka, kb = key(a.item), key(b.item)
		if ka ~= kb then
			return ka < kb
		end
		return a.i < b.i
	end)
	for i, entry in indexed do
		list[i] = entry.item
	end
end

local function zKey(node)
	return node.zIndex or 1
end

local function assignSibling(node)
	order += 1
	node.order = order
	if node.children then
		local sorted = table.clone(node.children)
		stableSort(sorted, zKey)
		for _, child in sorted do
			assignSibling(child)
		end
	end
end

local function assignGlobal(root)
	local flat = {}
	local function walk(node)
		table.insert(flat, node)
		for _, child in node.children or {} do
			walk(child)
		end
	end
	for _, child in root.children or {} do
		walk(child)
	end
	stableSort(flat, zKey)
	for _, node in flat do
		order += 1
		node.order = order
	end
end

local guis = {}
for _, gui in env.playerGui:GetChildren() do
	if gui.ClassName == "ScreenGui" then
		local tree = buildScreen(gui)
		if tree then
			table.insert(guis, tree)
		end
	end
end
stableSort(guis, function(g)
	return g.displayOrder
end)
for _, tree in guis do
	order += 1
	tree.order = order
	if tree.zIndexBehavior == "Global" then
		assignGlobal(tree)
	else
		for _, child in
			(function()
				local sorted = table.clone(tree.children)
				stableSort(sorted, zKey)
				return sorted
			end)()
		do
			assignSibling(child)
		end
	end
end

-- Roblox 기본 UI 자리 (어림): 위쪽 막대 단추, 도구 칸 (공격 법구), 터치 점프 버튼 -----------------------

local core = {}
if args.core then
	table.insert(core, { kind = "topbar", label = "Roblox", rect = { 16, 12, 44, 44 }, round = 22 })
	table.insert(core, { kind = "topbar", label = "메뉴·채팅", rect = { 68, 12, 140, 44 }, round = 22 })
	-- 도구 칸: 60px 칸, 5px 틈, 화면 아래 가운데 (작은 화면은 50px 칸, 셋까지)
	local weapons = state.weapons or {}
	local small = args.width < 1024 or args.height < 500
	local icon = if small then 50 else 60
	local count = math.min(#weapons, if small then 3 else 10)
	local total = count * (icon + 5) + 5
	local left = args.width / 2 - total / 2
	local CombatShared = loader.require(shared.Combat)
	for i = 1, count do
		local name = ""
		pcall(function()
			name = CombatShared.weaponName(weapons[i])
		end)
		table.insert(core, {
			kind = "backpack",
			label = name,
			key = tostring(i),
			rect = { round(left + 5 + (i - 1) * (icon + 5)), args.height - icon - 5, icon, icon },
			round = 6,
		})
	end
	if args.touch then
		local jump = if math.min(args.width, args.height) <= 500 then 70 else 120
		local x = if jump == 70 then args.width - 95 else args.width - 170
		local y = if jump == 70 then args.height - 90 else args.height - 210
		table.insert(core, { kind = "jump", label = "점프", rect = { x, y, jump, jump }, round = jump / 2 })
	end
end

-- 쓰기 ---------------------------------------------------------------------------

local hudScale = nil
local status = hudGui and hudGui:FindFirstChild("StatusWindow")
if status and childOfClass(status, "UIScale") then
	hudScale = round(childOfClass(status, "UIScale").Scale)
end

local outPath = args.out
	or `build/gui_{args.which}{if args.tab then "_" .. (string.gsub(args.tab, "[/%s]", "_")) else ""}.json`
local dir = string.match(outPath, "^(.*)/[^/]*$")
if dir and dir ~= "" and not fs.isDir(dir) then
	fs.writeDir(dir)
end

local snapshot = {
	tool = "tools/gui_snapshot.luau",
	screen = {
		width = args.width,
		height = args.height,
		inset = args.inset,
		touch = args.touch,
		hudScale = hudScale,
		which = args.which,
		tab = args.tab,
		scroll = args.scroll,
	},
	assets = assets,
	core = core,
	guis = guis,
}
fs.writeFile(outPath, serde.encode("json", snapshot, false))

local count = 0
local function countNodes(node)
	count += 1
	for _, child in node.children or {} do
		countNodes(child)
	end
end
for _, tree in guis do
	countNodes(tree)
end
print(
	`{outPath}: {args.width}×{args.height}, HUD 배율 {hudScale or "?"}, 보이는 GUI {count}개 (창: {args.which}{if args.tab
		then " / " .. args.tab
		else ""})`
)
-- 알림 타이머 같은 남은 task 를 기다리지 않는다
process.exit(0)
