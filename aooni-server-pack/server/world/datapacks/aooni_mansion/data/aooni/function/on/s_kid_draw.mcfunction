playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"크레파스로 그린 파란 괴물. 구석에 '④-1' 과 숫자가…","color":"gray","italic":true}
function aooni:clue/q1 with storage aooni:v
execute if score #q1 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 아이방 그림에서 ","color":"white"},{"text":"봉인④의 첫째 자리","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
scoreboard players set #q1 aooni.var 1
