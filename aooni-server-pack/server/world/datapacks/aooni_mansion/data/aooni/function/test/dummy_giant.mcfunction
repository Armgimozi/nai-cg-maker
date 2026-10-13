# 좀비는 즉시 회복 물약에 오히려 다치므로 체력을 직접 채운다
tag @s add aooni.giant
$attribute @s minecraft:max_health base set $(hp)
$data merge entity @s {Health:$(hp)f}
attribute @s minecraft:scale base set 1.3
function aooni:oni/model_big
execute store result score #bhp_prev aooni.var run data get entity @s Health 10
particle minecraft:large_smoke ~ ~1.5 ~ 0.8 1.2 0.8 0.03 120
playsound minecraft:entity.ravager.roar master @a[distance=..48] ~ ~ ~ 2 0.5
