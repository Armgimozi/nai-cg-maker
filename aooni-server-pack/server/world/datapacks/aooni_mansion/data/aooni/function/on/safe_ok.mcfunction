execute if score #k_front aooni.var matches 1 run return run tellraw @s {"text":"금고는 비어 있다.","color":"gray"}
execute unless score #d1 aooni.var = #c1 aooni.var run return run function aooni:safe/wrong
execute unless score #d2 aooni.var = #c2 aooni.var run return run function aooni:safe/wrong
execute unless score #d3 aooni.var = #c3 aooni.var run return run function aooni:safe/wrong
execute unless score #d4 aooni.var = #c4 aooni.var run return run function aooni:safe/wrong
scoreboard players set #k_front aooni.var 1
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 금고에서 ","color":"white"},{"text":"[현관 열쇠]","color":"gold","bold":true},{"text":"을(를) 찾았다!","color":"white"}]}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.2
function aooni:game/progress
playsound minecraft:block.iron_door.open block @a[distance=..12] ~ ~ ~ 1 1.4
