package kr.labyrinth.classes.skills;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.core.Text;
import net.kyori.adventure.title.Title;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/** 사제 (힐러): 치유의 빛 · 정화의 파동 · 성스러운 가호 · 부활의 성가. 치유·버프는 아군(TargetFilter)에게만. */
public final class PriestSkills {

    private PriestSkills() {}

    public static List<Skill> all() { return List.of(new HealingLight(), new PurifyingWave(), new SacredWard(), new ResurrectionHymn()); }

    static final class HealingLight implements Skill {
        public String id() { return "healing_light"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Player target = c.targets().lookedAtAlly(c.p("range", 20));
            if (target == null) {
                if (!c.flag("self_if_no_target", true)) return c.fail("<#ff8080>치유할 아군을 바라보세요");
                target = p;
            }
            double healed = c.heal(target, c.p("heal", 0.18));
            Location feet = target.getLocation();
            SkillFx.ground(c.fx("fx", "heal_glyph"), feet, 1.8, 20, 4);
            SkillFx.helix(feet, 0.6, 2.0, 20, Particle.DUST, SkillFx.dust(0xd8ffb0, 1.0f));
            SkillFx.burst(feet.clone().add(0, 1.2, 0), Particle.HAPPY_VILLAGER, 10, 0.4, 0, null);
            if (!target.equals(p)) SkillFx.line(p.getEyeLocation(), feet.clone().add(0, 1.2, 0), 0.5, Particle.END_ROD, null);
            SkillFx.sound(feet, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 1f, 1.4f);
            if (!target.equals(p) && healed >= 1 && c.services().hud().skillMessages()) {
                c.services().hud().actionBar(target, Text.mm("<#ffe58a>✚ " + Text.escape(p.getName()) + "</#ffe58a><gray> 님이 <green>"
                        + Text.num(healed) + "</green> 회복시켰습니다"), 30);
            }
            return true;
        }
    }

    static final class PurifyingWave implements Skill {
        public String id() { return "purifying_wave"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double radius = c.p("radius", 8);
            Location center = p.getLocation();
            SkillFx.ground(c.fx("fx", "holy_wave"), center, radius * 2, 16, 8);
            SkillFx.circle(center.clone().add(0, 0.3, 0), radius, 48, Particle.END_ROD, null);
            SkillFx.sound(center, Sound.BLOCK_BEACON_ACTIVATE, 0.8f, 1.6f);
            SkillFx.sound(center, Sound.BLOCK_BELL_RESONATE, 0.6f, 1.4f);
            boolean cleanse = c.flag("cleanse", true);
            for (Player a : c.targets().alliesIn(center, radius)) {
                if (cleanse) c.services().effects().cleanse(a);
                c.heal(a, c.p("heal", 0.08));
                SkillFx.burst(a.getLocation().add(0, 1, 0), Particle.END_ROD, 8, 0.3, 0.05, null);
            }
            for (LivingEntity e : c.targets().enemiesIn(center, radius)) {
                c.damage(e, c.p("damage", 0.8), DamageType.MAGIC);
                SkillFx.burst(e.getLocation().add(0, e.getHeight() * 0.6, 0), Particle.DUST, 10, 0.3, 0, SkillFx.dust(0xfff4d6, 1.2f));
            }
            return true;
        }
    }

    static final class SacredWard implements Skill {
        public String id() { return "sacred_ward"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double radius = c.p("radius", 12);
            double duration = c.p("duration", 6);
            double healPower = c.stats().healPower();
            SkillFx.sound(p.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 1f, 1.5f);
            SkillFx.sound(p.getLocation(), Sound.ITEM_ARMOR_EQUIP_GOLD, 1f, 1.2f);
            int n = 0;
            for (Player a : c.targets().alliesIn(p.getLocation(), radius)) {
                double amount = c.services().stats().maxHp(a) * c.p("shield", 0.15) + healPower * c.p("heal_power_scale", 0.5);
                c.services().effects().addShield(a, amount, duration, "sacred_ward");
                c.services().effects().applyBuff(a, Map.of("damage", c.p("damage_buff", 0.10)), duration, "sacred_ward");
                SkillFx.helix(a.getLocation(), 0.7, 2.4, 28, Particle.DUST, SkillFx.dust(0xffe58a, 1.2f));
                if (!a.equals(p) && c.services().hud().skillMessages()) {
                    c.services().hud().actionBar(a, Text.mm("<#ffe58a>✦ 성스러운 가호 <gray>— 보호막 <white>" + Text.num(amount)
                            + "</white> · 피해 +" + Text.pct(c.p("damage_buff", 0.10))), 40);
                }
                n++;
            }
            SkillFx.circle(p.getLocation().add(0, 0.2, 0), radius, 60, Particle.DUST, SkillFx.dust(0xffe58a, 1.0f));
            return n > 0;
        }
    }

