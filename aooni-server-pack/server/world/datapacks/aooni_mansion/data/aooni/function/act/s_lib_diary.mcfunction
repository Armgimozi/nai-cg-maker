setblock 5 -59 7 minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 5.5 -58.5 7.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_lib_diary
