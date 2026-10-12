setblock 44 -59 30 minecraft:polished_blackstone_button[face=wall,facing=west,powered=false]
execute if score #state aooni.var matches 1 positioned 44.5 -58.5 30.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_kit_fridge
