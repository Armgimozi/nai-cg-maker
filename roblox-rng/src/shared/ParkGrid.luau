--!strict
-- 공원 부지 전시 격자(순수 계산: 숫자만) + 3D 배치 모드 규칙. 서버(ParkService: 받침대 자리)와
-- 클라이언트(ParkEdit: 칸 찾기·집어서 옮기기)가 같이 씀. Instance/Vector3 를 쓰지 않아서 테스트에서 바로 돌림.
--
-- 부지 좌표: 부지 중앙 바닥이 원점, -Z = 입구(광장 쪽), +X = 부지 CFrame 의 RightVector (ParkLayout 과 같음).
-- 칸 번호 -> 격자 자리는 PlayerState.slotCell (입구 쪽 줄부터, 한 줄 안에서는 가운데에 가까운 칸부터).
-- 입구에서 공원 안쪽(+Z)을 보면 오른쪽이 -X 라서 slotCell 의 열 1(왼쪽 끝)이 x 가 가장 큰 열.

local Config = require(script.Parent.Config)
local Landmarks = require(script.Parent.Landmarks)
local PlayerState = require(script.Parent.PlayerState)

type Snapshot = PlayerState.Snapshot

local ParkGrid = {}

ParkGrid.GRID = Config.PARK_GRID
ParkGrid.SPACING = 12 -- 칸 가운데 사이 거리(스터드)
ParkGrid.FRONT_MARGIN = 6 -- 입구와 첫 줄 사이 빈 공간
-- 부지 크기(둘레 띠 제외). 서버 ParkLayout.PLOT_WIDTH/PLOT_DEPTH 와 같아야 함(테스트가 확인)
ParkGrid.PLOT_WIDTH = 76
ParkGrid.PLOT_DEPTH = 80
ParkGrid.BASE_TOP = 0.6 -- 부지 윗면 높이
ParkGrid.PEDESTAL_SIZE = 10
ParkGrid.PEDESTAL_HEIGHT = 0.6
ParkGrid.MINIATURE_SIZE = 9
-- 칸 찾기 기본 반지름: 칸 한 변(12)의 네 귀퉁이(가운데에서 8.5)까지 덮음 = 격자 안 어디를 가리켜도 가장 가까운 칸
ParkGrid.SNAP_RADIUS = ParkGrid.SPACING * 0.75

-- 월드 칸 모델(ParkService 가 만드는 Slots 폴더의 칸 Model) 속성 `Look` 값: 명소 Id 이거나 아래 둘 중 하나
-- (명소 Id 는 '#' 으로 시작하지 않음)
ParkGrid.LOOK_LOCKED = "#locked"
ParkGrid.LOOK_EMPTY = "#empty"

local GRID = ParkGrid.GRID
local MIDDLE = (GRID + 1) / 2
local FIRST_ROW_Z = -ParkGrid.PLOT_DEPTH / 2 + ParkGrid.FRONT_MARGIN + ParkGrid.SPACING / 2

-- 칸 가운데(부지 좌표)와 격자 자리 -> 칸 번호
local OFFSETS: { { number } } = {}
local SLOT_BY_CELL: { [number]: number } = {} -- row * 100 + column -> 칸 번호
for slot = 1, GRID * GRID do
	local row, column = PlayerState.slotCell(slot)
	OFFSETS[slot] = { (MIDDLE - column) * ParkGrid.SPACING, FIRST_ROW_Z + (row - 1) * ParkGrid.SPACING }
	SLOT_BY_CELL[row * 100 + column] = slot
end

-- 칸 가운데(부지 좌표 x, z). 받침대 바닥 = 부지 윗면(y = BASE_TOP)
function ParkGrid.slotOffset(slot: number): (number, number)
	local offset = OFFSETS[slot]
	return offset[1], offset[2]
end

