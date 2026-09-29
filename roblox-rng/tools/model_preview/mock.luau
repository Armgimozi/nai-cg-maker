-- Roblox 밖에서 Models(명소 모형) 를 만들어 검사하는 가짜 Roblox 환경.
-- 모든 명소를 build/create 해서 규칙(바닥 10x10, 높이 22, 파트 수 등)을 검사하고, 마지막에 파트 목록(JSON)을 출력.
-- 보통은 tools/model_preview/preview.sh 로 실행합니다.
local SCRATCH = ARGS[1]
local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()

-- 가짜 Roblox 환경은 tools/roblox_mock.luau (맵 미리보기와 같이 씀). 여기서는 모르는 속성을 쓰면 오류(strict).
local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()
Mock.strict = true

local sin, cos = math.sin, math.cos
local vec, newInstance, corners = Mock.vec, Mock.newInstance, Mock.corners
local violations, warnings = Mock.violations, Mock.warnings
local ReplicatedStorage = Mock.ReplicatedStorage

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
		table.insert(
			dump,
			string.format(
				'{"id":"%s","shape":"%s","parts":[%s]}',
				landmark.Id,
				landmark.Shape,
				table.concat(items, ",")
			)
		)
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
