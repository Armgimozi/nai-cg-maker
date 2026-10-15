package kr.labyrinth.items.enhance;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.event.EnhanceEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 대장장이 강화 (GDD §11.13): 확인(대상·단계·강화석·골드) → 골드·강화석 소모 → 판정 → 단계 기록·다시 그리기 →
 * {@link EnhanceEvent} → 망치질 연출 뒤 결과 연출(성공 빛·소리 / 실패 소리 / 하락 경고). +8 이상 성공은 서버 전체 방송.
 * 판정은 클릭 순간 끝나고(창을 닫아도 결과는 같다), 연출만 0.8초 늦게 보인다.
 */
public final class EnhanceService {

    /** 강화할 수 없는 이유. */
    public enum Problem { NONE, DISABLED, NO_ITEM, VANILLA, NOT_ENHANCEABLE, MAX_LEVEL, NO_STONES, NO_GOLD, CHANGED }

    /**
     * 지금 강화하면 어떻게 되는가 (창 표시용, 소모 없음).
     * @param downgrade 실패하면 한 단계 내려가는가
     */
    public record Plan(ItemDef def, int level, int target, double chance, long gold, String stone, int stones,
                       int haveStones, int haveScrolls, boolean downgrade, Problem problem) {
        public boolean ok() { return problem == Problem.NONE; }
    }

    /** 강화 한 번의 결과. */
    public record Result(EnhanceRules.Outcome outcome, int from, int to, ItemStack item, long gold, int stones) {}

    /** 망치질 연출 길이(틱) — 이 뒤에 결과 연출과 창 갱신. */
    public static final long REVEAL_TICKS = 16L;

    private final Services services;
    private EnhanceGlow glow;

    public EnhanceService(Services services) { this.services = services; }

    public void start() {
        configure();
        glow = new EnhanceGlow(services);
        glow.start();
    }

    public void stop() {
        if (glow != null) glow.stop();
    }

    public void reload() { configure(); }

    private void configure() {
        Enhancement.configure(services.plugin().getConfig().getConfigurationSection("enhance"));
    }

    public EnhanceRules rules() { return Enhancement.rules(); }

    // ── 재료 ──────────────────────────────────────────────────────────────

    /** 가방(핫바 포함) 안 미궁 아이템 id 개수. */
    public int count(Player p, String itemId) {
        if (itemId == null) return 0;
        int n = 0;
        for (ItemStack s : p.getInventory().getStorageContents()) {
            if (s == null || s.isEmpty()) continue;
            if (services.items().defOf(s).map(d -> d.id().equals(itemId)).orElse(false)) n += s.getAmount();
        }
        return n;
    }

    private void remove(Player p, String itemId, int amount) {
        int left = amount;
        PlayerInventory inv = p.getInventory();
        ItemStack[] contents = inv.getStorageContents();
        for (int i = 0; i < contents.length && left > 0; i++) {
            ItemStack s = contents[i];
            if (s == null || s.isEmpty()) continue;
            if (!services.items().defOf(s).map(d -> d.id().equals(itemId)).orElse(false)) continue;
            int take = Math.min(left, s.getAmount());
            s.setAmount(s.getAmount() - take);
            left -= take;
            contents[i] = s.getAmount() <= 0 ? null : s;
        }
        inv.setStorageContents(contents);
    }

    // ── 확인 ──────────────────────────────────────────────────────────────

    public Plan plan(Player p, ItemStack stack) {
        EnhanceRules r = rules();
        ItemDef def = stack == null || stack.isEmpty() ? null : services.items().defOf(stack).orElse(null);
        int level = Enhancement.level(stack);
        int target = level + 1;
        String protection = r.config().protectionItem();
        int scrolls = count(p, protection);
        if (!r.config().enabled()) return new Plan(def, level, target, 0, 0, null, 0, 0, scrolls, false, Problem.DISABLED);
        if (stack == null || stack.isEmpty()) return new Plan(null, 0, 1, 0, 0, null, 0, 0, scrolls, false, Problem.NO_ITEM);
        if (def == null) return new Plan(null, 0, 1, 0, 0, null, 0, 0, scrolls, false, Problem.VANILLA);
        if (!EnhanceRules.enhanceable(def)) return new Plan(def, 0, 1, 0, 0, null, 0, 0, scrolls, false, Problem.NOT_ENHANCEABLE);
        boolean down = r.downgradesOnFail(level);
        if (level >= r.maxLevel()) return new Plan(def, level, level, 0, 0, null, 0, 0, scrolls, false, Problem.MAX_LEVEL);
        String stone = r.stoneFor(def);
        int need = r.stoneCount(target);
        int have = count(p, stone);
        long gold = r.gold(def, target, services.stats().get(p).craftDiscount());
        Problem problem = have < need ? Problem.NO_STONES
                : services.data().get(p).gold() < gold ? Problem.NO_GOLD : Problem.NONE;
        return new Plan(def, level, target, r.chance(target), gold, stone, need, have, scrolls, down, problem);
    }

