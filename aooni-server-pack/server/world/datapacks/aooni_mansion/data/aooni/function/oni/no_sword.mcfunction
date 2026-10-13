# 아오오니는 마검을 가질 수 없다. 주우면 금고 앞으로 돌려보낸다
execute store result score #c aooni.var run clear @s minecraft:netherite_sword 0
execute if score #c aooni.var matches 0 run return 0
clear @s minecraft:netherite_sword
summon minecraft:item 41.5 -54 3.5 {Item:{id:"minecraft:netherite_sword",count:1},PickupDelay:10s,Age:-32768s,Glowing:1b,Invulnerable:1b,Motion:[0.0d,0.0d,0.0d]}
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"마검이 아오오니의 손을 거부했다! ","color":"gold"},{"text":"마검은 2층 창고 금고 앞으로 돌아갔다.","color":"yellow"}]}
