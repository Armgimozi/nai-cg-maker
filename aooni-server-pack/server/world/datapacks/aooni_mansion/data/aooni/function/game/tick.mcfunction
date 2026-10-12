execute as @e[type=minecraft:zombie,tag=aooni.oni] at @s run function aooni:oni/tick
function aooni:hide/check
scoreboard players remove @a[tag=aooni.safe] aooni.grace 1
tag @a[tag=aooni.safe,scores={aooni.grace=..0}] remove aooni.safe
execute as @a[tag=aooni.alive,x=30,y=-61,z=42,dx=7,dy=4,dz=3] at @s run function aooni:player/escape
execute if score #stairs aooni.var matches 1 if score #store aooni.var matches 0 run function aooni:puzzle/plates
