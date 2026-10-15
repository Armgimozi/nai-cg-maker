"""PvP 최종안 설정 (pvp_spec) — pv_sim / pv_duel 이 쓰는 dict."""
import pv_sim as S

CC_MULT = {"stun": 0.8, "frozen": 1.0, "root": 0.8, "silence": 0.8, "blind": 0.7, "slow": 1.0, "cooldown_slow": 0.5}
CC_CAP = {"stun": 1.0, "frozen": 1.5, "root": 1.5, "silence": 1.5, "blind": 1.5, "slow": 3.0, "cooldown_slow": 2.0}
SLOW_POTENCY_CAP = 0.5
DR = dict(window=8.0, steps=[1.0, 0.5, 0.25, 0.0], cats=("control", "root", "silence", "blind"))
CLASS_MULT = {"guardian": 1.0, "berserker": 1.0, "hunter": 0.9, "arcanist": 1.2, "priest": 1.0, "shadow": 1.2}
SKILL_CAP = 2.5


def make(**kw):
    P = dict(S.PVP_NOCAP)
    P.update(name="새 PvP", dmg=2.0, level_curve=dict(ref=20, exp=2.35), buffer=dict(low_per_level=42.0, knee=20, per_level=12.0),
             def_weight=0.0, res=dict(cap=0.4, k=8), crit_scale=0.6, ult=1.0, wskill=1.0,
             skill_mult=S.skill_mults(SKILL_CAP), heal=0.6, potion=0.6, lifesteal=0.5, shield=0.8,
             dampening=dict(start=20, per_s=0.025, floor=0.1), class_mult=dict(CLASS_MULT),
             cc_mult=dict(CC_MULT), cc_cap=dict(CC_CAP), dr=dict(DR), stun_immune=2.0,
             slow_cap=SLOW_POTENCY_CAP)
    P.update(kw)
    return P


PVP_NEW = make()
