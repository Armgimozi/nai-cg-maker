-- Roblox 밖에서 Models(명소 모형) 를 만들어 검사하는 가짜 Roblox 환경.
-- 모든 명소를 build/create 해서 규칙(바닥 10x10, 높이 22, 파트 수 등)을 검사하고, 마지막에 파트 목록(JSON)을 출력.
-- 보통은 tools/model_preview/preview.sh 로 실행합니다.
local SCRATCH = ARGS[1]
local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()

local sqrt, sin, cos, abs = math.sqrt, math.sin, math.cos, math.abs

-- Vector3 -------------------------------------------------------------------
local Vector3 = {}
local VMT = {}
local function vec(x, y, z)
	return setmetatable({ X = x, Y = y, Z = z }, VMT)
end
VMT.__index = function(v, k)
	if k == "Magnitude" then
		return sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
	elseif k == "Unit" then
		local m = sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
		return vec(v.X / m, v.Y / m, v.Z / m)
	elseif k == "Dot" then
		return function(a, b)
			return a.X * b.X + a.Y * b.Y + a.Z * b.Z
		end
	elseif k == "Cross" then
		return function(a, b)
			return vec(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X)
		end
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
	return vec(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
VMT.__div = function(a, b)
	assert(type(b) == "number")
	return vec(a.X / b, a.Y / b, a.Z / b)
end
VMT.__unm = function(a)
	return vec(-a.X, -a.Y, -a.Z)
end
VMT.__tostring = function(v)
	return string.format("(%.3f, %.3f, %.3f)", v.X, v.Y, v.Z)
end
function Vector3.new(x, y, z)
	return vec(x or 0, y or 0, z or 0)
end
Vector3.zero = vec(0, 0, 0)
Vector3.one = vec(1, 1, 1)
Vector3.yAxis = vec(0, 1, 0)

-- CFrame (rotation matrix rows m[1..9] + position) ---------------------------
local CFrame = {}
local CMT = {}
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
CMT.__index = function(cf, k)
	local m = cf.m
	if k == "Position" then
		return cf.p
	elseif k == "X" then
		return cf.p.X
	elseif k == "Y" then
		return cf.p.Y
	elseif k == "Z" then
		return cf.p.Z
	elseif k == "RightVector" then
		return vec(m[1], m[4], m[7])
	elseif k == "UpVector" then
		return vec(m[2], m[5], m[8])
	elseif k == "LookVector" then
		return vec(-m[3], -m[6], -m[9])
	elseif k == "Inverse" then
		return function(self)
			local t = transpose(self.m)
			return cframe(-rotate(t, self.p), t)
		end
	elseif k == "ToObjectSpace" then
		return function(self, other)
			return self:Inverse() * other
		end
	elseif k == "PointToWorldSpace" then
		return function(self, v)
			return self * v
		end
	end
	error("CFrame has no member " .. tostring(k), 2)
end
CMT.__mul = function(a, b)
	if getmetatable(b) == VMT then
		return rotate(a.m, b) + a.p
	end
	assert(getmetatable(b) == CMT, "bad CFrame mul")
	return cframe(rotate(a.m, b.p) + a.p, matmul(a.m, b.m))
end
CMT.__add = function(a, b)
	return cframe(a.p + b, a.m)
end
function CFrame.new(x, y, z)
	if x == nil then
		return cframe(vec(0, 0, 0), IDENT)
	elseif type(x) == "table" then
		assert(y == nil, "CFrame.new(pos, lookAt) not mocked")
		return cframe(x, IDENT)
	end
	return cframe(vec(x, y, z), IDENT)
end
CFrame.identity = CFrame.new()
function CFrame.Angles(rx, ry, rz)
	local cx, sx, cy, sy, cz, sz = cos(rx), sin(rx), cos(ry), sin(ry), cos(rz), sin(rz)
	local Rx = { 1, 0, 0, 0, cx, -sx, 0, sx, cx }
	local Ry = { cy, 0, sy, 0, 1, 0, -sy, 0, cy }
	local Rz = { cz, -sz, 0, sz, cz, 0, 0, 0, 1 }
	return cframe(vec(0, 0, 0), matmul(matmul(Rx, Ry), Rz))
end
function CFrame.lookAt(at, target, up)
	up = up or vec(0, 1, 0)
	local look = (target - at).Unit
	local right = look:Cross(up)
	assert(right.Magnitude > 1e-6, "CFrame.lookAt degenerate (vertical)")
	right = right.Unit
	local up2 = right:Cross(look)
	-- columns: right, up2, -look
	return cframe(at, { right.X, up2.X, -look.X, right.Y, up2.Y, -look.Y, right.Z, up2.Z, -look.Z })
end

-- Instances -----------------------------------------------------------------
local BASEPART = { Part = true, WedgePart = true, CornerWedgePart = true, MeshPart = true }
local violations = {}
local IMT = {}
local function newInstance(className)
	local obj = { __props = {}, __children = {} }
	obj.__props.ClassName = className
	obj.__props.Name = className
	if BASEPART[className] then
		local p = obj.__props
		p.Anchored = false
		p.CanCollide = true
		p.CanQuery = true
		p.CanTouch = true
		p.Massless = false
		p.Transparency = 0
		p.Size = vec(4, 1, 2)
		p.CFrame = CFrame.new()
		p.PivotOffset = CFrame.new()
		p.Shape = "PartType.Block"
		p.Material = "Material.Plastic"
		p.Color = Color3.new(0.6, 0.6, 0.6)
	elseif className == "Model" then
		obj.__props.WorldPivot = CFrame.new()
		obj.__props.__scale = 1
	end
	return setmetatable(obj, IMT)
end

local methods = {}
function methods.IsA(self, name)
	local cls = self.__props.ClassName
	if name == cls or name == "Instance" then
		return true
	end
	if name == "BasePart" then
		return BASEPART[cls] == true
	end
	if name == "PVInstance" then
		return BASEPART[cls] == true or cls == "Model"
	end
	return false
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
function methods.FindFirstChild(self, name)
	for _, child in self.__children do
		if child.Name == name then
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
function methods.Destroy(self)
	self.Parent = nil
	self.__props.__destroyed = true
end
function methods.Clone(self)
	local copy = newInstance(self.__props.ClassName)
	for k, v in self.__props do
		if k ~= "Parent" and k ~= "PrimaryPart" then
			copy.__props[k] = v
		end
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
function methods.GetPivot(self)
	local p = self.__props
	if p.ClassName == "Model" then
		if p.PrimaryPart then
			return p.PrimaryPart.CFrame * p.PrimaryPart.PivotOffset
		end
		return p.WorldPivot
	end
	return p.CFrame * p.PivotOffset
end
function methods.PivotTo(self, target)
	local pivot = self:GetPivot()
	local delta = target * pivot:Inverse()
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") then
			d.CFrame = delta * d.CFrame
		end
	end
	if not self.__props.PrimaryPart then
		self.__props.WorldPivot = target
	end
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
function methods.GetBoundingBox(self)
	local frame = if self.PrimaryPart then self.PrimaryPart.CFrame else self.WorldPivot
	frame = cframe(frame.p, frame.m)
	local inv = frame:Inverse()
	local lo, hi = vec(math.huge, math.huge, math.huge), vec(-math.huge, -math.huge, -math.huge)
	local any = false
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") then
			any = true
			for _, c in corners(d) do
				local l = inv * c
				lo = vec(math.min(lo.X, l.X), math.min(lo.Y, l.Y), math.min(lo.Z, l.Z))
				hi = vec(math.max(hi.X, l.X), math.max(hi.Y, l.Y), math.max(hi.Z, l.Z))
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
	assert(newScale > 0 and newScale < math.huge, "bad scale " .. tostring(newScale))
	local factor = newScale / self.__props.__scale
	local pivot = self:GetPivot()
	for _, d in self:GetDescendants() do
		if d:IsA("BasePart") then
			local offset = pivot:ToObjectSpace(d.CFrame)
			d.CFrame = pivot * cframe(offset.p * factor, offset.m)
			d.Size = d.Size * factor
			local po = d.PivotOffset
			d.PivotOffset = cframe(po.p * factor, po.m)
		end
	end
	self.__props.__scale = newScale
end

IMT.__index = function(self, k)
	if methods[k] then
		return methods[k]
	end
	local v = self.__props[k]
	if v ~= nil then
		return v
	end
	if k == "Parent" or k == "PrimaryPart" then
		return nil
	end
	error(self.__props.ClassName .. " has no property " .. tostring(k), 2)
end
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
IMT.__newindex = function(self, k, v)
	assert(KNOWN[k], "unknown property set: " .. tostring(k))
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
	if k == "CanQuery" and v == false and p.CanCollide then
		table.insert(violations, "CanQuery=false while CanCollide=true")
	end
	if k == "Size" and p.Shape == "PartType.Ball" and (abs(v.X - v.Y) > 1e-6 or abs(v.Y - v.Z) > 1e-6) then
		table.insert(violations, "non-uniform Ball " .. tostring(v))
	end
	if k == "Size" and p.Shape == "PartType.Cylinder" and abs(v.Y - v.Z) > 1e-6 then
		table.insert(violations, "elliptic Cylinder " .. tostring(v))
	end
	if k == "Shape" and p.ClassName ~= "Part" then
		table.insert(violations, "Shape on " .. p.ClassName)
	end
	p[k] = v
end

local Instance = { new = newInstance }

local ReplicatedStorage = newInstance("Folder")
ReplicatedStorage.Name = "ReplicatedStorage"
local game = {
	GetService = function(_, name)
		assert(name == "ReplicatedStorage", "unexpected service " .. name)
		return ReplicatedStorage
	end,
}

local warnings = {}
_G.Vector3 = Vector3
_G.CFrame = CFrame
_G.Instance = Instance
_G.game = game
_G.warn = function(...)
	table.insert(warnings, table.concat({ ... }, " "))
end

-- Load modules ----------------------------------------------------------------
local shared = Harness.folder("src/shared")
local Landmarks = Harness.require(shared.Landmarks)
local Models = Harness.require(shared.Models)
local test, eq, near = Harness.test, Harness.eq, Harness.near

local function parts(model)
	local out = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			table.insert(out, d)
		end
	end
	return out
end

local function worldBounds(part)
	if part.Shape == "PartType.Ball" then
		local r = part.Size.X / 2
		local c = part.CFrame.Position
		return vec(c.X - r, c.Y - r, c.Z - r), vec(c.X + r, c.Y + r, c.Z + r)
	end
	local lo, hi = vec(math.huge, math.huge, math.huge), vec(-math.huge, -math.huge, -math.huge)
	local cs
	if part.Shape == "PartType.Cylinder" then
		-- exact-ish: sample circle points on both caps
		cs = {}
		local hx, r = part.Size.X / 2, part.Size.Y / 2
		for _, sx in { -1, 1 } do
			for i = 0, 31 do
				local a = i / 32 * math.pi * 2
				table.insert(cs, part.CFrame * vec(sx * hx, r * cos(a), r * sin(a)))
			end
		end
	else
		cs = corners(part)
	end
	for _, c in cs do
		lo = vec(math.min(lo.X, c.X), math.min(lo.Y, c.Y), math.min(lo.Z, c.Z))
		hi = vec(math.max(hi.X, c.X), math.max(hi.Y, c.Y), math.max(hi.Z, c.Z))
	end
	return lo, hi
end

print("[Models]")
local KNOWN_SHAPES = {}
for _, landmark in Landmarks.List do
	KNOWN_SHAPES[landmark.Shape] = true
end
test("SHAPES covers every Landmarks shape", function()
	local n = 0
	for shape in KNOWN_SHAPES do
		n += 1
		assert(Models.SHAPES[shape], "missing " .. shape)
	end
	local m = 0
	for _ in Models.SHAPES do
		m += 1
	end
	assert(m >= n, "SHAPES size")
end)

local stats = {}
local dump = {}
for _, landmark in Landmarks.List do
	test("build " .. landmark.Id .. " (" .. landmark.Shape .. ")", function()
		local before = #violations
		local model = Models.build(landmark)
		eq(model.Name, landmark.Id, "Name")
		eq(#warnings, 0, "warnings: " .. tostring(warnings[1]))
		local root = model.PrimaryPart
		assert(root and root.Name == "Root", "Root PrimaryPart")
		eq(root.Transparency, 1, "Root transparency")
		near(root.Size.X, 10, 1e-9, "Root X")
		near(root.Size.Y, 0.2, 1e-9, "Root Y")
		near(root.CFrame.Position.Y, 0.1, 1e-9, "Root Y pos")
		near(model:GetPivot().Position.Y, 0, 1e-9, "pivot at bottom")
		local list = parts(model)
		local count = #list - 1
		assert(count <= 45, "too many parts: " .. count)
		local lo, hi = vec(math.huge, math.huge, math.huge), vec(-math.huge, -math.huge, -math.huge)
		local minVisibleY = math.huge
		local items = {}
		for _, part in list do
			assert(part.Anchored == true, "not anchored")
			assert(part.CanCollide == false, "collides")
			assert(part.Color ~= nil, "no color")
			local l, h = worldBounds(part)
			if part ~= root then
				lo = vec(math.min(lo.X, l.X), math.min(lo.Y, l.Y), math.min(lo.Z, l.Z))
				hi = vec(math.max(hi.X, h.X), math.max(hi.Y, h.Y), math.max(hi.Z, h.Z))
				minVisibleY = math.min(minVisibleY, l.Y)
				local cf = part.CFrame
				table.insert(
					items,
					string.format(
						'{"c":"%s","s":"%s","p":[%.4f,%.4f,%.4f],"m":[%s],"z":[%.4f,%.4f,%.4f],"col":[%.4f,%.4f,%.4f],"t":%.3f,"mat":"%s"}',
						part.ClassName,
						part.Shape,
						cf.p.X,
						cf.p.Y,
						cf.p.Z,
						table.concat(
							(function()
								local t = {}
								for i = 1, 9 do
									t[i] = string.format("%.6f", cf.m[i])
								end
								return t
							end)(),
							","
						),
						part.Size.X,
						part.Size.Y,
						part.Size.Z,
						part.Color.R,
						part.Color.G,
						part.Color.B,
						part.Transparency,
						part.Material
					)
				)
			end
		end
		table.insert(dump, string.format('{"id":"%s","shape":"%s","parts":[%s]}', landmark.Id, landmark.Shape, table.concat(items, ",")))
		table.insert(
			stats,
			string.format(
				"  %-12s %-11s parts=%2d  x[%.2f,%.2f] z[%.2f,%.2f] y[%.2f,%.2f]",
				landmark.Id,
				landmark.Shape,
				count,
				lo.X,
				hi.X,
				lo.Z,
				hi.Z,
				lo.Y,
				hi.Y
			)
		)
		local tol = 0.051
		assert(lo.X >= -5 - tol and hi.X <= 5 + tol, string.format("x out of footprint [%.3f, %.3f]", lo.X, hi.X))
		assert(lo.Z >= -5 - tol and hi.Z <= 5 + tol, string.format("z out of footprint [%.3f, %.3f]", lo.Z, hi.Z))
		assert(lo.Y >= -0.01, string.format("below ground %.3f", lo.Y))
		assert(hi.Y <= 22.001, string.format("too tall %.3f", hi.Y))
		if landmark.Shape == "skyisland" then
			assert(minVisibleY >= 0.5, string.format("skyisland touches ground %.3f", minVisibleY))
		end
		eq(#violations, before, "violations: " .. tostring(violations[before + 1]))
	end)
end

test("create: scaled to size, pivot at bottom-center, anchored", function()
	for _, landmark in Landmarks.List do
		local model = Models.create(landmark, 9)
		eq(model.Parent, nil, "unparented")
		eq(model.Name, landmark.Id)
		local pivot = model:GetPivot()
		near(pivot.Position.Magnitude, 0, 1e-6, landmark.Id .. " pivot")
		local cf, size = model:GetBoundingBox()
		near(math.max(size.X, size.Z), 9, 1e-6, landmark.Id .. " width")
		assert(size.Y <= 9 * 2.2 + 1e-6, "height cap")
		near(cf.Position.Y - size.Y / 2, 0, 1e-6, landmark.Id .. " bottom at pivot")
		for _, part in parts(model) do
			assert(part.Anchored and not part.CanCollide, "anchored/collide")
		end
	end
end)

test("create: Anchored=false flags", function()
	local model = Models.create(Landmarks.ById.eiffel, 2.4, { Anchored = false })
	for _, part in parts(model) do
		assert(part.Anchored == false and part.Massless == true, "anchored/massless")
		assert(not part.CanCollide and not part.CanQuery and not part.CanTouch, "collide/query/touch")
	end
	near(model:GetPivot().Position.Magnitude, 0, 1e-6, "pivot")
end)

test("create: override model (with PrimaryPart, offset, tall) is cloned, pivoted, height-capped", function()
	local folder = newInstance("Folder")
	folder.Name = "LandmarkModels"
	folder.Parent = ReplicatedStorage
	local src = newInstance("Model")
	src.Name = "pisa"
	local a = newInstance("MeshPart")
	a.Size = vec(2, 30, 2)
	a.CFrame = CFrame.new(100, 50, -20)
	a.Parent = src
	local b = newInstance("Part")
	b.Size = vec(4, 1, 1)
	b.CFrame = CFrame.new(101, 36, -20)
	b.Parent = src
	src.PrimaryPart = b
	src.Parent = folder
	local model = Models.create(Landmarks.ById.pisa, 5)
	assert(model ~= src, "must be a clone")
	eq(model.Name, "pisa")
	local cf, size = model:GetBoundingBox()
	near(size.Y, 11, 1e-6, "height capped at 2.2*size")
	local pivot = model:GetPivot()
	near(pivot.Position.Y, cf.Position.Y - size.Y / 2, 1e-6, "pivot at bottom")
	near(pivot.Position.X, cf.Position.X, 1e-6, "pivot at center X")
	-- source untouched
	near(src:GetBoundingBox().Position.Y, 50, 1e-6, "source unchanged")
	-- override without PrimaryPart, wide
	local src2 = newInstance("Model")
	src2.Name = "arc"
	local c = newInstance("Part")
	c.Size = vec(20, 4, 10)
	c.CFrame = CFrame.new(0, 10, 0)
	c.Parent = src2
	src2.Parent = folder
	local m2 = Models.create(Landmarks.ById.arc, 5, { Anchored = false })
	local _, s2 = m2:GetBoundingBox()
	near(s2.X, 5, 1e-6, "width")
	near(m2:GetPivot().Position.Y, 8, 1e-6, "pivot at bottom (no PrimaryPart)")
	for _, part in parts(m2) do
		assert(part.Anchored == false and part.CanTouch == false, "loose flags")
	end
	-- empty override falls back to build
	local src3 = newInstance("Model")
	src3.Name = "moai"
	src3.Parent = folder
	local m3 = Models.create(Landmarks.ById.moai, 5)
	assert(m3.PrimaryPart and m3.PrimaryPart.Name == "Root", "fallback to build")
	folder.Parent = nil
end)

test("unknown shape -> fallback, never errors", function()
	local fake = table.clone(Landmarks.ById.eiffel)
	fake.Id = "mystery"
	fake.Shape = "nope"
	local model = Models.create(fake, 4)
	assert(#parts(model) >= 3, "fallback parts")
end)

print("\n[stats]")
for _, line in stats do
	print(line)
end
if #violations > 0 then
	print("violations:", violations[1])
end
Harness.finish()
print("DUMP_BEGIN")
print("[" .. table.concat(dump, ",") .. "]")
print("DUMP_END")
