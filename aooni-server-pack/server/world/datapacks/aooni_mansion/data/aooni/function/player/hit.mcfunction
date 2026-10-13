# 아오오니에게 맞았다(같은 팀 아군 공격은 막혀 있으므로 맞힐 수 있는 건 아오오니뿐)
scoreboard players reset @s aooni.hit
execute if entity @s[tag=aooni.safe] run return 0
execute if entity @s[tag=aooni.hidden] run return 0
execute if score #freeze aooni.var matches 1.. run return 0
function aooni:player/caught
