-- 맵 전체 미리보기 1단계: 가짜 Roblox 환경(tools/roblox_mock.luau)에서 진짜 서버 모듈을 돌려 Workspace 를 만들고
-- 모든 BasePart(+ SurfaceGui 간판, 조명 값)를 JSON 으로 출력합니다. 렌더링은 render.js 가 합니다.
--
-- 사용법(roblox-rng 폴더에서, 보통은 tools/world_preview/preview.sh 가 부름):
--   luaurun tools/world_preview/world.luau [variant=이름] [field=Config필드] [players=3] [scenery=off]
--
-- 순서(init.server.luau 에 적힌 순서를 따름): default.project.json 의 Workspace/Lighting → World.build →
--   ParkService.init → Scenery(있으면) → 샘플 플레이어 부지 배정·전시 → 스케줄러 5초 → 덤프.
-- Scenery 는 src/server/Scenery.luau 또는 src/server/Scenery/init.luau. 없거나 오류가 나도 나머지는 그림.
--   부르는 방법(함수 이름·인자)은 init.server.luau 의 "Scenery.xxx(...)" 호출을 읽어서 똑같이 부릅니다.
--   variant=... 를 주면 그 호출이 읽는 Config 필드(이름에 VARIANT/SCENERY/MAP/THEME 가 든 것)를 바꾼 뒤 부름.
--   필드를 못 찾으면 field=이름 으로 직접 지정. 그래도 없으면 variant 를 첫 인자로 넘김.
-- 출력: 표준 출력의 DUMP_BEGIN / DUMP_END 사이 한 줄 JSON. 그 밖의 줄은 진행 상황·경고.

local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()
local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()

local opts: { [string]: string } = { players = "3" }
for _, arg in ARGS do
	local key, value = arg:match("^([%w_]+)=(.*)$")
	if key then
		opts[key] = value
	end
end

local shared = Harness.folder("src/shared")
local server = Harness.folder("src/server")
Mock.link(Mock.ReplicatedStorage, "Shared", shared)
Mock.link(Mock.services.ServerScriptService, "Server", server)

local notes: { string } = {}
local function note(text: string)
	table.insert(notes, text)
	print("[world] " .. text)
end

-- default.project.json -> Workspace / Lighting --------------------------------------
-- Rojo 속성 값: 숫자/문자열/불리언/배열(Vector3, Color3) 과 {"CFrame": {...}}, {"Enum": n} 같은 명시형.
-- CFrame 의 orientation 은 행(row) 3개: [[R00,R01,R02],[R10,R11,R12],[R20,R21,R22]] (rbx-dom Matrix3 x/y/z = 행)

local PART_TYPES = { [0] = "Ball", [1] = "Block", [2] = "Cylinder", [3] = "Wedge", [4] = "CornerWedge" }
local MATERIALS = {
	[256] = "Plastic",
	[272] = "SmoothPlastic",
	[288] = "Neon",
	[512] = "Wood",
	[528] = "WoodPlanks",
	[784] = "Marble",
	[788] = "Basalt",
	[800] = "Slate",
	[804] = "CrackedLava",
	[816] = "Concrete",
	[820] = "Limestone",
	[832] = "Granite",
	[836] = "Pavement",
	[848] = "Brick",
	[864] = "Pebble",
	[880] = "Cobblestone",
	[896] = "Rock",
	[912] = "Sandstone",
	[1040] = "CorrodedMetal",
	[1056] = "DiamondPlate",
	[1072] = "Foil",
	[1088] = "Metal",
	[1280] = "Grass",
	[1284] = "LeafyGrass",
	[1296] = "Sand",
	[1312] = "Fabric",
	[1328] = "Snow",
	[1344] = "Mud",
	[1360] = "Ground",
	[1376] = "Asphalt",
	[1392] = "Salt",
	[1536] = "Ice",
	[1552] = "Glacier",
	[1568] = "Glass",
	[1584] = "ForceField",
	[2048] = "Water",
}
local ENUM_PROPS = {
	Material = "Material",
	Shape = "PartType",
	TopSurface = "SurfaceType",
	BottomSurface = "SurfaceType",
	LeftSurface = "SurfaceType",
	RightSurface = "SurfaceType",
	FrontSurface = "SurfaceType",
	BackSurface = "SurfaceType",
	Face = "NormalId",
	Technology = "Technology",
}
local COLOR_PROPS = {
	Color = true,
	Ambient = true,
	OutdoorAmbient = true,
	FogColor = true,
	Decay = true,
	TintColor = true,
	ColorShift_Top = true,
	ColorShift_Bottom = true,
	BackgroundColor3 = true,
	TextColor3 = true,
	ImageColor3 = true,
}

