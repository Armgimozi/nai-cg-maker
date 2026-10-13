playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"거울 속, 내 어깨 너머로 파란 무언가가… 돌아보니 아무도 없다.","color":"gray","italic":true}
effect give @s minecraft:darkness 3 0 true
playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 0.6 1.2
tellraw @s {"text":"거울 아래에 '④-3' 과 숫자가 긁혀 있다…","color":"gray","italic":true}
function aooni:clue/q3 with storage aooni:v
execute if score #q3 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 다락방 거울에서 ","color":"white"},{"text":"봉인④의 셋째 자리","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
scoreboard players set #q3 aooni.var 1
