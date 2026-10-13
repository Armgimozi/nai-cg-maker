setblock 26 -54 18 minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 26.5 -53.5 18.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe3_d2
