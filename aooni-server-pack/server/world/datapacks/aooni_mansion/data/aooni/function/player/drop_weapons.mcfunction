# 잡힌 자리에 마검을 떨어뜨린다. 반짝여서 멀리서도 보인다
execute store result score #c aooni.var run clear @s minecraft:netherite_sword 0
execute if score #c aooni.var matches 1.. run summon minecraft:item ~ ~1 ~ {Item:{id:"minecraft:netherite_sword",count:1},PickupDelay:30s,Age:-32768s,Glowing:1b,Invulnerable:1b}
execute if score #c aooni.var matches 1.. run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"마검이 바닥에 떨어졌다! ","color":"gold","bold":true},{"text":"누군가 주워서 싸워야 한다!","color":"yellow"}]}
clear @s minecraft:netherite_sword
function aooni:player/arm_check
