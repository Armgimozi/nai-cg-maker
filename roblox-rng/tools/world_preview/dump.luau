-- 맵 미리보기 덤프: 가짜 Roblox 환경(Workspace/Lighting/Terrain)을 렌더러가 읽는 한 줄 JSON 으로 출력합니다.
-- world.luau(진짜 서버 모듈로 만든 맵)와 test_scene.luau(도구 점검용 작은 장면)가 같이 씁니다.
-- 사용법: local dump = compile(readfile("tools/world_preview/dump.luau"), "tools/world_preview/dump.luau")()
--   dump({ Mock = Mock, Harness = Harness, shared = 공용 모듈 폴더(없어도 됨), note = function(text), notes = {},
--          meta = { ... 보고서에 쓸 값 } })
-- 출력: 표준 출력의 DUMP_BEGIN / JSON 한 줄 / DUMP_END
--   parts  : BasePart 목록(지형 제외). o = 만든 곳(Mock.origin), s = 모양, p/m/z = 위치/회전(행 우선)/크기
--   gui    : SurfaceGui 간판(면 좌표계 + GUI 상자 목록)
--   lighting: 조명 값 + Atmosphere 등
--   terrain: 지형 격자(Mock.terrainDumpJson — roblox_mock.luau 주석 참고) 또는 null
--   hl     : 켜진 Highlight(대상 파트 번호 = parts 순서 0부터, 채우기·테두리 색·투명도, AlwaysOnTop 여부)
--   extra  : ctx.extra(world.luau hook 이 돌려준 표 — 카메라 "Camera" 등) 또는 null
-- 투명도는 이 화면 기준: Transparency 에 LocalTransparencyModifier 를 더함(클라이언트가 이 화면에서만 숨긴 파트)

