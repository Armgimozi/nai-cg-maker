playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"크레파스로 그린 파란 괴물. 구석에 숫자가 적혀 있다…","color":"gray","italic":true}
function aooni:clue/show2 with storage aooni:v
execute if score #f2 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 그림에서 숫자 단서 ","color":"white"},{"text":"②","color":"gold","bold":true},{"text":" 를 발견했다!","color":"white"}]}
scoreboard players set #f2 aooni.var 1
