-- Roblox 밖(순수 Luau 실행기)에서 src/shared 모듈을 돌리기 위한 최소 환경.
-- 실행기에는 readfile / listdir / compile 전역이 있어야 합니다(README 참고).
-- `script.Parent.X` 로 모듈을 찾는 Roblox 방식을 파일 경로로 흉내 냅니다.

local Harness = {}

-- Roblox 전역 흉내 --------------------------------------------------------
local Color3 = {}
Color3.__index = Color3
function Color3.new(r, g, b)
	return setmetatable({ R = r or 0, G = g or 0, B = b or 0 }, Color3)
end
function Color3.fromRGB(r, g, b)
	return Color3.new((r or 0) / 255, (g or 0) / 255, (b or 0) / 255)
end
_G.Color3 = Color3

-- Enum.Material.Brick 같은 접근을 "Material.Brick" 문자열로 흉내
_G.Enum = setmetatable({}, {
	__index = function(_, enumName)
		return setmetatable({}, {
			__index = function(_, itemName)
				return enumName .. "." .. itemName
			end,
		})
	end,
})

-- 가짜 Instance 트리 ------------------------------------------------------
local function isFile(path)
	return readfile(path) ~= nil
end

local function isDir(path)
	return #listdir(path) > 0
end

local nodeMeta = {}
local function node(path, parent)
	return setmetatable({ __path = path, __parent = parent }, nodeMeta)
end

nodeMeta.__index = function(self, key)
	if key == "Parent" then
		return rawget(self, "__parent")
	end
	local base = rawget(self, "__path")
	-- 모듈 노드의 자식을 찾을 때는 같은 폴더가 아니라 "모듈이름/" 폴더를 봅니다(Rojo 규칙과 동일)
	local dir = if rawget(self, "__file") then base:gsub("%.luau$", "") else base
	local file = dir .. "/" .. key .. ".luau"
	if isFile(file) then
		local child = node(file, self)
		rawset(child, "__file", true)
		return child
	end
	if isDir(dir .. "/" .. key) then
		return node(dir .. "/" .. key, self)
	end
	error("가짜 Instance 에 '" .. key .. "' 가 없습니다 (" .. dir .. ")", 2)
end

local cache = {}

local function requireNode(target)
	local path = rawget(target, "__path")
	if cache[path] ~= nil then
		return cache[path]
	end
	local source = readfile(path)
	assert(source, "모듈을 읽을 수 없습니다: " .. path)
	local fn = compile(source, path)
	local env = setmetatable({ script = target, require = requireNode }, { __index = _G })
	setfenv(fn, env)
	local result = fn()
	cache[path] = result
	return result
end

-- root: "src/shared" 같은 폴더 경로. 반환된 노드에서 .Config 등으로 모듈을 꺼내 require.
function Harness.folder(root)
	return node(root, nil)
end

Harness.require = requireNode

-- 아주 작은 테스트 러너 ----------------------------------------------------
local failures = 0
local passes = 0

function Harness.test(name, fn)
	local ok, err = pcall(fn)
	if ok then
		passes += 1
		print("  ok   " .. name)
	else
		failures += 1
		print("  FAIL " .. name .. "\n       " .. tostring(err))
	end
end

function Harness.eq(actual, expected, label)
	if actual ~= expected then
		error(string.format("%s: 기대 %s, 실제 %s", label or "값", tostring(expected), tostring(actual)), 2)
	end
end

function Harness.near(actual, expected, tolerance, label)
	if math.abs(actual - expected) > tolerance then
		error(string.format("%s: 기대 %.6g ± %.3g, 실제 %.6g", label or "값", expected, tolerance, actual), 2)
	end
end

function Harness.finish()
	print(string.format("\n%d passed, %d failed", passes, failures))
	return failures == 0
end

return Harness
