package kr.labyrinth.classes;

import java.util.ArrayList;
import java.util.List;
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
import kr.labyrinth.core.Settings;
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
 * 직업 서비스 실제 구현: 전직/변경({@link ClassChangeGate} 관문 · 시작 무기·시작 꾸러미), 마나(WIS 재생, {@link ManaPool}), 쿨다운({@link CooldownTracker}, cooldown_slow 반영),
 * 직업 스킬 입력(F/웅크리기+F/Q/웅크리기+Q → {@link SkillRegistry} 의 {@link Skill}), 액션바 피드백.
 */
public final class LabyrinthClassService implements ClassService, SkillContext.Host {

    private static final double TICK_SECONDS = 0.1;
    /** 기존 플레이어가 접속 때 시작 꾸러미를 받을 수 있는 최대 레벨. */
    static final int KIT_JOIN_MAX_LEVEL = 5;

    private static final class PlayerState {
        ManaPool mana;
        final CooldownTracker cooldowns = new CooldownTracker();
        long channelUntil;
        long lastInputMs;
    }

    private final Services services;
    private final SkillRegistry registry = new SkillRegistry();
    private final Map<UUID, PlayerState> states = new ConcurrentHashMap<>();
    private final ClassChangeGate gate;
    private BukkitTask task;

    public LabyrinthClassService(Services services) {
        this.services = services;
        this.gate = new ClassChangeGate(services);
    }

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

    /** 직업 변경 관문 (첫 선택 무료 · 전직의 두루마리 · 대기 시간 · 미궁 공략 중 금지). 직업 메뉴도 같은 판정을 쓴다. */
    public ClassChangeGate gate() { return gate; }

    @Override
    public boolean changeClass(Player player, String classId) {
        ClassDef def = services.content().classDef(classId);
        if (def == null) {
            Text.error(player, "알 수 없는 직업입니다: " + Text.escape(String.valueOf(classId)));
            return false;
        }
        ClassDef cur = classOf(player);
        return gate.run(player, cur, def, () -> applyClass(player, def, cur));
    }

    /**
     * 관리자 강제 변경 (/labadmin setclass): 관문(두루마리·대기 시간·미궁 공략 중)을 거치지 않고 변경 시각 기록도 건드리지 않는다.
     * classId null = 직업 없음 (다음 선택은 첫 선택처럼 무료). @return 바뀌었으면 true
     */
    public boolean adminSetClass(Player player, String classId) {
        ClassDef cur = classOf(player);
        if (classId == null) {
            if (cur == null) return false;
            setClass(player, null);
            Text.send(player, "<gray>관리자가 직업을 비웠습니다. <white>/직업</white> 으로 새 직업을 고르세요 (무료).");
            return true;
        }
        ClassDef def = services.content().classDef(classId);
        if (def == null || (cur != null && cur.id().equals(def.id()))) return false;
        applyClass(player, def, cur);
        return true;
    }

    /** 직업 적용 + 안내(제목·스킬 목록·패시브) + 연출 + 시작 무기·꾸러미. 검사는 부르는 쪽(관문·관리자). */
    private void applyClass(Player player, ClassDef def, ClassDef cur) {
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
        if (cur == null) giveStarterKit(player); // 처음 전직: 조건 없이 한 번
        else ensureStarterKit(player);           // 직업 변경: 기존 플레이어 규칙 (보통은 이미 받았거나 기록됨)
    }

    /** 접속할 때: 직업은 있는데 시작 무기를 받은 적도 가진 것도 없으면(예전 판에서 전직한 사람) 한 번 지급 + 시작 꾸러미 규칙. */
    public void ensureStarterWeapon(Player player) {
        ClassDef def = classOf(player);
        if (def != null) giveStarterWeapon(player, def);
        ensureStarterKit(player);
    }

    /**
     * 기존 플레이어의 시작 꾸러미: {@link #joinGrantsKit} 이고 직업이 있으면 모자란 몫을 지급, 조건 밖이면 받은 것으로 기록만 한다
     * (이미 진행한 사람에게 새로 주지 않음). 직업이 없으면 전직할 때 받는다.
     */
    private void ensureStarterKit(Player player) {
        if (services.settings().starterKit().isEmpty()) return;
        PlayerData d = services.data().get(player);
        if (!joinGrantsKit(d.level(), d.counter("dungeon.clear_floor_1"))) {
            Map<String, Integer> got = StarterKit.received(d.ext());
            Map<String, Integer> owed = StarterKit.owed(services.settings().starterKit(), services.settings().starterGold(), got);
            if (owed.isEmpty()) return;
            d.ext().put(StarterKit.GOT, StarterKit.record(got, owed)); // 지급 없이 받은 것으로
            d.markDirty();
        } else if (classOf(player) != null) {
            giveStarterKit(player);
        }
    }