-- 부지 좌표 (x, z) 에서 가장 가까운 칸. 그 칸 가운데까지 radius(기본 SNAP_RADIUS)보다 멀면 nil
function ParkGrid.slotAt(x: number, z: number, radius: number?): number?
	if x ~= x or z ~= z then
		return nil
	end
	local column = math.clamp(math.floor(MIDDLE - x / ParkGrid.SPACING + 0.5), 1, GRID)
	local row = math.clamp(math.floor((z - FIRST_ROW_Z) / ParkGrid.SPACING + 1.5), 1, GRID)
	local slot = SLOT_BY_CELL[row * 100 + column]
	local sx, sz = ParkGrid.slotOffset(slot)
	local limit = radius or ParkGrid.SNAP_RADIUS
	if (x - sx) ^ 2 + (z - sz) ^ 2 > limit * limit then
		return nil
	end
	return slot
end

-- 부지 좌표 (x, z) 가 부지 바닥(+ 둘레 margin) 안인지
function ParkGrid.onPlot(x: number, z: number, margin: number?): boolean
	local pad = margin or 0
	return math.abs(x) <= ParkGrid.PLOT_WIDTH / 2 + pad and math.abs(z) <= ParkGrid.PLOT_DEPTH / 2 + pad
end

-- 칸의 지금 모습: "#locked" / "#empty" / 명소 Id (월드 칸 모델의 Look 속성과 같은 값)
function ParkGrid.look(state: Snapshot, slot: number): string
	local slots, unlocked = PlayerState.parkSlots(state)
	if slot > unlocked then
		return ParkGrid.LOOK_LOCKED
	end
	return slots[slot] or ParkGrid.LOOK_EMPTY
end

-- 명소가 전시된 칸(0 = 전시 안 됨)
function ParkGrid.slotOf(state: Snapshot, id: string): number
	local slots, unlocked = PlayerState.parkSlots(state)
	for slot = 1, unlocked do
		if slots[slot] == id then
			return slot
		end
	end
	return 0
end

-- 보관함(배치 모드 아래 띠): 가졌지만 전시 안 된 명소, 희귀한 순서
function ParkGrid.storage(state: Snapshot): { string }
	local slots, unlocked = PlayerState.parkSlots(state)
	local shown: { [string]: boolean } = {}
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			shown[id] = true
		end
	end
	local result = {}
	for _, landmark in Landmarks.RarestFirst do
		if (state.Inventory[landmark.Id] or 0) > 0 and not shown[landmark.Id] then
			table.insert(result, landmark.Id)
		end
	end
	return result
end

-- 놓기 계획: 들고 있는 명소(heldId)를 칸 target 에 놓을 때 할 일. 옮기는 명소가 지금 있는 칸(From, 0 = 보관함)은
-- 화면 상태에서 다시 셈(들고 있는 사이 자동 굴림으로 자리가 밀렸을 수 있음).
--   Kind "locked" = 잠긴 칸(알림만), "cancel" = 제자리(내려놓기 취소),
--   "move" = 빈 칸으로 옮김, "swap" = 명소가 있는 칸과 자리 바꿈(Partner 가 From 칸으로 감),
--   "place" = 보관함에서 빈 칸에, "replace" = 보관함에서 명소가 있는 칸에(Partner 는 보관함으로).
-- Expected / ExpectedFrom 은 그대로 SetDisplay(Slot, Id, Expected, ExpectedFrom) 로 보냄(서버가 stale 확인)
export type DropPlan = {
	Kind: string,
	Slot: number,
	Id: string,
	From: number,
	Expected: string,
	Partner: string?,
}

function ParkGrid.dropPlan(state: Snapshot, heldId: string, target: number): DropPlan
	local slots, unlocked = PlayerState.parkSlots(state)
	local from = ParkGrid.slotOf(state, heldId)
	local plan: DropPlan = { Kind = "cancel", Slot = target, Id = heldId, From = from, Expected = "", Partner = nil }
	if target < 1 or target > unlocked then
		plan.Kind = if target >= 1 and target <= PlayerState.MAX_SLOTS then "locked" else "cancel"
		return plan
	end
	local occupant = slots[target]
	plan.Expected = occupant or ""
	if occupant == heldId then
		return plan -- 제자리
	end
	plan.Partner = occupant
	if from > 0 then
		plan.Kind = if occupant then "swap" else "move"
	else
		plan.Kind = if occupant then "replace" else "place"
	end
	return plan
