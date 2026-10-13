setblock 29 -54 18 minecraft:stone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 29.5 -53.5 18.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/safe3_ok
