execute if score #k_lib aooni.var matches 1 run return run tellraw @s {"text":"장식장 서랍에는 더 이상 아무것도 없다.","color":"gray"}
scoreboard players set #k_lib aooni.var 1
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 장식장 서랍에서 ","color":"white"},{"text":"[서재 열쇠]","color":"gold","bold":true},{"text":"을(를) 찾았다!","color":"white"}]}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.2
function aooni:game/progress
