setblock 29 -59 6 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 29.5 -58.5 6.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_din_plate
