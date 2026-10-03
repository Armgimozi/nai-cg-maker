--!native
-- Terrain.SmoothGrid(v1)와 PhysicsGrid(v2)를 Lune 에서 직접 쓰고 읽는다.
--
-- Lune 에는 Terrain:WriteVoxels 가 없어서, 플레이스 파일에 저장되는 지형 덩어리를 손으로 만든다.
-- 형식은 RBXMonkey(Blender 애드온)의 해독기와 RobloxToolchain 의 docs/terrain-format.md 를 따랐고,
-- Studio 가 저장한 지형 파일을 풀었다가 다시 쌓으면 바이트까지 같다는 것을 확인했다.
--
--   SmoothGrid  0x01 0x05, 그리고 덩어리(32×32×32 칸)마다
--               앞 덩어리와의 좌표 차(부호 있는 int32 셋을 바이트 단위로 엇갈려 12바이트)
--               + 칸 기록(X 가 가장 빠르고 Z, Y 순). 기록 첫 바이트: 아래 6비트 재질,
--               0x40 이면 차오름 바이트가 뒤따름(없으면 255), 0x80 이면 반복 바이트(반복 = 값+1)
--   PhysicsGrid 0x02 0x03, 무리 셋(각각 u32 BE 개수 + 12바이트 좌표 차). 첫 무리에는 둘레 한 칸이라도
--               지형에 닿는 8칸 영역을 모두 넣고, 나머지 둘은 비운다.
-- 칸 (x, y, z) 는 월드 [4x, 4x+4) 를 차지한다.

local SmoothGrid = {}

-- 재질 칸 번호
SmoothGrid.SLOT = {
	Air = 0,
	Water = 1,
	Grass = 2,
	Slate = 3,
	Concrete = 4,
	Brick = 5,
	Sand = 6,
	WoodPlanks = 7,
	Rock = 8,
	Glacier = 9,
	Snow = 10,
	Sandstone = 11,
	Mud = 12,
	Basalt = 13,
	Ground = 14,
	CrackedLava = 15,
	Asphalt = 16,
	Cobblestone = 17,
	Ice = 18,
	LeafyGrass = 19,
	Salt = 20,
	Limestone = 21,
	Pavement = 22,
}

SmoothGrid.EDGE = 32 -- 덩어리 한 변의 칸 수
SmoothGrid.CELLS = 32768

export type Chunk = { cx: number, cy: number, cz: number, mat: buffer, occ: buffer }

-- 차오름(0~1) → 바이트. 엔진의 WriteVoxels 와 같은 반올림
function SmoothGrid.occByte(o: number): number
	return math.clamp(math.floor(o * 256 - 0.5), 0, 255)
end

-- 칸 번호 (덩어리 안 좌표)
function SmoothGrid.index(x: number, y: number, z: number): number
	return x + z * 32 + y * 1024
end

local function u32(v: number): number
	return bit32.band(v, 0xffffffff)
end

local function writeDelta(out: { string }, dx: number, dy: number, dz: number)
	dx, dy, dz = u32(dx), u32(dy), u32(dz)
	for _, shift in { 24, 16, 8, 0 } do
		table.insert(
			out,
			string.char(bit32.extract(dx, shift, 8), bit32.extract(dy, shift, 8), bit32.extract(dz, shift, 8))
		)
	end
end

local function readDelta(s: string, offset: number): (number, number, number)
	local c = { 0, 0, 0 }
	for j = 0, 3 do
		for axis = 1, 3 do
			c[axis] = bit32.bor(bit32.lshift(c[axis], 8), string.byte(s, offset + j * 3 + axis))
		end
	end
	for axis = 1, 3 do
		if c[axis] >= 0x80000000 then
			c[axis] -= 0x100000000
		end
	end
	return c[1], c[2], c[3]
end

local function sortChunks(chunks: { Chunk })
	table.sort(chunks, function(a, b)
		if a.cx ~= b.cx then
			return a.cx < b.cx
		end
		if a.cy ~= b.cy then
			return a.cy < b.cy
		end
		return a.cz < b.cz
	end)
end

