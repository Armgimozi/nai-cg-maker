execute if score #wpn aooni.var matches 1 run return run tellraw @s {"text":"금고는 이미 비어 있다.","color":"gray"}
execute unless score #d1 aooni.var = #k1 aooni.var run return run function aooni:safe/wrong
execute unless score #d2 aooni.var = #k2 aooni.var run return run function aooni:safe/wrong
execute unless score #d3 aooni.var = #k3 aooni.var run return run function aooni:safe/wrong
execute unless score #d4 aooni.var = #k4 aooni.var run return run function aooni:safe/wrong
scoreboard players set #wpn aooni.var 1
function aooni:weapon/give
playsound minecraft:block.iron_door.open block @a[distance=..12] ~ ~ ~ 1 1.4
playsound minecraft:item.trident.thunder master @a[distance=..48] ~ ~ ~ 0.8 1.2
particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 60
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 금고에서 ","color":"white"},{"text":"[마검]","color":"gold","bold":true},{"text":"을(를) 꺼냈다!","color":"white"}]}
data modify entity @e[type=minecraft:text_display,tag=aooni.safe4,limit=1] text set value {"text":"마검 금고 · 비었음","color":"gray"}
function aooni:final/start
