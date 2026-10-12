setblock 45 -59 23 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 45.5 -58.5 23.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_kit_sink
