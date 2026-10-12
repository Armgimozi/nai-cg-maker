setblock 8 -59 19 minecraft:polished_blackstone_button[face=floor,facing=north,powered=false]
execute if score #state aooni.var matches 1 positioned 8.5 -58.5 19.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/s_jail_note
