scoreboard players remove #cd aooni.var 1
execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]
execute if score #n aooni.var matches ..1 run scoreboard players set #cd aooni.var 0
execute if score #n aooni.var matches ..1 run return run tellraw @a {"text":"인원이 부족해 시작을 취소했습니다 (최소 2명).","color":"red"}
execute if score #cd aooni.var matches 0 run return run function aooni:game/start
execute store result storage aooni:v sec int 1 run scoreboard players get #cd aooni.var
function aooni:lobby/countdown_show with storage aooni:v
