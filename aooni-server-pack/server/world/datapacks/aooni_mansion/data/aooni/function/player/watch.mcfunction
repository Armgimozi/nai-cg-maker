function aooni:player/clear_tags
team join aooni_out @s
gamemode spectator @s
tp @s 23 -45 18 0 60
tellraw @s {"text":"게임이 진행 중입니다. 다음 판까지 관전 모드로 지켜보세요.","color":"gray"}