end

-- 보관함에서 집은 명소가 처음 떠 있을 칸: 첫 빈 열린 칸, 없으면(공원 꽉 참) 전시 칸 중 수입이 가장 적은 명소의 칸
-- (PlayerState.betterHidden 이 견주는 명소 — 바꿔 넣으면 수입이 느는 자리, 같으면 앞 번호), 그것도 없으면 1.
-- 칸 번호가 작을수록 입구 쪽 앞줄이라 휴대폰의 좁은 위에서 보기에서도 화면 안(예전엔 부지 가운데 = 화면 위 끝 밖)
function ParkGrid.storageStart(state: Snapshot): number
	local slots, unlocked = PlayerState.parkSlots(state)
	local weakestSlot, weakest = 0, math.huge
	for slot = 1, unlocked do
		local id = slots[slot]
		if not id then
			return slot
		end
		local landmark = Landmarks.ById[id]
		local income = if landmark then PlayerState.landmarkIncome(landmark, state.Inventory[id] or 0) else 0
		if income < weakest then
			weakestSlot, weakest = slot, income
		end
	end
	return if weakestSlot > 0 then weakestSlot else 1
end

-- 보관(들고 있는 전시 명소를 보관함으로): SetDisplay(Slot, nil, Expected). 보관함에서 집은 것이면 nil
function ParkGrid.storePlan(state: Snapshot, heldId: string): { Slot: number, Expected: string }?
	local from = ParkGrid.slotOf(state, heldId)
	if from == 0 then
		return nil
	end
	return { Slot = from, Expected = heldId }
end

-- 위에서 보기 카메라 ----------------------------------------------------------------
-- 입구(-Z) 쪽 위에서 공원 안쪽(+Z)을 TOP_PITCH 각도로 내려다보는 카메라. 격자 앞 Rows 줄(열린 칸이 있는 줄 + 잠긴 줄
-- 하나: 어디가 늘어날지 보이게, ParkGrid.topRows)이 화면에서 HUD 가 가리지 않은 영역 안에 가장 크게 들어오는 거리와
-- 바라보는 곳(부지 좌표)을 찾음. 칸이 적을 때(휴대폰에서 특히) 명소가 작게 보이지 않게 쓰는 줄만 맞춤.
-- 받침대 네 귀퉁이와 명소 꼭대기(TOP_FIT_HEIGHT)까지 넣어서 뒷줄 명소가 화면 위로 잘리지 않게 함.
ParkGrid.TOP_PITCH = math.rad(55)
ParkGrid.TOP_FIT_HEIGHT = 12 -- 명소 꼭대기(받침대 윗면 위) — 큰 모형(최대 약 20)은 조금 잘려도 받침대는 보이게
ParkGrid.TOP_MIN_DISTANCE = 30
ParkGrid.TOP_MAX_DISTANCE = 500

export type TopView = {
	Eye: { number }, -- 부지 좌표 { x, y, z }
	Target: { number },
	Distance: number,
}

-- view: Aspect(가로/세로), Fov(세로 시야각, 도), Left/Right/Top/Bottom(화면 가장자리에서 가리는 비율 0..1),
-- Rows(맞출 앞 줄 수 1..GRID, 기본 GRID), Zoom(1 = 딱 맞게, 클수록 멀리)
export type TopViewInput = {
	Aspect: number,
	Fov: number,
	Left: number?,
	Right: number?,
	Top: number?,
	Bottom: number?,
	Rows: number?,
	Zoom: number?,
}