local function matrixCFrame(value): CFrame
	local p = value.position or { 0, 0, 0 }
	local o = value.orientation or { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } }
	return CFrame.new(p[1], p[2], p[3], o[1][1], o[1][2], o[1][3], o[2][1], o[2][2], o[2][3], o[3][1], o[3][2], o[3][3])
end

local function convert(prop: string, raw: any): any
	if type(raw) == "table" and raw[1] == nil then
		local kind, value = next(raw)
		if raw.position then
			return matrixCFrame(raw)
		elseif kind == "CFrame" then
			return matrixCFrame(value)
		elseif kind == "Vector3" then
			return Vector3.new(value[1], value[2], value[3])
		elseif kind == "Vector2" then
			return Vector2.new(value[1], value[2])
		elseif kind == "Color3" then
			return Color3.new(value[1], value[2], value[3])
		elseif kind == "Color3uint8" then
			return Color3.fromRGB(value[1], value[2], value[3])
		elseif kind == "Enum" then
			local enumName = ENUM_PROPS[prop]
			if enumName == "PartType" then
				return "PartType." .. (PART_TYPES[value] or "Block")
			elseif enumName == "Material" then
				return "Material." .. (MATERIALS[value] or "Plastic")
			elseif enumName then
				return enumName .. "." .. tostring(value)
			end
			return value
		end
		return value
	end
	if type(raw) == "table" then
		if COLOR_PROPS[prop] then
			return Color3.new(raw[1], raw[2], raw[3])
		elseif #raw == 3 then
			return Vector3.new(raw[1], raw[2], raw[3])
		elseif #raw == 2 then
			return Vector2.new(raw[1], raw[2])
		end
		return raw
	end
	if type(raw) == "string" and ENUM_PROPS[prop] then
		return ENUM_PROPS[prop] .. "." .. raw
	end
	return raw
end

-- Shape 을 Size 보다 먼저 정해야 Roblox 와 같은 결과(Ball/Cylinder 검사 순서)
local PROP_ORDER = { Shape = 1, Size = 2, CFrame = 3, Position = 4, Orientation = 5 }
local function setProperties(instance, properties)
	local keys = {}
	for key in properties do
		table.insert(keys, key)
	end
	table.sort(keys, function(a, b)
		local pa, pb = PROP_ORDER[a] or 9, PROP_ORDER[b] or 9
		if pa ~= pb then
			return pa < pb
		end
		return a < b
	end)
	for _, key in keys do
		local ok, err = pcall(function()
			instance[key] = convert(key, properties[key])
		end)
		if not ok then
			note(string.format("project: %s.%s 를 못 정했습니다: %s", instance.Name, key, tostring(err)))
		end
	end
end

local function buildProjectNode(parent, name: string, node)
	if node["$path"] then
		note(
			"project: "
				.. name
				.. " 는 $path 라서 미리보기에 안 나옵니다("
				.. tostring(node["$path"])
				.. ")"
		)
		return
	end
	local instance = Instance.new(node["$className"] or "Folder")
	instance.Name = name
	setProperties(instance, node["$properties"] or {})
	for childName, child in node do
		if childName:sub(1, 1) ~= "$" and type(child) == "table" then
			buildProjectNode(instance, childName, child)
		end
	end
	instance.Parent = parent
end

local function loadProject()
	local text = readfile("default.project.json")
	assert(text, "default.project.json 을 읽지 못했습니다")
	local tree = Mock.json.decode(text).tree
	Mock.origin = "project"
	for serviceName, target in { Workspace = Mock.Workspace, Lighting = Mock.Lighting } do
		local node = tree[serviceName]
		if node then
			setProperties(target, node["$properties"] or {})
			for childName, child in node do
				if childName:sub(1, 1) ~= "$" and type(child) == "table" then
					buildProjectNode(target, childName, child)
				end
			end
		end
	end
end
loadProject()

-- 서버 모듈 -----------------------------------------------------------------------
local Config = Harness.require(shared.Config)
local Landmarks = Harness.require(shared.Landmarks)
local PlayerState = Harness.require(shared.PlayerState)

local initSource = readfile("src/server/init.server.luau") or ""

local function sceneryFiles(): { string }
	local files = {}
	if readfile("src/server/Scenery.luau") then
		table.insert(files, "src/server/Scenery.luau")
	end
	for _, name in listdir("src/server/Scenery") do
		if name:match("%.luau$") then
			table.insert(files, "src/server/Scenery/" .. name)
		end
	end
	return files
end
local SCENERY_FILES = sceneryFiles()
local hasScenery = readfile("src/server/Scenery.luau") ~= nil or readfile("src/server/Scenery/init.luau") ~= nil
local sceneryOff = opts.scenery == "off" or opts.scenery == "0" or opts.scenery == "false"

