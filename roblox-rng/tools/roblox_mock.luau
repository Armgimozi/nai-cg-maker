-- Roblox 밖(tools/luaurun)에서 서버/공용 모듈을 돌리기 위한 가짜 Roblox 환경.
-- tools/model_preview/mock.luau(명소 모형 검사)와 tools/world_preview/world.luau(맵 전체 미리보기)가 같이 씁니다.
--
-- 사용법: tests/harness.luau 를 먼저 불러온 뒤(모듈 require 흉내) 이 파일을 compile 해서 실행하면
--   _G 에 Vector3 / CFrame / Color3 / Instance / game / workspace / task / Enum ... 이 깔리고 Mock 표를 돌려줍니다.
--   local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()
--
-- Mock.strict = true: 모르는 속성을 쓰거나 읽으면 오류(모형 검사용, 예전 mock.luau 와 같은 규칙).
-- Mock.strict = false(기본): GUI/조명 등 어떤 속성이든 받아 두고, 안 정한 속성을 읽으면 nil.
-- Mock.origin: 지금 만드는 Instance 에 붙일 "출처" 이름(맵 미리보기에서 World / Parks / Scenery 구분용).
--
-- 흉내 범위(일부러 단순화한 곳)
--   * Enum 값은 "PartType.Ball" 같은 문자열(tests/harness.luau 와 같은 방식)
--   * task.wait / task.delay 는 가짜 시계로 도는 작은 스케줄러(Mock.runScheduler 로 진행). 이벤트는 연결만 되고 불리지 않음
--   * Random.new(seed) 는 결정적 LCG(같은 seed 면 항상 같은 수열. 실제 Roblox 수열과는 다름)
--   * workspace:Raycast 는 파트를 상자(Ball 은 구)로 보고 계산
--   * Terrain:Fill* 는 기록만 해 둠(Mock.terrainFills). 미리보기는 이것을 대략적인 파트로 그림

local Mock = {}
Mock.strict = false
Mock.origin = "?"
Mock.violations = {} -- 모형 규칙 위반(비균일 Ball 등)
Mock.warnings = {} -- warn() 으로 나온 문장
Mock.errors = {} -- task 스레드 안에서 난 오류
Mock.terrainFills = {}

local sqrt, sin, cos, abs, atan2, asin = math.sqrt, math.sin, math.cos, math.abs, math.atan2, math.asin
local min, max, floor, huge, pi = math.min, math.max, math.floor, math.huge, math.pi

-- JSON (HttpService, default.project.json 읽기, 덤프 출력) ---------------------
local json = {}
Mock.json = json

