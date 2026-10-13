execute if score #final aooni.var matches 1 run return 0
execute unless score #wpn aooni.var matches 1 run return 0
scoreboard players set #final aooni.var 1
title @a[tag=aooni.player] times 10 60 20
title @a[tag=aooni.player] title {"text":"검이 뽑혔다","color":"gold","bold":true}
title @a[tag=aooni.player] subtitle {"text":"…거대한 무언가가 깨어난다","color":"red","italic":true}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.ravager.roar master @s ~ ~ ~ 0.8 0.5
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"5초 뒤 ","color":"gray"},{"text":"거대 아오오니","color":"dark_red","bold":true},{"text":"가 나타난다. 검을 든 사람은 앞으로, 나머지는 유인과 감옥 구출을 맡자!","color":"gray"}]}
schedule function aooni:final/start 100t
function aooni:game/progress
