playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"김 서린 거울에 손가락으로 쓴 숫자가 떠오른다…","color":"gray","italic":true}
function aooni:clue/pw1 with storage aooni:v
execute if score #pw1 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 화장실 거울에서 ","color":"white"},{"text":"봉인① 비밀번호","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
execute if score #pw1 aooni.var matches 0 run execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.4
scoreboard players set #pw1 aooni.var 1
