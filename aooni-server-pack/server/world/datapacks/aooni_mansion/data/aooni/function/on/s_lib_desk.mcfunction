execute if score #k_din aooni.var matches 1 run return run tellraw @s {"text":"서재 책상에는 더 이상 아무것도 없다.","color":"gray"}
scoreboard players set #k_din aooni.var 1
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 서재 책상에서 ","color":"white"},{"text":"[식당 열쇠]","color":"gold","bold":true},{"text":"을(를) 찾았다!","color":"white"}]}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.2
scoreboard players set #oni_on aooni.var 1
scoreboard players set #oni_cd aooni.var 100
playsound minecraft:block.wooden_door.close hostile @a[distance=..24] 2 -59 2 1 0.5
schedule function aooni:event/first_oni 40t
function aooni:game/progress
