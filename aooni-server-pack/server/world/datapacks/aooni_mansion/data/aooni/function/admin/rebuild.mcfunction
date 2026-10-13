scoreboard players set #built aooni.var 0
execute unless score #state aooni.var matches 0 run tellraw @s {"text":"게임이 끝나면 다시 짓습니다.","color":"gray"}
function aooni:setup/check_build
