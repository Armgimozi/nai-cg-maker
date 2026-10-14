setblock 3 -59 11 minecraft:stone_button[face=wall,facing=south,powered=false]
execute if score #state aooni.var matches 1 positioned 3.5 -58.5 11.5 as @p[tag=aooni.alive,distance=..6] at @s run function aooni:on/rescue
