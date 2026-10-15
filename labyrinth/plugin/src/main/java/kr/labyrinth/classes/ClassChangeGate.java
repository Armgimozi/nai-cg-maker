package kr.labyrinth.classes;

import kr.labyrinth.Services;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 직업 변경 관문 — {@link ClassChangeRule} 판정에 플레이어 상태(지금 직업·미궁 공략 중·전직의 두루마리·마지막 변경 시각)를 넣고,
 * 막히면 이유를 안내하고, 통과하면 두루마리 1장 소모 → 직업 적용 → 시각 기록까지 한 번에 한다.
 * {@link ClassService#changeClass} 의 모든 구현과 직업 메뉴 표시가 이것 하나를 쓴다. 관리자 {@code /labadmin setclass} 만 거치지 않는다.
 */
public final class ClassChangeGate {

    /** 마지막으로 직업을 정한(바꾼) 시각 (PlayerData ext, epoch ms). 첫 선택·변경 때 기록, 관리자 setclass 는 건드리지 않는다. */
    public static final String CHANGED_AT = "class.changed_at";

    private final Services services;

    public ClassChangeGate(Services services) { this.services = services; }

    /** 설정. 두루마리가 콘텐츠에 없으면 요구하지 않는다 (아무도 직업을 못 바꾸는 일 방지 — 콘솔 경고 1회). */
    public Settings.ClassChange rule() {
        Settings.ClassChange r = services.settings().classChange();
        if (r.requireItem() && services.content().item(r.item()) == null) {
            Log.warnOnce("class-change-item-" + r.item(), "[직업] config class_change.item 이 콘텐츠에 없습니다: " + r.item()
                    + " — 두루마리 없이 직업을 바꿀 수 있게 둡니다");
            return new Settings.ClassChange(false, r.item(), r.cooldownHours());
        }
        return r;
    }

    /** 지금 상태로 판정 (currentId = 지금 직업 id, null = 없음). */
    public ClassChangeRule.Verdict check(Player p, String currentId, String targetId) {
        Settings.ClassChange r = rule();
        boolean inRun = services.dungeon().currentInstance(p).isPresent();
        boolean has = !r.requireItem() || scrolls(p) > 0;
        return ClassChangeRule.check(r, currentId, targetId, inRun, has, lastChange(services.data().get(p)), System.currentTimeMillis());
    }

    /**
     * 관문 통과 → 두루마리 1장 소모 → apply(직업 적용·연출) → 변경 시각 기록. 막히면 이유를 채팅으로 알리고 false.
     *
     * @param current 지금 직업 (null = 첫 선택)
     */
    public boolean run(Player p, ClassDef current, ClassDef target, Runnable apply) {
        ClassChangeRule.Verdict v = check(p, current == null ? null : current.id(), target.id());
        if (!v.allowed()) {
            Text.error(p, explain(v, target));
            return false;
        }
        if (v.consumesItem() && !consumeOne(p)) {
            Text.error(p, explain(new ClassChangeRule.Verdict(ClassChangeRule.Block.NO_ITEM, false, true, true, 0), target));
            return false;
        }
        apply.run();
        PlayerData d = services.data().get(p);
        // 대기 시간은 '바꾼' 뒤부터 — 첫 선택(무료)은 세지 않아 잘못 고른 새 플레이어가 두루마리만 있으면 바로 바꿀 수 있다
        if (!v.first()) {
            d.ext().put(CHANGED_AT, System.currentTimeMillis());
            d.markDirty();
        }
        Settings.ClassChange r = rule();
        if (v.consumesItem()) {
            Text.send(p, "<gray><white>" + itemName() + "</white> 1장을 사용했습니다."
                    + (r.cooldownHours() > 0 ? " 다음 변경은 <white>" + ClassChangeRule.hours(r.cooldownHours()) + "</white> 뒤부터." : ""));
        } else if (v.first() && (r.requireItem() || r.cooldownHours() > 0)) {
            Text.send(p, "<gray>첫 직업은 무료입니다." + (r.requireItem() ? " 다음에 바꿀 때는 <white>" + itemName() + "</white> 1장이 듭니다." : "")
                    + (r.cooldownHours() > 0 ? " 바꾼 뒤에는 <white>" + ClassChangeRule.hours(r.cooldownHours()) + "</white> 동안 다시 바꿀 수 없습니다." : ""));
        }
        return true;
    }

    /** 막힌 이유 (Text.error 에 넣을 MiniMessage). */
    public String explain(ClassChangeRule.Verdict v, ClassDef target) {
        if (v.block() == null) return "";
        return switch (v.block()) {
            case SAME_CLASS -> "이미 <" + target.color() + ">" + target.name() + "</" + target.color() + "> 입니다.";
            case IN_RUN -> "미궁 공략 중에는 직업을 바꿀 수 없습니다. 입구로 돌아간 뒤 다시 시도하세요.";
            case COOLDOWN -> "아직 직업을 바꿀 수 없습니다 — 직업을 바꾼 뒤 " + ClassChangeRule.hours(rule().cooldownHours())
                    + "은 기다려야 합니다. 다음 변경까지 <white>" + ClassChangeRule.duration(v.cooldownLeftMs()) + "</white> 남았습니다."
                    + (v.missingItem() ? " <gray>(바꿀 때 <white>" + itemName() + "</white> 1장도 필요합니다)" : "");
            case NO_ITEM -> "직업을 바꾸려면 <white>" + itemName() + "</white> 1장이 필요합니다."
                    + (shopHint().isEmpty() ? "" : " <gray>(" + shopHint() + ")");
        };
    }

    /** 두루마리 이름 (콘텐츠에 없으면 id). */
    public String itemName() {
        ItemDef d = services.content().item(rule().item());
        return d == null ? rule().item() : Text.strip(d.name());
    }

    /** 두루마리를 파는 곳 "떠돌이 상인 핀 · 3,000 골드" (어느 상점에도 없으면 빈 문자열). */
    public String shopHint() {
        String id = rule().item();
        for (NpcDef n : services.content().npcs().values()) {
            if (n.shop() == null) continue;
            for (NpcDef.ShopEntry e : n.shop()) {
                if (id.equals(e.item())) return Text.strip(n.name()) + " · " + Text.num(e.price()) + " 골드";
            }
        }
        return "";
    }

    /** 가방(핫바 포함) 안의 두루마리 수. */
    public int scrolls(Player p) {
        String id = rule().item();
        int n = 0;
        for (ItemStack s : p.getInventory().getStorageContents()) {
            if (s == null || s.isEmpty()) continue;
            if (services.items().defOf(s).map(d -> d.id().equals(id)).orElse(false)) n += s.getAmount();
        }
        return n;
    }

    private boolean consumeOne(Player p) {
        String id = rule().item();
        ItemStack[] contents = p.getInventory().getStorageContents();
        for (int i = 0; i < contents.length; i++) {
            ItemStack s = contents[i];
            if (s == null || s.isEmpty() || !services.items().defOf(s).map(d -> d.id().equals(id)).orElse(false)) continue;
            s.setAmount(s.getAmount() - 1);
            contents[i] = s.getAmount() <= 0 ? null : s;
            p.getInventory().setStorageContents(contents);
            return true;
        }
        return false;
    }

    /** 마지막 변경 시각 (기록 없음 = 0). */
    public static long lastChange(PlayerData d) {
        return d.ext().get(CHANGED_AT) instanceof Number n ? n.longValue() : 0L;
    }
}
