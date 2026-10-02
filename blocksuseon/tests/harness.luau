-- Lune 에서 Roblox 식 모듈(require(script.Parent.X))을 불러오는 도우미.
-- src/ 폴더를 가짜 인스턴스 트리처럼 보이게 하고, 각 모듈을 따로 된 환경에서 실행한다.

local fs = require("@lune/fs")
local luau = require("@lune/luau")

local Harness = {}

export type Loader = {
	folder: (dir: string) -> any,
	require: (ref: any) -> any,
}

function Harness.new(globals: { [string]: any }): Loader
	local cache: { [string]: any } = {}
	local loader = {} :: Loader

	-- 폴더를 미리 다 읽어 둔다 (Lune 의 fs 는 메타메서드 안에서 쓸 수 없다)
	local function makeFolder(dir: string, parent: any?): any
		local folder = { __dir = dir, Name = string.match(dir, "[^/]+$"), Parent = parent }
		function folder.WaitForChild(self, name: string)
			local child = rawget(self, name)
			assert(child, `{dir}/{name} 가 없다`)
			return child
		end
		function folder.FindFirstChild(self, name: string)
			return rawget(self, name)
		end
		for _, entry in fs.readDir(dir) do
			local path = `{dir}/{entry}`
			if fs.isDir(path) then
				folder[entry] = makeFolder(path, folder)
			else
				-- Rojo 와 같은 규칙: Name.server.luau / Name.client.luau / Name.luau → Name
				local name = string.match(entry, "^(.-)%.server%.luau$")
					or string.match(entry, "^(.-)%.client%.luau$")
					or string.match(entry, "^(.-)%.luau$")
				if name then
					folder[name] = { __path = path, Name = name, Parent = folder }
				end
			end
		end
		return folder
	end

	local function load(ref: any): any
		assert(type(ref) == "table" and ref.__path, "Harness 는 script 경로 require 만 지원한다")
		local cached = cache[ref.__path]
		if cached ~= nil then
			return cached
		end
		local env = table.clone(globals)
		env.script = ref
		env.require = load
		local chunk = luau.load(fs.readFile(ref.__path), { debugName = ref.__path, environment = env })
		local result = chunk()
		cache[ref.__path] = result
		return result
	end

	loader.folder = makeFolder
	loader.require = load
	return loader
end

-- World 처럼 Roblox 데이터 타입을 쓰는 모듈을 Lune 에서 돌릴 때 넣을 전역
function Harness.robloxGlobals(game: any): { [string]: any }
	local roblox = require("@lune/roblox") :: any
	local env: { [string]: any } = {
		game = game,
		workspace = game:GetService("Workspace"),
	}
	for _, name in
		{
			"Instance",
			"Vector2",
			"Vector3",
			"CFrame",
			"Color3",
			"Enum",
			"UDim",
			"UDim2",
			"ColorSequence",
			"NumberRange",
			"NumberSequence",
			"NumberSequenceKeypoint",
			"Font",
		}
	do
		env[name] = roblox[name]
	end
	return env
end

return Harness
