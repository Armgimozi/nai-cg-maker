execute unless score #state aooni.var matches 0 run return run tellraw @s {"text":"이미 게임이 진행 중입니다.","color":"red"}
execute if score #cd aooni.var matches 1.. run return 0
execute unless score #built aooni.var matches 1.. run return run tellraw @s {"text":"저택을 짓는 중입니다. 잠시 후 다시 눌러 주세요.","color":"red"}
execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]
execute unless score #n aooni.var matches 4..6 run tellraw @a {"text":"","extra":[{"text":"※ 권장 인원은 4~6명입니다. (현재 ","color":"gray"},{"score":{"name":"#n","objective":"aooni.var"},"color":"gray"},{"text":"명) 그대로 시작합니다.","color":"gray"}]}
scoreboard players set #cd aooni.var 6
tellraw @a {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 님이 게임을 시작했습니다!","color":"green"}]}
