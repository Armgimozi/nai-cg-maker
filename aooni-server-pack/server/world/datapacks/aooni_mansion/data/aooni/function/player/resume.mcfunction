execute if entity @s[tag=aooni.jailed] run tp @s 5.5 -60 33.5 180 0
execute if score #final aooni.var matches 1 if entity @s[tag=aooni.oni_p,tag=!aooni.giant,tag=!aooni.oni_dead] at @s run function aooni:oni/giant with storage aooni:v
execute if score #wpn aooni.var matches 1 run function aooni:weapon/dedupe
tellraw @s {"text":"다시 저택으로 돌아왔다…","color":"gray","italic":true}
