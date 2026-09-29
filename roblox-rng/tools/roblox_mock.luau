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
--   * workspace:Raycast 는 파트를 상자(Ball 은 구)로 보고 계산 + 지형 맨 위 표면(물 포함, IgnoreWater 따름)
--   * Terrain: 4 스터드 복셀(재질 + 점유율 + 물 점유율)을 진짜로 채움 — Fill*/FillRegion/ReadVoxels/WriteVoxels/
--     ReadVoxelChannels/WriteVoxelChannels/ReplaceMaterial/Clear/SetMaterialColor, Water* 속성, Decoration.
--     Decoration · GrassLength 는 스크립트로 쓰면 오류(NotScriptable — Mock.origin = "project" 일 때만, 즉 project.json)
--     규칙은 아래 "Terrain" 부분 주석. Mock.terrainFills = 호출 기록, Mock.terrainDumpJson = 렌더러용 덤프

local Mock = {}
Mock.strict = false
Mock.origin = "?"
Mock.violations = {} -- 모형 규칙 위반(비균일 Ball 등)
Mock.warnings = {} -- warn() 으로 나온 문장
Mock.errors = {} -- task 스레드 안에서 난 오류
Mock.terrainFills = {} -- 지형 API 호출 기록 { Kind, Material, Origin }

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

-- Vector3int16 / Region3 / Region3int16 (지형 API 용) ------------------------------
local V16MT = {}
TYPE_OF[V16MT] = "Vector3int16"
local function toInt16(v: number?): number
	local n = v or 0
	n = if n >= 0 then floor(n) else -floor(-n) -- Roblox 처럼 0 쪽으로 자름
	return math.clamp(n, -32768, 32767)
end
local function vec16(x: number?, y: number?, z: number?)
	return setmetatable({ X = toInt16(x), Y = toInt16(y), Z = toInt16(z) }, V16MT)
end
V16MT.__index = function(_, k)
	error("Vector3int16 has no member " .. tostring(k), 2)
end
V16MT.__add = function(a, b)
	return vec16(a.X + b.X, a.Y + b.Y, a.Z + b.Z)
end
V16MT.__sub = function(a, b)
	return vec16(a.X - b.X, a.Y - b.Y, a.Z - b.Z)
