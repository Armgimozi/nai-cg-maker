setblock 32 -59 13 minecraft:stone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 32.5 -58.5 13.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/d_din
