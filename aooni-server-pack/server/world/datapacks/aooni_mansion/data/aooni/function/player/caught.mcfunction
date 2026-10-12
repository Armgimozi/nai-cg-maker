tag @e[type=minecraft:zombie,tag=aooni.oni,sort=nearest,limit=1] add aooni.got
tag @s remove aooni.alive
tag @s remove aooni.hidden
tag @s remove aooni.hid_new
scoreboard players remove @s aooni.lives 1
title @s times 5 40 15
title @s title {"text":"잡혔다…","color":"dark_red","bold":true}
effect give @s minecraft:blindness 3 0 true
playsound minecraft:entity.ghast.scream master @s ~ ~ ~ 1 0.5
playsound minecraft:entity.zombie.attack_iron_door hostile @a[distance=..24] ~ ~ ~ 1 0.6
tellraw @a {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 아오오니에게 잡혔다!","color":"red"}]}
execute if score @s aooni.lives matches 1.. run function aooni:player/jail
execute if score @s aooni.lives matches ..0 run function aooni:player/out
