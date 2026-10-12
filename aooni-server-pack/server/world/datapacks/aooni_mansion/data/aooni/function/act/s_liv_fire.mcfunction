setblock 20 -59 26 minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]
execute if score #state aooni.var matches 1 positioned 20.5 -58.5 26.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_liv_fire
