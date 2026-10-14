tag @s add aooni.jailed
team join aooni_out @s
effect give @s minecraft:resistance infinite 4 true
tp @s 6.5 -60 5.5 180 0
tellraw @s {"text":"","extra":[{"text":"감옥에 갇혔다. 동료가 감옥 입구의 버튼을 누르면 풀려난다. 남은 목숨: ","color":"gray"},{"score":{"name":"@s","objective":"aooni.lives"},"color":"yellow"}]}
