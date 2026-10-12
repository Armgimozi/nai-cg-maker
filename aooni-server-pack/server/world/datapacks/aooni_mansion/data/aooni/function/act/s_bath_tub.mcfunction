setblock 11 -59 34 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 11.5 -58.5 34.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_bath_tub
