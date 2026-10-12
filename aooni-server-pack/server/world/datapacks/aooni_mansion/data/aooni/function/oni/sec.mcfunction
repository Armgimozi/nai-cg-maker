scoreboard players add @s aooni.life 1
scoreboard players add @s aooni.tgt 1
execute if entity @a[tag=aooni.alive,tag=!aooni.hidden,distance=..16] run scoreboard players set @s aooni.lost 0
execute unless entity @a[tag=aooni.alive,tag=!aooni.hidden,distance=..16] run scoreboard players add @s aooni.lost 1
execute if score @s aooni.tgt matches 2.. if entity @a[tag=aooni.alive,tag=!aooni.hidden,distance=..22] run function aooni:oni/retarget
playsound minecraft:entity.iron_golem.step hostile @a[distance=..18] ~ ~ ~ 0.9 0.5
execute if score #diff aooni.var matches 1 if score @s aooni.lost matches 10.. run return run function aooni:oni/vanish
execute if score #diff aooni.var matches 2 if score @s aooni.lost matches 14.. run return run function aooni:oni/vanish
execute if score #diff aooni.var matches 3 if score @s aooni.lost matches 20.. run return run function aooni:oni/vanish
execute if score #diff aooni.var matches 1 if score @s aooni.life matches 60.. if score @s aooni.lost matches 4.. run return run function aooni:oni/vanish
execute if score #diff aooni.var matches 2 if score @s aooni.life matches 90.. if score @s aooni.lost matches 4.. run return run function aooni:oni/vanish
execute if score #diff aooni.var matches 3 if score @s aooni.life matches 120.. if score @s aooni.lost matches 4.. run return run function aooni:oni/vanish
execute if entity @s[y=-70,dy=-200] run function aooni:oni/vanish
