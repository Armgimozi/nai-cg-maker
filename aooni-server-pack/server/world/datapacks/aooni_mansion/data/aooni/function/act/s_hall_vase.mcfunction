setblock 36 -59 25 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 36.5 -58.5 25.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_hall_vase
