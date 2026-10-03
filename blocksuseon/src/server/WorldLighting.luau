-- 수계 하늘과 빛 (World.setupLighting 갈음). Lune(굽기)과 서버 둘 다에서 돈다.
-- Technology 는 스크립트로 못 바꾸는 속성이라 pcall: Lune 에서는 되고(플레이스 파일에 저장), 서버에서는 조용히 넘어간다.
-- 하나만 있어야 하는 것(Atmosphere, Sky, Bloom...)은 클래스로 찾고, 색보정처럼 여럿 겹치는 것은 이름으로 찾는다
local function ensure(parent: Instance, className: string, name: string, byName: boolean?): Instance
	local found = if byName then parent:FindFirstChild(name) else parent:FindFirstChildOfClass(className)
	if found and found.ClassName == className then
		return found
	end
	local inst = Instance.new(className)
	inst.Name = name
	inst.Parent = parent
	return inst
end

local function setupLighting(lighting: any)
	pcall(function()
		lighting.Technology = Enum.Technology.Future
	end)
	lighting.LightingStyle = Enum.LightingStyle.Realistic
	lighting.PrioritizeLightingQuality = true
	lighting.ClockTime = 15.5
	lighting.GeographicLatitude = 36 -- 한반도 위도: 해가 남쪽 하늘을 지난다
	lighting.Brightness = 2.6
	lighting.ExposureCompensation = 0.1
	lighting.EnvironmentDiffuseScale = 0.6
	lighting.EnvironmentSpecularScale = 0.8
	-- Environment*Scale 을 올리면 Ambient 를 내린다 (하늘빛이 대신 채운다)
	lighting.Ambient = Color3.fromRGB(64, 66, 76)
	lighting.OutdoorAmbient = Color3.fromRGB(118, 120, 132)
	lighting.ColorShift_Top = Color3.fromRGB(255, 244, 228)
	lighting.ColorShift_Bottom = Color3.fromRGB(0, 0, 0)
	lighting.GlobalShadows = true
	lighting.ShadowSoftness = 0.25

	local atmosphere = ensure(lighting, "Atmosphere", "Atmosphere") :: any
	atmosphere.Density = 0.3
	atmosphere.Offset = 0.22 -- 먼 산이 하늘에 묻히지 않고 실루엣으로
	atmosphere.Color = Color3.fromRGB(199, 210, 222)
	atmosphere.Decay = Color3.fromRGB(104, 112, 130)
	atmosphere.Glare = 0.35
	atmosphere.Haze = 1.4

	local sky = ensure(lighting, "Sky", "Sky") :: any
	sky.StarCount = 3000
	sky.SunAngularSize = 14
	sky.MoonAngularSize = 9
	sky.CelestialBodiesShown = true

	local bloom = ensure(lighting, "BloomEffect", "Bloom") :: any
	bloom.Intensity = 0.55
	bloom.Size = 28
	bloom.Threshold = 1.9 -- 햇빛 받은 회벽은 안 번지고 Neon(등롱, 영맥)만 번진다

	local sun = ensure(lighting, "SunRaysEffect", "SunRays") :: any
	sun.Intensity = 0.07
	sun.Spread = 0.7

	-- 기본 색보정 (천겁·맞음 색보정은 클라이언트가 따로 단다: ColorCorrection 은 여러 개가 겹쳐 곱해진다)
	local grade = ensure(lighting, "ColorCorrectionEffect", "기본색보정", true) :: any
	grade.Brightness = 0.02
	grade.Contrast = 0.1
	grade.Saturation = 0.12
	grade.TintColor = Color3.fromRGB(255, 250, 242)

	local dof = ensure(lighting, "DepthOfFieldEffect", "먼데흐림") :: any
	dof.FarIntensity = 0.12
	dof.FocusDistance = 60
	dof.InFocusRadius = 140
	dof.NearIntensity = 0
end
return setupLighting
