setblock -17 -59 5 minecraft:stone_button[face=wall,facing=south,powered=false]
execute positioned -16.5 -58.5 5.5 as @p[gamemode=!spectator,distance=..6] at @s run function aooni:on/l_solo