-- 주석(--) 밖에 있는 첫 위치
local function findCode(source: string, pattern: string, init: number?): (number?, number?, ...string)
	local pos = init or 1
	while true do
		local found = table.pack(source:find(pattern, pos))
		local s = found[1]
		if not s then
			return nil
		end
		local lineStart = 1
		local back = source:sub(1, s - 1):match(".*\n()")
		if back then
			lineStart = back
		end
		if not source:sub(lineStart, s - 1):find("%-%-") then
			return table.unpack(found, 1, found.n)
		end
		pos = found[2] + 1
	end
end

-- text 의 처음(여는 괄호 바로 뒤)부터 짝이 맞는 ')' 앞까지
local function untilClose(text: string): string
	local depth = 0
	local quote: string? = nil
	for i = 1, #text do
		local c = text:sub(i, i)
		if quote then
			if c == quote and text:sub(i - 1, i - 1) ~= "\\" then
				quote = nil
			end
		elseif c == '"' or c == "'" or c == "`" then
			quote = c
		elseif c == "(" or c == "{" or c == "[" then
			depth += 1
		elseif c == ")" or c == "}" or c == "]" then
			if depth == 0 then
				return text:sub(1, i - 1)
			end
			depth -= 1
		end
	end
	return text
end

type SceneryCall = { Fn: string, Method: boolean, Args: string, Position: number, Found: boolean }

-- init.server.luau 에서 Scenery 호출 찾기: Scenery.build(...) / pcall(Scenery.build, ...) / Scenery:build(...)
local function findSceneryCall(): SceneryCall
	local s, e, sep, fn = findCode(initSource, "Scenery%s*([%.:])%s*([%a_][%w_]*)")
	if not s then
		return { Fn = "build", Method = false, Args = "", Position = math.huge, Found = false }
	end
	local after = initSource:sub((e :: number) + 1)
	local args = ""
	local open = after:match("^%s*%(()")
	if open then
		args = untilClose(after:sub(open))
	else
		local comma = after:match("^%s*,()")
		if comma then
			args = untilClose(after:sub(comma))
		end
	end
	args = args:gsub("^%s+", ""):gsub("%s+$", "")
	return { Fn = fn, Method = sep == ":", Args = args, Position = s :: number, Found = true }
end

local sceneryCall = findSceneryCall()

-- variant 를 넣을 Config 필드 찾기
local VARIANT_WORDS = { "VARIANT", "SCENERY", "MAP", "THEME", "STYLE", "BIOME" }
local function looksLikeVariant(name: string): boolean
	local upper = name:upper()
	for _, word in VARIANT_WORDS do
		if upper:find(word, 1, true) then
			return true
		end
	end
	return false
end
local function findVariantField(): string?
	if opts.field then
		return opts.field
	end
	for field in sceneryCall.Args:gmatch("Config%.([%a_][%w_]*)") do
		return field
	end
	for _, path in SCENERY_FILES do
		local source = readfile(path) or ""
		for field in source:gmatch("Config%.([%a_][%w_]*)") do
			if looksLikeVariant(field) then
				return field
			end
		end
	end
	for key in Config do
		if type(key) == "string" and looksLikeVariant(key) and type(Config[key]) ~= "table" then
			return key
		end
	end
	return nil
end

local variantArg: string? = nil
local variantField: string? = nil
if opts.variant and opts.variant ~= "" then
	variantField = findVariantField()
	if variantField then
		local current = Config[variantField]
		local value: any = opts.variant
		if type(current) == "number" then
			value = tonumber(opts.variant) or opts.variant
		elseif type(current) == "boolean" then
			value = opts.variant == "true"
		end
		note(string.format("변형: Config.%s = %s (원래 %s)", variantField, tostring(value), tostring(current)))
		Config[variantField] = value
	else
		variantArg = opts.variant
		note("변형: Config 필드를 못 찾아서 Scenery 호출의 첫 인자로 넘깁니다: " .. opts.variant)
	end
end

local World = Harness.require(server.World)
local ParkService = Harness.require(server.ParkService)
local Scenery: any = nil
if sceneryOff then
	note("scenery=off: 풍경 없이 그림")
elseif hasScenery then
	local ok, result = pcall(Harness.require, server.Scenery)
	if ok then
		Scenery = result
	else
		note("Scenery 모듈을 불러오지 못했습니다: " .. tostring(result))
	end
else
	note(
		"Scenery 모듈이 아직 없습니다(src/server/Scenery.luau 또는 Scenery/init.luau) — 풍경 없이 그림"
	)
end

