function aooni:player/clear_tags
team join aooni_lobby @s
effect clear @s
clear @s
gamemode adventure @s
function aooni:player/reset_attrs
effect give @s minecraft:resistance infinite 4 true
effect give @s minecraft:saturation infinite 0 true
effect give @s minecraft:instant_health 1 4 true
tp @s -20.5 -60 14.5 180 0
spawnpoint @s -21 -60 14
