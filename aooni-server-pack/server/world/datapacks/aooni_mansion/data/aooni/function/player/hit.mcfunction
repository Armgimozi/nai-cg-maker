# 아오오니에게 맞았다(같은 팀 아군 공격은 막혀 있으므로 맞힐 수 있는 건 아오오니뿐)
scoreboard players reset @s aooni.hit
execute if entity @s[tag=aooni.safe] run return 0
execute if entity @s[tag=aooni.hidden] run return 0
execute if score #freeze aooni.var matches 1.. run return 0
scoreboard players set #byoni aooni.var 0
execute on attacker if entity @s[tag=aooni.oni_p] run scoreboard players set #byoni aooni.var 1
execute on attacker if entity @s[tag=aooni.dummy] run scoreboard players set #byoni aooni.var 1
execute if score #byoni aooni.var matches 0 run return 0
function aooni:player/caught
