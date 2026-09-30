-- ViewportFrame 에 명소 모형을 띄우는 헬퍼.
-- 정적인 썸네일(도감 카드)은 한 번 찍고 끝(매 프레임 작업 없음),
-- 회전이 필요한 화면(굴림 연출)만 setSpin 으로 등록해서 RenderStepped 루프 하나로 돌립니다.

local RunService = game:GetService("RunService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Landmarks = require(Shared.Landmarks)
local Models = require(Shared:WaitForChild("Models"))

local Ui = require(script.Parent.Ui)

local FIELD_OF_VIEW = 30 -- 세로 시야각(도). 좁을수록 원근 왜곡이 적어 미니어처처럼 보임
local YAW = math.rad(35) -- 정면(-Z)에서 오른쪽으로 돌아간 각도 (3/4 시점)
local PITCH = math.rad(22) -- 내려다보는 각도
local MARGIN = 1.04

-- 모형 틀 정보는 ViewportFrame 의 속성(Attribute)에 저장 → 모듈 쪽에 따로 들고 있을 필요가 없어서
-- 카드가 Destroy 되어도 정리할 것이 없음
local ATTR_HEIGHT_CENTER = "ViewCenterY"
local ATTR_FLAT = "ViewFlat"
local ATTR_HALF_HEIGHT = "ViewHalfHeight"

local Viewport = {}

type SpinEntry = { Speed: number, Angle: number }

-- 회전 중인 화면들. 부모가 사라지면(Destroy) 루프에서 알아서 빠짐
local spinning: { [ViewportFrame]: SpinEntry } = {}
local spinConnection: RBXScriptConnection? = nil

local function currentModel(vf: ViewportFrame): Model?
	return vf:FindFirstChildOfClass("Model")
end

-- 저장해 둔 틀 정보로 카메라 위치를 정함 (화면 비율이 바뀌면 다시 호출)
local function frameCamera(vf: ViewportFrame)
	local camera = vf.CurrentCamera
	local centerY = vf:GetAttribute(ATTR_HEIGHT_CENTER)
	local flat = vf:GetAttribute(ATTR_FLAT)
	local halfHeight = vf:GetAttribute(ATTR_HALF_HEIGHT)
	if not camera or type(centerY) ~= "number" or type(flat) ~= "number" or type(halfHeight) ~= "number" then
		return
	end

	local absolute = vf.AbsoluteSize
	local aspect = if absolute.X > 0 and absolute.Y > 0 then absolute.X / absolute.Y else 1
	local tanV = math.tan(math.rad(camera.FieldOfView / 2))
	local tanH = tanV * aspect

	-- 화면에 비치는 대략적인 반높이/반너비. 가로는 회전해도 넘지 않도록 수직축에서 가장 먼 모서리 기준
	local projectedHalfHeight = halfHeight * math.cos(PITCH) + flat * math.sin(PITCH)
	local distance = math.max(projectedHalfHeight / tanV + flat * 0.5, flat / tanH + flat) * MARGIN

	local target = Vector3.new(0, centerY, 0)
	local direction = Vector3.new(math.sin(YAW) * math.cos(PITCH), math.sin(PITCH), -math.cos(YAW) * math.cos(PITCH))
	camera.CFrame = CFrame.lookAt(target + direction * distance, target)
end

-- 새 ViewportFrame (카메라·조명 포함). props 로 Size/Position 등을 덮어씀
function Viewport.new(parent: Instance?, props: { [string]: any }?): ViewportFrame
	local vf = Ui.new("ViewportFrame", {
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Size = UDim2.fromScale(1, 1),
		Ambient = Color3.fromRGB(165, 165, 180),
		LightColor = Color3.fromRGB(255, 248, 235),
		-- 빛이 나아가는 방향. 카메라와 같은 쪽(앞·위·오른쪽)에서 비추도록
		LightDirection = Vector3.new(-0.6, -1, 0.8),
	})
	for key, value in props or {} do
		if key ~= "Parent" then
			(vf :: any)[key] = value
		end
	end

	local camera = Ui.new("Camera", { FieldOfView = FIELD_OF_VIEW, Parent = vf })
	vf.CurrentCamera = camera

	vf:GetPropertyChangedSignal("AbsoluteSize"):Connect(function()
		frameCamera(vf)
	end)

	vf.Parent = parent
	return vf
end

-- 모형을 화면에 올림. 이전 모형은 지움. 모형 피벗(바닥 중앙)을 원점에 놓고 3/4 각도로 카메라를 맞춤
function Viewport.setModel(vf: ViewportFrame, model: Model?)
	for _, child in vf:GetChildren() do
		if child:IsA("Model") and child ~= model then
			child:Destroy()
		end
	end
	if not model then
		vf:SetAttribute(ATTR_HEIGHT_CENTER, nil)
		return
	end

	local entry = spinning[vf]
	model:PivotTo(CFrame.Angles(0, if entry then entry.Angle else 0, 0))
	model.Parent = vf

	local ok, boxCFrame, size = pcall(function()
		return model:GetBoundingBox()
	end)
	if not ok then
		return
	end
	-- 회전축(피벗, 원점)에서 가장 먼 모서리까지의 가로 거리
	local center = boxCFrame.Position
	local reachX = math.abs(center.X) + size.X / 2
	local reachZ = math.abs(center.Z) + size.Z / 2
	vf:SetAttribute(ATTR_HEIGHT_CENTER, center.Y)
	vf:SetAttribute(ATTR_FLAT, math.max(0.5, math.sqrt(reachX * reachX + reachZ * reachZ)))
	vf:SetAttribute(ATTR_HALF_HEIGHT, math.max(0.5, size.Y / 2))
	frameCamera(vf)
end

-- 명소 모형을 만들어 올림. 모형을 못 만들면 false (화면은 비워 둠)
function Viewport.setLandmark(vf: ViewportFrame, landmark: Landmarks.Landmark, size: number?): boolean
	local ok, model = pcall(Models.create, landmark, size or 10)
	if not ok or typeof(model) ~= "Instance" or not model:IsA("Model") then
		warn("[LandmarkRNG] 모형을 만들지 못했어요 (" .. landmark.Id .. "): " .. tostring(model))
		Viewport.setModel(vf, nil)
		return false
	end
	Viewport.setModel(vf, model)
	return true
end

-- 카드용 정적 썸네일 (회전 없음)
function Viewport.thumbnail(parent: Instance?, landmark: Landmarks.Landmark, props: { [string]: any }?): ViewportFrame
	local vf = Viewport.new(nil, props)
	Viewport.setLandmark(vf, landmark, 10)
	vf.Parent = parent
	return vf
end

local function step(dt: number)
	for vf, entry in spinning do
		if not vf.Parent then
			spinning[vf] = nil -- Destroy 된 화면
			continue
		end
		local model = currentModel(vf)
		if model then
			entry.Angle = (entry.Angle + math.rad(entry.Speed) * dt) % (2 * math.pi)
			model:PivotTo(CFrame.Angles(0, entry.Angle, 0))
		end
	end
end

-- 초당 degreesPerSecond 도로 수직축 회전. 0 이면 멈춤(현재 각도 유지)
function Viewport.setSpin(vf: ViewportFrame, degreesPerSecond: number)
	if degreesPerSecond == 0 then
		spinning[vf] = nil
		return
	end
	local entry = spinning[vf]
	if entry then
		entry.Speed = degreesPerSecond
	else
		spinning[vf] = { Speed = degreesPerSecond, Angle = 0 }
	end
	if not spinConnection then
		spinConnection = RunService.RenderStepped:Connect(step)
	end
end

return Viewport
