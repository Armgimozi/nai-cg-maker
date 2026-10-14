# 결전 중 쓰러졌다면 승리 처리, 그 밖의 사고(관리자 /kill 등)면 아오오니로 되돌린다
execute if score #final aooni.var matches 1 run return run function aooni:oni/defeated
function aooni:oni/effects
tp @s 48.5 -45 33.5 0 0
