# 아오오니에게 맞아 체력이 다 닳았다(곧바로 감옥에서 부활한 상태). 들고 있던 마검은 쓰러진 자리에 떨어진다
function aooni:player/drop_sword_at_death
tag @s remove aooni.alive
tag @s remove aooni.hidden
tag @s remove aooni.hid_new
scoreboard players remove @s aooni.lives 1
title @s times 5 40 15
title @s title {"text":"쓰러졌다…","color":"dark_red","bold":true}
effect give @s minecraft:blindness 3 0 true
playsound minecraft:entity.ghast.scream master @s ~ ~ ~ 1 0.5
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 아오오니에게 당했다! ","color":"red"},{"text":"(남은 목숨 ","color":"gray"},{"score":{"name":"@s","objective":"aooni.lives"},"color":"yellow"},{"text":")","color":"gray"}]}
execute if score @s aooni.lives matches 1.. run function aooni:player/jail
execute if score @s aooni.lives matches ..0 run function aooni:player/out
execute as @a[tag=aooni.oni_p] at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.6 0.6