end
V16MT.__mul = function(a, b)
	if type(a) == "number" then
		return vec16(a * b.X, a * b.Y, a * b.Z)
	elseif type(b) == "number" then
		return vec16(a.X * b, a.Y * b, a.Z * b)
	end
	return vec16(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
V16MT.__eq = function(a, b)
	return a.X == b.X and a.Y == b.Y and a.Z == b.Z
end
V16MT.__tostring = function(v)
	return string.format("%d, %d, %d", v.X, v.Y, v.Z)
end
local Vector3int16 = { new = vec16 }

-- Region3: 안쪽에 최소·최대 모서리(__min/__max)를 들고, 밖으로는 Roblox 처럼 CFrame·Size 만 보임
local R3MT = {}
TYPE_OF[R3MT] = "Region3"
local function region3(lo, hi)
	return setmetatable({ __min = lo, __max = hi }, R3MT)
end
R3MT.__index = function(r, k)
	local lo, hi = rawget(r, "__min"), rawget(r, "__max")
	if k == "CFrame" then
		return cframe((lo + hi) / 2, IDENT)
	elseif k == "Size" then
		return hi - lo
	elseif k == "ExpandToGrid" then
		return function(_self, resolution: number)
			local g = resolution
			return region3(
				vec(floor(lo.X / g) * g, floor(lo.Y / g) * g, floor(lo.Z / g) * g),
				vec(math.ceil(hi.X / g) * g, math.ceil(hi.Y / g) * g, math.ceil(hi.Z / g) * g)
			)
		end
	end
	error("Region3 has no member " .. tostring(k), 2)
end
R3MT.__tostring = function(r)
	return tostring(r.CFrame) .. "; " .. tostring(r.Size)
end
local Region3 = {}
function Region3.new(lo, hi)
	assert(getmetatable(lo) == VMT and getmetatable(hi) == VMT, "Region3.new(Vector3, Vector3)")
	return region3(lo, hi)
end

local R316MT = {}
TYPE_OF[R316MT] = "Region3int16"
R316MT.__index = function(_, k)
	error("Region3int16 has no member " .. tostring(k), 2)
end
local Region3int16 = {}
function Region3int16.new(lo, hi)
	return setmetatable({ Min = lo, Max = hi }, R316MT)
end

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
	Reflectance = true,
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

-- 스크립트로 못 쓰는 속성(Roblox API 의 NotScriptable): Mock.origin 이 "project"(default.project.json 을 읽는 중)일 때만 받음
local NOT_SCRIPTABLE: { [string]: { [string]: boolean } } = {
	Terrain = { Decoration = true, GrassLength = true },
}
Mock.NOT_SCRIPTABLE = NOT_SCRIPTABLE

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
	if NOT_SCRIPTABLE[p.ClassName] and NOT_SCRIPTABLE[p.ClassName][k] and Mock.origin ~= "project" then
		-- Roblox 에서 스크립트가 쓰면 오류(Studio 속성 창 / place 파일 = default.project.json 에서만 정함)
		error(string.format("%s.%s 는 스크립트로 바꿀 수 없습니다(NotScriptable)", p.ClassName, k), 2)
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
local Camera = newInstance("Camera")
Camera.Name = "Camera"
Camera.FieldOfView = 70
Camera.CFrame = CFrame.new(0, 20, 20)
Camera.Parent = Workspace
Workspace.CurrentCamera = Camera
function methods.GetServerTimeNow(_self)
	return 1.7e9 + clock
end

-- Terrain: 4 스터드 복셀 격자 흉내 ---------------------------------------------------
-- Roblox 매끈한 지형처럼 복셀(4x4x4 스터드, 격자 원점 0)마다 단단한 재질 + 점유율(0~1) + 물 점유율(Shorelines)을 둠.
-- 저장: 8x8x8 복셀 청크(32 스터드). 청크 전체가 같은 값이면 값 하나(균일 청크), 아니면 buffer(복셀당 3바이트:
-- 재질 번호, 단단한 점유율 0~255, 물 점유율 0~255). 3000x3000 바다를 FillBlock 해도 속이 꽉 찬 청크는 균일 청크라 빠르고 작음.
-- 채우기 규칙(Roblox 동작을 따름. 확인 못 한 곳은 "추정")
--   * 복셀 점유율 = 복셀 가운데에서 모양 표면까지 거리 d(안쪽 +)로 clamp(0.5 + d / 4, 0, 1). 평평한 면은 정확히 채운 비율
--   * 단단한 재질: 점유율 = max(기존, 새 값). 재질은 새 값이 기존 이상이거나 0.5 이상이면 새 재질(추정)
--     물이 있던 복셀에 땅을 채우면 물은 그대로 남음(Shorelines: 한 복셀에 물 + 땅. 그리면 땅이 보임)
--   * Water: 물 점유율 = max(기존, 새 값) 이고 땅을 깎음(단단한 점유율 <= 1 - 새 값).
--     Roblox 에서도 물 Fill* 은 땅을 덮어써서, 땅을 다 만든 뒤 바다를 FillBlock 하면 섬이 지워집니다.
--     바다는 물을 먼저 채우고 땅을 나중에 채우거나, ReplaceMaterial(영역, 4, Air, Water) 로 빈 곳만 채우세요.
--     깎인 양은 Mock.terrainStats().CutByWater 로 알 수 있음(미리보기 world.luau 가 경고로 알려 줌)
--   * Air: 단단한 것·물 모두 1 - 새 값 이하로
-- 읽기(ReadVoxels): 복셀 재질 = 단단한 점유율 >= 물 점유율이면 단단한 재질, 아니면 Water(점유율 = 물), 둘 다 0 이면 Air.
-- 표면(미리보기·Raycast): 기둥마다 맨 위 단단한 복셀과 그 아래 복셀 점유율로 높이를 매끈하게 계산(Mock.terrainColumn).
-- 흉내 안 하는 것: CopyRegion/PasteRegion, GetCell/SetCell(옛 API), 지형 물리. Raycast 는 맨 위 표면만 봄(동굴 안쪽 X)

local TERRAIN_MATERIALS = {
	"Air",
	"Water",
	"Grass",
	"LeafyGrass",
	"Sand",
	"Rock",
	"Slate",
	"Basalt",
	"Ground",
	"Mud",
	"Snow",
	"Ice",
	"Glacier",
	"Salt",
	"Limestone",
	"Sandstone",
	"Pavement",
	"Cobblestone",
	"Brick",
	"WoodPlanks",
	"Asphalt",
	"Concrete",
	"Granite",
	"CrackedLava",
}
local TERRAIN_INDEX: { [string]: number } = {} -- "Material.Grass" -> 2 (0 = Air, 1 = Water)
for i, name in TERRAIN_MATERIALS do
	TERRAIN_INDEX["Material." .. name] = i - 1
end
-- Terrain.MaterialColors 기본값(Roblox 새 장소 기본)
local DEFAULT_MATERIAL_COLORS: { [string]: { number } } = {
	Grass = { 106, 127, 63 },
	LeafyGrass = { 115, 132, 74 },
	Sand = { 143, 126, 95 },
	Rock = { 102, 108, 111 },
	Slate = { 63, 127, 107 },
	Basalt = { 30, 30, 37 },
	Ground = { 102, 92, 59 },
	Mud = { 58, 46, 36 },
	Snow = { 195, 199, 218 },
	Ice = { 129, 194, 224 },
	Glacier = { 101, 176, 234 },
	Salt = { 198, 189, 181 },
	Limestone = { 206, 173, 148 },
	Sandstone = { 137, 90, 71 },
	Pavement = { 148, 148, 140 },
	Cobblestone = { 132, 123, 90 },
	Brick = { 138, 86, 62 },
	WoodPlanks = { 139, 109, 79 },
	Asphalt = { 115, 123, 107 },
	Concrete = { 127, 102, 63 },
	Granite = { 132, 123, 90 },
	CrackedLava = { 232, 156, 74 },
}

local terrainColors = {} -- Enum 문자열("Material.Grass") -> Color3 (SetMaterialColor 로 바꾼 것만)
local chunks: { [number]: any } = {} -- 청크 키 -> { u = true, sm, so, lo } 또는 { u = false, b = buffer }
local terrainState = {
	version = 0, -- 쓸 때마다 +1 (기둥 표면 캐시 무효화)
	bounds = nil :: { number }?, -- 청크 번호 { minX, minY, minZ, maxX, maxY, maxZ }
	cutByWater = 0, -- 물 채우기가 깎은 땅(복셀 단위, 점유율 합)
	calls = {} :: { [string]: number }, -- "FillBlock Grass" -> 횟수
}

local function chunkKey(cx: number, cy: number, cz: number): number
	return ((cx + 32768) * 65536 + (cy + 32768)) * 65536 + (cz + 32768)
end
local function keyToChunk(key: number): (number, number, number)
	local cz = key % 65536
	local rest = (key - cz) / 65536
	local cy = rest % 65536
	local cx = (rest - cy) / 65536
	return cx - 32768, cy - 32768, cz - 32768
end

local function terrainMaterialIndex(material: any, label: string): number
	local index = TERRAIN_INDEX[material]
	if index == nil then
		error(
			string.format(
				"Terrain:%s: %s 는 지형 재질이 아닙니다(Roblox 도 오류)",
				label,
				tostring(material)
			),
			3
		)
	end
	return index
end

local function countCall(label: string, material: any)
	local key = label .. " " .. tostring(material):gsub("^Material%.", "")
	terrainState.calls[key] = (terrainState.calls[key] or 0) + 1
	table.insert(Mock.terrainFills, { Kind = label, Material = material, Origin = Mock.origin })
end

local function chunkForWrite(cx: number, cy: number, cz: number)
	local key = chunkKey(cx, cy, cz)
	local c = chunks[key]
	if not c then
		c = { u = true, sm = 0, so = 0, lo = 0 }
		chunks[key] = c
		local b = terrainState.bounds
		if not b then
			terrainState.bounds = { cx, cy, cz, cx, cy, cz }
		else
			b[1], b[2], b[3] = min(b[1], cx), min(b[2], cy), min(b[3], cz)
			b[4], b[5], b[6] = max(b[4], cx), max(b[5], cy), max(b[6], cz)
		end
	end
	return c
end

local function densify(c): buffer
	if c.u then
		local b = buffer.create(1536)
		local sm, so, lo = c.sm, c.so, c.lo
		if sm ~= 0 or so ~= 0 or lo ~= 0 then
			for i = 0, 1533, 3 do
				buffer.writeu8(b, i, sm)
				buffer.writeu8(b, i + 1, so)
				buffer.writeu8(b, i + 2, lo)
			end
		end
		c.u = false
		c.b = b
	end
	return c.b
end

local function readVoxel(vx: number, vy: number, vz: number): (number, number, number)
	local cx, cy, cz = vx // 8, vy // 8, vz // 8
	local c = chunks[chunkKey(cx, cy, cz)]
	if not c then
		return 0, 0, 0
	end
	if c.u then
		return c.sm, c.so, c.lo
	end
	local off = (((vx - cx * 8) * 8 + (vy - cy * 8)) * 8 + (vz - cz * 8)) * 3
	local b = c.b
	return buffer.readu8(b, off), buffer.readu8(b, off + 1), buffer.readu8(b, off + 2)
end

local function writeVoxel(vx: number, vy: number, vz: number, sm: number, so: number, lo: number)
	if so == 0 then
		sm = 0
	end
	local cx, cy, cz = vx // 8, vy // 8, vz // 8
	local c = chunks[chunkKey(cx, cy, cz)]
	if not c then
		if so == 0 and lo == 0 then
			return
		end
		c = chunkForWrite(cx, cy, cz)
	end
	if c.u and c.sm == sm and c.so == so and c.lo == lo then
		return
	end
	local b = densify(c)
	local off = (((vx - cx * 8) * 8 + (vy - cy * 8)) * 8 + (vz - cz * 8)) * 3
	buffer.writeu8(b, off, sm)
	buffer.writeu8(b, off + 1, so)
	buffer.writeu8(b, off + 2, lo)
end

-- 청크 통째로 점유율 1 채우기. kind: 0 = Air, 1 = Water, 2 = 단단한 재질
local function fillWholeChunk(cx: number, cy: number, cz: number, kind: number, mi: number)
	local key = chunkKey(cx, cy, cz)
	local c = chunks[key]
	if kind == 0 then
		chunks[key] = nil
		return
	end
	if kind == 1 then
		if c then
			if c.u then
				terrainState.cutByWater += c.so / 255 * 512
			else
				local b = c.b
				local cut = 0
				for i = 1, 1534, 3 do
					cut += buffer.readu8(b, i)
				end
				terrainState.cutByWater += cut / 255
			end
		else
			c = chunkForWrite(cx, cy, cz)
		end
		c.u, c.b, c.sm, c.so, c.lo = true, nil, 0, 0, 255
		return
	end
	if not c then
		c = chunkForWrite(cx, cy, cz)
	end
	if c.u then
		c.sm, c.so = mi, 255
	else
		local b = c.b
		for i = 0, 1533, 3 do
			buffer.writeu8(b, i, mi)
			buffer.writeu8(b, i + 1, 255)
		end
	end
end

local function fillPartChunk(
	cx: number,
	cy: number,
	cz: number,
	x0: number,
	x1: number,
	y0: number,
	y1: number,
	z0: number,
	z1: number,
	sdf: (number, number, number) -> number,
	kind: number,
	mi: number,
	flat: boolean
)
	local c = chunks[chunkKey(cx, cy, cz)]
	local b = if c and not c.u then c.b else nil
	local cut = 0
	-- flat: 이 청크 기둥 안에서는 거리가 높이에만 달림(축 정렬 상자가 가로로 덮음) → 층마다 한 번만 계산
	local layer: { number }? = nil
	if flat then
		layer = {}
		for vy = y0, y1 do
			local d = sdf(cx * 32 + 16, vy * 4 + 2, cz * 32 + 16)
			layer[vy - y0 + 1] = if d >= 2 then 255 elseif d <= -2 then 0 else floor((d * 0.25 + 0.5) * 255 + 0.5)
		end
	end
	for vx = x0, x1 do
		local x = vx * 4 + 2
		local ox = (vx - cx * 8) * 8
		for vy = y0, y1 do
			local y = vy * 4 + 2
			local oxy = (ox + vy - cy * 8) * 8 - cz * 8
			local lo0 = if layer then layer[vy - y0 + 1] else -1
			for vz = z0, z1 do
				local o = lo0
				if o < 0 then
					local d = sdf(x, y, vz * 4 + 2)
					o = if d >= 2 then 255 elseif d <= -2 then 0 else floor((d * 0.25 + 0.5) * 255 + 0.5)
				end
				if o > 0 then
					if not b then
						b = densify(chunkForWrite(cx, cy, cz))
					end
					local off = (oxy + vz) * 3
					local sm, so, lo = buffer.readu8(b, off), buffer.readu8(b, off + 1), buffer.readu8(b, off + 2)
					if kind == 2 then
						if o >= so or o >= 128 then
							sm = mi
						end
						if o > so then
							so = o
						end
					else
						local cap = 255 - o
						if so > cap then
							if kind == 1 then
								cut += so - cap
							end
							so = cap
							if so == 0 then
								sm = 0
							end
						end
						if kind == 1 then
							if o > lo then
								lo = o
							end
						elseif lo > cap then
							lo = cap
						end
					end
					buffer.writeu8(b, off, sm)
					buffer.writeu8(b, off + 1, so)
					buffer.writeu8(b, off + 2, lo)
				end
			end
		end
	end
	terrainState.cutByWater += cut / 255
end

-- sdf(x, y, z): 모양 안쪽이면 +, 바깥이면 - 인 표면까지 거리(스터드). 볼록 모양만(청크 통째 판정이 볼록성에 기댐).
-- (minX..maxZ): 모양의 월드 경계 상자
local function fillShape(
	label: string,
	minX: number,
	minY: number,
	minZ: number,
	maxX: number,
	maxY: number,
	maxZ: number,
	sdf: (number, number, number) -> number,
	material: any,
	flatBox: { number }? -- 축 정렬 상자면 { minX, maxX, minZ, maxZ }
)
	local mi = terrainMaterialIndex(material, label)
	countCall(label, material)
	local kind = if mi == 0 then 0 elseif mi == 1 then 1 else 2
	terrainState.version += 1
	local vx0, vx1 = floor((minX - 2) / 4), floor((maxX + 2) / 4)
	local vy0, vy1 = floor((minY - 2) / 4), floor((maxY + 2) / 4)
	local vz0, vz1 = floor((minZ - 2) / 4), floor((maxZ + 2) / 4)
	assert(
		(vx1 - vx0 + 1) * (vy1 - vy0 + 1) * (vz1 - vz0 + 1) < 2e9,
		"Terrain:" .. label .. ": 영역이 너무 큽니다"
	)
	for cx = vx0 // 8, vx1 // 8 do
		local bx0, bx1 = max(vx0, cx * 8), min(vx1, cx * 8 + 7)
		for cy = vy0 // 8, vy1 // 8 do
			local by0, by1 = max(vy0, cy * 8), min(vy1, cy * 8 + 7)
			for cz = vz0 // 8, vz1 // 8 do
				local bz0, bz1 = max(vz0, cz * 8), min(vz1, cz * 8 + 7)
				-- 청크 가운데가 모양에서 (청크 반대각선 24.3 + 2) 보다 멀면 닿는 복셀 없음
				local dc = sdf(cx * 32 + 16, cy * 32 + 16, cz * 32 + 16)
				if dc > -26.3 then
					local whole = dc >= 2
						and bx0 == cx * 8
						and bx1 == cx * 8 + 7
						and by0 == cy * 8
						and by1 == cy * 8 + 7
						and bz0 == cz * 8
						and bz1 == cz * 8 + 7
					if whole then
						-- 볼록 모양의 안쪽 거리는 오목 함수라 복셀 가운데들의 상자 8 꼭짓점이 최솟값을 가짐
						local ax, bx = cx * 32 + 2, cx * 32 + 30
						local ay, by = cy * 32 + 2, cy * 32 + 30
						local az, bz = cz * 32 + 2, cz * 32 + 30
						whole = sdf(ax, ay, az) >= 2
							and sdf(bx, ay, az) >= 2
							and sdf(ax, by, az) >= 2
							and sdf(bx, by, az) >= 2
							and sdf(ax, ay, bz) >= 2
							and sdf(bx, ay, bz) >= 2
							and sdf(ax, by, bz) >= 2
							and sdf(bx, by, bz) >= 2
					end
					if whole then
						fillWholeChunk(cx, cy, cz, kind, mi)
					else
						local flat = flatBox ~= nil
							and flatBox[1] <= cx * 32
							and flatBox[2] >= cx * 32 + 32
							and flatBox[3] <= cz * 32
							and flatBox[4] >= cz * 32 + 32
						fillPartChunk(cx, cy, cz, bx0, bx1, by0, by1, bz0, bz1, sdf, kind, mi, flat)
					end
				end
			end
		end
	end
end

-- 모양별 거리 함수 --------------------------------------------------------------------
local function boxShape(cf, size)
	local p, m = cf.p, cf.m
	local px, py, pz = p.X, p.Y, p.Z
	local m1, m2, m3, m4, m5, m6, m7, m8, m9 = m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]
	local hx, hy, hz = abs(size.X) / 2, abs(size.Y) / 2, abs(size.Z) / 2
	local sdf = function(x: number, y: number, z: number): number
		local dx, dy, dz = x - px, y - py, z - pz
		local lx = abs(m1 * dx + m4 * dy + m7 * dz) - hx
		local ly = abs(m2 * dx + m5 * dy + m8 * dz) - hy
		local lz = abs(m3 * dx + m6 * dy + m9 * dz) - hz
		local inside = max(lx, ly, lz)
		if inside <= 0 then
			return -inside
		end
		local ox, oy, oz = max(lx, 0), max(ly, 0), max(lz, 0)
		return -sqrt(ox * ox + oy * oy + oz * oz)
	end
	local ex = abs(m1) * hx + abs(m2) * hy + abs(m3) * hz
	local ey = abs(m4) * hx + abs(m5) * hy + abs(m6) * hz
	local ez = abs(m7) * hx + abs(m8) * hy + abs(m9) * hz
	local flat = nil
	if abs(abs(m5) - 1) < 1e-9 and (abs(abs(m1) - 1) < 1e-9 or abs(abs(m3) - 1) < 1e-9) then
		flat = { px - ex, px + ex, pz - ez, pz + ez }
	end
	return sdf, px - ex, py - ey, pz - ez, px + ex, py + ey, pz + ez, flat
