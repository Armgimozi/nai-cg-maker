setblock 50 -49 1 minecraft:stone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 50.5 -48.5 1.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe4_ok
