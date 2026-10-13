execute store result bossbar aooni:goal value run scoreboard players get #found aooni.var
scoreboard players set #goal aooni.var 1
execute if score #found aooni.var matches 4.. run scoreboard players set #goal aooni.var 2
execute if score #wpn aooni.var matches 1 run scoreboard players set #goal aooni.var 3
execute if score #goal aooni.var matches 1 run bossbar set aooni:goal name {"text":"","extra":[{"text":"숫자 ","color":"gray"},{"score":{"name":"#found","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"상자를 열어 비밀번호 쪽지 4장을 찾아라","color":"white"}]}
execute if score #goal aooni.var matches 2 run bossbar set aooni:goal name {"text":"","extra":[{"text":"숫자 ","color":"gray"},{"score":{"name":"#found","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"2층 창고 금고에 비밀번호를 넣어 마검을 꺼내라!","color":"white"}]}
execute if score #goal aooni.var matches 3 run bossbar set aooni:goal name {"text":"","extra":[{"text":"숫자 ","color":"gray"},{"score":{"name":"#found","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"마검으로 아오오니를 족쳐라!","color":"white"}]}
