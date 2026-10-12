playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"김 서린 거울에 손가락으로 쓴 글씨가 있다…","color":"gray","italic":true}
function aooni:clue/show1 with storage aooni:v
execute if score #f1 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 거울에서 숫자 단서 ","color":"white"},{"text":"①","color":"gold","bold":true},{"text":" 를 발견했다!","color":"white"}]}
scoreboard players set #f1 aooni.var 1
