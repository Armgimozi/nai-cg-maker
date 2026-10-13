# 아오오니는 마검을 가질 수 없다. 주우면 금고 앞으로 돌려보낸다
execute store result score #c aooni.var run clear @s minecraft:netherite_sword 0
execute if score #c aooni.var matches 0 run return 0
clear @s minecraft:netherite_sword
function aooni:weapon/respawn
execute if score #wmsg aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"마검이 아오오니의 손을 거부했다! ","color":"gold"},{"text":"마검은 저택 어딘가로 날아갔다(반짝이는 곳).","color":"yellow"}]}
scoreboard players set #wmsg aooni.var 5
