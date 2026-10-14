scoreboard objectives add aooni.var dummy
scoreboard objectives add aooni.side dummy {"text":"아오오니 저택","color":"blue","bold":true}
scoreboard objectives add aooni.lives dummy
scoreboard objectives add aooni.gid dummy
scoreboard objectives add aooni.leave minecraft.custom:minecraft.leave_game
scoreboard objectives add aooni.grace dummy
scoreboard objectives add aooni.deaths deathCount
# 회복 음식을 먹었는지(먹은 횟수 통계)
scoreboard objectives add aooni.eb minecraft.used:minecraft.bread
scoreboard objectives add aooni.es minecraft.used:minecraft.cooked_beef
scoreboard objectives add aooni.wc dummy
# 연습 끝내기: OP 가 아니어도 /trigger aooni.quit
scoreboard objectives add aooni.quit trigger
team add aooni_alive
team modify aooni_alive displayName {"text":"생존자","color":"aqua"}
team modify aooni_alive color aqua
team modify aooni_alive collisionRule never
team modify aooni_alive friendlyFire false
team modify aooni_alive nametagVisibility hideForOtherTeams
team add aooni_oni
team modify aooni_oni displayName {"text":"아오오니","color":"dark_blue"}
team modify aooni_oni color dark_blue
team modify aooni_oni collisionRule never
team modify aooni_oni nametagVisibility never
team modify aooni_oni seeFriendlyInvisibles false
team modify aooni_oni friendlyFire false
team add aooni_out
team modify aooni_out color gray
team modify aooni_out collisionRule never
team modify aooni_out friendlyFire false
team modify aooni_out seeFriendlyInvisibles false
team add aooni_lobby
team modify aooni_lobby friendlyFire false
team modify aooni_lobby collisionRule never
bossbar add aooni:goal {"text":"목표","color":"white"}
bossbar set aooni:goal color blue
bossbar set aooni:goal max 4
bossbar add aooni:boss {"text":"아오오니","color":"dark_red","bold":true}
bossbar set aooni:boss color red
bossbar set aooni:boss style notched_10
execute unless score #state aooni.var matches 0..2 run scoreboard players set #state aooni.var 0
execute unless score #diff aooni.var matches 1..3 run scoreboard players set #diff aooni.var 2
execute unless score #gid aooni.var matches 0.. run scoreboard players set #gid aooni.var 0
execute unless score #test aooni.var matches 0..2 run scoreboard players set #test aooni.var 0
scoreboard players set #t aooni.var 0
scoreboard players set #60 aooni.var 60
scoreboard players set #2 aooni.var 2
function aooni:setup/gamerules
time set 18000
weather clear
difficulty normal
setworldspawn -21 -60 14
forceload add -32 -6 61 61
schedule function aooni:setup/check_build 2s
