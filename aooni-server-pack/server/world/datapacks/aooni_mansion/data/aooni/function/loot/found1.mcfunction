execute if score #f1 aooni.var matches 1 run return 0
scoreboard players set #f1 aooni.var 1
scoreboard players add #found aooni.var 1
clear @s minecraft:paper[minecraft:custom_data={aooni_dig:1}]
function aooni:loot/read1 with storage aooni:v
execute as @a[tag=aooni.player,tag=!aooni.oni_p] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.3
function aooni:game/progress
