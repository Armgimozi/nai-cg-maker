tag @s add aooni.out
team join aooni_out @s
gamemode spectator @s
tp @s 23 -45 18 0 60
tellraw @a {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 은(는) 더 이상 돌아오지 못했다… (탈락)","color":"dark_gray"}]}
