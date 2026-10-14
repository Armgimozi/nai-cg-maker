kill @e[tag=aooni.fx]
kill @e[type=minecraft:zombie,tag=aooni.oni]
# 이전 버전의 연습용 좀비가 남아 있으면 정리
kill @e[type=minecraft:zombie,tag=aooni.dummy]
function aooni:build/lobby
function aooni:build/mansion
function aooni:build/fixtures
kill @e[type=minecraft:item]
scoreboard players set #built aooni.var 7
function aooni:lobby/show_diff
execute if score #state aooni.var matches 0 as @a[gamemode=!creative] run function aooni:player/to_lobby
tellraw @a {"text":"","extra":[{"text":"[아오오니 저택] ","color":"blue"},{"text":"저택과 대기실을 지었습니다.","color":"gray"}]}
