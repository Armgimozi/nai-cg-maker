-- 최소한의 Roblox API 흉내(Vector3/CFrame(이동만)/Instance/game) — ArmorService·ItemService 로직 검증용.

local Vector3mt = {}
local function v3(x, y, z)
	return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, Vector3mt)
end
local function isv(a)
	return type(a) == "table" and getmetatable(a) == Vector3mt
end
Vector3mt.__add = function(a, b)
	return v3(a.X + b.X, a.Y + b.Y, a.Z + b.Z)
end
Vector3mt.__sub = function(a, b)
	return v3(a.X - b.X, a.Y - b.Y, a.Z - b.Z)
end
Vector3mt.__mul = function(a, b)
	if type(a) == "number" then
		a, b = b, a
	end
	if isv(b) then
		return v3(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
	end
	return v3(a.X * b, a.Y * b, a.Z * b)
end
Vector3mt.__div = function(a, b)
	if isv(b) then
		return v3(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
	end
	return v3(a.X / b, a.Y / b, a.Z / b)
end
Vector3mt.__tostring = function(a)
	return string.format("(%.4f, %.4f, %.4f)", a.X, a.Y, a.Z)
end
Vector3 = { new = v3, one = v3(1, 1, 1), zero = v3(0, 0, 0) }

local CFmt = {}
local function cf(p)
	return setmetatable({ Position = p }, CFmt)
end
CFmt.__mul = function(a, b)
	if isv(b) then
		return a.Position + b
	end
	return cf(a.Position + b.Position)
end
CFrame = {
	new = function(x, y, z)
		if isv(x) then
			return cf(x)
		end
		return cf(v3(x, y, z))
	end,
	identity = cf(v3(0, 0, 0)),
}
Color3 = {
	new = function(r, g, b)
		return { R = r, G = g, B = b }
	end,
}
Enum = { HumanoidRigType = { R15 = "R15", R6 = "R6" } }

local BASES = {
	MeshPart = { "BasePart", "PVInstance" },
	Part = { "BasePart", "PVInstance" },
	Model = { "PVInstance" },
	Tool = { "BackpackItem" },
	SpecialMesh = { "DataModelMesh" },
}

local Inst = {}
local methods = {}
Inst.__index = function(t, k)
	local m = methods[k]
	if m then
		return m
	end
	local props = rawget(t, "_props")
	if props[k] ~= nil then
		return props[k]
	end
	for _, c in rawget(t, "_children") do
		if c.Name == k then
			return c
		end
	end
	return nil
end
Inst.__newindex = function(t, k, v)
	local props = rawget(t, "_props")
	if k == "Parent" then
		local old = props.Parent
		if old then
			local ch = rawget(old, "_children")
			for i, c in ch do
				if c == t then
					table.remove(ch, i)
					break
				end
			end
		end
		props.Parent = v
		if v then
			table.insert(rawget(v, "_children"), t)
		end
	else
		props[k] = v
	end
end

local function newInst(cls)
	local o = setmetatable({ _props = { ClassName = cls, Name = cls }, _children = {}, _attrs = {} }, Inst)
	if cls == "Weld" then
		o.C0 = CFrame.identity
		o.C1 = CFrame.identity
	end
	if cls == "Tool" then
		o.Grip = CFrame.identity
	end
	return o
end

function methods:IsA(c)
	if self.ClassName == c or c == "Instance" then
		return true
	end
	for _, b in BASES[self.ClassName] or {} do
		if b == c then
			return true
		end
	end
	return false
end
function methods:GetChildren()
	return table.clone(rawget(self, "_children"))
end
function methods:GetDescendants()
	local out = {}
	local function walk(o)
		for _, c in rawget(o, "_children") do
			table.insert(out, c)
			walk(c)
		end
	end
	walk(self)
	return out
end
function methods:FindFirstChild(name, recursive)
	for _, c in (recursive and self:GetDescendants() or rawget(self, "_children")) do
		if c.Name == name then
			return c
		end
	end
	return nil
end
function methods:FindFirstChildOfClass(cls)
	for _, c in rawget(self, "_children") do
		if c.ClassName == cls then
			return c
		end
	end
	return nil
end
function methods:FindFirstChildWhichIsA(cls, recursive)
	for _, c in (recursive and self:GetDescendants() or rawget(self, "_children")) do
		if c:IsA(cls) then
			return c
		end
	end
	return nil
end
function methods:WaitForChild(name)
	return assert(self:FindFirstChild(name), "WaitForChild 실패: " .. name)
end
function methods:Clone()
	local o = newInst(self.ClassName)
	for k, v in rawget(self, "_props") do
		if k ~= "Parent" then
			rawget(o, "_props")[k] = v
		end
	end
	for k, v in rawget(self, "_attrs") do
		rawget(o, "_attrs")[k] = v
	end
	for _, c in rawget(self, "_children") do
		c:Clone().Parent = o
	end
	return o
end
function methods:Destroy()
	self.Parent = nil
end
function methods:SetAttribute(k, v)
	rawget(self, "_attrs")[k] = v
end
function methods:GetAttribute(k)
	return rawget(self, "_attrs")[k]
end

Instance = { new = newInst }

local services = {}
game = {
	GetService = function(_, name)
		services[name] = services[name] or newInst(name)
		return services[name]
	end,
}

warn = function(...)
	print("  (warn)", ...)
end
