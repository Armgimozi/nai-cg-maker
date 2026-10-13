execute if score #wpn aooni.var matches 1 run return run tellraw @s {"text":"제단은 비어 있다. 검은 이미 누군가 뽑았다.","color":"gray"}
execute if score #altar aooni.var matches 0 run return run tellraw @s {"text":"","extra":[{"text":"제단에 자물쇠 구멍 네 개가 있다… ","color":"gray"},{"text":"봉인 ","color":"light_purple"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 풀림","color":"light_purple"}]}
scoreboard players set #wpn aooni.var 1
kill @e[type=minecraft:item_display,tag=aooni.altar_item]
data modify entity @e[type=minecraft:text_display,tag=aooni.altar_t,limit=1] text set value {"text":"제단 · 비었음","color":"gray"}
function aooni:weapon/give
particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 60
playsound minecraft:item.trident.thunder master @a[distance=..32] ~ ~ ~ 0.8 1.2
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 제단에서 ","color":"white"},{"text":"[전설의 검]","color":"gold","bold":true},{"text":"을(를) 뽑았다! ","color":"white"},{"text":"…저택 깊은 곳에서 무언가가 울부짖는다.","color":"red","italic":true}]}
function aooni:final/check
