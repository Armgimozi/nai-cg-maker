# 오프라인으로 들고 나갔던 마검이 이미 다시 나타났다면, 돌아온 사람 것은 지운다(상자 속 마검도 먼저 꺼내서 센다)
execute as @e[type=minecraft:marker,tag=aooni.spot] at @s if data block ~ ~ ~ Items[{id:"minecraft:netherite_sword"}] run function aooni:weapon/unchest
execute store result score #sw aooni.var run clear @a minecraft:netherite_sword 0
execute store result score #swi aooni.var if entity @e[type=minecraft:item,nbt={Item:{id:"minecraft:netherite_sword"}}]
scoreboard players operation #sw aooni.var += #swi aooni.var
execute if score #sw aooni.var matches 2.. run clear @s minecraft:netherite_sword
function aooni:player/arm_check