-- 앞 rows 줄을 맞출 때 화면에 넣을 점(부지 좌표 { x, y, z }): 받침대 네 귀퉁이 + 앞·뒷줄 양끝 명소 꼭대기
local fitCache: { [number]: { { number } } } = {}
function ParkGrid.topFitPoints(rows: number?): { { number } }
	local count = math.clamp(math.floor(rows or GRID), 1, GRID)
	local cached = fitCache[count]
	if cached then
		return cached
	end
	local points: { { number } } = {}
	local edge = (GRID - 1) / 2 * ParkGrid.SPACING + ParkGrid.PEDESTAL_SIZE / 2
	local front = FIRST_ROW_Z - ParkGrid.PEDESTAL_SIZE / 2
	local back = FIRST_ROW_Z + (count - 1) * ParkGrid.SPACING
	local tall = ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT + ParkGrid.TOP_FIT_HEIGHT
	for _, x in { -edge, edge } do
		table.insert(points, { x, ParkGrid.BASE_TOP, front })
		table.insert(points, { x, ParkGrid.BASE_TOP, back + ParkGrid.PEDESTAL_SIZE / 2 })
	end
	-- 명소 꼭대기는 받침대 바깥 끝(edge)까지: 카메라에 가까운 앞줄 양끝 명소가 원근 때문에 화면 옆으로 삐져나가지 않게
	for _, x in { -edge, edge } do
		table.insert(points, { x, tall, FIRST_ROW_Z })
		table.insert(points, { x, tall, back })
	end
	fitCache[count] = points
	return points
end

-- 위에서 보기에서 맞출 줄 수: 열린 칸이 있는 줄 + 잠긴 줄 하나(공원 확장으로 어디가 늘어날지), 최대 GRID
function ParkGrid.topRows(unlocked: number): number
	return math.clamp(math.ceil(math.max(unlocked, 0) / GRID) + 1, 1, GRID)
end

-- 카메라(바라보는 곳 target, 거리 d)로 본 점의 화면 위치(-1..1, 오른쪽·위가 +). 카메라 뒤면 nil
-- 카메라 오른쪽 = 부지 -X (입구에서 안쪽을 볼 때 오른쪽), 위 = 화면 위
function ParkGrid.project(
	point: { number },
	targetX: number,
	targetZ: number,
	distance: number,
	aspect: number,
	fov: number
): (number?, number?)
	local s, c = math.sin(ParkGrid.TOP_PITCH), math.cos(ParkGrid.TOP_PITCH)
	local vx = point[1] - targetX
	local vy = point[2] - (ParkGrid.BASE_TOP + s * distance)
	local vz = point[3] - (targetZ - c * distance)
	local depth = -vy * s + vz * c
	if depth <= 0.1 then
		return nil, nil
	end
	local t = math.tan(math.rad(fov) / 2)
	return -vx / (depth * t * aspect), (vy * c + vz * s) / (depth * t)
end

