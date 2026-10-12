setblock 26 -58 35 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 26.5 -57.5 35.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_liv_cab
