scoreboard players set @s aooni.quit 0
scoreboard players enable @s aooni.quit
execute unless score #state aooni.var matches 1 run return run tellraw @s {"text":"진행 중인 연습이 없습니다.","color":"gray"}
execute unless score #test aooni.var matches 1.. run return run tellraw @s {"text":"실전은 이 명령으로 끝낼 수 없습니다. (관리자: /function aooni:admin/stop)","color":"red"}
tellraw @a {"text":"","extra":[{"text":"[아오오니 저택] ","color":"blue"},{"selector":"@s","color":"aqua"},{"text":" 님이 연습을 끝냈습니다.","color":"gray"}]}
function aooni:game/reset
