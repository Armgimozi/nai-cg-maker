# 실행한 사람이 아오오니가 되어 승패 없이 둘러본다
execute unless score #state aooni.var matches 0 run return run tellraw @s {"text":"게임이 끝난 뒤에 쓸 수 있습니다. (중단: /function aooni:admin/stop)","color":"red"}
execute unless entity @s[type=minecraft:player,gamemode=!creative,gamemode=!spectator] run return run tellraw @s {"text":"모험 모드인 플레이어가 직접 실행해야 합니다.","color":"red"}
scoreboard players set #cd aooni.var 0
function aooni:test/solo_oni
