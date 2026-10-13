execute unless score #state aooni.var matches 0 run return run tellraw @s {"text":"이미 게임이 진행 중입니다.","color":"red"}
execute if score #cd aooni.var matches 1.. run return run tellraw @s {"text":"게임 시작 카운트다운 중입니다.","color":"red"}
execute unless score #built aooni.var matches 1.. run return run tellraw @s {"text":"저택을 짓는 중입니다. 잠시 후 다시 눌러 주세요.","color":"red"}
execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]
execute if score #n aooni.var matches 0 run return run tellraw @s {"text":"크리에이티브 모드에서는 참가할 수 없습니다. /gamemode adventure 후 다시 눌러 주세요.","color":"red"}
execute unless score #n aooni.var matches 1 run return run tellraw @s {"text":"혼자 접속해 있을 때만 쓸 수 있습니다. 여럿이면 [게임 시작]을 누르세요.","color":"red"}
function aooni:test/solo
