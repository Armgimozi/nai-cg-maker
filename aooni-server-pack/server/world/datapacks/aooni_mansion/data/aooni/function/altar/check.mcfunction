execute if score #altar aooni.var matches 1 run return 0
execute unless score #w1 aooni.var matches 1 run return 0
execute unless score #w2 aooni.var matches 1 run return 0
execute unless score #w3 aooni.var matches 1 run return 0
execute unless score #w4 aooni.var matches 1 run return 0
scoreboard players set #altar aooni.var 1
summon minecraft:item_display 36.5 -58.4 28.5 {Tags:["aooni.fx","aooni.altar_item"],item:{id:"minecraft:netherite_sword",count:1},billboard:"fixed",brightness:{sky:15,block:15},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.9f,0.9f,0.9f]}}
data modify entity @e[type=minecraft:text_display,tag=aooni.altar_t,limit=1] text set value {"text":"전설의 검 · 버튼을 눌러 뽑아라","color":"gold","bold":true}
title @a[tag=aooni.player] times 10 60 20
title @a[tag=aooni.player] title {"text":"봉인이 모두 풀렸다","color":"gold","bold":true}
title @a[tag=aooni.player] subtitle {"text":"현관홀 제단에 전설의 검이 나타났다","color":"light_purple"}
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.beacon.activate master @s ~ ~ ~ 1 0.8
function aooni:game/progress
