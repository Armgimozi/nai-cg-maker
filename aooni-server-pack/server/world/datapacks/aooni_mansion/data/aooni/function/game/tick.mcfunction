execute if score #freeze aooni.var matches 1.. as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] positioned 38.5 -55 27.5 unless entity @s[distance=..0.4] run tp @s 38.5 -55 27.5
execute as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] at @s run tp @e[type=minecraft:block_display,tag=aooni.part] ~ ~ ~ ~ 0
execute as @a[tag=aooni.alive,scores={aooni.hit=1..}] at @s run function aooni:player/hit
scoreboard players reset @a[scores={aooni.hit=1..}] aooni.hit
execute as @a[tag=aooni.oni_p] at @s run function aooni:oni/no_sword
function aooni:hide/check
scoreboard players remove @a[tag=aooni.safe] aooni.grace 1
tag @a[tag=aooni.safe,scores={aooni.grace=..0}] remove aooni.safe
execute if score #final aooni.var matches 1 as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] at @s run function aooni:final/hp
