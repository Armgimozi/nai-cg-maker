tag @s add aooni.player
tag @s add aooni.alive
scoreboard players operation @s aooni.gid = #gid aooni.var
execute if score #diff aooni.var matches 1 run scoreboard players set @s aooni.lives 4
execute if score #diff aooni.var matches 2 run scoreboard players set @s aooni.lives 3
execute if score #diff aooni.var matches 3 run scoreboard players set @s aooni.lives 2
scoreboard players set @s aooni.grace 0
scoreboard players set @s aooni.leave 0
team join aooni_alive @s
gamemode adventure @s
clear @s
effect clear @s
function aooni:player/reset_attrs
function aooni:player/survivor_effects
effect give @s minecraft:instant_health 1 4 true
# 쓰러지면 감옥에서 부활한다
spawnpoint @s 5 -60 33
