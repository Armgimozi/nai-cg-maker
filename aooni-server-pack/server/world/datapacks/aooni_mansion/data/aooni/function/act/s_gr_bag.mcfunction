setblock 33 -54 9 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 33.5 -53.5 9.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_gr_bag