function ParkGrid.topView(view: TopViewInput): TopView
	local aspect = math.max(view.Aspect, 0.2)
	local fov = math.clamp(view.Fov, 20, 110)
	-- 보이는 영역(-1..1). 가리는 비율이 너무 커도 화면의 10% 는 남김
	local left = -1 + 2 * math.clamp(view.Left or 0, 0, 0.45)
	local right = 1 - 2 * math.clamp(view.Right or 0, 0, 0.45)
	local bottom = -1 + 2 * math.clamp(view.Bottom or 0, 0, 0.45)
	local top = 1 - 2 * math.clamp(view.Top or 0, 0, 0.45)
	local wantX, wantY = (left + right) / 2, (bottom + top) / 2
	local t = math.tan(math.rad(fov) / 2)
	local s = math.sin(ParkGrid.TOP_PITCH)
	local points = ParkGrid.topFitPoints(view.Rows)
	local rows = math.clamp(math.floor(view.Rows or GRID), 1, GRID)

	-- 거리 d 에서 격자 가운데가 영역 가운데에 오게 바라보는 곳을 옮기고(원근 때문에 몇 번 되풀이), 격자 범위를 돌려줌
	local function aim(distance: number): (number, number, number, number, boolean)
		local tx, tz = 0, FIRST_ROW_Z + (rows - 1) * ParkGrid.SPACING / 2
		local width, height, ok = 0, 0, true
		for _ = 1, 8 do
			local minX, maxX, minY, maxY = math.huge, -math.huge, math.huge, -math.huge
			ok = true
			for _, point in points do
				local x, y = ParkGrid.project(point, tx, tz, distance, aspect, fov)
				if not x or not y then
					ok = false
					break
				end
				minX, maxX = math.min(minX, x), math.max(maxX, x)
				minY, maxY = math.min(minY, y), math.max(maxY, y)
			end
			if not ok then
				break
			end
			width, height = maxX - minX, maxY - minY
			-- 카메라를 +X 로 옮기면 화면에서 점들이 오른쪽(+)으로, +Z 로 옮기면 아래(-)로 감
			tx += (wantX - (minX + maxX) / 2) * distance * t * aspect
			tz -= (wantY - (minY + maxY) / 2) * distance * t / s
		end
		return tx, tz, width, height, ok
	end

	local low, high = ParkGrid.TOP_MIN_DISTANCE, ParkGrid.TOP_MAX_DISTANCE
	for _ = 1, 30 do
		local middle = (low + high) / 2
		local _, _, width, height, ok = aim(middle)
		if ok and width <= right - left and height <= top - bottom then
			high = middle
		else
			low = middle
		end
	end
	local distance = math.clamp(high * (view.Zoom or 1), ParkGrid.TOP_MIN_DISTANCE, ParkGrid.TOP_MAX_DISTANCE)
	local tx, tz = aim(distance)
	local c = math.cos(ParkGrid.TOP_PITCH)
	return {
		Eye = { tx, ParkGrid.BASE_TOP + s * distance, tz - c * distance },
		Target = { tx, ParkGrid.BASE_TOP, tz },
		Distance = distance,
	}
end

-- 위에서 보기 배율(Zoom, 1 = 맞출 줄이 딱 맞음, 클수록 멀리) 범위와 휠 한 칸
ParkGrid.ZOOM_MIN, ParkGrid.ZOOM_MAX, ParkGrid.ZOOM_STEP = 0.8, 1.45, 0.08

-- 두 손가락 벌리기/모으기: 손가락을 댔을 때 배율 startZoom · 손가락 사이 거리 startDistance(px) 에서 지금 거리
-- distance 가 되면 새 배율(벌리면 가까이 = 작아짐, 범위 안으로)
function ParkGrid.pinchZoom(startZoom: number, startDistance: number, distance: number): number
	if startDistance <= 0 or distance <= 0 or startDistance ~= startDistance or distance ~= distance then
		return math.clamp(startZoom, ParkGrid.ZOOM_MIN, ParkGrid.ZOOM_MAX)
	end
	return math.clamp(startZoom * startDistance / distance, ParkGrid.ZOOM_MIN, ParkGrid.ZOOM_MAX)
end

-- 자동 배치를 켜면 지금 배치가 바뀌는지 (바뀌면 [자동] 을 한 번 더 눌러 "확인?")
function ParkGrid.autoWouldChange(state: Snapshot): boolean
	local slots, unlocked = PlayerState.parkSlots(state)
	local auto = table.clone(state) :: any
	auto.Settings = table.clone(state.Settings)
	auto.Settings.AutoPark = true
	local best = PlayerState.parkSlots(auto)
	for slot = 1, unlocked do
		if slots[slot] ~= best[slot] then
			return true
		end
	end
	return false
end

-- 스냅샷 사본(배치에 필요한 표만 새로)에 편집을 적용해서 돌려줌(미리 보기). edit 가 false 면 nil
function ParkGrid.preview(state: Snapshot, edit: (any) -> boolean): Snapshot?
	local copy = table.clone(state) :: any
	copy.Settings = table.clone(state.Settings)
	copy.Display = table.clone((state :: any).Display or {})
	if not edit(copy) then
		return nil
	end
	copy.Income = PlayerState.incomePerSecond(copy, copy)
	return copy
end

return ParkGrid
