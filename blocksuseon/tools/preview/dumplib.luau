-- dump BaseParts under a root (or list) to JSON for preview.py
local serde = require("@lune/serde")
local fs = require("@lune/fs")
local M = {}
function M.partJson(p)
  local shape = "Block"
  if p.ClassName == "WedgePart" then shape = "Wedge"
  elseif p.ClassName == "CornerWedgePart" then shape = "CornerWedge"
  elseif p.ClassName == "Part" then
    local s = p.Shape.Name
    if s == "Cylinder" then shape = "Cylinder" elseif s == "Ball" then shape = "Ball" end
  elseif p.ClassName == "SpawnLocation" or p.ClassName == "Seat" then shape = "Block" end
  local c = { p.CFrame:GetComponents() }
  return { shape = shape, cf = c, size = { p.Size.X, p.Size.Y, p.Size.Z },
    color = { math.floor(p.Color.R * 255 + 0.5), math.floor(p.Color.G * 255 + 0.5), math.floor(p.Color.B * 255 + 0.5) },
    transparency = p.Transparency, material = p.Material.Name, name = p.Name }
end
function M.dump(roots, path, filter)
  local out = {}
  for _, root in roots do
    for _, d in root:GetDescendants() do
      if d:IsA("BasePart") and (not filter or filter(d)) then table.insert(out, M.partJson(d)) end
    end
  end
  fs.writeFile(path, serde.encode("json", out))
  return #out
end
return M
