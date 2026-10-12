setblock 39 -54 2 minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 39.5 -53.5 2.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/dial1
