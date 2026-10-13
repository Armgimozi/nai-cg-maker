# 인원 제한 없이 생존자 연습(모험 모드인 사람 모두 생존자, 연습용 AI 아오오니)
execute unless score #state aooni.var matches 0 run return run tellraw @s {"text":"게임이 끝난 뒤에 쓸 수 있습니다. (중단: /function aooni:admin/stop)","color":"red"}
execute unless entity @a[gamemode=!creative,gamemode=!spectator] run return run tellraw @s {"text":"모험 모드인 플레이어가 없습니다. (크리에이티브는 참가자에서 빠집니다)","color":"red"}
scoreboard players set #cd aooni.var 0
function aooni:test/solo
