-- 플레이스 파일 만들기.   실행: lune run tools/bake_place   (blocksuseon 폴더에서)
--
-- 1) Rojo 로 스크립트만 든 플레이스를 빌드하고
-- 2) 그 안에 연국 맵(World.build)을 지어 넣어
-- 3) BlockSuseon.rbxl 로 저장한다.
-- 맵이 플레이스에 들어 있으므로 Studio 에서 바로 보고 고칠 수 있다.

local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local Harness = require("../tests/harness")

local SCRIPTS_PLACE = "build/scripts.rbxl"
local OUTPUT = "BlockSuseon.rbxl"

fs.writeDir("build")

local result = process.exec("rojo", { "build", "default.project.json", "--output", SCRIPTS_PLACE })
if not result.ok then
	error("rojo build 실패:\n" .. result.stderr)
end

local game = roblox.deserializePlace(fs.readFile(SCRIPTS_PLACE))
local loader = Harness.new(Harness.robloxGlobals(game))
local World = loader.require(loader.folder("src/server").World)

local workspace = game:GetService("Workspace")
local existing = workspace:FindFirstChild(World.MODEL_NAME)
if existing then
	existing:Destroy()
end
World.build(workspace, game:GetService("Lighting"))

fs.writeFile(OUTPUT, roblox.serializePlace(game))
print(`{OUTPUT} 저장 ({#fs.readFile(OUTPUT)} 바이트)`)
