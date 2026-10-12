playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"가방 속 쪽지에 숫자가 적혀 있다…","color":"gray","italic":true}
function aooni:clue/show4 with storage aooni:v
execute if score #f4 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 여행 가방에서 숫자 단서 ","color":"white"},{"text":"④","color":"gold","bold":true},{"text":" 를 발견했다!","color":"white"}]}
scoreboard players set #f4 aooni.var 1