local ESCAPES =
	{ ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
local function encodeString(s: string): string
	return '"' .. s:gsub('[%c"\\]', function(c)
		return ESCAPES[c] or string.format("\\u%04x", c:byte())
	end) .. '"'
end

local function isArray(t): boolean
	local n = #t
	local count = 0
	for _ in t do
		count += 1
	end
	return count == n
end

function json.encode(value: any): string
	local kind = type(value)
	if kind == "nil" then
		return "null"
	elseif kind == "boolean" then
		return tostring(value)
	elseif kind == "number" then
		if value ~= value or value == huge or value == -huge then
			return "null"
		elseif value == floor(value) and abs(value) < 1e15 then
			return string.format("%d", value)
		end
		return string.format("%.5g", value)
	elseif kind == "string" then
		return encodeString(value)
	elseif kind == "table" then
		local out = {}
		if isArray(value) then
			for i, v in value do
				out[i] = json.encode(v)
			end
			return "[" .. table.concat(out, ",") .. "]"
		end
		local keys = {}
		for k in value do
			table.insert(keys, tostring(k))
		end
		table.sort(keys)
		for _, k in keys do
			table.insert(out, encodeString(k) .. ":" .. json.encode(value[k]))
		end
		return "{" .. table.concat(out, ",") .. "}"
	end
	error("json.encode: " .. kind .. " 는 못 바꿉니다")
end

function json.decode(text: string): any
	local pos = 1
	local function skip()
		pos = text:find("[^ \t\r\n]", pos) or #text + 1
	end
	local parseValue
	local function parseString(): string
		local out = {}
		pos += 1
		while true do
			local c = text:sub(pos, pos)
			if c == "" then
				error("json: 끝나지 않은 문자열")
			elseif c == '"' then
				pos += 1
				return table.concat(out)
			elseif c == "\\" then
				local e = text:sub(pos + 1, pos + 1)
				if e == "u" then
					table.insert(out, utf8.char(tonumber(text:sub(pos + 2, pos + 5), 16) :: number))
					pos += 6
				else
					local map = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" }
					table.insert(out, map[e] or e)
					pos += 2
				end
			else
				table.insert(out, c)
				pos += 1
			end
		end
	end
	function parseValue(): any
		skip()
		local c = text:sub(pos, pos)
		if c == "{" then
			local obj = {}
			pos += 1
			skip()
			if text:sub(pos, pos) == "}" then
				pos += 1
				return obj
			end
			while true do
				skip()
				local key = parseString()
				skip()
				assert(text:sub(pos, pos) == ":", "json: ':' 가 필요합니다")
				pos += 1
				obj[key] = parseValue()
				skip()
				local d = text:sub(pos, pos)
				pos += 1
				if d == "}" then
					return obj
				end
				assert(d == ",", "json: ',' 가 필요합니다")
			end
		elseif c == "[" then
			local arr = {}
			pos += 1
			skip()
			if text:sub(pos, pos) == "]" then
				pos += 1
				return arr
			end
			while true do
				table.insert(arr, parseValue())
				skip()
				local d = text:sub(pos, pos)
				pos += 1
				if d == "]" then
					return arr
				end
				assert(d == ",", "json: ',' 가 필요합니다")
			end
		elseif c == '"' then
			return parseString()
		elseif text:sub(pos, pos + 3) == "true" then
			pos += 4
			return true
		elseif text:sub(pos, pos + 4) == "false" then
			pos += 5
			return false
		elseif text:sub(pos, pos + 3) == "null" then
			pos += 4
			return nil
		end
		local number = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", pos)
		assert(number and #number > 0, "json: 알 수 없는 값 (위치 " .. pos .. ")")
		pos += #number
		return tonumber(number)
	end
	local result = parseValue()
	return result
end

-- typeof ----------------------------------------------------------------------
local TYPE_OF = {} -- 메타테이블 -> Roblox 타입 이름
local rawTypeof = typeof
local function mockTypeof(value: any): string
	if type(value) == "table" then
		local name = TYPE_OF[getmetatable(value)]
		if name then
			return name
		end
	end
	return rawTypeof(value)
end
Mock.typeof = mockTypeof

-- Vector3 ---------------------------------------------------------------------
local Vector3 = {}
local VMT = {}
TYPE_OF[VMT] = "Vector3"
local function vec(x: number, y: number, z: number)
	return setmetatable({ X = x, Y = y, Z = z }, VMT)
end
local VMETHODS = {}
function VMETHODS.Dot(a, b)
	return a.X * b.X + a.Y * b.Y + a.Z * b.Z
end
function VMETHODS.Cross(a, b)
	return vec(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X)
end
function VMETHODS.Lerp(a, b, t)
	return vec(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t, a.Z + (b.Z - a.Z) * t)
end
function VMETHODS.Min(a, b)
	return vec(min(a.X, b.X), min(a.Y, b.Y), min(a.Z, b.Z))
end
function VMETHODS.Max(a, b)
	return vec(max(a.X, b.X), max(a.Y, b.Y), max(a.Z, b.Z))
end
function VMETHODS.Abs(a)
	return vec(abs(a.X), abs(a.Y), abs(a.Z))
end
function VMETHODS.Floor(a)
	return vec(floor(a.X), floor(a.Y), floor(a.Z))
end
function VMETHODS.Ceil(a)
	return vec(math.ceil(a.X), math.ceil(a.Y), math.ceil(a.Z))
end
function VMETHODS.Sign(a)
	return vec(math.sign(a.X), math.sign(a.Y), math.sign(a.Z))
end
function VMETHODS.FuzzyEq(a, b, eps)
	eps = eps or 1e-5
	return abs(a.X - b.X) <= eps and abs(a.Y - b.Y) <= eps and abs(a.Z - b.Z) <= eps
end
function VMETHODS.Angle(a, b)
	local d = VMETHODS.Dot(a, b) / (a.Magnitude * b.Magnitude)
	return math.acos(math.clamp(d, -1, 1))
end
VMT.__index = function(v, k)
	if k == "Magnitude" then
		return sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
	elseif k == "Unit" then
		local m = sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
		if m == 0 then
			return vec(0 / 0, 0 / 0, 0 / 0)
		end
		return vec(v.X / m, v.Y / m, v.Z / m)
	elseif k == "x" or k == "y" or k == "z" then
		return rawget(v, string.upper(k))
	end
	local method = VMETHODS[k]
	if method then
		return method
	end
	error("Vector3 has no member " .. tostring(k), 2)
end
VMT.__add = function(a, b)
	assert(getmetatable(a) == VMT and getmetatable(b) == VMT, "bad Vector3 add")
	return vec(a.X + b.X, a.Y + b.Y, a.Z + b.Z)
end
VMT.__sub = function(a, b)
	assert(getmetatable(a) == VMT and getmetatable(b) == VMT, "bad Vector3 sub")
	return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z)
end
VMT.__mul = function(a, b)
	if type(a) == "number" then
		return vec(a * b.X, a * b.Y, a * b.Z)
	elseif type(b) == "number" then
		return vec(a.X * b, a.Y * b, a.Z * b)
	end
	assert(getmetatable(a) == VMT and getmetatable(b) == VMT, "bad Vector3 mul")
	return vec(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
VMT.__div = function(a, b)
	if type(b) == "number" then
		return vec(a.X / b, a.Y / b, a.Z / b)
	elseif type(a) == "number" then
		return vec(a / b.X, a / b.Y, a / b.Z)
	end
	return vec(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
end
VMT.__idiv = function(a, b)
	if type(b) == "number" then
		return vec(a.X // b, a.Y // b, a.Z // b)
	end
	return vec(a.X // b.X, a.Y // b.Y, a.Z // b.Z)
end
VMT.__unm = function(a)
	return vec(-a.X, -a.Y, -a.Z)
end
VMT.__eq = function(a, b)
	return a.X == b.X and a.Y == b.Y and a.Z == b.Z
end
VMT.__tostring = function(v)
	return string.format("%g, %g, %g", v.X, v.Y, v.Z)
end
function Vector3.new(x: number?, y: number?, z: number?)
	return vec(x or 0, y or 0, z or 0)
end
Vector3.zero = vec(0, 0, 0)
Vector3.one = vec(1, 1, 1)
Vector3.xAxis = vec(1, 0, 0)
Vector3.yAxis = vec(0, 1, 0)
Vector3.zAxis = vec(0, 0, 1)
local NORMALS = {
	["NormalId.Right"] = vec(1, 0, 0),
	["NormalId.Left"] = vec(-1, 0, 0),
	["NormalId.Top"] = vec(0, 1, 0),
	["NormalId.Bottom"] = vec(0, -1, 0),
	["NormalId.Back"] = vec(0, 0, 1),
	["NormalId.Front"] = vec(0, 0, -1),
}
function Vector3.FromNormalId(normal: string)
	return NORMALS[normal]
end
Mock.vec = vec
Mock.VMT = VMT

-- Vector2 ---------------------------------------------------------------------
local Vector2 = {}
local V2MT = {}
TYPE_OF[V2MT] = "Vector2"
local function vec2(x: number, y: number)
	return setmetatable({ X = x, Y = y }, V2MT)
end
V2MT.__index = function(v, k)
	if k == "Magnitude" then
		return sqrt(v.X * v.X + v.Y * v.Y)
	elseif k == "Unit" then
		local m = sqrt(v.X * v.X + v.Y * v.Y)
		return vec2(v.X / m, v.Y / m)
	elseif k == "Dot" then
		return function(a, b)
			return a.X * b.X + a.Y * b.Y
		end
	elseif k == "Lerp" then
		return function(a, b, t)
			return vec2(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t)
		end
	end
	error("Vector2 has no member " .. tostring(k), 2)
end
V2MT.__add = function(a, b)
	return vec2(a.X + b.X, a.Y + b.Y)
end
V2MT.__sub = function(a, b)
	return vec2(a.X - b.X, a.Y - b.Y)
end
V2MT.__mul = function(a, b)
	if type(a) == "number" then
		return vec2(a * b.X, a * b.Y)
	elseif type(b) == "number" then
		return vec2(a.X * b, a.Y * b)
	end
	return vec2(a.X * b.X, a.Y * b.Y)
end
V2MT.__div = function(a, b)
	if type(b) == "number" then
		return vec2(a.X / b, a.Y / b)
	end
	return vec2(a.X / b.X, a.Y / b.Y)
end
V2MT.__unm = function(a)
	return vec2(-a.X, -a.Y)
end
V2MT.__eq = function(a, b)
	return a.X == b.X and a.Y == b.Y
end
function Vector2.new(x: number?, y: number?)
	return vec2(x or 0, y or 0)
end
Vector2.zero = vec2(0, 0)
Vector2.one = vec2(1, 1)
Vector2.xAxis = vec2(1, 0)
Vector2.yAxis = vec2(0, 1)

-- CFrame (회전 행렬 행 우선 m[1..9] + 위치 p) -----------------------------------
local CFrame = {}
local CMT = {}
TYPE_OF[CMT] = "CFrame"
local function cframe(p, m)
	return setmetatable({ p = p, m = m }, CMT)
end
local IDENT = { 1, 0, 0, 0, 1, 0, 0, 0, 1 }
local function matmul(a, b)
	local r = {}
	for i = 0, 2 do
		for j = 0, 2 do
			local s = 0
			for k = 0, 2 do
				s += a[i * 3 + k + 1] * b[k * 3 + j + 1]
			end
			r[i * 3 + j + 1] = s
		end
	end
	return r
end
local function rotate(m, v)
	return vec(
		m[1] * v.X + m[2] * v.Y + m[3] * v.Z,
		m[4] * v.X + m[5] * v.Y + m[6] * v.Z,
		m[7] * v.X + m[8] * v.Y + m[9] * v.Z
	)
end
local function transpose(m)
	return { m[1], m[4], m[7], m[2], m[5], m[8], m[3], m[6], m[9] }
end
local function inverse(cf)
	local t = transpose(cf.m)
	return cframe(-rotate(t, cf.p), t)
end
-- 행렬 -> 쿼터니언 (x, y, z, w)
local function toQuaternion(m)
	local trace = m[1] + m[5] + m[9]
	if trace > 0 then
		local s = sqrt(trace + 1) * 2
		return (m[8] - m[6]) / s, (m[3] - m[7]) / s, (m[4] - m[2]) / s, s / 4
	elseif m[1] > m[5] and m[1] > m[9] then
		local s = sqrt(1 + m[1] - m[5] - m[9]) * 2
		return s / 4, (m[2] + m[4]) / s, (m[3] + m[7]) / s, (m[8] - m[6]) / s
	elseif m[5] > m[9] then
		local s = sqrt(1 + m[5] - m[1] - m[9]) * 2
		return (m[2] + m[4]) / s, s / 4, (m[6] + m[8]) / s, (m[3] - m[7]) / s
	end
	local s = sqrt(1 + m[9] - m[1] - m[5]) * 2
	return (m[3] + m[7]) / s, (m[6] + m[8]) / s, s / 4, (m[4] - m[2]) / s
end
local function fromQuaternion(x, y, z, w)
	local n = sqrt(x * x + y * y + z * z + w * w)
	x, y, z, w = x / n, y / n, z / n, w / n
	return {
		1 - 2 * (y * y + z * z),
		2 * (x * y - z * w),
		2 * (x * z + y * w),
		2 * (x * y + z * w),
		1 - 2 * (x * x + z * z),
		2 * (y * z - x * w),
		2 * (x * z - y * w),
		2 * (y * z + x * w),
		1 - 2 * (x * x + y * y),
	}
end
local function rotX(a)
	local c, s = cos(a), sin(a)
	return { 1, 0, 0, 0, c, -s, 0, s, c }
end
local function rotY(a)
	local c, s = cos(a), sin(a)
	return { c, 0, s, 0, 1, 0, -s, 0, c }
end
local function rotZ(a)
	local c, s = cos(a), sin(a)
	return { c, -s, 0, s, c, 0, 0, 0, 1 }
end
-- R = Rx * Ry * Rz 일 때의 각도
local function eulerXYZ(m)
	local ry = asin(math.clamp(m[3], -1, 1))
	return atan2(-m[6], m[9]), ry, atan2(-m[2], m[1])
end
-- R = Ry * Rx * Rz 일 때의 각도 (Orientation 순서)
local function eulerYXZ(m)
	local rx = asin(math.clamp(-m[6], -1, 1))
	return rx, atan2(m[3], m[9]), atan2(m[4], m[5])
end

local CMETHODS = {}
function CMETHODS.Inverse(self)
	return inverse(self)
end
function CMETHODS.ToObjectSpace(self, other)
	return inverse(self) * other
end
function CMETHODS.ToWorldSpace(self, other)
	return self * other
end
function CMETHODS.PointToWorldSpace(self, v)
	return self * v
end
function CMETHODS.PointToObjectSpace(self, v)
	return rotate(transpose(self.m), v - self.p)
end
function CMETHODS.VectorToWorldSpace(self, v)
	return rotate(self.m, v)
end
function CMETHODS.VectorToObjectSpace(self, v)
	return rotate(transpose(self.m), v)
end
function CMETHODS.GetComponents(self)
	local m = self.m
	return self.p.X, self.p.Y, self.p.Z, m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]
end
CMETHODS.components = CMETHODS.GetComponents
function CMETHODS.ToEulerAnglesXYZ(self)
	return eulerXYZ(self.m)
end
function CMETHODS.ToEulerAnglesYXZ(self)
	return eulerYXZ(self.m)
end
CMETHODS.ToOrientation = CMETHODS.ToEulerAnglesYXZ
function CMETHODS.ToAxisAngle(self)
	local x, y, z, w = toQuaternion(self.m)
	local angle = 2 * math.acos(math.clamp(w, -1, 1))
	local s = sqrt(max(0, 1 - w * w))
	if s < 1e-9 then
		return vec(1, 0, 0), 0
	end
	return vec(x / s, y / s, z / s), angle
end
function CMETHODS.Lerp(a, b, t)
	local ax, ay, az, aw = toQuaternion(a.m)
	local bx, by, bz, bw = toQuaternion(b.m)
	local d = ax * bx + ay * by + az * bz + aw * bw
	if d < 0 then
		bx, by, bz, bw, d = -bx, -by, -bz, -bw, -d
	end
	local wa, wb
	if d > 0.9995 then
		wa, wb = 1 - t, t
	else
		local theta = math.acos(d)
		wa, wb = sin((1 - t) * theta) / sin(theta), sin(t * theta) / sin(theta)
	end
	local m = fromQuaternion(ax * wa + bx * wb, ay * wa + by * wb, az * wa + bz * wb, aw * wa + bw * wb)
	return cframe(a.p:Lerp(b.p, t), m)
end
function CMETHODS.Orthonormalize(self)
	return self
end
function CMETHODS.FuzzyEq(a, b, eps)
	eps = eps or 1e-5
	for i = 1, 9 do
		if abs(a.m[i] - b.m[i]) > eps then
			return false
		end
	end
	return a.p:FuzzyEq(b.p, eps)
end
CMT.__index = function(cf, k)
	local m = cf.m
	if k == "Position" or k == "p" then
		return cf.p
	elseif k == "X" or k == "x" then
		return cf.p.X
	elseif k == "Y" or k == "y" then
		return cf.p.Y
	elseif k == "Z" or k == "z" then
		return cf.p.Z
	elseif k == "RightVector" or k == "XVector" then
		return vec(m[1], m[4], m[7])
	elseif k == "UpVector" or k == "YVector" then
		return vec(m[2], m[5], m[8])
	elseif k == "LookVector" then
		return vec(-m[3], -m[6], -m[9])
	elseif k == "ZVector" then
		return vec(m[3], m[6], m[9])
	elseif k == "Rotation" then
		return cframe(vec(0, 0, 0), m)
	end
	local method = CMETHODS[k]
	if method then
		return method
	end
	error("CFrame has no member " .. tostring(k), 2)
end
CMT.__mul = function(a, b)
	if getmetatable(b) == VMT then
		return rotate(a.m, b) + a.p
	end
	assert(getmetatable(a) == CMT and getmetatable(b) == CMT, "bad CFrame mul")
	return cframe(rotate(a.m, b.p) + a.p, matmul(a.m, b.m))
end
CMT.__add = function(a, b)
	assert(getmetatable(b) == VMT, "CFrame + Vector3 만 됩니다")
	return cframe(a.p + b, a.m)
end
CMT.__sub = function(a, b)
	assert(getmetatable(b) == VMT, "CFrame - Vector3 만 됩니다")
	return cframe(a.p - b, a.m)
end
CMT.__eq = function(a, b)
	for i = 1, 9 do
		if a.m[i] ~= b.m[i] then
			return false
		end
	end
	return a.p == b.p
end
CMT.__tostring = function(cf)
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = CMETHODS.GetComponents(cf)
	return string.format(
		"%g, %g, %g, %g, %g, %g, %g, %g, %g, %g, %g, %g",
		x,
		y,
		z,
		r00,
		r01,
		r02,
		r10,
		r11,
		r12,
		r20,
		r21,
		r22
	)
end

local function lookAtMatrix(at, target, up)
	up = up or vec(0, 1, 0)
	local look = (target - at).Unit
	local right = look:Cross(up)
	if right.Magnitude < 1e-6 then
		-- 바로 위/아래를 볼 때: Roblox 처럼 다른 up 을 씀
		right = look:Cross(vec(0, 0, -1))
		if right.Magnitude < 1e-6 then
			right = look:Cross(vec(1, 0, 0))
		end
	end
	right = right.Unit
	local up2 = right:Cross(look)
	-- 열: right, up2, -look
	return { right.X, up2.X, -look.X, right.Y, up2.Y, -look.Y, right.Z, up2.Z, -look.Z }
end

function CFrame.new(...)
	local n = select("#", ...)
	local a, b, c = ...
	if n == 0 then
		return cframe(vec(0, 0, 0), IDENT)
	elseif n == 1 then
		assert(getmetatable(a) == VMT, "CFrame.new(Vector3)")
		return cframe(a, IDENT)
	elseif n == 2 then
		-- 옛 방식 CFrame.new(pos, lookAt)
		return cframe(a, lookAtMatrix(a, b))
	elseif n == 3 then
		return cframe(vec(a, b, c), IDENT)
	elseif n == 7 then
		local _, _, _, qx, qy, qz, qw = ...
		return cframe(vec(a, b, c), fromQuaternion(qx, qy, qz, qw))
	elseif n == 12 then
		local args = { ... }
		return cframe(
			vec(a, b, c),
			{ args[4], args[5], args[6], args[7], args[8], args[9], args[10], args[11], args[12] }
		)
	end
	error("CFrame.new: 인자 " .. n .. "개는 흉내 내지 않습니다")
end
CFrame.identity = CFrame.new()
function CFrame.Angles(rx: number, ry: number, rz: number)
	return cframe(vec(0, 0, 0), matmul(matmul(rotX(rx), rotY(ry)), rotZ(rz)))
end
CFrame.fromEulerAnglesXYZ = CFrame.Angles
function CFrame.fromEulerAnglesYXZ(rx: number, ry: number, rz: number)
	return cframe(vec(0, 0, 0), matmul(matmul(rotY(ry), rotX(rx)), rotZ(rz)))
end
CFrame.fromOrientation = CFrame.fromEulerAnglesYXZ
function CFrame.fromEulerAngles(rx: number, ry: number, rz: number, order: string?)
	if order == nil or order == "RotationOrder.XYZ" then
		return CFrame.Angles(rx, ry, rz)
	elseif order == "RotationOrder.YXZ" then
		return CFrame.fromEulerAnglesYXZ(rx, ry, rz)
	end
	error("CFrame.fromEulerAngles: " .. tostring(order) .. " 순서는 흉내 내지 않습니다")
end
function CFrame.fromAxisAngle(axis, angle: number)
	local u = axis.Unit
	local s = sin(angle / 2)
	return cframe(vec(0, 0, 0), fromQuaternion(u.X * s, u.Y * s, u.Z * s, cos(angle / 2)))
end
function CFrame.fromMatrix(pos, vx, vy, vz)
	vz = vz or vx:Cross(vy).Unit
	return cframe(pos, { vx.X, vy.X, vz.X, vx.Y, vy.Y, vz.Y, vx.Z, vy.Z, vz.Z })
end
function CFrame.lookAt(at, target, up)
	return cframe(at, lookAtMatrix(at, target, up))
end
function CFrame.lookAlong(at, direction, up)
	return cframe(at, lookAtMatrix(at, at + direction, up))
end
Mock.cframe = cframe
Mock.CMT = CMT

-- Color3 / BrickColor ---------------------------------------------------------
local Color3 = {}
local C3MT = {}
TYPE_OF[C3MT] = "Color3"
local function color(r: number, g: number, b: number)
	return setmetatable({ R = r, G = g, B = b }, C3MT)
end
local C3METHODS = {}
function C3METHODS.Lerp(a, b, t)
	return color(a.R + (b.R - a.R) * t, a.G + (b.G - a.G) * t, a.B + (b.B - a.B) * t)
end
function C3METHODS.ToHSV(c)
	local r, g, b = c.R, c.G, c.B
	local hi, lo = max(r, g, b), min(r, g, b)
	local d = hi - lo
	local h = 0
	if d > 0 then
		if hi == r then
			h = ((g - b) / d) % 6
		elseif hi == g then
			h = (b - r) / d + 2
		else
			h = (r - g) / d + 4
		end
		h /= 6
	end
	return h, if hi > 0 then d / hi else 0, hi
end
function C3METHODS.ToHex(c)
	return string.format(
		"%02X%02X%02X",
		floor(math.clamp(c.R, 0, 1) * 255 + 0.5),
		floor(math.clamp(c.G, 0, 1) * 255 + 0.5),
		floor(math.clamp(c.B, 0, 1) * 255 + 0.5)
	)
end
C3MT.__index = function(_, k)
	local method = C3METHODS[k]
	if method then
		return method
	elseif k == "r" or k == "g" or k == "b" then
		return nil
	end
	error("Color3 has no member " .. tostring(k), 2)
end
C3MT.__eq = function(a, b)
	return a.R == b.R and a.G == b.G and a.B == b.B
end
C3MT.__tostring = function(c)
	return string.format("%g, %g, %g", c.R, c.G, c.B)
end
function Color3.new(r: number?, g: number?, b: number?)
	return color(r or 0, g or 0, b or 0)
end
function Color3.fromRGB(r: number?, g: number?, b: number?)
	return color((r or 0) / 255, (g or 0) / 255, (b or 0) / 255)
end
function Color3.fromHSV(h: number, s: number, v: number)
	h = (h % 1) * 6
	local i = floor(h)
	local f = h - i
	local p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
	if i == 0 then
		return color(v, t, p)
	elseif i == 1 then
		return color(q, v, p)
	elseif i == 2 then
		return color(p, v, t)
	elseif i == 3 then
		return color(p, q, v)
	elseif i == 4 then
		return color(t, p, v)
	end
	return color(v, p, q)
end
function Color3.fromHex(hex: string)
	hex = hex:gsub("^#", "")
	if #hex == 3 then
		hex = hex:sub(1, 1):rep(2) .. hex:sub(2, 2):rep(2) .. hex:sub(3, 3):rep(2)
	end
	return Color3.fromRGB(
		tonumber(hex:sub(1, 2), 16) :: number,
		tonumber(hex:sub(3, 4), 16) :: number,
		tonumber(hex:sub(5, 6), 16) :: number
	)
end
Color3.toHSV = C3METHODS.ToHSV

-- 자주 쓰는 BrickColor 몇 개만(나머지는 회색)
local BRICK = {
	["White"] = { 242, 243, 243 },
	["Institutional white"] = { 248, 248, 248 },
	["Medium stone grey"] = { 163, 162, 165 },
	["Dark stone grey"] = { 99, 95, 98 },
	["Black"] = { 27, 42, 53 },
	["Really black"] = { 17, 17, 17 },
	["Bright red"] = { 196, 40, 28 },
	["Bright blue"] = { 13, 105, 172 },
	["Bright green"] = { 75, 151, 75 },
	["Bright yellow"] = { 245, 205, 48 },
	["Bright orange"] = { 218, 133, 65 },
	["Reddish brown"] = { 105, 64, 40 },
	["Brown"] = { 124, 92, 70 },
	["Sand green"] = { 120, 144, 130 },
	["Earth green"] = { 39, 70, 45 },
	["Dark green"] = { 40, 127, 71 },
	["Lime green"] = { 0, 255, 0 },
	["Cyan"] = { 4, 175, 236 },
	["Pastel blue"] = { 128, 187, 219 },
	["Brick yellow"] = { 215, 197, 154 },
	["Cool yellow"] = { 253, 234, 141 },
	["Nougat"] = { 204, 142, 105 },
}
local BrickColor = {}
local BCMT = { __index = {} }
TYPE_OF[BCMT] = "BrickColor"
function BrickColor.new(value: any, g: number?, b: number?)
	if type(value) == "number" and g then
		return setmetatable({ Name = "Custom", Color = Color3.fromRGB(value, g, b) }, BCMT)
	elseif mockTypeof(value) == "Color3" then
		return setmetatable({ Name = "Custom", Color = value }, BCMT)
	end
	local rgb = BRICK[value] or BRICK["Medium stone grey"]
	return setmetatable({ Name = tostring(value), Color = Color3.fromRGB(rgb[1], rgb[2], rgb[3]) }, BCMT)
end
function BrickColor.White()
	return BrickColor.new("White")
end
function BrickColor.Gray()
	return BrickColor.new("Medium stone grey")
end
function BrickColor.Black()
	return BrickColor.new("Black")
end

-- GUI/기타 값 타입 ------------------------------------------------------------
local UDim = {}
local UDMT = {}
TYPE_OF[UDMT] = "UDim"
local function udim(s: number, o: number)
	return setmetatable({ Scale = s, Offset = o }, UDMT)
end
UDMT.__index = function(_, k)
	error("UDim has no member " .. tostring(k), 2)
end
UDMT.__add = function(a, b)
	return udim(a.Scale + b.Scale, a.Offset + b.Offset)
end
UDMT.__sub = function(a, b)
	return udim(a.Scale - b.Scale, a.Offset - b.Offset)
end
UDMT.__eq = function(a, b)
	return a.Scale == b.Scale and a.Offset == b.Offset
end
function UDim.new(s: number?, o: number?)
	return udim(s or 0, o or 0)
end

local UDim2 = {}
local UD2MT = {}
TYPE_OF[UD2MT] = "UDim2"
local function udim2(x, y)
	return setmetatable({ X = x, Y = y }, UD2MT)
end
UD2MT.__index = function(u, k)
	if k == "Width" then
		return u.X
	elseif k == "Height" then
		return u.Y
	elseif k == "Lerp" then
		return function(a, b, t)
			return udim2(
				udim(a.X.Scale + (b.X.Scale - a.X.Scale) * t, a.X.Offset + (b.X.Offset - a.X.Offset) * t),
				udim(a.Y.Scale + (b.Y.Scale - a.Y.Scale) * t, a.Y.Offset + (b.Y.Offset - a.Y.Offset) * t)
			)
		end
	end
	error("UDim2 has no member " .. tostring(k), 2)
end
UD2MT.__add = function(a, b)
	return udim2(a.X + b.X, a.Y + b.Y)
end
UD2MT.__sub = function(a, b)
	return udim2(a.X - b.X, a.Y - b.Y)
end
UD2MT.__eq = function(a, b)
	return a.X == b.X and a.Y == b.Y
end
function UDim2.new(a: any, b: any, c: any, d: any)
	if getmetatable(a) == UDMT or getmetatable(b) == UDMT then
		return udim2(a or udim(0, 0), b or udim(0, 0))
	end
	return udim2(udim(a or 0, b or 0), udim(c or 0, d or 0))
end
function UDim2.fromScale(x: number?, y: number?)
	return udim2(udim(x or 0, 0), udim(y or 0, 0))
end
function UDim2.fromOffset(x: number?, y: number?)
	return udim2(udim(0, x or 0), udim(0, y or 0))
end

local function valueType(name: string, fields: { string })
	local mt = {}
	TYPE_OF[mt] = name
	mt.__index = function(_, k)
		error(name .. " has no member " .. tostring(k), 2)
	end
	return {
		new = function(...)
			local args = { ... }
			local obj = {}
			for i, field in fields do
				obj[field] = args[i]
			end
			return setmetatable(obj, mt)
		end,
	}
end
local Rect = valueType("Rect", { "MinX", "MinY", "MaxX", "MaxY" })
local NumberRange = valueType("NumberRange", { "Min", "Max" })
local ColorSequenceKeypoint = valueType("ColorSequenceKeypoint", { "Time", "Value" })
local NumberSequenceKeypoint = valueType("NumberSequenceKeypoint", { "Time", "Value", "Envelope" })
local PhysicalProperties =
	valueType("PhysicalProperties", { "Density", "Friction", "Elasticity", "FrictionWeight", "ElasticityWeight" })
local TweenInfo =
	valueType("TweenInfo", { "Time", "EasingStyle", "EasingDirection", "RepeatCount", "Reverses", "DelayTime" })
local function queryParams(name: string)
	local mt = {}
	TYPE_OF[mt] = name
	mt.__index = {
		AddToFilter = function(self, value)
			local list = if type(value) == "table" and getmetatable(value) == nil then value else { value }
			for _, v in list do
				table.insert(self.FilterDescendantsInstances, v)
			end
		end,
	}
	return {
		new = function()
			return setmetatable({
				FilterDescendantsInstances = {},
				FilterType = "RaycastFilterType.Exclude",
				IgnoreWater = false,
				CollisionGroup = "Default",
				RespectCanCollide = false,
				MaxParts = 0,
			}, mt)
		end,
	}
end
local RaycastParams = queryParams("RaycastParams")
local OverlapParams = queryParams("OverlapParams")
local Ray = valueType("Ray", { "Origin", "Direction" })

local ColorSequence = {}
local CSMT = { __index = {} }
TYPE_OF[CSMT] = "ColorSequence"
function ColorSequence.new(a: any, b: any?)
	if type(a) == "table" and getmetatable(a) == nil then
		return setmetatable({ Keypoints = a }, CSMT)
	end
	b = b or a
	return setmetatable({ Keypoints = { ColorSequenceKeypoint.new(0, a), ColorSequenceKeypoint.new(1, b) } }, CSMT)
end
local NumberSequence = {}
local NSMT = { __index = {} }
TYPE_OF[NSMT] = "NumberSequence"
function NumberSequence.new(a: any, b: any?)
	if type(a) == "table" then
		return setmetatable({ Keypoints = a }, NSMT)
	end
	b = b or a
	return setmetatable({ Keypoints = { NumberSequenceKeypoint.new(0, a), NumberSequenceKeypoint.new(1, b) } }, NSMT)
end
local Font = {}
local FONTMT = { __index = {} }
TYPE_OF[FONTMT] = "Font"
function Font.new(family: string, weight: any?, style: any?)
	return setmetatable({ Family = family, Weight = weight, Style = style }, FONTMT)
end
function Font.fromEnum(value: string)
	return setmetatable({ Family = value }, FONTMT)
end
function Font.fromName(name: string, weight: any?, style: any?)
	return Font.new(name, weight, style)
end

-- Random: 결정적 LCG (시드가 같으면 수열이 같음) ---------------------------------
local Random = {}
local RMT = {}
TYPE_OF[RMT] = "Random"
local RMETHODS = {}
local TWO32 = 4294967296
local function step(self): number
	-- 32비트 LCG 두 번으로 53비트에 가까운 [0, 1) 수
	self.state = (self.state * 1664525 + 1013904223) % TWO32
	local hi = self.state
	self.state = (self.state * 1664525 + 1013904223) % TWO32
	return (hi + self.state / TWO32) / TWO32
end
function RMETHODS.NextNumber(self, lo: number?, hi: number?)
	local x = step(self)
	if lo then
		return lo + (hi - lo) * x
	end
	return x
end
function RMETHODS.NextInteger(self, lo: number, hi: number)
	return lo + floor(step(self) * (hi - lo + 1))
end
function RMETHODS.NextUnitVector(self)
	local z = step(self) * 2 - 1
	local a = step(self) * pi * 2
	local r = sqrt(1 - z * z)
	return vec(r * cos(a), r * sin(a), z)
end
function RMETHODS.Shuffle(self, t)
	for i = #t, 2, -1 do
		local j = RMETHODS.NextInteger(self, 1, i)
		t[i], t[j] = t[j], t[i]
	end
end
function RMETHODS.Clone(self)
	return setmetatable({ state = self.state }, RMT)
end
RMT.__index = RMETHODS
function Random.new(seed: number?)
	local s = floor(abs(seed or 0) * 1000003) % TWO32
	local r = setmetatable({ state = (s + 12345) % TWO32 }, RMT)
	step(r)
	return r
end
math.randomseed(20240501)

-- Enum: "PartType.Ball" 같은 문자열 ---------------------------------------------
local Enum = setmetatable({}, {
	__index = function(_, enumName)
		return setmetatable({}, {
			__index = function(_, itemName)
				return enumName .. "." .. itemName
			end,
		})
	end,
})

-- 가짜 시계 + task 스케줄러 ------------------------------------------------------
local clock = 0
local queue = {} -- { At, Seq, Thread, Args }
local seq = 0
local cancelled: { [thread]: boolean } = {}

local function report(thread: thread, err: any)
	local message = tostring(err)
	local trace = debug.traceback(thread)
	table.insert(Mock.errors, message .. "\n" .. trace)
	print("[mock] task 오류: " .. message)
end

-- 스레드마다 만든 때의 Mock.origin 을 기억(task.wait 뒤에 만든 파트도 같은 출처로)
local threadOrigin: { [thread]: string } = setmetatable({}, { __mode = "k" }) :: any

local function resume(thread: thread, ...)
	if cancelled[thread] or coroutine.status(thread) ~= "suspended" then
		return
	end
	local saved = Mock.origin
	Mock.origin = threadOrigin[thread] or saved
	local ok, err = coroutine.resume(thread, ...)
	Mock.origin = saved
	if not ok then
		report(thread, err)
	end
end

local function schedule(at: number, thread: thread, ...)
	seq += 1
	table.insert(queue, { At = at, Seq = seq, Thread = thread, Args = table.pack(...) })
end

local function toThread(f: any): thread
	local thread = if type(f) == "thread" then f else coroutine.create(f)
	if not threadOrigin[thread] then
		threadOrigin[thread] = Mock.origin
	end
	return thread
end

local task = {}
function task.spawn(f: any, ...)
	local thread = toThread(f)
	resume(thread, ...)
	return thread
end
function task.defer(f: any, ...)
	local thread = toThread(f)
	schedule(clock, thread, ...)
	return thread
end
function task.delay(t: number?, f: any, ...)
	local thread = toThread(f)
	schedule(clock + (t or 0), thread, ...)
	return thread
end
function task.wait(t: number?)
	local dt = max(t or 0, 1 / 60)
	if coroutine.isyieldable() then
		local start = clock
		schedule(clock + dt, coroutine.running())
		coroutine.yield()
		return clock - start
	end
	-- 메인 스레드에서는 기다릴 수 없으니 시계만 넘김
	clock += dt
	return dt
end
function task.cancel(thread: thread)
	cancelled[thread] = true
end
function task.synchronize() end
function task.desynchronize() end

-- 스레드 안에서 fn 을 돌림(task.wait 가 되도록). 오류는 (false, 메시지)
function Mock.run(fn: () -> ...any): (boolean, any)
	local thread = coroutine.create(fn)
	threadOrigin[thread] = Mock.origin
	local ok, err = coroutine.resume(thread)
	if not ok then
		return false, tostring(err) .. "\n" .. debug.traceback(thread)
	end
	return true, nil
end

-- 가짜 시계를 untilTime 초까지 진행하며 기다리던 task 를 깨움
function Mock.runScheduler(untilTime: number, maxSteps: number?)
	local steps = 0
	local limit = maxSteps or 20000
	while #queue > 0 and steps < limit do
		table.sort(queue, function(a, b)
			if a.At ~= b.At then
				return a.At < b.At
			end
			return a.Seq < b.Seq
		end)
		local item = queue[1]
		if item.At > untilTime then
			break
		end
		table.remove(queue, 1)
		clock = max(clock, item.At)
		steps += 1
		resume(item.Thread, table.unpack(item.Args, 1, item.Args.n))
	end
	clock = max(clock, untilTime)
	return steps, #queue
end
function Mock.clock(): number
	return clock
end

-- 이벤트: 연결은 받지만 불리지 않음 ----------------------------------------------
local Signal = {}
Signal.__index = Signal
TYPE_OF[Signal] = "RBXScriptSignal"
function Signal.new()
	return setmetatable({ Handlers = {} }, Signal)
end
function Signal:Connect(fn)
	table.insert(self.Handlers, fn)
	local connection = { Connected = true }
	function connection.Disconnect(c)
		c.Connected = false
		local i = table.find(self.Handlers, fn)
		if i then
			table.remove(self.Handlers, i)
		end
	end
	return connection
end
Signal.Once = Signal.Connect
Signal.ConnectParallel = Signal.Connect
function Signal:Wait()
	if coroutine.isyieldable() then
		return coroutine.yield() -- 영원히 깨어나지 않음
	end
	return nil
end
function Signal:Fire(...)
	for _, fn in table.clone(self.Handlers) do
		task.spawn(fn, ...)
	end
end
Mock.Signal = Signal

-- Instance --------------------------------------------------------------------
-- 클래스 -> 부모 클래스 (IsA 용)
local SUPER: { [string]: string } = {
	BasePart = "PVInstance",
	PVInstance = "Instance",
	FormFactorPart = "BasePart",
	Part = "FormFactorPart",
	WedgePart = "FormFactorPart",
	CornerWedgePart = "BasePart",
	TrussPart = "BasePart",
	SpawnLocation = "Part",
	Seat = "Part",
	TriangleMeshPart = "BasePart",
	MeshPart = "TriangleMeshPart",
	PartOperation = "TriangleMeshPart",
	UnionOperation = "PartOperation",
	NegateOperation = "PartOperation",
	Terrain = "BasePart",
	Model = "PVInstance",
	WorldRoot = "Model",
	Workspace = "WorldRoot",
	GuiBase2d = "Instance",
	GuiObject = "GuiBase2d",
	Frame = "GuiObject",
	TextLabel = "GuiObject",
	TextButton = "GuiButton",
	ImageLabel = "GuiObject",
	ImageButton = "GuiButton",
	GuiButton = "GuiObject",
	TextBox = "GuiObject",
	ScrollingFrame = "GuiObject",
	CanvasGroup = "GuiObject",
	LayerCollector = "GuiBase2d",
	SurfaceGuiBase = "LayerCollector",
	SurfaceGui = "SurfaceGuiBase",
	BillboardGui = "LayerCollector",
	ScreenGui = "LayerCollector",
	UIBase = "Instance",
	UIComponent = "UIBase",
	UICorner = "UIComponent",
	UIStroke = "UIComponent",
	UIGradient = "UIComponent",
	UIPadding = "UIComponent",
	UIScale = "UIComponent",
	UIConstraint = "UIComponent",
	UIAspectRatioConstraint = "UIConstraint",
	UISizeConstraint = "UIConstraint",
	UITextSizeConstraint = "UIConstraint",
	UIGridStyleLayout = "UIComponent",
	UIListLayout = "UIGridStyleLayout",
	UIGridLayout = "UIGridStyleLayout",
	Light = "Instance",
	PointLight = "Light",
	SpotLight = "Light",
	SurfaceLight = "Light",
	ValueBase = "Instance",
	IntValue = "ValueBase",
	NumberValue = "ValueBase",
	StringValue = "ValueBase",
	BoolValue = "ValueBase",
	ObjectValue = "ValueBase",
	CFrameValue = "ValueBase",
	Vector3Value = "ValueBase",
	Color3Value = "ValueBase",
	JointInstance = "Instance",
	Weld = "JointInstance",
	Motor6D = "JointInstance",
	Constraint = "Instance",
	WeldConstraint = "Instance",
	FaceInstance = "Instance",
	Decal = "FaceInstance",
	Texture = "Decal",
	DataModelMesh = "Instance",
	SpecialMesh = "DataModelMesh",
	PostEffect = "Instance",
	BloomEffect = "PostEffect",
	BlurEffect = "PostEffect",
	ColorCorrectionEffect = "PostEffect",
	SunRaysEffect = "PostEffect",
	DepthOfFieldEffect = "PostEffect",
}
local function isA(className: string, name: string): boolean
	local cls: string? = className
	while cls do
		if cls == name then
			return true
		end
		cls = SUPER[cls]
	end
	return name == "Instance"
end
Mock.isA = isA

-- 모형 검사(strict)에서 쓸 수 있는 속성(예전 mock.luau 와 같은 목록)
local KNOWN = {
	Name = true,
	Parent = true,
	Anchored = true,
	CanCollide = true,
	CanQuery = true,
	CanTouch = true,
	Massless = true,
	CastShadow = true,
	Transparency = true,
	Size = true,
	CFrame = true,
	PivotOffset = true,
	Shape = true,
	Material = true,
	Color = true,
	TopSurface = true,
	BottomSurface = true,
	PrimaryPart = true,
	WorldPivot = true,
}

-- 속성 기본값(클래스별). 표에 없는 속성은 strict 가 아니면 nil
local DEFAULTS: { [string]: { [string]: any } } = {
	Light = { Enabled = true, Brightness = 1, Range = 8, Shadows = false },
	UIStroke = { Enabled = true, Thickness = 1, Transparency = 0 },
	GuiObject = {
		Visible = true,
		BackgroundTransparency = 0,
		BorderSizePixel = 1,
		ZIndex = 1,
		Rotation = 0,
		LayoutOrder = 0,
	},
	LayerCollector = { Enabled = true },
	UIGradient = { Enabled = true, Rotation = 0 },
	Decal = { Transparency = 0 },
}

local IMT = {}
TYPE_OF[IMT] = "Instance"
local methods = {}
local classDefaults: { [string]: { [string]: any } } = {}
local function defaultsFor(className: string): { [string]: any }
	local cached = classDefaults[className]
	if cached then
		return cached
	end
	local out = {}
	local chain = {}
	local cls: string? = className
	while cls do
		table.insert(chain, 1, cls)
		cls = SUPER[cls]
	end
	for _, c in chain do
		for k, v in DEFAULTS[c] or {} do
			out[k] = v
		end
	end
	classDefaults[className] = out
	return out
end

local nextId = 0
local function newInstance(className: string, parent: any?)
	nextId += 1
	local obj = { __props = {}, __children = {}, __id = nextId, __origin = Mock.origin }
	local p = obj.__props
	p.ClassName = className
	p.Name = className
	for k, v in defaultsFor(className) do
		p[k] = v
	end
	if isA(className, "BasePart") then
		p.Anchored = false
		p.CanCollide = true
		p.CanQuery = true
		p.CanTouch = true
		p.Massless = false
		p.CastShadow = true
		p.Transparency = 0
		p.Size = vec(4, 1, 2)
		p.CFrame = CFrame.new()
		p.PivotOffset = CFrame.new()
		p.Shape = "PartType.Block"
		p.Material = "Material.Plastic"
		p.Color = Color3.new(0.6, 0.6, 0.6)
		p.Reflectance = 0
		-- WedgePart/CornerWedgePart 에는 Shape 속성이 없지만 예전 mock 처럼 Block 으로 둠(렌더러는 ClassName 을 먼저 봄)
		if className == "CornerWedgePart" then
			p.Size = vec(2, 2, 2)
		elseif className == "SpawnLocation" then
			p.Size = vec(12, 1, 12)
		end
	elseif className == "Model" or className == "Workspace" then
		p.WorldPivot = nil -- 처음 정하기 전에는 경계 상자 가운데(아래 WorldPivot 참고)
		p.__scale = 1
	end
	local instance = setmetatable(obj, IMT)
	if parent then
		instance.Parent = parent
	end
	return instance
end
Mock.newInstance = newInstance

function methods.IsA(self, name)
	return isA(self.__props.ClassName, name)
end
function methods.GetChildren(self)
	return table.clone(self.__children)
end
function methods.GetDescendants(self)
	local out = {}
	local function walk(node)
		for _, child in node.__children do
			table.insert(out, child)
			walk(child)
		end
	end
	walk(self)
	return out
end
function methods.FindFirstChild(self, name, recursive)
	for _, child in self.__children do
		if child.Name == name then
			return child
		end
	end
	local links = rawget(self, "__links")
	if links and links[name] then
		return links[name]
	end
	if recursive then
		for _, child in self.__children do
			local found = child:FindFirstChild(name, true)
			if found then
				return found
			end
		end
	end
	return nil
end
function methods.WaitForChild(self, name, _timeout)
	local found = methods.FindFirstChild(self, name)
	if found == nil then
		error(
			"WaitForChild: "
				.. self:GetFullName()
				.. " 에 "
				.. tostring(name)
				.. " 가 없습니다(가짜 환경은 기다리지 않음)",
			2
		)
	end
	return found
end
function methods.FindFirstChildOfClass(self, cls)
	for _, child in self.__children do
		if child.ClassName == cls then
			return child
		end
	end
	return nil
end
function methods.FindFirstChildWhichIsA(self, cls, recursive)
	local list = if recursive then self:GetDescendants() else self.__children
	for _, child in list do
		if child:IsA(cls) then
			return child
		end
	end
	return nil
end
function methods.FindFirstAncestor(self, name)
	local node = self.__props.Parent
	while node do
		if node.Name == name then
			return node
		end
		node = node.__props.Parent
	end
	return nil
end
function methods.FindFirstAncestorOfClass(self, cls)
	local node = self.__props.Parent
	while node do
		if node.ClassName == cls then
			return node
		end
		node = node.__props.Parent
	end
	return nil
end
function methods.FindFirstAncestorWhichIsA(self, cls)
	local node = self.__props.Parent
	while node do
		if node:IsA(cls) then
			return node
		end
		node = node.__props.Parent
	end
	return nil
end
function methods.IsDescendantOf(self, other)
	local node = self.__props.Parent
	while node do
		if node == other then
			return true
		end
		node = node.__props.Parent
	end
	return false
end
function methods.IsAncestorOf(self, other)
	return methods.IsDescendantOf(other, self)
end
function methods.GetFullName(self)
	local names = {}
	local node = self
	while node and rawget(node, "__props") and node.__props.ClassName ~= "DataModel" do
		table.insert(names, 1, node.__props.Name)
		node = node.__props.Parent
	end
	return table.concat(names, ".")
end
function methods.Destroy(self)
	self.Parent = nil
	self.__props.__destroyed = true
	for _, child in table.clone(self.__children) do
		child:Destroy()
	end
end
methods.Remove = methods.Destroy
function methods.ClearAllChildren(self)
	for _, child in table.clone(self.__children) do
		child:Destroy()
	end
end
function methods.Clone(self)
	local copy = newInstance(self.__props.ClassName)
	for k, v in self.__props do
		if k ~= "Parent" and k ~= "PrimaryPart" then
			copy.__props[k] = v
		end
	end
	if rawget(self, "__attributes") then
		rawset(copy, "__attributes", table.clone(self.__attributes))
	end
	if rawget(self, "__tags") then
		rawset(copy, "__tags", table.clone(self.__tags))
	end
	local map = {}
	for _, child in self.__children do
		local c = child:Clone()
		map[child] = c
		c.Parent = copy
	end
	if self.__props.PrimaryPart then
		copy.__props.PrimaryPart = map[self.__props.PrimaryPart]
	end
	return copy
end
function methods.SetAttribute(self, name, value)
	local attrs = rawget(self, "__attributes")
	if not attrs then
		attrs = {}
		rawset(self, "__attributes", attrs)
	end
	attrs[name] = value
end
function methods.GetAttribute(self, name)
	local attrs = rawget(self, "__attributes")
	return attrs and attrs[name]
end
function methods.GetAttributes(self)
	return table.clone(rawget(self, "__attributes") or {})
end
function methods.AddTag(self, tag)
	local tags = rawget(self, "__tags")
	if not tags then
		tags = {}
		rawset(self, "__tags", tags)
	end
	tags[tag] = true
end
function methods.RemoveTag(self, tag)
	local tags = rawget(self, "__tags")
	if tags then
		tags[tag] = nil
	end
end
function methods.HasTag(self, tag)
	local tags = rawget(self, "__tags")
	return tags ~= nil and tags[tag] == true
end
function methods.GetTags(self)
	local out = {}
	for tag in rawget(self, "__tags") or {} do
		table.insert(out, tag)
	end
	return out
end
function methods.GetPropertyChangedSignal(_self, _name)
	return Signal.new()
end
function methods.GetAttributeChangedSignal(_self, _name)
	return Signal.new()
end

local function corners(part)
	local s = part.Size / 2
	local out = {}
	for _, sx in { -1, 1 } do
		for _, sy in { -1, 1 } do
			for _, sz in { -1, 1 } do
				table.insert(out, part.CFrame * vec(sx * s.X, sy * s.Y, sz * s.Z))
			end
		end
	end
	return out
end
Mock.corners = corners

-- 모델 안 모든 파트의 월드 축 경계 상자 가운데(아직 WorldPivot 을 정하지 않은 Model 의 피벗)
local function contentCenter(model)
	local lo, hi = vec(huge, huge, huge), vec(-huge, -huge, -huge)
	local any = false
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d.ClassName ~= "Terrain" then
			any = true
			for _, c in corners(d) do
				lo = lo:Min(c)
				hi = hi:Max(c)
			end
		end
	end
	if not any then
		return CFrame.new()
	end
	return cframe((lo + hi) / 2, IDENT)
end

local function worldPivot(model)
	return model.__props.WorldPivot or contentCenter(model)
end

function methods.GetPivot(self)
	local p = self.__props
	if isA(p.ClassName, "Model") then
		if p.PrimaryPart then
			return p.PrimaryPart.CFrame * p.PrimaryPart.PivotOffset
		end
		return worldPivot(self)
	end
	return p.CFrame * p.PivotOffset
end
function methods.PivotTo(self, target)
	local pivot = self:GetPivot()
	local delta = target * inverse(pivot)
	if self:IsA("BasePart") then
		self.CFrame = delta * self.CFrame
		return
	end
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") and d.ClassName ~= "Terrain" then
			d.CFrame = delta * d.CFrame
		elseif d:IsA("Model") and d.__props.WorldPivot then
			d.__props.WorldPivot = delta * d.__props.WorldPivot
		end
	end
	if self.__props.PrimaryPart then
		if self.__props.WorldPivot then
			self.__props.WorldPivot = delta * self.__props.WorldPivot
		end
	else
		self.__props.WorldPivot = target
	end
end
function methods.TranslateBy(self, offset)
	self:PivotTo(self:GetPivot() + offset)
end
function methods.MoveTo(self, position)
	local pivot = self:GetPivot()
	self:PivotTo(pivot + (position - pivot.Position))
end
function methods.SetPrimaryPartCFrame(self, target)
	local primary = self.__props.PrimaryPart
	assert(primary, "SetPrimaryPartCFrame: PrimaryPart 가 없습니다")
	local delta = target * inverse(primary.CFrame)
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") then
			d.CFrame = delta * d.CFrame
		end
	end
end
function methods.GetPrimaryPartCFrame(self)
	return self.__props.PrimaryPart.CFrame
end
function methods.GetBoundingBox(self)
	local frame = if self.PrimaryPart then self.PrimaryPart.CFrame else worldPivot(self)
	frame = cframe(frame.p, frame.m)
	local inv = inverse(frame)
	local lo, hi = vec(huge, huge, huge), vec(-huge, -huge, -huge)
	local any = false
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") and d.ClassName ~= "Terrain" then
			any = true
			for _, c in corners(d) do
				local l = inv * c
				lo = vec(min(lo.X, l.X), min(lo.Y, l.Y), min(lo.Z, l.Z))
				hi = vec(max(hi.X, l.X), max(hi.Y, l.Y), max(hi.Z, l.Z))
			end
		end
	end
	if not any then
		return frame, vec(0, 0, 0)
	end
	local center = (lo + hi) / 2
	return frame * CFrame.new(center.X, center.Y, center.Z), hi - lo
end
function methods.GetExtentsSize(self)
	local _, size = self:GetBoundingBox()
	return size
end
function methods.GetScale(self)
	return self.__props.__scale
end
function methods.ScaleTo(self, newScale)
	assert(newScale > 0 and newScale < huge, "bad scale " .. tostring(newScale))
	local factor = newScale / self.__props.__scale
	local pivot = self:GetPivot()
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") then
			local offset = inverse(pivot) * d.CFrame
			d.CFrame = pivot * cframe(offset.p * factor, offset.m)
			d.Size = d.Size * factor
			local po = d.PivotOffset
			d.PivotOffset = cframe(po.p * factor, po.m)
		end
	end
	self.__props.__scale = newScale
end
function methods.GetMass(self)
	local s = self.Size
	return s.X * s.Y * s.Z * 0.7
end
function methods.GetTouchingParts(_self)
	return {}
end
function methods.BreakJoints(_self) end
function methods.MakeJoints(_self) end

-- 이벤트처럼 읽히는 이름들(연결만 되고 불리지 않음)
local EVENTS = {
	Changed = true,
	ChildAdded = true,
	ChildRemoved = true,
	DescendantAdded = true,
	DescendantRemoving = true,
	AncestryChanged = true,
	Destroying = true,
	Touched = true,
	TouchEnded = true,
	MouseButton1Click = true,
	MouseButton1Down = true,
	Activated = true,
	Triggered = true,
	MouseClick = true,
	Completed = true,
}

IMT.__index = function(self, k)
	-- 속성이 먼저(서비스는 AddTag 같은 이름을 자기 함수로 덮어씀), 그다음 공통 메서드
	local p = self.__props
	local v = p[k]
	if v ~= nil then
		return v
	end
	local method = methods[k]
	if method then
		return method
	end
	if k == "Parent" or k == "PrimaryPart" then
		return nil
	end
	if k == "WorldPivot" and isA(p.ClassName, "Model") then
		return worldPivot(self)
	end
	if isA(p.ClassName, "BasePart") and p.CFrame then
		if k == "Position" then
			return p.CFrame.p
		elseif k == "Orientation" then
			local rx, ry, rz = eulerYXZ(p.CFrame.m)
			return vec(math.deg(rx), math.deg(ry), math.deg(rz))
		elseif k == "Rotation" then
			local rx, ry, rz = eulerXYZ(p.CFrame.m)
			return vec(math.deg(rx), math.deg(ry), math.deg(rz))
		elseif k == "BrickColor" then
			return BrickColor.new(p.Color)
		elseif k == "AssemblyLinearVelocity" or k == "AssemblyAngularVelocity" then
			return vec(0, 0, 0)
		end
	end
	local links = rawget(self, "__links")
	if links and links[k] then
		return links[k]
	end
	if EVENTS[k] then
		local signal = Signal.new()
		p[k] = signal
		return signal
	end
	for _, child in self.__children do
		if child.__props.Name == k then
			return child
		end
	end
	if Mock.strict then
		error(p.ClassName .. " has no property " .. tostring(k), 2)
	end
	return nil
end

IMT.__newindex = function(self, k, v)
	if Mock.strict then
		assert(KNOWN[k], "unknown property set: " .. tostring(k))
	end
	local p = self.__props
	if k == "Parent" then
		local old = p.Parent
		if old then
			local idx = table.find(old.__children, self)
			if idx then
				table.remove(old.__children, idx)
			end
		end
		p.Parent = v
		if v then
			table.insert(v.__children, self)
		end
		return
	end
	if k == "ClassName" then
		error("ClassName 은 읽기 전용입니다", 2)
	end
	local part = isA(p.ClassName, "BasePart")
	if part then
		if k == "Position" then
			p.CFrame = cframe(v, p.CFrame.m)
			return
		elseif k == "Orientation" then
			p.CFrame = cframe(p.CFrame.p, CFrame.fromOrientation(math.rad(v.X), math.rad(v.Y), math.rad(v.Z)).m)
			return
		elseif k == "Rotation" then
			p.CFrame = cframe(p.CFrame.p, CFrame.Angles(math.rad(v.X), math.rad(v.Y), math.rad(v.Z)).m)
			return
		elseif k == "BrickColor" then
			p.Color = v.Color
			return
		elseif k == "CFrame" then
			assert(getmetatable(v) == CMT, "CFrame 에 CFrame 이 아닌 값")
		elseif k == "Size" then
			assert(getmetatable(v) == VMT, "Size 에 Vector3 가 아닌 값")
		elseif k == "Color" then
			assert(getmetatable(v) == C3MT, "Color 에 Color3 가 아닌 값")
		end
	end
	if k == "CanQuery" and v == false and p.CanCollide then
		table.insert(Mock.violations, "CanQuery=false while CanCollide=true")
	end
	if k == "Size" and p.Shape == "PartType.Ball" and (abs(v.X - v.Y) > 1e-6 or abs(v.Y - v.Z) > 1e-6) then
		table.insert(Mock.violations, "non-uniform Ball " .. tostring(v))
	end
	if k == "Size" and p.Shape == "PartType.Cylinder" and abs(v.Y - v.Z) > 1e-6 then
		table.insert(Mock.violations, "elliptic Cylinder " .. tostring(v))
	end
	if k == "Shape" and p.ClassName ~= "Part" then
		table.insert(Mock.violations, "Shape on " .. p.ClassName)
	end
	if k == "TimeOfDay" and p.ClassName == "Lighting" and type(v) == "string" then
		local h, m, s = v:match("^(%d+):(%d+):?(%d*)")
		if h then
			p.ClockTime = tonumber(h) + tonumber(m) / 60 + (tonumber(s) or 0) / 3600
		end
	end
	if k == "WorldPivot" and v ~= nil then
		assert(getmetatable(v) == CMT, "WorldPivot 에 CFrame 이 아닌 값")
	end
	p[k] = v
end
IMT.__tostring = function(self)
	return self.__props.Name
end

local Instance = {}
function Instance.new(className: string, parent: any?)
	return newInstance(className, parent)
end
function Instance.fromExisting(other)
	return other:Clone()
end

-- 서비스 ------------------------------------------------------------------------
local game = newInstance("DataModel")
game.Name = "Game"
Mock.game = game
local services: { [string]: any } = {}
Mock.services = services

local function service(name: string)
	local existing = services[name]
	if existing then
		return existing
	end
	local s = newInstance(name)
	s.Name = name
	s.Parent = game
	services[name] = s
	return s
end

local Workspace = service("Workspace")
Workspace.__props.WorldPivot = CFrame.new()
Workspace.Gravity = 196.2
Workspace.FallenPartsDestroyHeight = -500
Workspace.StreamingEnabled = false
local Terrain = newInstance("Terrain")
Terrain.Name = "Terrain"
Terrain.Anchored = true
Terrain.Parent = Workspace
local Camera = newInstance("Camera")
Camera.Name = "Camera"
Camera.FieldOfView = 70
Camera.CFrame = CFrame.new(0, 20, 20)
Camera.Parent = Workspace
Workspace.CurrentCamera = Camera
Workspace.Terrain = Terrain
function methods.GetServerTimeNow(_self)
	return 1.7e9 + clock
end

-- Terrain: 채우기 호출만 기록 --------------------------------------------------
local terrainColors = {}
local function fill(kind: string, cf, size, material)
	table.insert(Mock.terrainFills, {
		Kind = kind,
		CFrame = cf,
		Size = size,
		Material = material,
		Origin = Mock.origin,
	})
end
Terrain.__props.FillBlock = function(_self, cf, size, material)
	fill("Block", cf, size, material)
end
Terrain.__props.FillBall = function(_self, center, radius, material)
	fill("Ball", CFrame.new(center), vec(radius * 2, radius * 2, radius * 2), material)
end
Terrain.__props.FillCylinder = function(_self, cf, height, radius, material)
	-- 지형 원기둥은 cf 의 Y 축 방향
	fill("Cylinder", cf, vec(radius * 2, height, radius * 2), material)
end
Terrain.__props.FillWedge = function(_self, cf, size, material)
	fill("Wedge", cf, size, material)
end
Terrain.__props.FillRegion = function(_self, _region, _resolution, material)
	table.insert(
		Mock.warnings,
		"Terrain:FillRegion 은 미리보기에 안 나옵니다 (" .. tostring(material) .. ")"
	)
end
Terrain.__props.Clear = function(_self)
	table.clear(Mock.terrainFills)
end
Terrain.__props.SetMaterialColor = function(_self, material, c)
	terrainColors[material] = c
end
Terrain.__props.GetMaterialColor = function(_self, material)
	return terrainColors[material] or Color3.new(0.5, 0.5, 0.5)
end
Mock.terrainColors = terrainColors

-- Raycast: 파트를 상자(Ball 은 구)로 보고 가장 가까운 것 --------------------------
local function rayBox(part, origin, dir)
	local inv = inverse(part.CFrame)
	local o = inv * origin
	local d = rotate(inv.m, dir)
	local h = part.Size / 2
	local tmin, tmax = -huge, huge
	local normal = vec(0, 1, 0)
	for _, axis in { "X", "Y", "Z" } do
		local oa, da, ha = o[axis], d[axis], h[axis]
		if abs(da) < 1e-12 then
			if oa < -ha or oa > ha then
				return nil
			end
		else
			local t1, t2 = (-ha - oa) / da, (ha - oa) / da
			local sign = -1
			if t1 > t2 then
				t1, t2 = t2, t1
				sign = 1
			end
			if t1 > tmin then
				tmin = t1
				normal = vec(
					if axis == "X" then sign else 0,
					if axis == "Y" then sign else 0,
					if axis == "Z" then sign else 0
				)
			end
			tmax = min(tmax, t2)
			if tmin > tmax then
				return nil
			end
		end
	end
	if tmin < 0 or tmin > 1 then
		return nil
	end
	return tmin, rotate(part.CFrame.m, normal)
end
local function rayBall(part, origin, dir)
	local r = min(part.Size.X, part.Size.Y, part.Size.Z) / 2
	local oc = origin - part.CFrame.p
	local a = dir:Dot(dir)
	local b = 2 * oc:Dot(dir)
	local c = oc:Dot(oc) - r * r
	local disc = b * b - 4 * a * c
	if disc < 0 then
		return nil
	end
	local t = (-b - sqrt(disc)) / (2 * a)
	if t < 0 or t > 1 then
		return nil
	end
	return t, (origin + dir * t - part.CFrame.p).Unit
end
function methods.Raycast(self, origin, direction, params)
	local filter = params and params.FilterDescendantsInstances or {}
	local include = params and params.FilterType == "RaycastFilterType.Include"
	local function filtered(part)
		for _, f in filter do
			if part == f or part:IsDescendantOf(f) then
				return true
			end
		end
		return false
	end
	local best, bestNormal, bestPart = huge, nil, nil
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") and d.ClassName ~= "Terrain" and d.CanQuery ~= false then
			local skip = filtered(d)
			if include then
				skip = not skip
			end
			if not skip then
				local t, n
				if d.Shape == "PartType.Ball" then
					t, n = rayBall(d, origin, direction)
				else
					t, n = rayBox(d, origin, direction)
				end
				if t and t < best then
					best, bestNormal, bestPart = t, n, d
				end
			end
		end
	end
	if not bestPart then
		return nil
	end
	return {
		Instance = bestPart,
		Position = origin + direction * best,
		Normal = bestNormal,
		Distance = direction.Magnitude * best,
		Material = bestPart.Material,
	}
end

local Lighting = service("Lighting")
for k, v in
	{
		ClockTime = 14,
		Brightness = 2,
		GeographicLatitude = 41.733,
		Ambient = Color3.fromRGB(70, 70, 70),
		OutdoorAmbient = Color3.fromRGB(128, 128, 128),
		FogStart = 0,
		FogEnd = 100000,
		FogColor = Color3.fromRGB(192, 192, 192),
		ExposureCompensation = 0,
		GlobalShadows = true,
		EnvironmentDiffuseScale = 0,
		EnvironmentSpecularScale = 0,
		ShadowSoftness = 0.2,
	}
do
	Lighting.__props[k] = v
end
function methods.GetSunDirection(_self)
	return vec(0, 1, 0) -- 미리보기 렌더러가 ClockTime 으로 직접 계산
end
function methods.GetMinutesAfterMidnight(self)
	return (self.ClockTime or 0) * 60
end
function methods.SetMinutesAfterMidnight(self, minutes)
	self.ClockTime = minutes / 60
end

local ReplicatedStorage = service("ReplicatedStorage")
service("ServerStorage")
service("ServerScriptService")
service("ReplicatedFirst")
service("StarterGui")
service("StarterPack")
service("StarterPlayer")
service("SoundService")

local CollectionService = service("CollectionService")
function methods.GetTagged(_self, tag)
	local out = {}
	for _, d in game:GetDescendants() do
		if d:HasTag(tag) then
			table.insert(out, d)
		end
	end
	return out
end
CollectionService.__props.AddTag = function(_self, inst, tag)
	inst:AddTag(tag)
end
CollectionService.__props.RemoveTag = function(_self, inst, tag)
	inst:RemoveTag(tag)
end
CollectionService.__props.HasTag = function(_self, inst, tag)
	return inst:HasTag(tag)
end
CollectionService.__props.GetTags = function(_self, inst)
	return inst:GetTags()
end
CollectionService.__props.GetInstanceAddedSignal = function()
	return Signal.new()
end
CollectionService.__props.GetInstanceRemovedSignal = function()
	return Signal.new()
end

local RunService = service("RunService")
RunService.__props.IsServer = function()
	return true
end
RunService.__props.IsClient = function()
	return false
end
RunService.__props.IsStudio = function()
	return false
end
RunService.__props.IsRunning = function()
	return true
end
RunService.__props.Heartbeat = Signal.new()
RunService.__props.Stepped = Signal.new()
RunService.__props.RenderStepped = Signal.new()
RunService.__props.PreSimulation = Signal.new()
RunService.__props.PostSimulation = Signal.new()

local TweenService = service("TweenService")
TweenService.__props.Create = function(_self, instance, info, goals)
	-- 미리보기는 정지 화면: Play 해도 속성을 바꾸지 않음(시작 상태 그대로)
	return {
		Instance = instance,
		TweenInfo = info,
		Goals = goals,
		Completed = Signal.new(),
		Play = function() end,
		Pause = function() end,
		Cancel = function() end,
		Destroy = function() end,
	}
end

local Debris = service("Debris")
Debris.__props.AddItem = function() end

local HttpService = service("HttpService")
HttpService.__props.JSONEncode = function(_self, value)
	return json.encode(value)
end
HttpService.__props.JSONDecode = function(_self, text)
	return json.decode(text)
end
HttpService.__props.GenerateGUID = function(_self, braces)
	nextId += 1
	local id = string.format("00000000-0000-4000-8000-%012d", nextId)
	return if braces == false then id else "{" .. id .. "}"
end

local Players = service("Players")
Players.__props.GetPlayers = function()
	return {}
end
Players.__props.PlayerAdded = Signal.new()
Players.__props.PlayerRemoving = Signal.new()
Players.__props.MaxPlayers = 8

local PhysicsService = service("PhysicsService")
for _, name in
	{
		"RegisterCollisionGroup",
		"UnregisterCollisionGroup",
		"CollisionGroupSetCollidable",
		"CreateCollisionGroup",
		"SetPartCollisionGroup",
	}
do
	PhysicsService.__props[name] = function() end
end
PhysicsService.__props.IsCollisionGroupRegistered = function()
	return true
end

function methods.GetService(self, name)
	assert(self == game, "GetService 는 game 에서만")
	return service(name)
end
methods.FindService = methods.GetService
function methods.BindToClose(_self, _fn) end
function methods.IsLoaded(_self)
	return true
end
game.__props.PlaceId = 0
game.__props.GameId = 0
game.__props.JobId = "preview"
game.__props.Workspace = Workspace
game.__props.Lighting = Lighting
game.__props.Loaded = Signal.new()

-- 하네스 노드(파일 모듈 폴더)를 가짜 Instance 의 자식처럼 연결(예: ReplicatedStorage.Shared)
function Mock.link(parent, name: string, node)
	local links = rawget(parent, "__links")
	if not links then
		links = {}
		rawset(parent, "__links", links)
	end
	links[name] = node
end

-- 전역 설치 ---------------------------------------------------------------------
_G.Vector3 = Vector3
_G.Vector2 = Vector2
_G.CFrame = CFrame
_G.Color3 = Color3
_G.BrickColor = BrickColor
_G.UDim = UDim
_G.UDim2 = UDim2
_G.Rect = Rect
_G.NumberRange = NumberRange
_G.NumberSequence = NumberSequence
_G.NumberSequenceKeypoint = NumberSequenceKeypoint
_G.ColorSequence = ColorSequence
_G.ColorSequenceKeypoint = ColorSequenceKeypoint
_G.PhysicalProperties = PhysicalProperties
_G.TweenInfo = TweenInfo
_G.RaycastParams = RaycastParams
_G.OverlapParams = OverlapParams
_G.Ray = Ray
_G.Font = Font
_G.Random = Random
_G.Enum = Enum
_G.Instance = Instance
_G.game = game
_G.workspace = Workspace
_G.Workspace = Workspace
_G.task = task
_G.typeof = mockTypeof
_G.time = function()
	return clock
end
_G.tick = function()
	return 1.7e9 + clock
end
_G.elapsedTime = _G.time
_G.wait = task.wait
_G.delay = task.delay
_G.spawn = task.defer
_G.warn = function(...)
	local parts = {}
	for i = 1, select("#", ...) do
		parts[i] = tostring((select(i, ...)))
	end
	table.insert(Mock.warnings, table.concat(parts, " "))
end
_G.settings = function()
	return {}
end
_G.UserSettings = _G.settings

Mock.ReplicatedStorage = ReplicatedStorage
Mock.Workspace = Workspace
Mock.Lighting = Lighting
Mock.Terrain = Terrain
Mock.isBasePart = function(inst)
	return isA(inst.__props.ClassName, "BasePart")
end

return Mock
