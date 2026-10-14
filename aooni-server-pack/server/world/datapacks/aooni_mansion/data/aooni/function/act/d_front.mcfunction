setblock 25 -54 42 minecraft:stone_button[face=wall,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 25.5 -53.5 42.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/d_front