end

local Terrain = newInstance("Terrain")
Terrain.Name = "Terrain"
Terrain.Anchored = true
Terrain.Parent = Workspace
Workspace.Terrain = Terrain
for k, v in
	{
		WaterColor = Color3.fromRGB(12, 84, 92),
		WaterTransparency = 0.3,
		WaterReflectance = 1,
		WaterWaveSize = 0.15,
		WaterWaveSpeed = 10,
		Decoration = false,
		GrassLength = 0.7,
	}
do
	Terrain.__props[k] = v
end

Terrain.__props.FillBlock = function(_self, cf, size, material)
	assert(getmetatable(cf) == CMT and getmetatable(size) == VMT, "Terrain:FillBlock(CFrame, Vector3, Material)")
	local sdf, x0, y0, z0, x1, y1, z1, flat = boxShape(cf, size)
	fillShape("FillBlock", x0, y0, z0, x1, y1, z1, sdf, material, flat)
end
Terrain.__props.FillBall = function(_self, center, radius: number, material)
	assert(getmetatable(center) == VMT and type(radius) == "number", "Terrain:FillBall(Vector3, number, Material)")
	local px, py, pz = center.X, center.Y, center.Z
	local r = abs(radius)
	fillShape("FillBall", px - r, py - r, pz - r, px + r, py + r, pz + r, function(x, y, z)
		local dx, dy, dz = x - px, y - py, z - pz
		return r - sqrt(dx * dx + dy * dy + dz * dz)
	end, material)
