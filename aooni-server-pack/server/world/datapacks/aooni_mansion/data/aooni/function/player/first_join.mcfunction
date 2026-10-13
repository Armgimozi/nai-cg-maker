tag @s add aooni.seen
scoreboard players set @s aooni.leave 0
execute if score #state aooni.var matches 1 run return run function aooni:player/watch
function aooni:player/to_lobby
tellraw @s {"text":"","extra":[{"text":"\n아오오니 저택","color":"blue","bold":true},{"text":"에 오신 것을 환영합니다!\n","color":"white"},{"text":"대기실의 ","color":"gray"},{"text":"[규칙 보기]","color":"aqua"},{"text":" 로 규칙을 보고, 아오오니를 하고 싶으면 ","color":"gray"},{"text":"[아오오니 지원]","color":"red"},{"text":", 모두 모이면 ","color":"gray"},{"text":"[게임 시작]","color":"green"},{"text":" (권장 4~6명)\n혼자라면 ","color":"gray"},{"text":"[혼자 연습]","color":"aqua"},{"text":" 버튼으로 미리 해 볼 수 있습니다.","color":"gray"}]}
