scoreboard players set #stairs aooni.var 1
fill 16 -60 12 16 -59 12 minecraft:air
setblock 16 -60 12 minecraft:iron_door[half=lower,facing=north,hinge=left,open=true]
setblock 16 -59 12 minecraft:iron_door[half=upper,facing=north,hinge=left,open=true]
fill 17 -60 12 17 -59 12 minecraft:air
setblock 17 -60 12 minecraft:iron_door[half=lower,facing=north,hinge=right,open=true]
setblock 17 -59 12 minecraft:iron_door[half=upper,facing=north,hinge=right,open=true]
tag @e[type=minecraft:marker,tag=aooni.z4] add aooni.on
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 1
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.iron_door.open master @s ~ ~ ~ 0.7 0.5
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"♪ 아름다운 선율이 끝나자, 어딘가에서 ","color":"light_purple"},{"text":"계단의 철문","color":"gold"},{"text":"이 열리는 소리가 났다! 피아노 뚜껑 안쪽에 숫자가 새겨져 있다…","color":"light_purple"}]}
function aooni:clue/pw3 with storage aooni:v
execute if score #pw3 aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 피아노 뚜껑에서 ","color":"white"},{"text":"봉인③ 비밀번호","color":"gold","bold":true},{"text":"를 찾았다!","color":"white"}]}
execute if score #pw3 aooni.var matches 0 run execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.4
scoreboard players set #pw3 aooni.var 1
function aooni:game/progress
