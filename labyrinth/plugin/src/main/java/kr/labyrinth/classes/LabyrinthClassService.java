package kr.labyrinth.classes;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.classes.skills.Skill;
import kr.labyrinth.classes.skills.SkillContext;
import kr.labyrinth.classes.skills.SkillFx;
import kr.labyrinth.classes.skills.SkillRegistry;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.WeaponTypes;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

/**
 * 직업 서비스 실제 구현: 전직/변경, 마나(WIS 재생, {@link ManaPool}), 쿨다운({@link CooldownTracker}, cooldown_slow 반영),
 * 직업 스킬 입력(F/웅크리기+F/Q/웅크리기+Q → {@link SkillRegistry} 의 {@link Skill}), 액션바 피드백.
 */
public final class LabyrinthClassService implements ClassService, SkillContext.Host {

    private static final double TICK_SECONDS = 0.1;

    private static final class PlayerState {
        ManaPool mana;
        final CooldownTracker cooldowns = new CooldownTracker();
        long channelUntil;
        long lastInputMs;
    }

    private final Services services;
    private final SkillRegistry registry = new SkillRegistry();
    private final Map<UUID, PlayerState> states = new ConcurrentHashMap<>();
    private BukkitTask task;

    public LabyrinthClassService(Services services) { this.services = services; }

    public SkillRegistry registry() { return registry; }

