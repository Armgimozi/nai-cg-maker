playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"가방 속 쪽지: '④-2' 와 숫자 하나.","color":"gray","italic":true}
function aooni:clue/q2 with storage aooni:v
execute if score #q2 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 여행 가방에서 ","color":"white"},{"text":"봉인④의 둘째 자리","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
scoreboard players set #q2 aooni.var 1
