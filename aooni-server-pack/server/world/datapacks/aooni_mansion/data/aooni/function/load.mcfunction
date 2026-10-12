scoreboard objectives add aooni.var dummy
scoreboard objectives add aooni.side dummy {"text":"아오오니 저택","color":"blue","bold":true}
scoreboard objectives add aooni.lives dummy
scoreboard objectives add aooni.gid dummy
scoreboard objectives add aooni.leave minecraft.custom:minecraft.leave_game
scoreboard objectives add aooni.grace dummy
scoreboard objectives add aooni.hidet dummy
scoreboard objectives add aooni.life dummy
scoreboard objectives add aooni.lost dummy
scoreboard objectives add aooni.tgt dummy
scoreboard objectives add aooni.deaths deathCount
team add aooni_alive
team modify aooni_alive displayName {"text":"생존자","color":"aqua"}
team modify aooni_alive color aqua
team modify aooni_alive collisionRule never
team modify aooni_alive friendlyFire false
team add aooni_oni
team modify aooni_oni color dark_blue
team modify aooni_oni collisionRule never
team modify aooni_oni nametagVisibility never
team modify aooni_oni seeFriendlyInvisibles false
team modify aooni_oni friendlyFire false
team add aooni_out
team modify aooni_out color gray
team modify aooni_out collisionRule never
bossbar add aooni:goal {"text":"목표","color":"white"}
bossbar set aooni:goal color blue
bossbar set aooni:goal max 8
execute unless score #state aooni.var matches 0..2 run scoreboard players set #state aooni.var 0
execute unless score #diff aooni.var matches 1..3 run scoreboard players set #diff aooni.var 2
execute unless score #gid aooni.var matches 0.. run scoreboard players set #gid aooni.var 0
scoreboard players set #t aooni.var 0
scoreboard players set #60 aooni.var 60
function aooni:setup/gamerules
time set 18000
weather clear
difficulty normal
setworldspawn -21 -60 14
forceload add -32 -4 50 50
schedule function aooni:setup/check_build 2s
