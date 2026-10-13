tag @s add aooni.player
scoreboard players operation @s aooni.gid = #gid aooni.var
scoreboard players set @s aooni.leave 0
team join aooni_oni @s
gamemode adventure @s
clear @s
effect clear @s
function aooni:player/reset_attrs
function aooni:oni/effects
effect give @s minecraft:slowness 20 255 true
effect give @s minecraft:blindness 20 0 true
tp @s 38.5 -55 27.5 0 0
spawnpoint @s 38 -55 27
execute at @s run function aooni:oni/model
