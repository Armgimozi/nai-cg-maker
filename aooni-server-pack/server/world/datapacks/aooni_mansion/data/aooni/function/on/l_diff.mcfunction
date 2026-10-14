execute unless score #state aooni.var matches 0 run return 0
scoreboard players add #diff aooni.var 1
execute if score #diff aooni.var matches 4.. run scoreboard players set #diff aooni.var 1
function aooni:lobby/show_diff
execute if score #diff aooni.var matches 1 run tellraw @a {"text":"","extra":[{"text":"난이도: ","color":"gray"},{"text":"쉬움","color":"green","bold":true},{"text":"  (생존자 목숨 4개 · 5대 맞으면 쓰러짐 · 아오오니 기본 속도)","color":"gray"}]}
execute if score #diff aooni.var matches 2 run tellraw @a {"text":"","extra":[{"text":"난이도: ","color":"gray"},{"text":"보통","color":"yellow","bold":true},{"text":"  (생존자 목숨 3개 · 4대 맞으면 쓰러짐 · 아오오니 신속 I)","color":"gray"}]}
execute if score #diff aooni.var matches 3 run tellraw @a {"text":"","extra":[{"text":"난이도: ","color":"gray"},{"text":"어려움","color":"red","bold":true},{"text":"  (생존자 목숨 2개 · 3대 맞으면 쓰러짐 · 아오오니 신속 II)","color":"gray"}]}
playsound minecraft:ui.button.click master @s ~ ~ ~ 1 1.2
