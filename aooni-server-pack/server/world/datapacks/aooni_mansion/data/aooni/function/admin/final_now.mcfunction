# 테스트용: 숫자를 다 찾은 것으로 하고 생존자 한 명에게 마검을 줘서 바로 결전
execute unless score #state aooni.var matches 1 run return run tellraw @s {"text":"게임 중에만 쓸 수 있습니다.","color":"red"}
execute if score #wpn aooni.var matches 1 run return run tellraw @s {"text":"이미 결전 중입니다.","color":"red"}
scoreboard players set #found aooni.var 4
scoreboard players set #freeze aooni.var 1
scoreboard players set #wpn aooni.var 1
execute as @r[tag=aooni.alive] run function aooni:weapon/give
function aooni:final/start
