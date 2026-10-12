setblock 31 -59 35 minecraft:stone_button[face=wall,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 31.5 -58.5 35.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/d_front