end
Terrain.__props.FillCylinder = function(_self, cf, height: number, radius: number, material)
	-- 지형 원기둥은 cf 의 Y 축 방향(파트 Cylinder 의 X 축과 다름)
	assert(getmetatable(cf) == CMT, "Terrain:FillCylinder(CFrame, number, number, Material)")
	local p, m = cf.p, cf.m
	local px, py, pz = p.X, p.Y, p.Z
	local m1, m2, m3, m4, m5, m6, m7, m8, m9 = m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]
	local r, hh = abs(radius), abs(height) / 2
	local ex = abs(m2) * hh + r * sqrt(max(0, 1 - m2 * m2))
	local ey = abs(m5) * hh + r * sqrt(max(0, 1 - m5 * m5))
	local ez = abs(m8) * hh + r * sqrt(max(0, 1 - m8 * m8))
	fillShape("FillCylinder", px - ex, py - ey, pz - ez, px + ex, py + ey, pz + ez, function(x, y, z)
		local dx, dy, dz = x - px, y - py, z - pz
		local lx = m1 * dx + m4 * dy + m7 * dz
		local ly = m2 * dx + m5 * dy + m8 * dz
		local lz = m3 * dx + m6 * dy + m9 * dz
		local dr = sqrt(lx * lx + lz * lz) - r
		local dh = abs(ly) - hh
		local inside = max(dr, dh)
		if inside <= 0 then
			return -inside
		end
		local ox, oy = max(dr, 0), max(dh, 0)
		return -sqrt(ox * ox + oy * oy)
	end, material)
end
Terrain.__props.FillWedge = function(_self, cf, size, material)
	-- WedgePart 와 같은 모양: 바닥 전체 + 뒤(+Z) 면 전체, 경사면은 -Z 아래 모서리에서 +Z 위 모서리로
	assert(getmetatable(cf) == CMT and getmetatable(size) == VMT, "Terrain:FillWedge(CFrame, Vector3, Material)")
	local box, x0, y0, z0, x1, y1, z1 = boxShape(cf, size)
	local p, m = cf.p, cf.m
	local px, py, pz = p.X, p.Y, p.Z
	local m2, m3, m5, m6, m8, m9 = m[2], m[3], m[5], m[6], m[8], m[9]
	local h, d = abs(size.Y), abs(size.Z)
	local n = sqrt(h * h + d * d)
	fillShape("FillWedge", x0, y0, z0, x1, y1, z1, function(x, y, z)
		local dx, dy, dz = x - px, y - py, z - pz
		local ly = m2 * dx + m5 * dy + m8 * dz
		local lz = m3 * dx + m6 * dy + m9 * dz
		return min(box(x, y, z), -(ly * d - lz * h) / n)
	end, material)
