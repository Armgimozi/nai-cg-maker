setblock 1 -54 24 minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]
execute if score #state aooni.var matches 1 positioned 1.5 -53.5 24.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_kid_draw
