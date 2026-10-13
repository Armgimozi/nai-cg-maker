execute store result score @s aooni.wc run clear @s minecraft:netherite_sword 0
execute if score @s aooni.wc matches 1.. if entity @s[tag=!aooni.armed] run function aooni:player/arm
execute if score @s aooni.wc matches ..0 if entity @s[tag=aooni.armed] run function aooni:player/disarm
