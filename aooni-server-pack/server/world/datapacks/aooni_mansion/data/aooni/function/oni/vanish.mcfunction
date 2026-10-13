particle minecraft:large_smoke ~ ~1 ~ 0.4 0.8 0.4 0.02 40
playsound minecraft:entity.enderman.teleport hostile @a[distance=..24] ~ ~ ~ 1 0.5
execute if entity @s[tag=aooni.got] run tellraw @a[tag=aooni.alive] {"text":"아오오니는 사냥감을 끌고 어둠 속으로 사라졌다…","color":"dark_red","italic":true}
execute unless entity @s[tag=aooni.got] unless entity @s[tag=aooni.repel] run tellraw @a[tag=aooni.alive] {"text":"…발소리가 멀어졌다.","color":"gray","italic":true}
execute on passengers run kill @s
tag @s remove aooni.oni
tp @s ~ -120 ~
kill @s
function aooni:oni/reset_cd
