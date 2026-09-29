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

-- 보관(들고 있는 전시 명소를 보관함으로): SetDisplay(Slot, nil, Expected). 보관함에서 집은 것이면 nil
function ParkGrid.storePlan(state: Snapshot, heldId: string): { Slot: number, Expected: string }?
	local from = ParkGrid.slotOf(state, heldId)
	if from == 0 then
		return nil
	end
	return { Slot = from, Expected = heldId }
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