-- init.server.luau 의 호출 인자 식을 같은 이름들(Config, 공용 모듈, World ...)로 계산
local function evalArgs(text: string): { n: number, [number]: any }
	if text:match("^%s*$") then
		return { n = 0 }
	end
	local env = setmetatable({
		Config = Config,
		Shared = shared,
		World = World,
		ParkService = ParkService,
		Scenery = Scenery,
		Workspace = Mock.Workspace,
		workspace = Mock.Workspace,
	}, {
		__index = function(_, key)
			local found = rawget(_G, key)
			if found ~= nil then
				return found
			end
			if type(key) == "string" and readfile("src/shared/" .. key .. ".luau") then
				return Harness.require(shared[key])
			end
			return nil
		end,
	})
	local ok, fn = pcall(compile, "return " .. text, "scenery-args")
	if not ok then
		note("Scenery 인자 식을 해석하지 못했습니다: " .. text)
		return { n = 0 }
	end
	setfenv(fn, env)
	local result = table.pack(pcall(fn))
	if not result[1] then
		note("Scenery 인자 계산 오류: " .. tostring(result[2]))
		return { n = 0 }
	end
	return table.pack(table.unpack(result, 2, result.n))
end

local function runStep(origin: string, label: string, fn: () -> ())
	Mock.origin = origin
	local ok, err = Mock.run(fn)
	if not ok then
		note(label .. " 실패: " .. tostring(err))
	end
end

local steps = {
	{
		Position = findCode(initSource, "World%.build") or 1,
		Origin = "World",
		Run = World.build,
		Label = "World.build",
	},
	{
		Position = findCode(initSource, "ParkService%.init") or 2,
		Origin = "Parks",
		Run = ParkService.init,
		Label = "ParkService.init",
	},
}
if Scenery then
	local fn = Scenery[sceneryCall.Fn]
	if type(fn) ~= "function" then
		note("Scenery." .. sceneryCall.Fn .. " 함수가 없습니다")
	else
		if not sceneryCall.Found then
			note("init.server.luau 에 아직 Scenery 호출이 없어 Scenery.build() 로 부릅니다")
		end
		local label = "Scenery." .. sceneryCall.Fn .. "(" .. sceneryCall.Args .. ")"
		table.insert(steps, {
			Position = sceneryCall.Position,
			Origin = "Scenery",
			Label = label,
			Run = function()
				local args = evalArgs(sceneryCall.Args)
				if variantArg and args.n == 0 then
					args = { n = 1, variantArg }
				end
				if sceneryCall.Method then
					fn(Scenery, table.unpack(args, 1, args.n))
				else
					fn(table.unpack(args, 1, args.n))
				end
			end,
		})
	end
	local list = Scenery.VARIANTS or Scenery.Variants or Scenery.variants
	if type(list) == "table" then
		local names = {}
		for key, value in list do
			table.insert(names, if type(key) == "string" then key else tostring(value))
		end
		table.sort(names)
		note("Scenery 변형 목록: " .. table.concat(names, ", "))
	end
end
table.sort(steps, function(a, b)
	return a.Position < b.Position
end)
for _, step in steps do
	runStep(step.Origin, step.Label, step.Run)
end

