scoreboard players remove #freeze aooni.var 1
execute if score #freeze aooni.var matches 1.. as @a[tag=aooni.oni_p] run title @s actionbar {"text":"","extra":[{"text":"깨어나기까지 ","color":"gray"},{"score":{"name":"#freeze","objective":"aooni.var"},"color":"red"},{"text":"초…","color":"gray"}]}
execute if score #freeze aooni.var matches 0 run function aooni:game/oni_wake
