setblock 13 -59 8 minecraft:stone_button[face=wall,facing=west,powered=false]
execute if score #state aooni.var matches 1 positioned 13.5 -58.5 8.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe2_ok
