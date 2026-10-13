# 마검은 상자에 가둘 수 없다 → 상자 위로 튀어나온다
data remove block ~ ~ ~ Items[{id:"minecraft:netherite_sword"}]
summon minecraft:item ~ ~1 ~ {Item:{id:"minecraft:netherite_sword",count:1},PickupDelay:10s,Age:-32768s,Glowing:1b,Invulnerable:1b,Motion:[0.0d,0.0d,0.0d]}
playsound minecraft:block.chest.close block @a[distance=..16] ~ ~ ~ 1 0.6
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"마검은 상자에 가둘 수 없다! ","color":"gold"},{"text":"상자 위로 튀어나왔다.","color":"yellow"}]}
