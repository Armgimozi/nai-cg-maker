playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"","extra":[{"text":"부부의 일기: ","color":"gray","italic":true},{"text":"'아이방, 손님방, 작업실, 그리고 우리 방. 네 방의 발판을 동시에 밟으면 창고가 열린다.' ","color":"dark_aqua"},{"text":"마지막 장 귀퉁이에 숫자가 적혀 있다.","color":"gray","italic":true}]}
tellraw @s {"text":"'④-4'","color":"gray","italic":true}
function aooni:clue/q4 with storage aooni:v
execute if score #q4 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 부부의 일기에서 ","color":"white"},{"text":"봉인④의 넷째 자리","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
scoreboard players set #q4 aooni.var 1
