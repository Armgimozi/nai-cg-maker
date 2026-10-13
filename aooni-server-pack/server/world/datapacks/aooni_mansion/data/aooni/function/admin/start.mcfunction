scoreboard players set #cd aooni.var 0
execute store result score #n aooni.var if entity @a[gamemode=!creative,gamemode=!spectator]
execute if score #n aooni.var matches ..1 run return run tellraw @s {"text":"최소 2명(모험 모드)이 필요합니다.","color":"red"}
execute if score #state aooni.var matches 0 run function aooni:game/start
