scoreboard players set #swlost aooni.var 0
function aooni:weapon/respawn
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"사라졌던 마검이 저택 어딘가에 다시 나타났다! ","color":"gold"},{"text":"(반짝이는 곳)","color":"yellow"}]}
