scoreboard players set @s aooni.leave 0
execute if score #state aooni.var matches 1 if entity @s[tag=aooni.player] if score @s aooni.gid = #gid aooni.var run return run function aooni:player/resume
execute if score #state aooni.var matches 1 run return run function aooni:player/watch
function aooni:player/to_lobby
