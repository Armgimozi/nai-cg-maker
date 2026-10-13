setblock 40 -59 35 minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 40.5 -58.5 35.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe1_d1
