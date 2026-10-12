playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"빈 접시 위에 붉은 소스로 숫자가 쓰여 있다…","color":"gray","italic":true}
function aooni:clue/show3 with storage aooni:v
execute if score #f3 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 접시에서 숫자 단서 ","color":"white"},{"text":"③","color":"gold","bold":true},{"text":" 를 발견했다!","color":"white"}]}
scoreboard players set #f3 aooni.var 1