-- 샘플 플레이어: 부지 3개(기본)를 채워서 공원이 붐비는 모습으로 --------------------------
local SAMPLES = {
	{ Name = "TravelKing", DisplayName = "여행왕", Park = 10, Count = 36, Stride = 5 },
	{ Name = "Explorer", DisplayName = "모험가", Park = 4, Count = 14, Stride = 7 },
	{ Name = "Newbie", DisplayName = "새내기", Park = 0, Count = 3, Stride = 11 },
}
local playerCount = math.clamp(tonumber(opts.players) or 3, 0, 8)
Mock.origin = "Players"
for i = 1, playerCount do
	local sample = SAMPLES[(i - 1) % #SAMPLES + 1]
	local player = { Name = sample.Name .. i, DisplayName = sample.DisplayName, UserId = 1000 + i }
	local data = PlayerState.new()
	data.Upgrades.Park = sample.Park
	-- 명소 목록을 stride 간격으로 건너뛰며 고름(목록 길이와 서로소인 간격이라 한 바퀴에 모두 다름)
	local list = Landmarks.List
	local stride = sample.Stride
	local function gcd(a: number, b: number): number
		while b ~= 0 do
			a, b = b, a % b
		end
		return a
	end
	while gcd(stride, #list) ~= 1 do
		stride += 1
	end
	for k = 1, math.min(sample.Count, #list) do
		local index = (i * 3 + k * stride) % #list + 1
		local landmark = list[index]
		data.Inventory[landmark.Id] = 1 + (index * 7) % 40
		data.Discovered[landmark.Id] = true
	end
	local ok, err = Mock.run(function()
		ParkService.assign(player)
		ParkService.update(player, data)
	end)
	if not ok then
		note("샘플 플레이어 " .. i .. " 전시 실패: " .. tostring(err))
	end
end

local stepsRun, pending = Mock.runScheduler(5)
if stepsRun > 0 or pending > 0 then
	note(string.format("스케줄러: task %d개 실행, 5초 뒤에도 기다리는 task %d개", stepsRun, pending))
end

-- 덤프 --------------------------------------------------------------------------------
local function num(x: number): string
	if x ~= x or x == math.huge or x == -math.huge then
		return "0"
	end
	local s = string.format("%.4f", x)
	s = s:gsub("0+$", ""):gsub("%.$", "")
	if s == "-0" then
		return "0"
	end
	return s
end
local function nums(list: { number }): string
	local out = {}
	for i, v in list do
		out[i] = num(v)
	end
	return "[" .. table.concat(out, ",") .. "]"
end
local function colorOf(c): string
	return nums({ c.R, c.G, c.B })
end
local function str(s: any): string
	return Mock.json.encode(tostring(s))
end
local function enumName(value: any): string
	local text = tostring(value)
	return text:match("%.([%w_]+)$") or text
end

local function pathOf(instance): string
	local names = {}
	local node = instance
	while node and node ~= Mock.Workspace do
		table.insert(names, 1, node.Name)
		node = node.Parent
	end
	return table.concat(names, "/")
end

local function shapeOf(part): (string, boolean)
	local class = part.ClassName
	if class == "WedgePart" then
		return "Wedge", false
	elseif class == "CornerWedgePart" then
		return "CornerWedge", false
	elseif class == "Part" or class == "SpawnLocation" or class == "Seat" then
		return enumName(part.Shape or "PartType.Block"), false
	end
	return "Block", true -- MeshPart, Union, Truss ... 은 상자로 대신 그림
end

local partRecords = {}
local approx = 0
local function partRecord(
	name: string,
	path: string,
	origin: string,
	class: string,
	shape: string,
	cf,
	size,
	c,
	material: string,
	transparency: number,
	castShadow: boolean,
	canCollide: boolean
)
	local m = cf.m
	table.insert(
		partRecords,
		string.format(
			'{"n":%s,"path":%s,"o":%s,"c":%s,"s":%s,"p":%s,"m":%s,"z":%s,"col":%s,"mat":%s,"t":%s,"cs":%s,"cc":%s}',
			str(name),
			str(path),
			str(origin),
			str(class),
			str(shape),
			nums({ cf.p.X, cf.p.Y, cf.p.Z }),
			nums(m),
			nums({ size.X, size.Y, size.Z }),
			colorOf(c),
			str(material),
			num(transparency),
			tostring(castShadow),
			tostring(canCollide)
		)
	)
end

local parts = {}
for _, d in Mock.Workspace:GetDescendants() do
	if Mock.isBasePart(d) and d.ClassName ~= "Terrain" then
		table.insert(parts, d)
	end
end
for _, part in parts do
	local shape, isApprox = shapeOf(part)
	if isApprox then
		approx += 1
	end
	partRecord(
		part.Name,
		pathOf(part),
		rawget(part, "__origin"),
		part.ClassName,
		shape,
		part.CFrame,
		part.Size,
		part.Color,
		enumName(part.Material),
		part.Transparency or 0,
		part.CastShadow ~= false,
		part.CanCollide ~= false
	)
end
if approx > 0 then
	note(string.format("MeshPart/Union/Truss 등 %d개는 상자로 대신 그립니다", approx))
end

-- 지형 채우기 -> 파트처럼(원기둥은 Y 축이라 X 축 원기둥으로 돌려서)
local TERRAIN_COLORS = {
	Grass = { 106, 127, 63 },
	LeafyGrass = { 115, 132, 74 },
	Water = { 12, 84, 92 },
	Sand = { 143, 126, 95 },
	Rock = { 102, 108, 111 },
	Ground = { 102, 92, 59 },
	Mud = { 58, 46, 36 },
	Snow = { 195, 199, 218 },
	Slate = { 63, 127, 107 },
	Sandstone = { 137, 90, 71 },
	Basalt = { 30, 30, 37 },
	Asphalt = { 115, 123, 107 },
	Salt = { 198, 189, 181 },
	Ice = { 129, 194, 224 },
	Glacier = { 101, 176, 234 },
	Limestone = { 206, 173, 148 },
	Pavement = { 148, 148, 140 },
	Cobblestone = { 132, 123, 90 },
	Concrete = { 127, 102, 63 },
	Brick = { 138, 86, 62 },
	Granite = { 132, 123, 90 },
	WoodPlanks = { 139, 109, 79 },
	CrackedLava = { 232, 156, 74 },
}
for i, f in Mock.terrainFills do
	local material = enumName(f.Material)
	if material ~= "Air" then
		local rgb = TERRAIN_COLORS[material] or { 120, 120, 120 }
		local c = Mock.terrainColors[f.Material] or Color3.fromRGB(rgb[1], rgb[2], rgb[3])
		local cf, size, shape = f.CFrame, f.Size, f.Kind
		if shape == "Cylinder" then
			cf = cf * CFrame.Angles(0, 0, math.pi / 2)
			size = Vector3.new(f.Size.Y, f.Size.X, f.Size.X)
		end
		partRecord(
			"Terrain" .. f.Kind,
			"Terrain/" .. i,
			f.Origin,
			"Terrain",
			shape,
			cf,
			size,
			c,
			material,
			if material == "Water" then 0.3 else 0,
			material ~= "Water",
			material ~= "Water"
		)
	end
end
if #Mock.terrainFills > 0 then
	note(
		string.format(
			"지형 채우기 %d개는 파트 모양으로 대신 그립니다(매끈한 지형 표면은 아님)",
			#Mock.terrainFills
		)
	)
end

-- SurfaceGui 간판: 면 좌표계 + GUI 상자 목록(렌더러가 캔버스에 그려서 면에 붙임) -----------
-- 면별 GUI 가로(오른쪽)·세로(위) 방향(파트 좌표). Front/Back/Left/Right 는 밖에서 면을 볼 때의 오른쪽.
-- Top/Bottom 은 추정(Top: 오른쪽 +X, 위 -Z).
local FACES = {
	Front = { N = Vector3.new(0, 0, -1), R = Vector3.new(-1, 0, 0), U = Vector3.new(0, 1, 0), W = "X", H = "Y" },
	Back = { N = Vector3.new(0, 0, 1), R = Vector3.new(1, 0, 0), U = Vector3.new(0, 1, 0), W = "X", H = "Y" },
	Right = { N = Vector3.new(1, 0, 0), R = Vector3.new(0, 0, -1), U = Vector3.new(0, 1, 0), W = "Z", H = "Y" },
	Left = { N = Vector3.new(-1, 0, 0), R = Vector3.new(0, 0, 1), U = Vector3.new(0, 1, 0), W = "Z", H = "Y" },
	Top = { N = Vector3.new(0, 1, 0), R = Vector3.new(1, 0, 0), U = Vector3.new(0, 0, -1), W = "X", H = "Z" },
	Bottom = { N = Vector3.new(0, -1, 0), R = Vector3.new(-1, 0, 0), U = Vector3.new(0, 0, -1), W = "X", H = "Z" },
}

-- ImageIds: 에셋 Id -> 이름(art/png/<이름>.png 로 그림)
local imageNames = {}
do
	local ok, ids = pcall(Harness.require, shared.ImageIds)
	if ok and type(ids) == "table" then
		for name, value in ids do
			local id = tostring(value):match("(%d+)")
			if id then
				imageNames[id] = name
			end
		end
	end
end

local GUI_CLASSES = { Frame = true, TextLabel = true, TextButton = true, ImageLabel = true, ImageButton = true }

local function childOfClass(instance, class: string)
	for _, child in instance:GetChildren() do
		if child.ClassName == class then
			return child
		end
	end
	return nil
end

local function udimPx(u, parentSize: number): number
	return u.Scale * parentSize + u.Offset
end

local function textFields(node, gui)
	local text = gui.Text
	if type(text) ~= "string" or text == "" then
		return
	end
	local stroke = childOfClass(gui, "UIStroke")
	local plain = if gui.RichText then text:gsub("<[^>]*>", "") else text
	node.text = {
		s = plain,
		rich = if gui.RichText then text else nil,
		color = gui.TextColor3 and { gui.TextColor3.R, gui.TextColor3.G, gui.TextColor3.B } or { 0, 0, 0 },
		t = gui.TextTransparency or 0,
		scaled = gui.TextScaled == true,
		size = gui.TextSize or 14,
		font = enumName(gui.Font or "Font.SourceSans"),
		xa = enumName(gui.TextXAlignment or "TextXAlignment.Center"),
		ya = enumName(gui.TextYAlignment or "TextYAlignment.Center"),
		stroke = if stroke and stroke.Enabled ~= false
			then { w = stroke.Thickness or 1, color = { stroke.Color.R, stroke.Color.G, stroke.Color.B } }
			else nil,
	}
end

local function guiNodes(container, rect, out: { any })
	-- 형제는 ZIndex 순서(ZIndexBehavior.Sibling)
	local children = {}
	for _, child in container:GetChildren() do
		if GUI_CLASSES[child.ClassName] and child.Visible ~= false then
			table.insert(children, child)
		end
	end
	table.sort(children, function(a, b)
		return (a.ZIndex or 1) < (b.ZIndex or 1)
	end)
	-- 부모의 UIPadding 은 자식 배치 영역을 줄임
	local pad = childOfClass(container, "UIPadding")
	local inner = rect
	if pad then
		local l = pad.PaddingLeft and udimPx(pad.PaddingLeft, rect.w) or 0
		local r = pad.PaddingRight and udimPx(pad.PaddingRight, rect.w) or 0
		local t = pad.PaddingTop and udimPx(pad.PaddingTop, rect.h) or 0
		local b = pad.PaddingBottom and udimPx(pad.PaddingBottom, rect.h) or 0
		inner = { x = rect.x + l, y = rect.y + t, w = rect.w - l - r, h = rect.h - t - b }
	end
	for _, gui in children do
		local size = gui.Size or UDim2.new()
		local position = gui.Position or UDim2.new()
		local anchor = gui.AnchorPoint or Vector2.new()
		local rel = enumName(gui.SizeConstraint or "SizeConstraint.RelativeXY")
		local bw = if rel == "RelativeYY" then inner.h else inner.w
		local bh = if rel == "RelativeXX" then inner.w else inner.h
		local w = udimPx(size.X, bw)
		local h = udimPx(size.Y, bh)
		local x = inner.x + udimPx(position.X, inner.w) - anchor.X * w
		local y = inner.y + udimPx(position.Y, inner.h) - anchor.Y * h
		local node: { [string]: any } = { cls = gui.ClassName, x = x, y = y, w = w, h = h, rot = gui.Rotation or 0 }
		local bgT = gui.BackgroundTransparency or 0
		if bgT < 1 and gui.BackgroundColor3 then
			node.bg = { gui.BackgroundColor3.R, gui.BackgroundColor3.G, gui.BackgroundColor3.B }
			node.bgT = bgT
		end
		local corner = childOfClass(gui, "UICorner")
		if corner then
			local radius = corner.CornerRadius or UDim.new(0, 8)
			node.corner = udimPx(radius, math.min(w, h))
		end
		local stroke = childOfClass(gui, "UIStroke")
		if stroke and stroke.Enabled ~= false and (gui.ClassName == "Frame" or gui.ClassName == "ImageLabel") then
			node.stroke = {
				w = stroke.Thickness or 1,
				color = { stroke.Color.R, stroke.Color.G, stroke.Color.B },
				t = stroke.Transparency or 0,
			}
		end
		local gradient = childOfClass(gui, "UIGradient")
		if gradient and gradient.Enabled ~= false and gradient.Color then
			local keys = gradient.Color.Keypoints
			local a, b = keys[1].Value, keys[#keys].Value
			node.gradient = { from = { a.R, a.G, a.B }, to = { b.R, b.G, b.B }, rot = gradient.Rotation or 0 }
		end
		if gui.ClassName == "ImageLabel" or gui.ClassName == "ImageButton" then
			local id = tostring(gui.Image or ""):match("(%d+)")
			if id then
				local sc = gui.SliceCenter
				local ic = gui.ImageColor3 or Color3.new(1, 1, 1)
				node.image = {
					name = imageNames[id] or id,
					color = { ic.R, ic.G, ic.B },
					t = gui.ImageTransparency or 0,
					scale = enumName(gui.ScaleType or "ScaleType.Stretch"),
					slice = if sc then { sc.MinX, sc.MinY, sc.MaxX, sc.MaxY } else nil,
					sliceScale = gui.SliceScale or 1,
				}
			end
		end
		if gui.ClassName == "TextLabel" or gui.ClassName == "TextButton" then
			textFields(node, gui)
			local tpad = childOfClass(gui, "UIPadding")
			if tpad and node.text then
				node.text.pad = {
					tpad.PaddingLeft and udimPx(tpad.PaddingLeft, w) or 0,
					tpad.PaddingTop and udimPx(tpad.PaddingTop, h) or 0,
					tpad.PaddingRight and udimPx(tpad.PaddingRight, w) or 0,
					tpad.PaddingBottom and udimPx(tpad.PaddingBottom, h) or 0,
				}
			end
		end
		table.insert(out, node)
		guiNodes(gui, { x = x, y = y, w = w, h = h }, out)
	end
end

local guiRecords = {}
for _, d in Mock.Workspace:GetDescendants() do
	if d.ClassName == "SurfaceGui" and d.Enabled ~= false then
		local part = d.Adornee or d.Parent
		if part and Mock.isBasePart(part) then
			local face = FACES[enumName(d.Face or "NormalId.Front")] or FACES.Front
			local fw, fh = part.Size[face.W], part.Size[face.H]
			local pps = d.PixelsPerStud or 50
			local canvasW, canvasH
			if enumName(d.SizingMode or "SurfaceGuiSizingMode.FixedSize") == "PixelsPerStud" then
				canvasW, canvasH = fw * pps, fh * pps
			else
				local cs = d.CanvasSize or Vector2.new(800, 600)
				canvasW, canvasH = cs.X, cs.Y
			end
			local nodes = {}
			guiNodes(d, { x = 0, y = 0, w = canvasW, h = canvasH }, nodes)
			if #nodes > 0 then
				local cf = part.CFrame
				local depth = part.Size[if face.N.X ~= 0 then "X" elseif face.N.Y ~= 0 then "Y" else "Z"]
				local center = cf * (face.N * (depth / 2))
				table.insert(
					guiRecords,
					Mock.json.encode({
						path = pathOf(part),
						o = rawget(d, "__origin"),
						center = { center.X, center.Y, center.Z },
						normal = {
							cf:VectorToWorldSpace(face.N).X,
							cf:VectorToWorldSpace(face.N).Y,
							cf:VectorToWorldSpace(face.N).Z,
						},
						right = {
							cf:VectorToWorldSpace(face.R).X,
							cf:VectorToWorldSpace(face.R).Y,
							cf:VectorToWorldSpace(face.R).Z,
						},
						up = {
							cf:VectorToWorldSpace(face.U).X,
							cf:VectorToWorldSpace(face.U).Y,
							cf:VectorToWorldSpace(face.U).Z,
						},
						w = fw,
						h = fh,
						cw = canvasW,
						ch = canvasH,
						lit = (d.LightInfluence or 1) > 0,
						nodes = nodes,
					})
				)
			end
		end
	end
end

-- 조명
local L = Mock.Lighting
local function c3(c): { number }?
	return if c then { c.R, c.G, c.B } else nil
end
local lighting: { [string]: any } = {
	ClockTime = L.ClockTime,
	Brightness = L.Brightness,
	GeographicLatitude = L.GeographicLatitude,
	Ambient = c3(L.Ambient),
	OutdoorAmbient = c3(L.OutdoorAmbient),
	ExposureCompensation = L.ExposureCompensation,
	FogStart = L.FogStart,
	FogEnd = L.FogEnd,
	FogColor = c3(L.FogColor),
	GlobalShadows = L.GlobalShadows,
}
for _, child in L:GetChildren() do
	if child.ClassName == "Atmosphere" then
		lighting.Atmosphere = {
			Density = child.Density or 0.395,
			Offset = child.Offset or 0,
			Haze = child.Haze or 0,
			Glare = child.Glare or 0,
			Color = c3(child.Color or Color3.fromRGB(199, 199, 199)),
			Decay = c3(child.Decay or Color3.fromRGB(106, 112, 125)),
		}
	elseif child.ClassName == "Sky" then
		lighting.Sky = { Name = child.Name }
	elseif child.ClassName == "ColorCorrectionEffect" and child.Enabled ~= false then
		lighting.ColorCorrection = {
			Brightness = child.Brightness or 0,
			Contrast = child.Contrast or 0,
			Saturation = child.Saturation or 0,
			TintColor = c3(child.TintColor or Color3.new(1, 1, 1)),
		}
	end
end

local counts = {}
for _, part in parts do
	local origin = rawget(part, "__origin")
	counts[origin] = (counts[origin] or 0) + 1
end
local summary = {}
for origin, n in counts do
	table.insert(summary, origin .. "=" .. n)
end
table.sort(summary)
note("파트 수: " .. table.concat(summary, ", ") .. string.format(", SurfaceGui %d개", #guiRecords))
for _, w in Mock.warnings do
	note("warn: " .. w)
end
for _, v in Mock.violations do
	note("규칙 위반: " .. v)
end
for _, e in Mock.errors do
	note("task 오류: " .. e)
end

local meta = {
	variant = opts.variant,
	variantField = variantField,
	scenery = Scenery ~= nil,
	sceneryCall = if Scenery then "Scenery." .. sceneryCall.Fn .. "(" .. sceneryCall.Args .. ")" else nil,
	players = playerCount,
	notes = notes,
}

print("DUMP_BEGIN")
print(
	string.format(
		'{"meta":%s,"lighting":%s,"parts":[%s],"gui":[%s]}',
		Mock.json.encode(meta),
		Mock.json.encode(lighting),
		table.concat(partRecords, ","),
		table.concat(guiRecords, ",")
	)
)
print("DUMP_END")
