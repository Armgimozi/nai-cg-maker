playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"빈 접시 위에 붉은 소스로 숫자가 쓰여 있다…","color":"gray","italic":true}
function aooni:clue/pw2 with storage aooni:v
execute if score #pw2 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 식당 접시에서 ","color":"white"},{"text":"봉인② 비밀번호","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
execute if score #pw2 aooni.var matches 0 run execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.4
scoreboard players set #pw2 aooni.var 1
