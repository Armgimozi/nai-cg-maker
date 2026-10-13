execute unless score #state aooni.var matches 1 run return 0
tag @s add aooni.oni_dead
execute unless entity @a[tag=aooni.lasthit] run tag @a[tag=aooni.armed] add aooni.lasthit
function aooni:game/victory
