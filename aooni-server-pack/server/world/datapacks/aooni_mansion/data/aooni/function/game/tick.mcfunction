execute if score #freeze aooni.var matches 1.. as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] positioned 48.5 -45 33.5 unless entity @s[distance=..0.4] run tp @s 48.5 -45 33.5
execute as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] at @s run tp @e[type=minecraft:item_display,tag=aooni.part] ~ ~ ~ ~ 0
execute as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] run function aooni:oni/anim
execute as @a[scores={aooni.eb=1..}] run function aooni:item/ate_bread
execute as @a[scores={aooni.es=1..}] run function aooni:item/ate_steak
execute as @a[tag=aooni.oni_p] at @s run function aooni:oni/no_sword
execute as @a[tag=aooni.oni_p] if items entity @s container.* minecraft:paper run function aooni:oni/no_paper
function aooni:hide/check
execute if score #final aooni.var matches 1 as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] at @s run function aooni:final/hp
