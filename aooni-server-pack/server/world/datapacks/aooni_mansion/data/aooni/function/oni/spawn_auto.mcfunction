tag @e[type=minecraft:marker,tag=aooni.cand] remove aooni.cand
execute as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s if entity @a[tag=aooni.alive,distance=..36] unless entity @a[tag=aooni.alive,distance=..10] run tag @s add aooni.cand
execute unless entity @e[type=minecraft:marker,tag=aooni.cand] as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s unless entity @a[tag=aooni.alive,distance=..7] run tag @s add aooni.cand
execute at @e[type=minecraft:marker,tag=aooni.cand,sort=random,limit=1] run function aooni:oni/spawn
function aooni:oni/reset_cd
