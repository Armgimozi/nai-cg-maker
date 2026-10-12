setblock 31 -59 29 minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]
execute if score #state aooni.var matches 1 positioned 31.5 -58.5 29.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_hall_photo
