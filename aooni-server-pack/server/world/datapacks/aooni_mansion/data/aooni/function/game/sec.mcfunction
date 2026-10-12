scoreboard players add #sec aooni.var 1
execute store result score #alive aooni.var if entity @a[tag=aooni.alive]
execute store result score #jailed aooni.var if entity @a[tag=aooni.jailed]
execute store result score #escaped aooni.var if entity @a[tag=aooni.escaped]
execute store result score #onis aooni.var if entity @e[type=minecraft:zombie,tag=aooni.oni]
function aooni:game/sidebar
bossbar set aooni:goal players @a[tag=aooni.player]
execute if score #alive aooni.var matches 0 run return run function aooni:game/end
execute if score #oni_on aooni.var matches 1 run function aooni:oni/manager
execute as @e[type=minecraft:zombie,tag=aooni.oni] at @s run function aooni:oni/sec
execute as @a[tag=aooni.hidden] at @s run function aooni:hide/sec
execute as @a[tag=aooni.alive,tag=!aooni.hidden] at @s if entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..12] run function aooni:player/near_oni
execute if score #rescue_cd aooni.var matches 1.. run scoreboard players remove #rescue_cd aooni.var 1
execute as @a[tag=aooni.jailed] unless entity @s[x=1,y=-61,z=31,dx=8,dy=5,dz=4] run tp @s 5.5 -60 33.5 180 0
scoreboard players remove #amb aooni.var 1
execute if score #amb aooni.var matches ..0 run function aooni:fx/ambient
function aooni:fx/glimmer
