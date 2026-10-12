function aooni:player/clear_tags
tag @s add aooni.player
tag @s add aooni.alive
scoreboard players operation @s aooni.gid = #gid aooni.var
execute if score #diff aooni.var matches 1 run scoreboard players set @s aooni.lives 3
execute if score #diff aooni.var matches 2 run scoreboard players set @s aooni.lives 2
execute if score #diff aooni.var matches 3 run scoreboard players set @s aooni.lives 1
scoreboard players set @s aooni.grace 0
scoreboard players set @s aooni.hidet 0
scoreboard players set @s aooni.leave 0
team join aooni_alive @s
gamemode adventure @s
clear @s
effect clear @s
effect give @s minecraft:resistance infinite 4 true
effect give @s minecraft:saturation infinite 0 true
effect give @s minecraft:weakness infinite 9 true
attribute @s minecraft:knockback_resistance base set 1
spawnpoint @s 33 -60 30