    /** 안내 문구. */
    public static String message(Problem pr) {
        return switch (pr) {
            case NONE -> "";
            case DISABLED -> "이 서버에서는 강화가 꺼져 있습니다.";
            case NO_ITEM -> "강화할 장비를 먼저 고르세요.";
            case VANILLA -> "미궁 장비만 강화할 수 있습니다. (바닐라 무기·방어구는 인챈트로)";
            case NOT_ENHANCEABLE -> "무기·방어구·방패만 강화할 수 있습니다. (장신구·재료 불가)";
            case MAX_LEVEL -> "이미 최대 단계입니다.";
            case NO_STONES -> "강화석이 부족합니다.";
            case NO_GOLD -> "골드가 부족합니다.";
            case CHANGED -> "고른 장비가 바뀌었습니다. 다시 골라 주세요.";
        };
    }

    // ── 강화 ──────────────────────────────────────────────────────────────

    /**
     * 강화 한 번. 실패하면(조건 부족) 안내를 보내고 null.
     * @param slot     플레이어 인벤토리 칸 번호 (0~35 가방, 36~39 방어구, 40 보조손)
     * @param expected 고를 때 본 아이템 (그 칸 아이템이 그대로인지 확인)
     * @param protect  보호 주문서 사용 (가지고 있고, 하락할 단계일 때만 의미가 있다)
     */
    public Result enhance(Player p, int slot, ItemStack expected, boolean protect) {
        PlayerInventory inv = p.getInventory();
        ItemStack cur = slot < 0 || slot > 40 ? null : inv.getItem(slot);
        if (cur == null || expected == null || !cur.isSimilar(expected)) {
            Text.error(p, message(Problem.CHANGED));
            return null;
        }
        Plan plan = plan(p, cur);
        if (!plan.ok()) {
            Text.error(p, message(plan.problem()));
            return null;
        }
        EnhanceRules r = rules();
        PlayerData d = services.data().get(p);
        if (!d.takeGold(plan.gold())) {
            Text.error(p, message(Problem.NO_GOLD));
            return null;
        }
        remove(p, plan.stone(), plan.stones());
        boolean useScroll = protect && plan.downgrade() && plan.haveScrolls() > 0;
        EnhanceRules.Outcome o = r.resolve(plan.level(), ThreadLocalRandom.current().nextDouble(), useScroll);
        if (EnhanceRules.consumesProtection(o)) remove(p, r.config().protectionItem(), 1);
        int to = EnhanceRules.levelAfter(plan.level(), o);

        // 소모 뒤 칸이 비었을 수 있으니(강화석이 같은 칸?) 장비는 원래 칸에서 다시 꺼내 고친다
        ItemStack item = inv.getItem(slot);
        if (item == null || !item.isSimilar(expected)) item = cur;
        Enhancement.setLevel(item, to);
        services.items().refresh(item);
        inv.setItem(slot, item);
        services.stats().markDirty(p);
        services.hud().refresh(p);
        Result res = new Result(o, plan.level(), to, item.clone(), plan.gold(), plan.stones());
        try {
            Bukkit.getPluginManager().callEvent(new EnhanceEvent(p, plan.def(), item.clone(), plan.level(), to,
                    o.name().toLowerCase(java.util.Locale.ROOT)));
        } catch (Throwable t) {
            Log.error("EnhanceEvent 처리 오류", t);
        }
        Log.info("[강화] " + p.getName() + " " + plan.def().id() + " +" + plan.level() + " → +" + to + " (" + o + ", "
                + EnhanceRules.pct(plan.chance()) + ")");
        hammer(p, plan, res);
        return res;
    }

