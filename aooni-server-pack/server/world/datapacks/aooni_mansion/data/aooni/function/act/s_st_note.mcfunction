setblock 20 -54 34 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 20.5 -53.5 34.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_st_note
