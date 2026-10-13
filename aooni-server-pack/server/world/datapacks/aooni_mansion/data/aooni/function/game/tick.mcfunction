execute as @a[tag=aooni.oni_p,tag=!aooni.oni_dead] at @s run tp @e[type=minecraft:block_display,tag=aooni.part] ~ ~ ~ ~ 0
execute as @a[tag=aooni.alive,scores={aooni.hit=1..}] at @s run function aooni:player/hit
scoreboard players reset @a[scores={aooni.hit=1..}] aooni.hit
execute as @a[tag=aooni.oni_p] at @s run function aooni:oni/no_sword
function aooni:hide/check
scoreboard players remove @a[tag=aooni.safe] aooni.grace 1
tag @a[tag=aooni.safe,scores={aooni.grace=..0}] remove aooni.safe
execute if score #final aooni.var matches 1 as @a[tag=aooni.oni_p,tag=!aooni.oni_dead] at @s run function aooni:final/hp
