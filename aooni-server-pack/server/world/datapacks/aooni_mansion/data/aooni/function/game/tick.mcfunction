execute as @e[type=minecraft:zombie,tag=aooni.oni] at @s run function aooni:oni/tick
function aooni:hide/check
execute as @e[type=minecraft:item_display,tag=aooni.altar_item] at @s run rotate @s ~4 0
scoreboard players remove @a[tag=aooni.safe] aooni.grace 1
tag @a[tag=aooni.safe,scores={aooni.grace=..0}] remove aooni.safe
execute if score #stairs aooni.var matches 1 if score #store aooni.var matches 0 run function aooni:puzzle/plates
