setblock 13 -59 4 minecraft:polished_blackstone_button[face=wall,facing=west,powered=false]
execute if score #state aooni.var matches 1 positioned 13.5 -58.5 4.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe2_d1