end

-- 격자에 맞춘 영역 -> 복셀 번호 범위(양끝 포함)
local function regionVoxels(region, resolution: number, label: string): (number, number, number, number, number, number)
	assert(getmetatable(region) == R3MT, "Terrain:" .. label .. ": Region3 가 아닙니다")
	if resolution ~= 4 then
		error("Terrain:" .. label .. ": resolution 은 4 만 됩니다", 3)
	end
	local lo, hi = region.__min, region.__max
	for _, v in { lo.X, lo.Y, lo.Z, hi.X, hi.Y, hi.Z } do
		if v % 4 ~= 0 then
			error("Terrain:" .. label .. ": Region has to be aligned to the grid (use Region3:ExpandToGrid)", 3)
		end
	end
	return lo.X / 4, lo.Y / 4, lo.Z / 4, hi.X / 4 - 1, hi.Y / 4 - 1, hi.Z / 4 - 1
end

Terrain.__props.FillRegion = function(_self, region, resolution: number, material)
	local x0, y0, z0, x1, y1, z1 = regionVoxels(region, resolution, "FillRegion")
	local lo, hi = region.__min, region.__max
	local sdf, _, _, _, _, _, _, flat = boxShape(region.CFrame, hi - lo)
	fillShape("FillRegion", x0 * 4, y0 * 4, z0 * 4, (x1 + 1) * 4, (y1 + 1) * 4, (z1 + 1) * 4, sdf, material, flat)
end

-- ReadVoxels 가 보여 주는 복셀 하나의 재질 번호·점유율
local function visibleVoxel(sm: number, so: number, lo: number): (number, number)
	if so > 0 and so >= lo then
		return sm, so / 255
	elseif lo > 0 then
		return 1, lo / 255
	end
	return 0, 0
end

