setblock 44 -54 10 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 44.5 -53.5 10.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_sto_box