    /** 접속(기존 플레이어) 경로의 시작 꾸러미 조건: Lv.5 이하이고 지하 1층을 깬 적이 없을 때만. 처음 전직할 때는 조건 없이 한 번. */
    static boolean joinGrantsKit(int level, long floor1Clears) {
        return level <= KIT_JOIN_MAX_LEVEL && floor1Clears <= 0;
    }

    /**
     * 시작 꾸러미 (config.yml starter_kit — 수련생 방어구 4종 · 물약 · 귀환 주문서 · 빵 · 골드) 중 아직 받지 않은 몫을 지급.
     * 꾸러미를 늘린 판에서는 예전 꾸러미를 받은 사람에게 차이만 준다. 콘텐츠에 없는 아이템 줄은 건너뛰고(기록도 안 함),
     * minecraft: 로 시작하는 id 는 바닐라 아이템. 가방이 차면 발밑에 떨군다.
     */
    private void giveStarterKit(Player player) {
        var kit = services.settings().starterKit();
        if (kit.isEmpty()) return;
        PlayerData d = services.data().get(player);
        Map<String, Integer> got = StarterKit.received(d.ext());
        Map<String, Integer> owed = StarterKit.owed(kit, services.settings().starterGold(), got);
        if (owed.isEmpty()) return;
        Map<String, Integer> given = new java.util.LinkedHashMap<>();
        List<String> shown = new ArrayList<>();
        boolean fresh = got.isEmpty();
        for (Map.Entry<String, Integer> e : owed.entrySet()) {
            String id = e.getKey();
            int amount = e.getValue();
            if (StarterKit.GOLD.equals(id)) {
                d.addGold(amount);
                given.put(id, amount);
                shown.add("<#ffd36b>" + Text.num(amount) + " 골드</#ffd36b>");
            } else if (id.startsWith("minecraft:")) {
                org.bukkit.Material m = org.bukkit.Material.matchMaterial(id);
                if (m == null || !m.isItem()) {
                    Log.warnOnce("starter-kit-" + id, "[직업] 시작 꾸러미 바닐라 아이템 id 가 잘못됐습니다: " + id);
                    continue;
                }
                var stack = new org.bukkit.inventory.ItemStack(m, amount);
                player.getInventory().addItem(stack).values().forEach(left -> player.getWorld().dropItemNaturally(player.getLocation(), left));
                given.put(id, amount);
                // 바닐라 이름은 접속한 사람의 언어로 (<lang:item.minecraft.bread> → "빵")
                shown.add("<white><lang:" + m.translationKey() + "></white>" + (amount > 1 ? " <gray>×" + amount : ""));
            } else {
                ItemDef item = services.content().item(id);
                if (item == null) {
                    Log.warnOnce("starter-kit-" + id, "[직업] 시작 꾸러미 아이템이 콘텐츠에 없습니다: " + id);
                    continue;
                }
                int n = services.items().give(player, item.id(), amount, "starter");
                if (n <= 0) continue;
                given.put(id, n);
                shown.add("<white>" + item.name() + "</white>" + (n > 1 ? " <gray>×" + n : ""));
            }
        }
        if (given.isEmpty()) return;
        services.stats().markDirty(player);
        d.ext().put(StarterKit.GOT, StarterKit.record(got, given));
        d.ext().remove(StarterKit.LEGACY_FLAG);
        d.markDirty();
        Text.send(player, "<gray>" + (fresh ? "시작 꾸러미를 받았습니다: " : "시작 꾸러미가 늘어나 더 받았습니다: ") + String.join("<gray>, ", shown));
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
        services.stats().markDirty(player); // 빈 손 칸에 들어갔을 수 있다 — setClass 의 재계산은 지급 전에 끝났다
        d.ext().put(flag, true);
        d.markDirty();
        Text.send(player, "<gray>시작 무기를 받았습니다: <white>" + best.name() + "</white> <gray>— 스킬은 무엇을 들었든 <white>"
                + kr.labyrinth.core.InputKeys.CLASS_KEYS);
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
        ItemDef weapon = services.items().heldWeapon(player); // 추천 무기 재사용 대기 판정용 (스킬 자체는 무엇을 들었든 나간다)
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
        // 추천 무기면 기본 재사용 대기 −10% (요구 능력치를 못 맞춰 능력치가 안 붙는 무기는 제외), 그다음 재사용 감소 스탯
        if (st.cooldowns.ready(sk.id())) {
            double base = WeaponTypes.classSkillCooldown(cls, WeaponTypes.effective(weapon, services.stats().requirementStats(player)), sk.cooldown());
            st.cooldowns.start(sk.id(), CooldownTracker.effective(base, services.stats().get(player).cooldownReduction()));
        }
        if (services.hud().skillMessages()) bar(player, "<" + col + "><b>✦ " + sk.name() + "</b></" + col + ">  <#6fc3ff>MP " + Text.num(mana(player)) + "<gray>/"
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