    /** 관리자: 아이템 단계를 바로 바꾼다 (테스트·보상). */
    public boolean setLevel(ItemStack stack, int level) {
        ItemDef def = services.items().defOf(stack).orElse(null);
        if (!EnhanceRules.enhanceable(def)) return false;
        Enhancement.setLevel(stack, level);
        services.items().refresh(stack);
        return true;
    }

    // ── 연출 ──────────────────────────────────────────────────────────────

    /** 망치질 세 번(0.6초) → 결과 연출·채팅·방송. */
    private void hammer(Player p, Plan plan, Result res) {
        for (int i = 0; i < 3; i++) {
            final int k = i;
            Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
                if (!p.isOnline()) return;
                Location at = front(p);
                p.playSound(at, Sound.BLOCK_ANVIL_USE, 0.55f, 0.9f + k * 0.12f);
                p.spawnParticle(Particle.CRIT, at, 8, 0.15, 0.1, 0.15, 0.25);
                p.spawnParticle(Particle.LAVA, at, 1, 0.1, 0.05, 0.1, 0);
            }, i * 6L);
        }
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!p.isOnline()) return;
            try {
                reveal(p, plan, res);
            } catch (Throwable t) {
                Log.error("강화 결과 연출 오류", t);
            }
        }, REVEAL_TICKS);
    }

    private static Location front(Player p) {
        Location eye = p.getEyeLocation();
        return eye.add(eye.getDirection().setY(0).normalize().multiply(0.9)).subtract(0, 0.5, 0);
    }

    private void reveal(Player p, Plan plan, Result res) {
        Component name = res.item().effectiveName();
        Location at = front(p);
        Title.Times times = Title.Times.times(Duration.ofMillis(120), Duration.ofMillis(1600), Duration.ofMillis(500));
        switch (res.outcome()) {
            case SUCCESS -> {
                boolean big = rules().shines(res.to());
                p.playSound(p.getLocation(), Sound.BLOCK_ANVIL_USE, 0.6f, 1.6f);
                p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.7f, big ? 1.2f : 1.6f);
                p.playSound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1.0f, 1.2f);
                p.spawnParticle(Particle.END_ROD, at, big ? 40 : 18, 0.25, 0.25, 0.25, 0.08);
                p.spawnParticle(Particle.WAX_ON, at, 12, 0.3, 0.3, 0.3, 0.5);
                p.spawnParticle(Particle.DUST, at, 20, 0.35, 0.35, 0.35, 0,
                        new Particle.DustOptions(Color.fromRGB(0xFFD36B), 1.3f));
                if (big) p.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, p.getLocation().add(0, 1, 0), 30, 0.4, 0.6, 0.4, 0.3);
                p.showTitle(Title.title(Text.mm("<gradient:#ffd36b:#fff4d6><b>강화 성공!</b></gradient>"),
                        Text.mm("<white>+" + res.from() + " → <#ffd36b><b>+" + res.to() + "</b>"), times));
                Text.send(p, "<#ffd36b>강화 성공!</#ffd36b> <item> <gray>(+" + res.from() + " → +" + res.to() + ")",
                        Text.ph("item", name));
                if (res.to() >= rules().config().broadcastFrom()) broadcast(p, res);
            }
            case FAIL -> {
                p.playSound(p.getLocation(), Sound.BLOCK_ANVIL_LAND, 0.6f, 0.7f);
                p.playSound(p.getLocation(), Sound.BLOCK_FIRE_EXTINGUISH, 0.5f, 1.2f);
                p.spawnParticle(Particle.SMOKE, at, 14, 0.2, 0.15, 0.2, 0.02);
                p.showTitle(Title.title(Text.mm("<#c8c8d0>강화 실패"),
                        Text.mm("<gray>+" + res.from() + " 그대로 · 재료가 사라졌습니다"), times));
                Text.send(p, "<#c8c8d0>강화 실패</#c8c8d0> <item> <gray>— 단계는 그대로, 골드·강화석이 사라졌습니다.",
                        Text.ph("item", name));
            }
            case DOWNGRADE -> {
                p.playSound(p.getLocation(), Sound.BLOCK_ANVIL_DESTROY, 0.7f, 0.8f);
                p.playSound(p.getLocation(), Sound.ENTITY_ITEM_BREAK, 0.8f, 0.7f);
                p.spawnParticle(Particle.LARGE_SMOKE, at, 10, 0.2, 0.15, 0.2, 0.02);
                p.spawnParticle(Particle.DUST, at, 18, 0.3, 0.3, 0.3, 0,
                        new Particle.DustOptions(Color.fromRGB(0xE04646), 1.2f));
                p.showTitle(Title.title(Text.mm("<#ff6b6b><b>⚠ 단계 하락</b>"),
                        Text.mm("<#ff8a8a>+" + res.from() + " → +" + res.to()), times));
                Text.send(p, "<#ff6b6b>강화 실패 — 단계가 내려갔습니다.</#ff6b6b> <item> <gray>(+" + res.from() + " → +"
                        + res.to() + ") <dark_gray>보호 주문서를 켜면 막을 수 있습니다.", Text.ph("item", name));
            }
            case PROTECTED -> {
                p.playSound(p.getLocation(), Sound.ITEM_SHIELD_BLOCK, 0.8f, 1.1f);
                p.playSound(p.getLocation(), Sound.BLOCK_BEACON_DEACTIVATE, 0.6f, 1.4f);
                p.spawnParticle(Particle.ENCHANT, at, 30, 0.3, 0.3, 0.3, 0.6);
                p.showTitle(Title.title(Text.mm("<#7fd8ff>보호 주문서 발동"),
                        Text.mm("<gray>강화는 실패했지만 <white>+" + res.from() + "</white> 을 지켰습니다"), times));
                Text.send(p, "<#7fd8ff>강화 실패 — 보호 주문서가 단계를 지켰습니다.</#7fd8ff> <item> <gray>(+" + res.from()
                        + " 유지, 주문서 1장 사용)", Text.ph("item", name));
            }
        }
    }

    /** 고단계 성공 서버 방송 (아이템에 마우스를 올리면 툴팁). */
    private void broadcast(Player p, Result res) {
        boolean max = rules().radiant(res.to());
        String head = max ? "<gradient:#ff8a3d:#ffd36b:#fff4d6><b>[강화]</b></gradient>" : "<#ffd36b><b>[강화]</b></#ffd36b>";
        Bukkit.getServer().sendMessage(Text.mm(head + " <white>" + Text.escape(p.getName()) + "</white> <gray>님이 </gray><item> "
                + "<gray>+" + res.to() + " 강화에 성공했습니다!", Text.ph("item", res.item().displayName())));
        for (Player o : Bukkit.getOnlinePlayers()) {
            if (max) o.playSound(o.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.6f, 1.2f);
            else o.playSound(o.getLocation(), Sound.BLOCK_NOTE_BLOCK_CHIME, 0.6f, 1.6f);
        }
    }

    public void open(Player p) {
        if (!rules().config().enabled()) {
            Text.error(p, message(Problem.DISABLED));
            return;
        }
        new EnhanceMenu(services, this, p).open(p);
        p.playSound(p.getLocation(), Sound.BLOCK_ANVIL_PLACE, 0.4f, 1.2f);
    }

    // ── 자가 진단 ─────────────────────────────────────────────────────────

    /**
     * 자가 진단용: 강화할 수 있는 모든 장비를 만들어 0~최대 단계로 기록·다시 그리기·스탯을 확인한다.
     * @return 확인한 아이템 수
     */
    public static int selfCheck(Services services) {
        EnhanceRules r = Enhancement.rules();
        int n = 0;
        for (ItemDef def : services.content().items().values()) {
            if (!EnhanceRules.enhanceable(def)) continue;
            ItemStack s = services.items().create(def.id());
            if (s == null) continue;
            Map<String, Double> base = services.items().rolledStats(s);
            for (int lv = 1; lv <= r.maxLevel(); lv++) {
                Enhancement.setLevel(s, lv);
                services.items().refresh(s);
                if (Enhancement.level(s) != lv) throw new IllegalStateException(def.id() + " 강화 단계 기록 실패 +" + lv);
            }
            Map<String, Double> top = services.items().rolledStats(s);
            for (String k : r.scaledKeys(def)) {
                Double b = base.get(k);
                Double t = top.get(k);
                if (b != null && b > 0 && (t == null || t < b)) throw new IllegalStateException(def.id() + "." + k + " 강화 배율 이상");
            }
            if (r.stoneFor(def) == null || services.content().item(r.stoneFor(def)) == null) {
                throw new IllegalStateException(def.id() + " 강화석 정의 없음: " + r.stoneFor(def));
            }
            n++;
        }
        return n;
    }
}
