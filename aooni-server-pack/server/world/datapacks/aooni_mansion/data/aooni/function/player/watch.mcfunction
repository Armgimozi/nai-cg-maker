function aooni:player/clear_tags
team join aooni_out @s
gamemode spectator @s
tp @s 23 -45 18 0 60
tellraw @s {"text":"게임이 진행 중입니다. 다음 판까지 관전 모드로 지켜보세요.","color":"gray"}
execute if score #test aooni.var matches 1.. run scoreboard players enable @s aooni.quit
execute if score #test aooni.var matches 1.. run tellraw @s {"text":"","extra":[{"text":"지금은 혼자 연습 중입니다. 끝내려면 ","color":"gray"},{"text":"/trigger aooni.quit","color":"yellow"}]}