function SmoothGrid.encode(chunks: { Chunk }): string
	sortChunks(chunks)
	local out = { "\1\5" }
	local px, py, pz = 0, 0, 0
	local record = buffer.create(SmoothGrid.CELLS * 3)
	for _, chunk in chunks do
		writeDelta(out, chunk.cx - px, chunk.cy - py, chunk.cz - pz)
		px, py, pz = chunk.cx, chunk.cy, chunk.cz
		local mat, occ = chunk.mat, chunk.occ
		local i, n = 0, 0
		while i < SmoothGrid.CELLS do
			local m = buffer.readu8(mat, i)
			local o = if m == 0 then 0 else buffer.readu8(occ, i)
			local run = 1
			while i + run < SmoothGrid.CELLS and run < 256 do
				local m2 = buffer.readu8(mat, i + run)
				local o2 = if m2 == 0 then 0 else buffer.readu8(occ, i + run)
				if m2 ~= m or o2 ~= o then
					break
				end
				run += 1
			end
			local lead = m
			local explicit = m ~= 0 and o ~= 255
			if explicit then
				lead = bit32.bor(lead, 0x40)
			end
			if run > 1 then
				lead = bit32.bor(lead, 0x80)
			end
			buffer.writeu8(record, n, lead)
			n += 1
			if explicit then
				buffer.writeu8(record, n, o)
				n += 1
			end
			if run > 1 then
				buffer.writeu8(record, n, run - 1)
				n += 1
			end
			i += run
		end
		table.insert(out, buffer.readstring(record, 0, n))
	end
	return table.concat(out)
end

function SmoothGrid.decode(s: string): { Chunk }
	assert(string.byte(s, 1) == 1 and string.byte(s, 2) == 5, "SmoothGrid v1 (덩어리 32) 가 아니다")
	local offset, chunks = 2, {}
	local px, py, pz = 0, 0, 0
	while offset < #s do
		local dx, dy, dz = readDelta(s, offset)
		offset += 12
		px, py, pz = px + dx, py + dy, pz + dz
		local mat, occ = buffer.create(SmoothGrid.CELLS), buffer.create(SmoothGrid.CELLS)
		local i = 0
		while i < SmoothGrid.CELLS do
			offset += 1
			local lead = string.byte(s, offset)
			local m, o, run = bit32.band(lead, 0x3f), 255, 1
			if bit32.btest(lead, 0x40) then
				offset += 1
				o = string.byte(s, offset)
			end
			if bit32.btest(lead, 0x80) then
				offset += 1
				run = string.byte(s, offset) + 1
			end
			if m == 0 then
				o = 0
			end
			buffer.fill(mat, i, m, run)
			buffer.fill(occ, i, o, run)
			i += run
		end
		assert(i == SmoothGrid.CELLS, "칸 기록이 덩어리를 넘친다")
		table.insert(chunks, { cx = px, cy = py, cz = pz, mat = mat, occ = occ })
	end
	return chunks
end

-- 물리 색인: 둘레 한 칸이라도 지형이 있는 8칸 영역
function SmoothGrid.physicsGrid(chunks: { Chunk }): string
	local seen: { [number]: boolean } = {}
	local list = {}
	local function key(ax: number, ay: number, az: number): number
		-- 영역 좌표는 ±4096 안이다 (맵 ±128k 스터드)
		return ((ax + 4096) * 8192 + (ay + 4096)) * 8192 + (az + 4096)
	end
	for _, chunk in chunks do
		for i = 0, SmoothGrid.CELLS - 1 do
			if buffer.readu8(chunk.mat, i) ~= 0 then
				local x = chunk.cx * 32 + i % 32
				local z = chunk.cz * 32 + (i // 32) % 32
				local y = chunk.cy * 32 + i // 1024
				for ax = (x - 1) // 8, (x + 1) // 8 do
					for ay = (y - 1) // 8, (y + 1) // 8 do
						for az = (z - 1) // 8, (z + 1) // 8 do
							local k = key(ax, ay, az)
							if not seen[k] then
								seen[k] = true
								table.insert(list, { ax, ay, az })
							end
						end
					end
				end
			end
		end
	end
	table.sort(list, function(a, b)
		if a[1] ~= b[1] then
			return a[1] < b[1]
		end
		if a[2] ~= b[2] then
			return a[2] < b[2]
		end
		return a[3] < b[3]
	end)
	local out = { "\2\3", string.pack(">I4", #list) }
	local px, py, pz = 0, 0, 0
	for _, c in list do
		writeDelta(out, c[1] - px, c[2] - py, c[3] - pz)
		px, py, pz = c[1], c[2], c[3]
	end
	table.insert(out, string.pack(">I4>I4", 0, 0))
	return table.concat(out)
end

-- 물리 색인을 푼다 (테스트용). 반환: 무리 셋의 좌표 목록, 끝까지 정확히 읽었는가
function SmoothGrid.decodePhysics(s: string): ({ { { number } } }, boolean)
	local offset = 2
	local groups = {}
	for g = 1, 3 do
		local count = string.unpack(">I4", s, offset + 1)
		offset += 4
		local px, py, pz, list = 0, 0, 0, {}
		for _ = 1, count do
			local dx, dy, dz = readDelta(s, offset)
			offset += 12
			px, py, pz = px + dx, py + dy, pz + dz
			table.insert(list, { px, py, pz })
		end
		groups[g] = list
	end
	return groups, offset == #s
end

return SmoothGrid