Terrain.__props.ReadVoxels = function(_self, region, resolution: number)
	local x0, y0, z0, x1, y1, z1 = regionVoxels(region, resolution, "ReadVoxels")
	local materials, occupancies = {}, {}
	for vx = x0, x1 do
		local mx, ox = {}, {}
		for vy = y0, y1 do
			local my, oy = {}, {}
			for vz = z0, z1 do
				local index, occupancy = visibleVoxel(readVoxel(vx, vy, vz))
				table.insert(my, "Material." .. TERRAIN_MATERIALS[index + 1])
				table.insert(oy, occupancy)
			end
			table.insert(mx, my)
			table.insert(ox, oy)
		end
		table.insert(materials, mx)
		table.insert(occupancies, ox)
	end
	local size = vec(x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
	materials.Size = size
	occupancies.Size = size
	return materials, occupancies
end

local function checkVoxelArray(array, x0, y0, z0, x1, y1, z1, label: string)
	assert(
		type(array) == "table" and #array == x1 - x0 + 1 and #array[1] == y1 - y0 + 1 and #array[1][1] == z1 - z0 + 1,
		"Terrain:" .. label .. ": 배열 크기가 영역과 다릅니다"
	)
end

Terrain.__props.WriteVoxels = function(_self, region, resolution: number, materials, occupancies)
	local x0, y0, z0, x1, y1, z1 = regionVoxels(region, resolution, "WriteVoxels")
	checkVoxelArray(materials, x0, y0, z0, x1, y1, z1, "WriteVoxels")
	checkVoxelArray(occupancies, x0, y0, z0, x1, y1, z1, "WriteVoxels")
	countCall("WriteVoxels", "")
	terrainState.version += 1
	for i = 1, x1 - x0 + 1 do
		for j = 1, y1 - y0 + 1 do
			for k = 1, z1 - z0 + 1 do
				local mi = terrainMaterialIndex(materials[i][j][k], "WriteVoxels")
				local o = floor(math.clamp(occupancies[i][j][k], 0, 1) * 255 + 0.5)
				local vx, vy, vz = x0 + i - 1, y0 + j - 1, z0 + k - 1
				if mi == 0 or o == 0 then
					writeVoxel(vx, vy, vz, 0, 0, 0)
				elseif mi == 1 then
					writeVoxel(vx, vy, vz, 0, 0, o)
				else
					writeVoxel(vx, vy, vz, mi, o, 0)
				end
			end
		end
	end
end

-- Shorelines 채널 API: SolidMaterial / SolidOccupancy / LiquidOccupancy
Terrain.__props.ReadVoxelChannels = function(_self, region, resolution: number, channelIds: { string })
	local x0, y0, z0, x1, y1, z1 = regionVoxels(region, resolution, "ReadVoxelChannels")
	local out = {}
	local wanted = {}
	for _, id in channelIds do
		assert(
			id == "SolidMaterial" or id == "SolidOccupancy" or id == "LiquidOccupancy",
			"모르는 채널 " .. tostring(id)
		)
		wanted[id] = true
		out[id] = {}
	end
	for vx = x0, x1 do
		local planes = {}
		for id in wanted do
			planes[id] = {}
			table.insert(out[id], planes[id])
		end
		for vy = y0, y1 do
			local rows = {}
			for id in wanted do
				rows[id] = {}
				table.insert(planes[id], rows[id])
			end
			for vz = z0, z1 do
				local sm, so, lo = readVoxel(vx, vy, vz)
				if rows.SolidMaterial then
					table.insert(rows.SolidMaterial, "Material." .. TERRAIN_MATERIALS[sm + 1])
				end
				if rows.SolidOccupancy then
					table.insert(rows.SolidOccupancy, so / 255)
				end
				if rows.LiquidOccupancy then
					table.insert(rows.LiquidOccupancy, lo / 255)
				end
			end
		end
	end
	out.Size = vec(x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
	return out
end

Terrain.__props.WriteVoxelChannels = function(_self, region, resolution: number, channels)
	local x0, y0, z0, x1, y1, z1 = regionVoxels(region, resolution, "WriteVoxelChannels")
	for id, array in channels do
		if id ~= "Size" then
			assert(
				id == "SolidMaterial" or id == "SolidOccupancy" or id == "LiquidOccupancy",
				"모르는 채널 " .. tostring(id)
			)
			checkVoxelArray(array, x0, y0, z0, x1, y1, z1, "WriteVoxelChannels")
		end
	end
	countCall("WriteVoxelChannels", "")
	terrainState.version += 1
	local mats, solids, liquids = channels.SolidMaterial, channels.SolidOccupancy, channels.LiquidOccupancy
	for i = 1, x1 - x0 + 1 do
		for j = 1, y1 - y0 + 1 do
			for k = 1, z1 - z0 + 1 do
				local vx, vy, vz = x0 + i - 1, y0 + j - 1, z0 + k - 1
				local sm, so, lo = readVoxel(vx, vy, vz)
				if mats then
					sm = terrainMaterialIndex(mats[i][j][k], "WriteVoxelChannels")
					if sm == 1 then
						error("Terrain:WriteVoxelChannels: SolidMaterial 에 Water 는 못 넣습니다", 2)
					end
				end
				if solids then
					so = floor(math.clamp(solids[i][j][k], 0, 1) * 255 + 0.5)
				end
				if liquids then
					lo = floor(math.clamp(liquids[i][j][k], 0, 1) * 255 + 0.5)
				end
				if sm == 0 then
					so = 0
				end
				writeVoxel(vx, vy, vz, sm, so, lo)
			end
		end
	end
end

Terrain.__props.ReplaceMaterial = function(_self, region, resolution: number, source, target)
	local x0, y0, z0, x1, y1, z1 = regionVoxels(region, resolution, "ReplaceMaterial")
	local si = terrainMaterialIndex(source, "ReplaceMaterial")
	local ti = terrainMaterialIndex(target, "ReplaceMaterial")
	countCall("ReplaceMaterial", tostring(source) .. "->" .. tostring(target))
	terrainState.version += 1
	for vx = x0, x1 do
		for vy = y0, y1 do
			for vz = z0, z1 do
				local sm, so, lo = readVoxel(vx, vy, vz)
				local current = visibleVoxel(sm, so, lo)
				if current == si then
					-- 빈 복셀(Air)을 바꾸면 꽉 채움, 물이면 물 점유율, 땅이면 땅 점유율을 그대로
					local occupancy = if si == 0 then 255 elseif si == 1 then lo else so
					if ti == 0 then
						writeVoxel(vx, vy, vz, 0, 0, 0)
					elseif ti == 1 then
						writeVoxel(vx, vy, vz, 0, 0, occupancy)
					elseif si == 1 then
						writeVoxel(vx, vy, vz, ti, occupancy, 0)
					else
						writeVoxel(vx, vy, vz, ti, occupancy, lo)
					end
				end
			end
		end
	end
end

Terrain.__props.Clear = function(_self)
	table.clear(chunks)
	terrainState.bounds = nil
	terrainState.version += 1
	countCall("Clear", "")
end
Terrain.__props.SetMaterialColor = function(_self, material, c)
	local index = terrainMaterialIndex(material, "SetMaterialColor")
	assert(index >= 2, "Terrain:SetMaterialColor: Air/Water 는 색을 못 바꿉니다(물은 WaterColor)")
	assert(getmetatable(c) == C3MT, "Terrain:SetMaterialColor(Material, Color3)")
	terrainColors[material] = c
end
Terrain.__props.GetMaterialColor = function(_self, material)
	local index = terrainMaterialIndex(material, "GetMaterialColor")
	local custom = terrainColors[material]
	if custom then
		return custom
	end
	local rgb = DEFAULT_MATERIAL_COLORS[TERRAIN_MATERIALS[index + 1]] or { 128, 128, 128 }
	return Color3.fromRGB(rgb[1], rgb[2], rgb[3])
end
Terrain.__props.CellCenterToWorld = function(_self, x: number, y: number, z: number)
	return vec(x * 4 + 2, y * 4 + 2, z * 4 + 2)
end
Terrain.__props.CellCornerToWorld = function(_self, x: number, y: number, z: number)
	return vec(x * 4, y * 4, z * 4)
end
Terrain.__props.WorldToCell = function(_self, p)
	return vec(floor(p.X / 4), floor(p.Y / 4), floor(p.Z / 4))
end
Terrain.__props.WorldToCellPreferSolid = Terrain.__props.WorldToCell
Terrain.__props.WorldToCellPreferEmpty = Terrain.__props.WorldToCell
Terrain.__props.CopyRegion = function()
	error("Terrain:CopyRegion 은 흉내 내지 않습니다", 2)
end
Terrain.__props.PasteRegion = function()
	error("Terrain:PasteRegion 은 흉내 내지 않습니다", 2)
end
Terrain.__props.MaxExtents = Region3int16.new(vec16(-32000, -32000, -32000), vec16(32000, 32000, 32000))
Mock.terrainColors = terrainColors

-- 기둥 표면 ----------------------------------------------------------------------------
-- 기둥(가로 4x4 스터드 복셀 한 줄 vx, vz)의 위 표면.
-- 돌려줌: 땅 윗면 높이(없으면 nil), 윗면 재질 번호, 물 윗면(없거나 땅이 더 높으면 nil), 물 밑면(물 아래 땅이 없을 때)
-- 땅 높이: 맨 위 단단한 복셀 t 의 점유율 oT, 그 아래 복셀 oB 로
--   oT >= 0.5 이거나 아래가 꽉 참/빔 → t 바닥 + 4·oT (평평한 땅이면 정확히 채운 높이)
--   oT < 0.5 이고 0.5 <= oB < 1 → 두 복셀 가운데 사이에서 점유율 0.5 가 되는 곳(비탈)
--   둘 다 0.5 미만 → 아래 복셀 바닥 + 4·oB
local function columnSurface(vx: number, vz: number): (number?, number, number?, number?)
	local bounds = terrainState.bounds
	if not bounds then
		return nil, 0, nil, nil
	end
	local cx, cz = vx // 8, vz // 8
	if cx < bounds[1] or cx > bounds[4] or cz < bounds[3] or cz > bounds[6] then
		return nil, 0, nil, nil
	end
	local lx, lz = vx - cx * 8, vz - cz * 8
	local waterTop: number?, waterBottom: number? = nil, nil
	local inWater = false
	local top: number? = nil
	for cy = bounds[5], bounds[2], -1 do
		local c = chunks[chunkKey(cx, cy, cz)]
		if c == nil or (c.u and c.so == 0 and c.lo == 0) then
			if inWater then
				inWater = false
				waterBottom = (cy + 1) * 32
			end
		else
			local b = if c.u then nil else c.b
			for ly = 7, 0, -1 do
				local so, lo
				if b then
					local off = ((lx * 8 + ly) * 8 + lz) * 3
					so, lo = buffer.readu8(b, off + 1), buffer.readu8(b, off + 2)
				else
					so, lo = c.so, c.lo
				end
				local vy = cy * 8 + ly
				if lo > 0 then
					if waterTop == nil then
						-- 한 복셀에 땅 + 물이면 물은 땅 위 빈 곳을 채움(Shorelines)
						waterTop = vy * 4 + min(255, lo + so) / 255 * 4
						inWater = true
					end
				elseif inWater then
					inWater = false
					waterBottom = vy * 4 + 4
				end
				if so > 3 then
					top = vy
					break
				end
			end
			if top then
				break
			end
		end
	end
	if top == nil then
		if inWater then
			waterBottom = bounds[2] * 32
		end
		return nil, 0, waterTop, waterBottom
	end
	local smT, soT = readVoxel(vx, top, vz)
	local smB, soB = readVoxel(vx, top - 1, vz)
	local oT, oB = soT / 255, soB / 255
	local h
	if oT >= 0.5 or oB >= 0.99 or oB <= 0 then
		h = top * 4 + oT * 4
	elseif oB >= 0.5 then
		h = (top - 1) * 4 + 2 + 4 * (oB - 0.5) / (oB - oT)
	else
		h = (top - 1) * 4 + oB * 4
	end
	local material = if soT >= 64 or soB == 0 then smT else smB
	if waterTop and waterTop <= h then
		waterTop = nil
	end
	return h, material, waterTop, waterBottom
end

local columnCache: { [number]: { any } } = {}
local function cachedColumn(vx: number, vz: number): (number?, number, number?, number?)
	local key = (vx + 32768) * 65536 + (vz + 32768)
	local e = columnCache[key]
	if e and e[1] == terrainState.version then
		return e[2], e[3], e[4], e[5]
	end
	local h, material, w, wb = columnSurface(vx, vz)
	columnCache[key] = { terrainState.version, h, material, w, wb }
	return h, material, w, wb
end

-- (x, z) 의 매끈한 지형 높이: 이웃 기둥 가운데 4개를 쌍선형 보간(하나라도 없으면 가장 가까운 기둥). 없으면 nil
local function terrainHeight(x: number, z: number, withWater: boolean): number?
	local fx, fz = (x - 2) / 4, (z - 2) / 4
	local vx, vz = floor(fx), floor(fz)
	local tx, tz = fx - vx, fz - vz
	local function at(ix: number, iz: number): number?
		local h, _, w = cachedColumn(ix, iz)
		if withWater and w and (h == nil or w > h) then
			return w
		end
		return h
	end
	local a, b, c, d = at(vx, vz), at(vx + 1, vz), at(vx, vz + 1), at(vx + 1, vz + 1)
	if a and b and c and d then
		return (a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz
	end
	return at(floor(fx + 0.5), floor(fz + 0.5))
end

-- 지형 광선: 맨 위 표면(물 포함 여부 선택)과 처음 만나는 t(0~1), 법선, 재질. 시작점이 이미 표면 아래면 nil
local function terrainRaycast(origin, direction, ignoreWater: boolean): (number?, any, string?)
	local bounds = terrainState.bounds
	if not bounds then
		return nil
	end
	local lo = { bounds[1] * 32, bounds[2] * 32, bounds[3] * 32 }
	local hi = { (bounds[4] + 1) * 32, (bounds[5] + 1) * 32, (bounds[6] + 1) * 32 }
	local o = { origin.X, origin.Y, origin.Z }
	local d = { direction.X, direction.Y, direction.Z }
	local t0, t1 = 0, 1
	for i = 1, 3 do
		if abs(d[i]) < 1e-12 then
			if o[i] < lo[i] or o[i] > hi[i] then
				return nil
			end
		else
			local a, b = (lo[i] - o[i]) / d[i], (hi[i] - o[i]) / d[i]
			if a > b then
				a, b = b, a
			end
			t0, t1 = max(t0, a), min(t1, b)
			if t0 > t1 then
				return nil
			end
		end
	end
	local length = direction.Magnitude
	if length < 1e-9 then
		return nil
	end
	local function gap(t: number): number
		local h = terrainHeight(o[1] + d[1] * t, o[3] + d[3] * t, not ignoreWater)
		return if h then o[2] + d[2] * t - h else huge
	end
	local t = t0
	local g = gap(t)
	if g <= 0 then
		return nil
	end
	while t < t1 do
		local previous = t
		t = min(t + math.clamp(g * 0.5, 0.2, 6) / length, t1)
		g = gap(t)
		if g <= 0 then
			local a, b = previous, t
			for _ = 1, 14 do
				local mid = (a + b) / 2
				if gap(mid) <= 0 then
					b = mid
				else
					a = mid
				end
			end
			local x, y, z = o[1] + d[1] * b, o[2] + d[2] * b, o[3] + d[3] * b
			local solid = terrainHeight(x, z, false)
			if not ignoreWater and (solid == nil or y > solid + 0.05) then
				return b, vec(0, 1, 0), "Material.Water"
			end
			local e = 1
			local hx0, hx1 = terrainHeight(x - e, z, false) or y, terrainHeight(x + e, z, false) or y
			local hz0, hz1 = terrainHeight(x, z - e, false) or y, terrainHeight(x, z + e, false) or y
			local _, material = cachedColumn(floor(x / 4), floor(z / 4))
			return b,
				vec(-(hx1 - hx0) / (2 * e), 1, -(hz1 - hz0) / (2 * e)).Unit,
				"Material." .. TERRAIN_MATERIALS[material + 1]
		end
	end
	return nil
end

-- 미리보기/검사용 --------------------------------------------------------------------
-- (x, z) 의 지형: 땅 높이(없으면 nil), 윗면 재질("Grass" 등), 물 윗면(없으면 nil)
function Mock.terrainColumn(x: number, z: number): (number?, string, number?)
	local h, material, w = cachedColumn(floor(x / 4), floor(z / 4))
	return h, TERRAIN_MATERIALS[material + 1], w
end
Mock.terrainHeight = terrainHeight
Mock.terrainVoxel = function(vx: number, vy: number, vz: number)
	return readVoxel(vx, vy, vz)
end
function Mock.terrainStats()
	local uniform, dense = 0, 0
	for _, c in chunks do
		if c.u then
			uniform += 1
		else
			dense += 1
		end
	end
	return {
		UniformChunks = uniform,
		DenseChunks = dense,
		CutByWater = terrainState.cutByWater,
		Calls = terrainState.calls,
		Bounds = terrainState.bounds,
	}
end

-- 렌더러용 덤프(JSON 문자열, 지형이 없으면 nil).
-- 격자 두 벌: coarse(청크 모서리마다 한 기둥, 32 스터드 간격, 지형 경계 상자 전체) +
--   tiles(흔한 모양과 다른 청크 기둥마다 4 스터드 간격 9x9 기둥. 너무 많으면 8/16 스터드 간격).
--   "흔한 모양" = 청크 기둥(세로 청크 목록) 서명이 가장 많은 것(보통 바다). 다른 기둥 둘레 한 칸까지 타일.
-- 기둥 값: h = 땅 높이, w = 물 윗면, b = 물 밑면(물 아래 땅 없을 때) — 모두 1/8 스터드 정수, 없으면 null. m = 재질 번호
function Mock.terrainDumpJson(props: { [string]: any }): string?
	local bounds = terrainState.bounds
	if not bounds then
		return nil
	end
	local bx0, by0, bz0, bx1, by1, bz1 = bounds[1], bounds[2], bounds[3], bounds[4], bounds[5], bounds[6]
	local maxVx, maxVz = (bx1 + 1) * 8 - 1, (bz1 + 1) * 8 - 1
	-- 1) 청크 기둥 서명
	local tokens: { [number]: { string } } = {}
	for key, c in chunks do
		if not (c.u and c.so == 0 and c.lo == 0) then
			local cx, cy, cz = keyToChunk(key)
			local ck = (cx + 32768) * 65536 + (cz + 32768)
			local list = tokens[ck]
			if not list then
				list = {}
				tokens[ck] = list
			end
			table.insert(
				list,
				if c.u
					then string.format("%06d:%d:%d:%d", cy + 32768, c.sm, c.so, c.lo)
					else string.format("%06d:D", cy + 32768) .. buffer.tostring(c.b)
			)
		end
	end
	local signature: { [number]: string } = {}
	local counts: { [string]: number } = {}
	for cx = bx0, bx1 do
		for cz = bz0, bz1 do
			local ck = (cx + 32768) * 65536 + (cz + 32768)
			local list = tokens[ck]
			local sig = ""
			if list then
				table.sort(list)
				sig = table.concat(list, "|")
			end
			signature[ck] = sig
			counts[sig] = (counts[sig] or 0) + 1
		end
	end
	local modal, best = nil, 1
	for sig, n in counts do
		if n > best or (n == best and sig == "") then
			modal, best = sig, n
		end
	end
	-- 2) 타일 = 흔하지 않은 기둥 + 둘레 한 칸
	local tileSet: { [number]: boolean } = {}
	local tileList: { { number } } = {}
	for cx = bx0, bx1 do
		for cz = bz0, bz1 do
			if signature[(cx + 32768) * 65536 + (cz + 32768)] ~= modal then
				for ax = max(bx0, cx - 1), min(bx1, cx + 1) do
					for az = max(bz0, cz - 1), min(bz1, cz + 1) do
						local k = (ax + 32768) * 65536 + (az + 32768)
						if not tileSet[k] then
							tileSet[k] = true
							table.insert(tileList, { ax, az })
						end
					end
				end
			end
		end
	end
	table.sort(tileList, function(a, b)
		return if a[2] ~= b[2] then a[2] < b[2] else a[1] < b[1]
	end)
	local step = 1
	if #tileList * 81 > 260000 then
		step = if #tileList * 25 > 260000 then 4 else 2
	end

	local function q(v: number?): string
		return if v then tostring(math.round(v * 8)) else "null"
	end
	local function grid(xs: { number }, zs: { number }): string
		local h, m, w, b = {}, {}, {}, {}
		for _, vz in zs do
			for _, vx in xs do
				local height, material, water, bottom = cachedColumn(vx, vz)
				table.insert(h, q(height))
				table.insert(m, tostring(material))
				table.insert(w, q(water))
				table.insert(b, q(if water and not height then bottom else nil))
			end
		end
		local px, pz = {}, {}
		for i, vx in xs do
			px[i] = tostring(vx * 4 + 2)
		end
		for i, vz in zs do
			pz[i] = tostring(vz * 4 + 2)
		end
		return string.format(
			'"xs":[%s],"zs":[%s],"h":[%s],"m":[%s],"w":[%s],"b":[%s]',
			table.concat(px, ","),
			table.concat(pz, ","),
			table.concat(h, ","),
			table.concat(m, ","),
			table.concat(w, ","),
			table.concat(b, ",")
		)
	end

	local coarseX, coarseZ = {}, {}
	for cx = bx0, bx1 + 1 do
		table.insert(coarseX, min(cx * 8, maxVx))
	end
	for cz = bz0, bz1 + 1 do
		table.insert(coarseZ, min(cz * 8, maxVz))
	end
	local tiles = {}
	for _, tile in tileList do
		local xs, zs = {}, {}
		for a = 0, 8, step do
			table.insert(xs, min(tile[1] * 8 + a, maxVx))
			table.insert(zs, min(tile[2] * 8 + a, maxVz))
		end
		table.insert(tiles, string.format('{"cx":%d,"cz":%d,%s}', tile[1], tile[2], grid(xs, zs)))
	end

	local names = {}
	for i, name in TERRAIN_MATERIALS do
		names[i] = json.encode(name)
	end
	local colors = {}
	for i = 3, #TERRAIN_MATERIALS do
		local name = TERRAIN_MATERIALS[i]
		local c = Terrain:GetMaterialColor("Material." .. name)
		table.insert(colors, string.format('"%s":[%.4f,%.4f,%.4f]', name, c.R, c.G, c.B))
	end
	local stats = Mock.terrainStats()
	return string.format(
		'{"voxel":4,"chunk":32,"step":%d,"materials":[%s],"colors":{%s},"props":%s,'
			.. '"bounds":[%d,%d,%d,%d,%d,%d],"coarse":{"cx0":%d,"cz0":%d,%s},"tiles":[%s],'
			.. '"stats":{"uniformChunks":%d,"denseChunks":%d,"cutByWater":%.1f,"calls":%s}}',
		step * 4,
		table.concat(names, ","),
		table.concat(colors, ","),
		json.encode(props),
		bx0 * 32,
		by0 * 32,
		bz0 * 32,
		(bx1 + 1) * 32,
		(by1 + 1) * 32,
		(bz1 + 1) * 32,
		bx0,
		bz0,
		grid(coarseX, coarseZ),
		table.concat(tiles, ","),
		stats.UniformChunks,
		stats.DenseChunks,
		stats.CutByWater,
		json.encode(stats.Calls)
	)
end

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
	local bestMaterial = bestPart and bestPart.Material
	-- 지형(Workspace 에서 쏠 때만): 걸러내기 목록에 Terrain 이 있으면 Exclude 는 빼고, Include 는 그때만
	if self == Workspace then
		local skipTerrain = filtered(Terrain)
		if include then
			skipTerrain = not skipTerrain
		end
		if not skipTerrain then
			local t, n, material = terrainRaycast(origin, direction, params ~= nil and params.IgnoreWater == true)
			if t and t < best then
				best, bestNormal, bestPart, bestMaterial = t, n, Terrain, material
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
		Material = bestMaterial,
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
_G.Region3 = Region3
_G.Region3int16 = Region3int16
_G.Vector3int16 = Vector3int16
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