return function(ctx)
	local Mock = ctx.Mock
	local Harness = ctx.Harness
	local shared = ctx.shared
	local note = ctx.note
	-- 덤프 --------------------------------------------------------------------------------
	local function num(x: number): string
		if x ~= x or x == math.huge or x == -math.huge then
			return "0"
		end
		local s = string.format("%.4f", x)
		s = s:gsub("0+$", ""):gsub("%.$", "")
		if s == "-0" then
			return "0"
		end
		return s
	end
	local function nums(list: { number }): string
		local out = {}
		for i, v in list do
			out[i] = num(v)
		end
		return "[" .. table.concat(out, ",") .. "]"
	end
	local function colorOf(c): string
		return nums({ c.R, c.G, c.B })
	end
	local function str(s: any): string
		return Mock.json.encode(tostring(s))
	end
	local function enumName(value: any): string
		local text = tostring(value)
		return text:match("%.([%w_]+)$") or text
	end

	local function pathOf(instance): string
		local names = {}
		local node = instance
		while node and node ~= Mock.Workspace do
			table.insert(names, 1, node.Name)
			node = node.Parent
		end
		return table.concat(names, "/")
	end

	local function shapeOf(part): (string, boolean)
		local class = part.ClassName
		if class == "WedgePart" then
			return "Wedge", false
		elseif class == "CornerWedgePart" then
			return "CornerWedge", false
		elseif class == "Part" or class == "SpawnLocation" or class == "Seat" then
			return enumName(part.Shape or "PartType.Block"), false
		end
		return "Block", true -- MeshPart, Union, Truss ... 은 상자로 대신 그림
	end

	local partRecords = {}
	local approx = 0
	local function partRecord(
		name: string,
		path: string,
		origin: string,
		class: string,
		shape: string,
		cf,
		size,
		c,
		material: string,
		transparency: number,
		castShadow: boolean,
		canCollide: boolean
	)
		local m = cf.m
		table.insert(
			partRecords,
			string.format(
				'{"n":%s,"path":%s,"o":%s,"c":%s,"s":%s,"p":%s,"m":%s,"z":%s,"col":%s,"mat":%s,"t":%s,"cs":%s,"cc":%s}',
				str(name),
				str(path),
				str(origin),
				str(class),
				str(shape),
				nums({ cf.p.X, cf.p.Y, cf.p.Z }),
				nums(m),
				nums({ size.X, size.Y, size.Z }),
				colorOf(c),
				str(material),
				num(transparency),
				tostring(castShadow),
				tostring(canCollide)
			)
		)
	end

	local parts = {}
	local partIndex: { [any]: number } = {} -- 파트 -> partRecords 번호(0부터, Highlight 가 가리킴)
	for _, d in Mock.Workspace:GetDescendants() do
		if Mock.isBasePart(d) and d.ClassName ~= "Terrain" then
			table.insert(parts, d)
		end
	end
	-- 이 화면에서 보이는 투명도: Transparency 에 LocalTransparencyModifier 를 더함(클라이언트가 이 화면에서만 숨긴 파트)
	local function viewTransparency(part): number
		local t = part.Transparency or 0
		local ok, ltm = pcall(function()
			return part.LocalTransparencyModifier
		end)
		if ok and type(ltm) == "number" and ltm > 0 then
			t = t + (1 - t) * math.clamp(ltm, 0, 1)
		end
		return t
	end
	for _, part in parts do
		local shape, isApprox = shapeOf(part)
		if isApprox then
			approx += 1
		end
		partIndex[part] = #partRecords
		partRecord(
			part.Name,
			pathOf(part),
			rawget(part, "__origin"),
			part.ClassName,
			shape,
			part.CFrame,
			part.Size,
			part.Color,
			enumName(part.Material),
			viewTransparency(part),
			part.CastShadow ~= false,
			part.CanCollide ~= false
		)
	end
	if approx > 0 then
		note(string.format("MeshPart/Union/Truss 등 %d개는 상자로 대신 그립니다", approx))
	end

	-- SurfaceGui 간판: 면 좌표계 + GUI 상자 목록(렌더러가 캔버스에 그려서 면에 붙임) -----------
	-- 면별 GUI 가로(오른쪽)·세로(위) 방향(파트 좌표). Front/Back/Left/Right 는 밖에서 면을 볼 때의 오른쪽.
	-- Top/Bottom 은 추정(Top: 오른쪽 +X, 위 -Z).
	local FACES = {
		Front = { N = Vector3.new(0, 0, -1), R = Vector3.new(-1, 0, 0), U = Vector3.new(0, 1, 0), W = "X", H = "Y" },
		Back = { N = Vector3.new(0, 0, 1), R = Vector3.new(1, 0, 0), U = Vector3.new(0, 1, 0), W = "X", H = "Y" },
		Right = { N = Vector3.new(1, 0, 0), R = Vector3.new(0, 0, -1), U = Vector3.new(0, 1, 0), W = "Z", H = "Y" },
		Left = { N = Vector3.new(-1, 0, 0), R = Vector3.new(0, 0, 1), U = Vector3.new(0, 1, 0), W = "Z", H = "Y" },
		Top = { N = Vector3.new(0, 1, 0), R = Vector3.new(1, 0, 0), U = Vector3.new(0, 0, -1), W = "X", H = "Z" },
		Bottom = { N = Vector3.new(0, -1, 0), R = Vector3.new(-1, 0, 0), U = Vector3.new(0, 0, -1), W = "X", H = "Z" },
	}

	-- ImageIds: 에셋 Id -> 이름(art/png/<이름>.png 로 그림)
	local imageNames = {}
	if shared then
		local ok, ids = pcall(Harness.require, shared.ImageIds)
		if ok and type(ids) == "table" then
			for name, value in ids do
				local id = tostring(value):match("(%d+)")
				if id then
					imageNames[id] = name
				end
			end
		end
	end

	local GUI_CLASSES = { Frame = true, TextLabel = true, TextButton = true, ImageLabel = true, ImageButton = true }

	local function childOfClass(instance, class: string)
		for _, child in instance:GetChildren() do
			if child.ClassName == class then
				return child
			end
		end
		return nil
	end

	local function udimPx(u, parentSize: number): number
		return u.Scale * parentSize + u.Offset
	end

	local function textFields(node, gui)
		local text = gui.Text
		if type(text) ~= "string" or text == "" then
			return
		end
		local stroke = childOfClass(gui, "UIStroke")
		local plain = if gui.RichText then text:gsub("<[^>]*>", "") else text
		node.text = {
			s = plain,
			rich = if gui.RichText then text else nil,
			color = gui.TextColor3 and { gui.TextColor3.R, gui.TextColor3.G, gui.TextColor3.B } or { 0, 0, 0 },
			t = gui.TextTransparency or 0,
			scaled = gui.TextScaled == true,
			size = gui.TextSize or 14,
			font = enumName(gui.Font or "Font.SourceSans"),
			xa = enumName(gui.TextXAlignment or "TextXAlignment.Center"),
			ya = enumName(gui.TextYAlignment or "TextYAlignment.Center"),
			stroke = if stroke and stroke.Enabled ~= false
				then { w = stroke.Thickness or 1, color = { stroke.Color.R, stroke.Color.G, stroke.Color.B } }
				else nil,
		}
	end

	local function guiNodes(container, rect, out: { any })
		-- 형제는 ZIndex 순서(ZIndexBehavior.Sibling)
		local children = {}
		for _, child in container:GetChildren() do
			if GUI_CLASSES[child.ClassName] and child.Visible ~= false then
				table.insert(children, child)
			end
		end
		table.sort(children, function(a, b)
			return (a.ZIndex or 1) < (b.ZIndex or 1)
		end)
		-- 부모의 UIPadding 은 자식 배치 영역을 줄임
		local pad = childOfClass(container, "UIPadding")
		local inner = rect
		if pad then
			local l = pad.PaddingLeft and udimPx(pad.PaddingLeft, rect.w) or 0
			local r = pad.PaddingRight and udimPx(pad.PaddingRight, rect.w) or 0
			local t = pad.PaddingTop and udimPx(pad.PaddingTop, rect.h) or 0
			local b = pad.PaddingBottom and udimPx(pad.PaddingBottom, rect.h) or 0
			inner = { x = rect.x + l, y = rect.y + t, w = rect.w - l - r, h = rect.h - t - b }
		end
		for _, gui in children do
			local size = gui.Size or UDim2.new()
			local position = gui.Position or UDim2.new()
			local anchor = gui.AnchorPoint or Vector2.new()
			local rel = enumName(gui.SizeConstraint or "SizeConstraint.RelativeXY")
			local bw = if rel == "RelativeYY" then inner.h else inner.w
			local bh = if rel == "RelativeXX" then inner.w else inner.h
			local w = udimPx(size.X, bw)
			local h = udimPx(size.Y, bh)
			local x = inner.x + udimPx(position.X, inner.w) - anchor.X * w
			local y = inner.y + udimPx(position.Y, inner.h) - anchor.Y * h
			local node: { [string]: any } = { cls = gui.ClassName, x = x, y = y, w = w, h = h, rot = gui.Rotation or 0 }
			local bgT = gui.BackgroundTransparency or 0
			if bgT < 1 and gui.BackgroundColor3 then
				node.bg = { gui.BackgroundColor3.R, gui.BackgroundColor3.G, gui.BackgroundColor3.B }
				node.bgT = bgT
			end
			local corner = childOfClass(gui, "UICorner")
			if corner then
				local radius = corner.CornerRadius or UDim.new(0, 8)
				node.corner = udimPx(radius, math.min(w, h))
			end
			local stroke = childOfClass(gui, "UIStroke")
			if stroke and stroke.Enabled ~= false and (gui.ClassName == "Frame" or gui.ClassName == "ImageLabel") then
				node.stroke = {
					w = stroke.Thickness or 1,
					color = { stroke.Color.R, stroke.Color.G, stroke.Color.B },
					t = stroke.Transparency or 0,
				}
			end
			local gradient = childOfClass(gui, "UIGradient")
			if gradient and gradient.Enabled ~= false and gradient.Color then
				local keys = gradient.Color.Keypoints
				local a, b = keys[1].Value, keys[#keys].Value
				node.gradient = { from = { a.R, a.G, a.B }, to = { b.R, b.G, b.B }, rot = gradient.Rotation or 0 }
			end
			if gui.ClassName == "ImageLabel" or gui.ClassName == "ImageButton" then
				local id = tostring(gui.Image or ""):match("(%d+)")
				if id then
					local sc = gui.SliceCenter
					local ic = gui.ImageColor3 or Color3.new(1, 1, 1)
					node.image = {
						name = imageNames[id] or id,
						color = { ic.R, ic.G, ic.B },
						t = gui.ImageTransparency or 0,
						scale = enumName(gui.ScaleType or "ScaleType.Stretch"),
						slice = if sc then { sc.MinX, sc.MinY, sc.MaxX, sc.MaxY } else nil,
						sliceScale = gui.SliceScale or 1,
					}
				end
			end
			if gui.ClassName == "TextLabel" or gui.ClassName == "TextButton" then
				textFields(node, gui)
				local tpad = childOfClass(gui, "UIPadding")
				if tpad and node.text then
					node.text.pad = {
						tpad.PaddingLeft and udimPx(tpad.PaddingLeft, w) or 0,
						tpad.PaddingTop and udimPx(tpad.PaddingTop, h) or 0,
						tpad.PaddingRight and udimPx(tpad.PaddingRight, w) or 0,
						tpad.PaddingBottom and udimPx(tpad.PaddingBottom, h) or 0,
					}
				end
			end
			table.insert(out, node)
			guiNodes(gui, { x = x, y = y, w = w, h = h }, out)
		end
	end

	local guiRecords = {}
	for _, d in Mock.Workspace:GetDescendants() do
		if d.ClassName == "SurfaceGui" and d.Enabled ~= false then
			local part = d.Adornee or d.Parent
			if part and Mock.isBasePart(part) then
				local face = FACES[enumName(d.Face or "NormalId.Front")] or FACES.Front
				local fw, fh = part.Size[face.W], part.Size[face.H]
				local pps = d.PixelsPerStud or 50
				local canvasW, canvasH
				if enumName(d.SizingMode or "SurfaceGuiSizingMode.FixedSize") == "PixelsPerStud" then
					canvasW, canvasH = fw * pps, fh * pps
				else
					local cs = d.CanvasSize or Vector2.new(800, 600)
					canvasW, canvasH = cs.X, cs.Y
				end
				local nodes = {}
				guiNodes(d, { x = 0, y = 0, w = canvasW, h = canvasH }, nodes)
				if #nodes > 0 then
					local cf = part.CFrame
					local depth = part.Size[if face.N.X ~= 0 then "X" elseif face.N.Y ~= 0 then "Y" else "Z"]
					local center = cf * (face.N * (depth / 2))
					table.insert(
						guiRecords,
						Mock.json.encode({
							path = pathOf(part),
							o = rawget(d, "__origin"),
							center = { center.X, center.Y, center.Z },
							normal = {
								cf:VectorToWorldSpace(face.N).X,
								cf:VectorToWorldSpace(face.N).Y,
								cf:VectorToWorldSpace(face.N).Z,
							},
							right = {
								cf:VectorToWorldSpace(face.R).X,
								cf:VectorToWorldSpace(face.R).Y,
								cf:VectorToWorldSpace(face.R).Z,
							},
							up = {
								cf:VectorToWorldSpace(face.U).X,
								cf:VectorToWorldSpace(face.U).Y,
								cf:VectorToWorldSpace(face.U).Z,
							},
							w = fw,
							h = fh,
							cw = canvasW,
							ch = canvasH,
							lit = (d.LightInfluence or 1) > 0,
							nodes = nodes,
						})
					)
				end
			end
		end
	end

	-- 조명
	local L = Mock.Lighting
	local function c3(c): { number }?
		return if c then { c.R, c.G, c.B } else nil
	end
	local lighting: { [string]: any } = {
		ClockTime = L.ClockTime,
		Brightness = L.Brightness,
		GeographicLatitude = L.GeographicLatitude,
		Ambient = c3(L.Ambient),
		OutdoorAmbient = c3(L.OutdoorAmbient),
		ExposureCompensation = L.ExposureCompensation,
		FogStart = L.FogStart,
		FogEnd = L.FogEnd,
		FogColor = c3(L.FogColor),
		GlobalShadows = L.GlobalShadows,
	}
	for _, child in L:GetChildren() do
		if child.ClassName == "Atmosphere" then
			lighting.Atmosphere = {
				Density = child.Density or 0.395,
				Offset = child.Offset or 0,
				Haze = child.Haze or 0,
				Glare = child.Glare or 0,
				Color = c3(child.Color or Color3.fromRGB(199, 199, 199)),
				Decay = c3(child.Decay or Color3.fromRGB(106, 112, 125)),
			}
		elseif child.ClassName == "Sky" then
			lighting.Sky = { Name = child.Name }
		elseif child.ClassName == "ColorCorrectionEffect" and child.Enabled ~= false then
			lighting.ColorCorrection = {
				Brightness = child.Brightness or 0,
				Contrast = child.Contrast or 0,
				Saturation = child.Saturation or 0,
				TintColor = c3(child.TintColor or Color3.new(1, 1, 1)),
			}
		end
	end

	local counts = {}
	for _, part in parts do
		local origin = rawget(part, "__origin")
		counts[origin] = (counts[origin] or 0) + 1
	end
	local summary = {}
	for origin, n in counts do
		table.insert(summary, origin .. "=" .. n)
	end
	table.sort(summary)
	note("파트 수: " .. table.concat(summary, ", ") .. string.format(", SurfaceGui %d개", #guiRecords))
	for _, w in Mock.warnings do
		note("warn: " .. w)
	end
	for _, v in Mock.violations do
		note("규칙 위반: " .. v)
	end
	for _, e in Mock.errors do
		note("task 오류: " .. e)
	end

	-- 지형
	local T = Mock.Terrain
	local terrainJson = Mock.terrainDumpJson({
		WaterColor = c3(T.WaterColor),
		WaterTransparency = T.WaterTransparency,
		WaterReflectance = T.WaterReflectance,
		WaterWaveSize = T.WaterWaveSize,
		WaterWaveSpeed = T.WaterWaveSpeed,
		Decoration = T.Decoration == true,
		GrassLength = T.GrassLength,
	})
	if terrainJson then
		local stats = Mock.terrainStats()
		local calls = {}
		for key, n in stats.Calls do
			table.insert(calls, key .. " x" .. n)
		end
		table.sort(calls)
		note(
			string.format(
				"지형: 청크 %d개(균일 %d, 복셀별 %d), 호출 %s",
				stats.UniformChunks + stats.DenseChunks,
				stats.UniformChunks,
				stats.DenseChunks,
				table.concat(calls, ", ")
			)
		)
		if stats.CutByWater > 0.5 then
			note(
				string.format(
					"warn: 물 채우기가 이미 있던 땅 약 %.0f 복셀을 깎았습니다(Roblox 도 물 Fill* 은 땅을 덮어씀. 물을 먼저 채우거나 ReplaceMaterial(Air→Water))",
					stats.CutByWater
				)
			)
		end
	end

	-- Highlight(강조): 켜진 것만. 대상(Adornee, 없으면 부모) 아래 보이는 파트 번호 + 색·투명도·깊이 방식
	local highlightRecords = {}
	for _, d in Mock.Workspace:GetDescendants() do
		if d.ClassName == "Highlight" and d.Enabled ~= false then
			local target = d.Adornee or d.Parent
			local list = {}
			if target then
				local candidates = if Mock.isBasePart(target) then { target } else {}
				for _, child in target:GetDescendants() do
					if Mock.isBasePart(child) then
						table.insert(candidates, child)
					end
				end
				for _, part in candidates do
					local index = partIndex[part]
					if index and viewTransparency(part) < 0.999 then
						table.insert(list, index)
					end
				end
			end
			if #list > 0 then
				local fill = d.FillColor or Color3.fromRGB(255, 0, 0)
				local outline = d.OutlineColor or Color3.new(1, 1, 1)
				table.insert(
					highlightRecords,
					Mock.json.encode({
						name = d.Name,
						parts = list,
						fill = { fill.R, fill.G, fill.B },
						ft = d.FillTransparency or 0.5,
						outline = { outline.R, outline.G, outline.B },
						ot = d.OutlineTransparency or 0,
						top = enumName(d.DepthMode or "HighlightDepthMode.AlwaysOnTop") == "AlwaysOnTop",
					})
				)
			end
		end
	end
	if #highlightRecords > 0 then
		note(string.format("Highlight %d개", #highlightRecords))
	end

	local meta = ctx.meta or {}
	meta.notes = ctx.notes

	print("DUMP_BEGIN")
	print(
		string.format(
			'{"meta":%s,"lighting":%s,"parts":[%s],"gui":[%s],"terrain":%s,"hl":[%s],"extra":%s}',
			Mock.json.encode(meta),
			Mock.json.encode(lighting),
			table.concat(partRecords, ","),
			table.concat(guiRecords, ","),
			terrainJson or "null",
			table.concat(highlightRecords, ","),
			if ctx.extra ~= nil then Mock.json.encode(ctx.extra) else "null"
		)
	)
	print("DUMP_END")
end
