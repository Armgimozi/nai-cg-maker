# 떨어진 마검은 사라지지 않고 반짝이게, 어디에도 없으면(소지자 퇴장 등) 10초 뒤 다시 나타나게
execute as @e[type=minecraft:item,nbt={Item:{id:"minecraft:netherite_sword"}}] run data merge entity @s {Age:-32768s,Invulnerable:1b,Glowing:1b}
execute store result score #sw aooni.var run clear @a minecraft:netherite_sword 0
execute store result score #swi aooni.var if entity @e[type=minecraft:item,nbt={Item:{id:"minecraft:netherite_sword"}}]
scoreboard players operation #sw aooni.var += #swi aooni.var
execute if score #sw aooni.var matches 1.. run scoreboard players set #swlost aooni.var 0
execute if score #sw aooni.var matches 0 run scoreboard players add #swlost aooni.var 1
execute if score #swlost aooni.var matches 10.. run function aooni:weapon/lost
# 어떤 이유로든 2개가 되면 바닥에 떨어진 쪽을 하나 지운다
execute if score #sw aooni.var matches 2.. if score #swi aooni.var matches 1.. run kill @e[type=minecraft:item,nbt={Item:{id:"minecraft:netherite_sword"}},limit=1]
