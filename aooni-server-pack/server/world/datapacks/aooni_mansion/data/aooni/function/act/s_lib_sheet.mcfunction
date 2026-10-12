setblock 2 -59 9 minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]
execute if score #state aooni.var matches 1 positioned 2.5 -58.5 9.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_lib_sheet
