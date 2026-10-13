setblock 43 -54 1 minecraft:stone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 43.5 -53.5 1.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe4_ok