    static final class ResurrectionHymn implements Skill {
        public String id() { return "resurrection_hymn"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double channel = c.p("channel", 3.0);
            int ticks = (int) Math.round(channel * 20);
            c.channel(channel + 0.2);
            c.services().effects().applyBuff(p, Map.of("move_speed", -c.p("move_slow", 0.6)), channel + 0.2, "resurrection_hymn");
            ItemDisplay pillar = SkillFx.spawn(c.fx("fx", "hymn_pillar"), p.getLocation(), 1f, ticks + 10);
            SkillFx.sound(p.getLocation(), Sound.BLOCK_BEACON_AMBIENT, 1.2f, 1.4f);
            Text.send(p, "<#ffe58a>부활의 성가를 부릅니다... <gray>(" + channel + "초)");
            double hp0 = c.services().stats().currentHp(p);
            boolean interruptOnDamage = c.flag("interrupt_on_damage", false);
            Location anchor = p.getLocation();
            SkillTask.repeat(0, 2, ticks / 2 + 1, step -> {
                boolean broken = !p.isOnline() || p.isDead() || !p.getWorld().equals(anchor.getWorld())
                        || c.services().effects().isStunned(p) || c.services().effects().isSilenced(p)
                        || (interruptOnDamage && c.services().stats().currentHp(p) < hp0 - 0.5);
                if (broken) {
                    c.services().hud().clearCast(p);
                    SkillFx.remove(pillar);
                    c.services().effects().removeBuff(p, "resurrection_hymn");
                    c.cancelCast(true, 10);
                    if (p.isOnline()) Text.error(p, "부활의 성가가 끊겼습니다.");
                    return false;
                }
                if (pillar != null && pillar.isValid()) pillar.teleport(p.getLocation());
                double prog = (double) step / (ticks / 2.0);
                SkillFx.circle(p.getLocation().add(0, 0.1 + prog * 2.4, 0), 1.2 - prog * 0.6, 12, Particle.END_ROD, null);
                if (step % 5 == 0) SkillFx.sound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_CHIME, 0.7f, 0.8f + (float) prog);
                c.services().hud().castBar(p, Text.mm("<#ffe58a>♪ 부활의 성가"), prog, 6);
                if (step * 2 >= ticks) {
                    finish(c, p, pillar);
                    return false;
                }
                return true;
            }, null);
            return true;
        }

        private static void finish(SkillContext c, Player p, ItemDisplay pillar) {
            c.endChannel();
            c.services().hud().clearCast(p);
            SkillFx.remove(pillar);
            c.services().effects().removeBuff(p, "resurrection_hymn");
            Location at = p.getLocation();
            List<Player> revived = new ArrayList<>();
            for (Player m : c.services().party().onlineMembers(p)) {
                if (m.equals(p) || !c.services().dungeon().isDowned(m) || !m.getWorld().equals(p.getWorld())) continue;
                if (!c.targets().isAlly(m)) continue;
                if (c.services().dungeon().revive(m, at, c.p("revive_hp", 0.40))) {
                    revived.add(m);
                    m.showTitle(Title.title(Text.mm("<#ffe58a><b>부활</b>"), Text.mm("<gray>" + Text.escape(p.getName()) + " 님의 성가")));
                    SkillFx.helix(m.getLocation(), 0.8, 3, 40, Particle.END_ROD, null);
                }
            }
            for (Player a : c.targets().alliesIn(at, c.p("radius", 20))) c.heal(a, c.p("heal", 0.30));
            SkillFx.burst(at.clone().add(0, 1, 0), Particle.TOTEM_OF_UNDYING, 60, 1.0, 0.4, null);
            SkillFx.ground(c.fx("fx_ring", "holy_wave"), at, 8, 16, 8);
            SkillFx.sound(at, Sound.ITEM_TOTEM_USE, 0.8f, 1.3f);
            SkillFx.sound(at, Sound.BLOCK_BELL_USE, 1f, 1.6f);
            Text.send(p, revived.isEmpty() ? "<#ffe58a>성가가 울려 퍼졌습니다. <gray>(쓰러진 동료 없음 — 주변 아군 회복)"
                    : "<#ffe58a>성가가 <white>" + revived.size() + "</white>명의 동료를 일으켰습니다!");
        }

    }
}