    public void start() {
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 2L, 2L);
    }

    public void stop() {
        if (task != null) task.cancel();
        states.clear();
    }

    public void forget(Player p) { states.remove(p.getUniqueId()); }

    private PlayerState state(Player p) {
        return states.computeIfAbsent(p.getUniqueId(), u -> {
            PlayerState s = new PlayerState();
            s.mana = new ManaPool(maxMana(p), System.currentTimeMillis());
            return s;
        });
    }

    // ── 직업 ──────────────────────────────────────────────────────────────

    @Override
    public ClassDef classOf(Player player) {
        return services.content().classDef(services.data().get(player).classId());
    }

    @Override
    public void setClass(Player player, String classId) {
        if (classId != null && services.content().classDef(classId) == null) return;
        PlayerData d = services.data().get(player);
        d.classId(classId);
        d.markDirty();
        services.stats().recalc(player);
        PlayerState s = state(player);
        s.cooldowns.clear();
        s.channelUntil = 0;
        s.mana.set(maxMana(player), System.currentTimeMillis());
        services.hud().refresh(player);
    }

    @Override
    public boolean changeClass(Player player, String classId) {
        ClassDef def = services.content().classDef(classId);
        if (def == null) {
            Text.error(player, "알 수 없는 직업입니다: " + Text.escape(String.valueOf(classId)));
            return false;
        }
        ClassDef cur = classOf(player);
        if (cur != null && cur.id().equals(def.id())) {
            Text.error(player, "이미 <" + def.color() + ">" + def.name() + "</" + def.color() + "> 입니다.");
            return false;
        }
        if (services.dungeon().currentInstance(player).isPresent()) {
            Text.error(player, "미궁 공략 중에는 직업을 바꿀 수 없습니다. 입구로 돌아간 뒤 다시 시도하세요.");
            return false;
        }
        setClass(player, def.id());
        String col = def.color();
        player.showTitle(Title.title(Text.mm("<" + col + "><b>" + def.name() + "</b>"),
                Text.mm("<gray>" + (cur == null ? "전직 완료" : "직업 변경 완료") + " — " + kr.labyrinth.core.InputKeys.CLASS_KEYS + " 로 스킬 사용")));
        Text.send(player, (cur == null ? "전직했습니다: " : "직업을 바꿨습니다: ") + "<" + col + "><b>" + def.name() + "</b></" + col + ">");
        for (ClassDef.SkillDef sk : def.skills()) {
            player.sendMessage(Text.mm(" <dark_gray>▪</dark_gray> <white>" + keyLabel(sk.input()) + "</white> <" + col + ">" + sk.name()
                    + "</" + col + "> <gray>(Lv." + sk.unlockLevel() + ", MP " + Text.num(sk.mana()) + ", " + fmt(sk.cooldown()) + "초)"));
        }
        if (def.passive() != null) {
            player.sendMessage(Text.mm(" <dark_gray>▪</dark_gray> <gold>패시브</gold> <" + col + ">" + def.passive().name() + "</" + col
                    + "> <gray>— " + Text.escape(def.passive().description())));
        }
        SkillFx.helix(player.getLocation(), 0.8, 2.4, 30, Particle.DUST, SkillFx.dust(rgb(col), 1.2f));
        SkillFx.sound(player.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 1.2f);
        giveStarterWeapon(player, def);
        return true;
    }

    /** 접속할 때: 직업은 있는데 추천 무기를 받은 적도 가진 것도 없으면(예전 판에서 전직한 사람) 한 번 지급. */
    public void ensureStarterWeapon(Player player) {
        ClassDef def = classOf(player);
        if (def != null) giveStarterWeapon(player, def);
    }

    /**
     * 직업 스킬은 아무 미궁 무기로나 나가지만 처음엔 손에 쥔 게 없으므로, 직업을 처음 골랐을 때 가방에 그 직업의 추천 무기가 없으면
     * 가장 낮은 등급 추천 무기를 하나 준다 ({@link WeaponTypes#starterWeapon}). 직업마다 한 번만 (PlayerData ext {@code class.starter.<직업>}).
     */
    private void giveStarterWeapon(Player player, ClassDef def) {
        PlayerData d = services.data().get(player);
        String flag = "class.starter." + def.id();
        if (Boolean.TRUE.equals(d.ext().get(flag))) return;
        for (org.bukkit.inventory.ItemStack it : player.getInventory().getContents()) {
            if (it == null || it.getType().isAir()) continue;
            ItemDef have = services.items().defOf(it).orElse(null);
            if (have != null && have.isWeapon() && def.recommendsWeapon(have.weaponType())) return;
        }
        ItemDef best = WeaponTypes.starterWeapon(services.content().items().values(), def);
        if (best == null || services.items().give(player, best.id(), 1, "starter") <= 0) return;
        d.ext().put(flag, true);
        d.markDirty();
        Text.send(player, "<gray>추천 무기를 받았습니다: <white>" + best.name() + "</white> <gray>— 손에 들고 <white>"
                + kr.labyrinth.core.InputKeys.CLASS_KEYS + "</white> 로 스킬을 씁니다 <dark_gray>(다른 미궁 무기도 되지만 추천 무기면 재사용 대기 −"
                + Text.pct(WeaponTypes.RECOMMENDED_COOLDOWN_CUT) + ")");
    }

    // ── 마나 ──────────────────────────────────────────────────────────────

    @Override
    public double maxMana(Player player) { return services.stats().get(player).maxMp(); }

    private double regen(Player p) { return services.stats().get(p).manaRegen(); }

    @Override
    public double mana(Player player) {
        return state(player).mana.current(maxMana(player), regen(player), System.currentTimeMillis());
    }

    @Override
    public boolean useMana(Player player, double amount) {
        boolean ok = state(player).mana.spend(amount, maxMana(player), regen(player), System.currentTimeMillis());
        if (ok) services.hud().refresh(player);
        return ok;
    }

    @Override
    public void restoreMana(Player player, double amount) {
        state(player).mana.restore(amount, maxMana(player), regen(player), System.currentTimeMillis());
        services.hud().refresh(player);
    }

    // ── SkillContext.Host ────────────────────────────────────────────────

    @Override
    public void refundMana(Player player, double amount) { restoreMana(player, amount); }

    @Override
    public void setCooldown(Player player, String skillId, double seconds) { state(player).cooldowns.set(skillId, seconds); }

    @Override
    public void setChannel(Player player, long untilMs) { state(player).channelUntil = untilMs; }

    @Override
    public boolean isChanneling(Player player) {
        PlayerState s = states.get(player.getUniqueId());
        return s != null && s.channelUntil > System.currentTimeMillis();
    }

    // ── 스킬 입력 ─────────────────────────────────────────────────────────

    @Override
    public boolean handleSkillInput(Player player, String input) {
        PlayerState st = state(player);
        long now = System.currentTimeMillis();
        if (now - st.lastInputMs < 120) return true; // 같은 키의 중복 이벤트
        st.lastInputMs = now;

        ClassDef cls = classOf(player);
        if (cls == null) {
            bar(player, "<gray>직업이 없습니다 — <white>/직업</white> 으로 전직하세요", 40);
            return true;
        }
        ClassDef.SkillDef sk = cls.skillByInput(input);
        if (sk == null) return false;
        String col = cls.color();
        ItemDef weapon = services.items().heldWeapon(player);
        if (!WeaponTypes.canCastClassSkill(cls, weapon)) {
            bar(player, "<#ff8080>미궁 무기를 들어야 합니다 <gray>(종류 무관 · 추천 " + weaponNames(cls) + ")", 40);
            deny(player);
            return true;
        }
        int level = services.data().get(player).level();
        if (level < sk.unlockLevel()) {
            bar(player, "<" + col + ">" + sk.name() + "</" + col + "> <#ff8080>— Lv." + sk.unlockLevel() + " 에 해금", 40);
            deny(player);
            return true;
        }
        if (services.effects().isStunned(player)) {
            bar(player, "<#ffe14a>✦ 기절 상태 — 행동할 수 없습니다", 30);
            return true;
        }
        if (services.effects().isSilenced(player)) {
            bar(player, "<#9a9aff>🔇 침묵 상태 — 스킬을 쓸 수 없습니다", 30);
            deny(player);
            return true;
        }
        if (st.channelUntil > now) {
            bar(player, "<gray>시전 중입니다...", 20);
            return true;
        }
        double cd = st.cooldowns.remaining(sk.id());
        if (cd > 0) {
            bar(player, "<" + col + ">" + sk.name() + "</" + col + "> <gray>재사용 대기 <white>" + fmt(cd) + "초", 30);
            deny(player);
            return true;
        }
        double cost = sk.mana();
        if (mana(player) + 1e-9 < cost) {
            bar(player, "<#6fc3ff>MP 부족 <gray>(" + Text.num(mana(player)) + " / " + Text.num(cost) + ")", 30);
            deny(player);
            return true;
        }
        Skill impl = registry.get(sk.id());
        if (impl == null) {
            Log.warnOnce("skill-missing-" + sk.id(), "[직업] 스킬 구현이 없습니다: " + sk.id());
            bar(player, "<gray>이 스킬은 아직 사용할 수 없습니다", 30);
            return true;
        }
        SkillContext ctx = new SkillContext(services, player, cls, sk, this, cost);
        boolean ok;
        try {
            ok = impl.cast(ctx);
        } catch (Throwable t) {
            Log.error("직업 스킬 오류: " + sk.id(), t);
            ok = false;
        }
        if (!ok) {
            if (ctx.failReason() != null) bar(player, ctx.failReason(), 35);
            deny(player);
            return true;
        }
        useMana(player, cost);
        // 채널링 스킬이 cancelCast 로 쿨다운을 이미 정했으면 덮어쓰지 않는다
        // 추천 무기면 기본 재사용 대기 −10% (레벨이 모자라 능력치가 안 붙는 무기는 제외), 그다음 재사용 감소 스탯
        if (st.cooldowns.ready(sk.id())) {
            double base = WeaponTypes.classSkillCooldown(cls, WeaponTypes.effective(weapon, level), sk.cooldown());
            st.cooldowns.start(sk.id(), CooldownTracker.effective(base, services.stats().get(player).cooldownReduction()));
        }
        bar(player, "<" + col + "><b>✦ " + sk.name() + "</b></" + col + ">  <#6fc3ff>MP " + Text.num(mana(player)) + "<gray>/"
                + Text.num(maxMana(player)), 30);
        return true;
    }

    @Override
    public double cooldownRemaining(Player player, String skillId) {
        PlayerState s = states.get(player.getUniqueId());
        return s == null ? 0 : s.cooldowns.remaining(skillId);
    }

    @Override
    public Component skillBar(Player player) {
        ClassDef cls = classOf(player);
        if (cls == null) return Component.empty();
        int level = services.data().get(player).level();
        StringBuilder sb = new StringBuilder();
        for (ClassDef.SkillDef sk : cls.skills()) {
            if (!sb.isEmpty()) sb.append(" <dark_gray>│</dark_gray> ");
            String key = keyLabel(sk.input());
            if (level < sk.unlockLevel()) {
                sb.append("<dark_gray>").append(key).append(" 🔒Lv.").append(sk.unlockLevel()).append("</dark_gray>");
                continue;
            }
            double cd = cooldownRemaining(player, sk.id());
            if (cd > 0) sb.append("<gray>").append(key).append(" <red>").append(fmt(cd)).append("s</red></gray>");
            else sb.append("<white>").append(key).append(" <").append(cls.color()).append(">").append(sk.name())
                    .append("</").append(cls.color()).append("></white>");
        }
        return Text.mm(sb.toString());
    }

    /** 무기를 손에 들었을 때 스킬 안내를 잠깐 보여 준다. */
    public void showSkillBar(Player player) {
        if (classOf(player) == null) return;
        services.hud().actionBar(player, skillBar(player), 50);
    }

    // ── 틱: 쿨다운 흐름 + 궁극기 준비 알림 ─────────────────────────────

    private void tick() {
        for (Map.Entry<UUID, PlayerState> e : states.entrySet()) {
            PlayerState s = e.getValue();
            if (s.cooldowns.isEmpty()) continue;
            Player p = Bukkit.getPlayer(e.getKey());
            if (p == null) continue;
            String ready = s.cooldowns.advance(TICK_SECONDS, services.effects().cooldownRate(p));
            if (ready != null) {
                ClassDef cls = classOf(p);
                ClassDef.SkillDef sk = cls == null ? null : cls.skills().stream().filter(x -> x.id().equals(ready)).findFirst().orElse(null);
                if (sk != null && "SNEAK_DROP".equals(sk.input())) {
                    SkillFx.sound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_CHIME, 0.6f, 1.6f);
                    bar(p, "<" + cls.color() + "><b>✦ " + sk.name() + "</b></" + cls.color() + "> <green>준비 완료", 30);
                } else if (sk != null) {
                    p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_HAT, 0.35f, 1.8f);
                }
            }
        }
    }

    // ── 표시 헬퍼 ─────────────────────────────────────────────────────────

    private void bar(Player p, String mm, int ticks) { services.hud().actionBar(p, Text.mm(mm), ticks); }

    private static void deny(Player p) { p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.5f, 0.6f); }

    public static String keyLabel(String input) {
        return kr.labyrinth.core.InputKeys.bracket(input);
    }

    public static String weaponName(String type) { return WeaponTypes.name(type); }

    /** 추천 무기 이름 목록 ("활", "검과 방패" …). */
    public static String weaponNames(ClassDef cls) {
        return String.join(", ", cls.weaponTypes().stream().map(LabyrinthClassService::weaponName).toList());
    }

    static String fmt(double s) { return s >= 10 ? String.valueOf(Math.round(s)) : String.format("%.1f", s); }

    private static int rgb(String hex) {
        try {
            return Integer.parseInt(hex.replace("#", ""), 16);
        } catch (RuntimeException e) {
            return 0xffffff;
        }
    }
}
