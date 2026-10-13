execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.searched] at @s run particle minecraft:glow ~ ~0.35 ~ 0.15 0.1 0.15 0 2
execute if score #found aooni.var matches 4.. if score #wpn aooni.var matches 0 run particle minecraft:glow 43.5 -53.65 1.5 0.2 0.15 0.2 0 6
