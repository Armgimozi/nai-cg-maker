execute if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:1}] at @e[type=minecraft:marker,tag=aooni.dig1,limit=1] run function aooni:loot/put_digit1
execute if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:2}] at @e[type=minecraft:marker,tag=aooni.dig2,limit=1] run function aooni:loot/put_digit2
execute if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:3}] at @e[type=minecraft:marker,tag=aooni.dig3,limit=1] run function aooni:loot/put_digit3
execute if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:4}] at @e[type=minecraft:marker,tag=aooni.dig4,limit=1] run function aooni:loot/put_digit4
clear @s minecraft:paper
