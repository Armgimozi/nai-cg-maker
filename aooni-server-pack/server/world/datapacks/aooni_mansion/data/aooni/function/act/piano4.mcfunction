setblock 42 -59 2 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 42.5 -58.5 2.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/piano4
