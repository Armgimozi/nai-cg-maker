playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
execute if score #sheet aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 책장 사이에서 ","color":"white"},{"text":"[악보]","color":"gold","bold":true},{"text":"를 찾았다! 피아노실 악보대에 옮겨 두었다.","color":"white"}]}
scoreboard players set #sheet aooni.var 1
function aooni:piano/show_sheet with storage aooni:v
function aooni:game/progress
