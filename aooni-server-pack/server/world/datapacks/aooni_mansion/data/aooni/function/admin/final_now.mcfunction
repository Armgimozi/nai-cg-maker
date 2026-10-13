# 테스트용: 봉인을 모두 풀고 생존자 한 명에게 검을 줘서 바로 결전
execute unless score #state aooni.var matches 1 run return run tellraw @s {"text":"게임 중에만 쓸 수 있습니다.","color":"red"}
scoreboard players set #w1 aooni.var 1
scoreboard players set #w2 aooni.var 1
scoreboard players set #w3 aooni.var 1
scoreboard players set #w4 aooni.var 1
scoreboard players set #oni_on aooni.var 1
function aooni:game/progress
function aooni:altar/check
scoreboard players set #wpn aooni.var 1
kill @e[type=minecraft:item_display,tag=aooni.altar_item]
execute as @r[tag=aooni.alive] run function aooni:weapon/give
function aooni:final/check
