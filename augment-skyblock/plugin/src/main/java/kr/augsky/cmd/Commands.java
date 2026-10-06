package kr.augsky.cmd;

import kr.augsky.AugSky;
import kr.augsky.augment.AugmentDef;
import kr.augsky.augment.PlayerData;
import kr.augsky.augment.Tier;
import kr.augsky.map.MapBuilder;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/** /증강, /스폰, /무기도감, /증강관리 */
public final class Commands implements TabExecutor {
    private final AugSky plugin;
    private final Map<UUID, Long> spawnCd = new HashMap<>();

    public Commands(AugSky plugin) {
        this.plugin = plugin;
    }

    private static void msg(CommandSender s, String mm) {
        s.sendMessage(Text.mm(mm));
    }

    @Override
    public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        switch (cmd.getName()) {
            case "augment" -> augment(s, a);
            case "augspawn" -> spawn(s);
            case "weapons" -> {
                if (s instanceof Player p) plugin.menus().openWeapons(p, 0);
            }
            case "armorcodex" -> {
                if (s instanceof Player p) plugin.menus().openArmor(p);
            }
            case "augadmin" -> admin(s, a);
            default -> {
                return false;
            }
        }
        return true;
    }

    // ------------------------------------------------------------------ /증강

    private void augment(CommandSender s, String[] a) {
        if (!(s instanceof Player p)) {
            msg(s, "게임 안에서 쓰는 명령어입니다.");
            return;
        }
        String sub = a.length == 0 ? "" : a[0];
        switch (sub) {
            case "", "목록", "list" -> plugin.menus().openMine(p);
            case "도감", "codex" -> plugin.menus().openCodex(p, a.length > 1 && Tier.parse(a[1]) != null ? Tier.parse(a[1]) : Tier.SILVER);
            case "선택", "choose" -> plugin.menus().openChoice(p);
            case "제단" -> places(p);
            case "책", "book" -> Items.give(p, plugin.items().guideBook());
            default -> help(p);
        }
    }

    private void help(Player p) {
        msg(p, "<#ffcc55>━━━━ 증강 스카이블럭 ━━━━");
        msg(p, "<white>/증강 <gray>내 증강 보기");
        msg(p, "<white>/증강 도감 <gray>모든 증강 보기");
        msg(p, "<white>/증강 선택 <gray>고르다 만 증강 선택지 다시 열기");
        msg(p, "<white>/증강 제단 <gray>남은 제단 수와 보스 상태");
        msg(p, "<white>/증강 책 <gray>안내서 다시 받기");
        msg(p, "<white>/무기도감 <gray>모든 무기 보기");
        msg(p, "<white>/갑옷도감 <gray>모든 갑옷 세트 보기");
        msg(p, "<white>/스폰 <gray>시작의 섬으로 이동");
    }

    /** 남은 제단 수와 보스 상태. 어디에 있는지는 알려 주지 않는다 (섬을 직접 찾아다니는 게 이 맵의 재미). */
    private void places(Player p) {
        var altars = plugin.altars();
        msg(p, "<#ffcc55>━━━━ 남은 제단 ━━━━");
        switch (altars.mode()) {
            case GLOBAL -> {
                World w = p.getWorld();
                msg(p, "<gray>" + Tier.SILVER.wrap("실버") + " 제단 <white>" + altars.remaining(w, Tier.SILVER) + "곳 <dark_gray>· "
                        + Tier.GOLD.wrap("골드") + " <gray>제단 <white>" + altars.remaining(w, Tier.GOLD) + "곳 <dark_gray>· "
                        + Tier.PRISM.wrap("프리즘") + " <gray>제단 <white>" + altars.remaining(w, Tier.PRISM) + "곳");
            }
            case PLAYER -> msg(p, "<gray>아직 쓰지 않은 제단: 실버 " + altars.usableCount(p, Tier.SILVER) + "곳 · 골드 "
                    + altars.usableCount(p, Tier.GOLD) + "곳 · 프리즘 " + altars.usableCount(p, Tier.PRISM) + "곳");
            case OFF -> msg(p, "<gray>제단은 몇 번이고 쓸 수 있습니다.");
        }
        List<String> lairs = plugin.mobs().lairs().describe(p);
        if (!lairs.isEmpty()) {
            msg(p, "<#ffcc55>━━━━ 보스 ━━━━");
            for (String line : lairs) msg(p, line);
        }
    }

    private void spawn(CommandSender s) {
        if (!(s instanceof Player p)) return;
        long now = System.currentTimeMillis();
        Long last = spawnCd.get(p.getUniqueId());
        if (last != null && now - last < 10_000 && !p.hasPermission("augsky.admin")) {
            msg(p, "<gray>잠시 뒤에 다시 쓰세요.");
            return;
        }
        spawnCd.put(p.getUniqueId(), now);
        p.teleport(plugin.spawnLocation());
        p.setFallDistance(0);
        msg(p, "<gray>시작의 섬으로 이동했습니다.");
    }

    // ------------------------------------------------------------------ /증강관리

    private void admin(CommandSender s, String[] a) {
        if (!s.hasPermission("augsky.admin")) {
            msg(s, "<#ff7070>권한이 없습니다.");
            return;
        }
        if (a.length == 0) {
            adminHelp(s);
            return;
        }
        String sub = a[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "무기", "weapon" -> {
                if (a.length < 2) {
                    msg(s, "/증강관리 무기 <id> [플레이어]");
                    return;
                }
                Player t = target(s, a, 2);
                ItemStack it = plugin.weapons().create(a[1]);
                if (t == null || it == null) {
                    msg(s, "<#ff7070>무기나 플레이어를 찾을 수 없습니다.");
                    return;
                }
                Items.give(t, it);
                msg(s, "<gray>" + t.getName() + "에게 무기 " + a[1] + " 지급");
            }
            case "아이템", "item" -> {
                if (a.length < 2) {
                    msg(s, "/증강관리 아이템 <id> [개수] [플레이어]");
                    return;
                }
                int n = a.length > 2 ? parseInt(a[2], 1) : 1;
                Player t = target(s, a, 3);
                ItemStack it = plugin.items().spec(a[1], n);
                if (t == null || it == null) {
                    msg(s, "<#ff7070>아이템이나 플레이어를 찾을 수 없습니다.");
                    return;
                }
                if (plugin.items().def(a[1]) != null) it.setAmount(Math.min(n, it.getMaxStackSize()));
                int left = n;
                while (left > 0) {
                    ItemStack one = it.clone();
                    one.setAmount(Math.min(left, it.getMaxStackSize()));
                    left -= one.getAmount();
                    Items.give(t, one);
                }
                msg(s, "<gray>" + t.getName() + "에게 " + a[1] + " ×" + n + " 지급");
            }
            case "증강", "augment" -> adminAugment(s, a);
            case "갑옷", "armor" -> {
                if (a.length < 2 || plugin.armor().get(a[1]) == null) {
                    msg(s, "/증강관리 갑옷 <" + String.join("|", plugin.armor().all().keySet()) + "> [부위|전부] [플레이어]");
                    return;
                }
                Player t = target(s, a, 3);
                if (t == null) {
                    msg(s, "<#ff7070>플레이어를 찾을 수 없습니다.");
                    return;
                }
                var sl = a.length > 2 ? kr.augsky.armor.ArmorService.Slot.parse(a[2]) : null;
                if (sl != null) Items.give(t, plugin.armor().create(a[1], sl));
                else for (var x : kr.augsky.armor.ArmorService.Slot.values()) Items.give(t, plugin.armor().create(a[1], x));
                msg(s, "<gray>" + t.getName() + "에게 갑옷 " + a[1] + " 지급");
            }
            case "선택지", "offer" -> {
                if (a.length < 3) {
                    msg(s, "/증강관리 선택지 <플레이어> <실버|골드|프리즘>");
                    return;
                }
                Player t = Bukkit.getPlayerExact(a[1]);
                Tier tier = Tier.parse(a[2]);
                if (t == null || tier == null) {
                    msg(s, "<#ff7070>플레이어나 등급을 찾을 수 없습니다.");
                    return;
                }
                if (plugin.augments().startOffer(t, tier)) plugin.menus().openChoice(t);
                else msg(s, "<gray>더 줄 수 있는 증강이 없습니다.");
            }
            case "소환", "spawn" -> {
                if (a.length < 2) {
                    msg(s, "/증강관리 소환 <몬스터id> [플레이어 | x y z]");
                    return;
                }
                Location at = null;
                if (a.length >= 5) {
                    World w = s instanceof Player p ? p.getWorld() : Bukkit.getWorlds().get(0);
                    at = new Location(w, parseD(a[2]), parseD(a[3]), parseD(a[4]));
                } else {
                    Player t = target(s, a, 2);
                    if (t != null) at = t.getLocation().add(t.getLocation().getDirection().setY(0).normalize().multiply(4));
                }
                if (at == null) {
                    msg(s, "<#ff7070>위치를 알 수 없습니다.");
                    return;
                }
                LivingEntity le = plugin.mobs().spawn(a[1], at, false);
                msg(s, le == null ? "<#ff7070>몬스터 id 를 확인하세요." : "<gray>" + a[1] + " 소환");
            }
            case "맵생성", "buildmap" -> {
                boolean force = false;
                String name = null;
                for (int i = 1; i < a.length; i++) {
                    if (a[i].equals("강제") || a[i].equalsIgnoreCase("force")) force = true;
                    else name = a[i];
                }
                World w = name != null ? Bukkit.getWorld(name) : (s instanceof Player p ? p.getWorld() : Bukkit.getWorlds().get(0));
                if (w == null) {
                    msg(s, "<#ff7070>월드를 찾을 수 없습니다.");
                    return;
                }
                // 이미 맵이 있는 월드에 다시 지으면 예전 섬과 새 섬이 뒤섞인다
                if (!force && (!plugin.altars().all(w).isEmpty() || !plugin.mobs().lairs().all(w).isEmpty()
                        || !w.getBlockAt(0, 64, 0).getType().isAir())) {
                    msg(s, "<#ff7070>이 월드에는 이미 맵이 있습니다. 새 맵은 빈 공허 월드에 지으세요.");
                    msg(s, "<gray>그래도 지으려면 /증강관리 맵생성 [월드] 강제 (예전 섬은 그대로 남습니다)");
                    return;
                }
                msg(s, "<gray>맵을 짓는 중... (" + w.getName() + ") 섬이 많아서 잠시 걸립니다.");
                plugin.mapBuilder().buildAll(w, m -> msg(s, "<gray>" + m), () -> msg(s, "<#7cff8c>맵 생성 완료."));
            }
            case "섬", "island" -> {
                if (!(s instanceof Player p) || a.length < 2) {
                    msg(s, "/증강관리 섬 <종류> [반지름]  (발밑에 섬 하나를 지어 봅니다)");
                    return;
                }
                Location l = p.getLocation();
                double rad = a.length > 2 ? parseD(a[2]) : 0;
                if (!plugin.mapBuilder().buildKind(p.getWorld(), a[1], l.getBlockX(), l.getBlockY() - 1, l.getBlockZ(), rad)) {
                    msg(s, "<#ff7070>없는 섬 종류입니다: " + String.join(", ", MapBuilder.kinds()));
                    return;
                }
                p.teleport(l.clone().add(0, 12, 0));
                msg(s, "<gray>" + a[1] + " 섬을 지었습니다.");
            }
            case "섬검사", "islandcheck" -> {
                World w = a.length > 1 ? Bukkit.getWorld(a[1]) : (s instanceof Player p ? p.getWorld() : Bukkit.getWorlds().get(0));
                if (w == null) {
                    msg(s, "<#ff7070>월드를 찾을 수 없습니다.");
                    return;
                }
                plugin.mapBuilder().checkIslands(w, s);
            }
            case "제단", "altar" -> {
                if (!(s instanceof Player p) || a.length < 2 || Tier.parse(a[1]) == null) {
                    msg(s, "/증강관리 제단 <실버|골드|프리즘>  (서 있는 자리에 제단을 세웁니다)");
                    return;
                }
                Location l = p.getLocation();
                plugin.mapBuilder().altarStructure(p.getWorld(), l.getBlockX(), l.getBlockY() - 1, l.getBlockZ(), Tier.parse(a[1]));
                p.teleport(l.clone().add(0, 3, 5));
                msg(s, "<gray>제단을 세웠습니다.");
            }
            case "균열", "rift" -> {
                if (!(s instanceof Player p) || a.length < 2 || !plugin.mobs().registry().rifts().containsKey(a[1])) {
                    msg(s, "/증강관리 균열 <" + String.join("|", plugin.mobs().registry().rifts().keySet()) + ">");
                    return;
                }
                plugin.mapBuilder().riftMarker(p.getWorld(), p.getLocation().getBlock().getLocation().add(0.5, 0, 0.5), a[1]);
                msg(s, "<gray>균열 표식을 세웠습니다. 주변에 균열의 몬스터가 나옵니다.");
            }
            case "둥지", "lair" -> {
                var reg = plugin.mobs().registry();
                if (!(s instanceof Player p) || a.length < 2 || reg.get(a[1]) == null || !reg.get(a[1]).boss()) {
                    List<String> bosses = new ArrayList<>();
                    for (var d : reg.all().values()) if (d.boss()) bosses.add(d.id());
                    msg(s, "/증강관리 둥지 <" + String.join("|", bosses) + ">  (서 있는 자리를 보스 둥지로)");
                    return;
                }
                plugin.mapBuilder().lairMarker(p.getWorld(), p.getLocation().getBlock().getLocation().add(0.5, 0, 0.5), a[1]);
                msg(s, "<gray>둥지를 세웠습니다. 잠시 뒤 보스가 나타납니다.");
            }
            case "리로드", "reload" -> {
                plugin.reloadContent();
                msg(s, "<#7cff8c>설정과 증강/무기/스킬/몬스터를 다시 불러왔습니다.");
            }
            case "리소스팩", "pack" -> {
                for (Player p : Bukkit.getOnlinePlayers()) plugin.pack().send(p);
                msg(s, "<gray>리소스팩을 다시 보냈습니다.");
            }
            case "정보", "info" -> {
                msg(s, "<gray>증강 " + plugin.augments().registry().all().size() + "개, 무기 " + plugin.weapons().all().size()
                        + "종, 스킬 " + plugin.skills().all().size() + "개, 몬스터 " + plugin.mobs().registry().all().size()
                        + "종, 활성 몬스터 " + plugin.mobs().activeCount());
            }
            default -> adminHelp(s);
        }
    }

    private void adminAugment(CommandSender s, String[] a) {
        if (a.length < 3) {
            msg(s, "/증강관리 증강 <추가|제거|초기화|목록> <플레이어> [증강id]");
            return;
        }
        Player t = Bukkit.getPlayerExact(a[2]);
        if (t == null) {
            msg(s, "<#ff7070>플레이어를 찾을 수 없습니다.");
            return;
        }
        switch (a[1]) {
            case "추가", "add" -> {
                if (a.length < 4) return;
                if (a[3].equals("*") || a[3].equals("전부")) {
                    int n = 0;
                    for (String id : plugin.augments().registry().all().keySet()) if (plugin.augments().grant(t, id, false)) n++;
                    msg(s, "<gray>증강 " + n + "개 추가");
                    return;
                }
                msg(s, plugin.augments().grant(t, a[3], true) ? "<gray>추가했습니다." : "<#ff7070>없는 증강이거나 최대 중첩입니다.");
            }
            case "제거", "remove" -> {
                if (a.length < 4) return;
                msg(s, plugin.augments().remove(t, a[3]) ? "<gray>제거했습니다." : "<#ff7070>갖고 있지 않습니다.");
            }
            case "초기화", "reset" -> {
                plugin.augments().reset(t);
                msg(s, "<gray>" + t.getName() + "의 증강을 모두 지웠습니다.");
            }
            case "목록", "list" -> {
                PlayerData d = plugin.augments().data(t);
                List<String> names = new ArrayList<>();
                for (var en : d.augments.entrySet()) {
                    AugmentDef def = plugin.augments().registry().get(en.getKey());
                    names.add((def == null ? en.getKey() : def.tier().wrap(def.name())) + (en.getValue() > 1 ? "×" + en.getValue() : ""));
                }
                msg(s, "<gray>" + t.getName() + ": " + (names.isEmpty() ? "없음" : String.join("<gray>, ", names)));
            }
            default -> msg(s, "/증강관리 증강 <추가|제거|초기화|목록> <플레이어> [증강id]");
        }
    }

    private void adminHelp(CommandSender s) {
        msg(s, "<#ffcc55>━━━━ 증강관리 ━━━━");
        msg(s, "<white>무기 <id> [플레이어]  <gray>무기 지급 (/무기도감 에서 클릭해도 됨)");
        msg(s, "<white>아이템 <id> [개수] [플레이어]  <gray>shard, prism_crystal, ticket_silver ...");
        msg(s, "<white>갑옷 <세트> [부위|전부] [플레이어]  <gray>/갑옷도감 에서 클릭해도 됨");
        msg(s, "<white>증강 <추가|제거|초기화|목록> <플레이어> [id]");
        msg(s, "<white>선택지 <플레이어> <등급>  <gray>제단 없이 선택창 열기");
        msg(s, "<white>소환 <몬스터id> [플레이어|x y z]");
        msg(s, "<white>제단 <등급> / 균열 <id> / 둥지 <보스id>  <gray>지금 위치에 세우기");
        msg(s, "<white>맵생성 [월드] [강제]  <gray>빈 공허 월드에 맵 전체 짓기");
        msg(s, "<white>섬 <종류> [반지름] / 섬검사  <gray>섬 하나 지어 보기 / 지은 맵의 섬마다 재료 확인");
        msg(s, "<white>리로드, 리소스팩, 정보");
    }

    private Player target(CommandSender s, String[] a, int idx) {
        if (a.length > idx) return Bukkit.getPlayerExact(a[idx]);
        return s instanceof Player p ? p : null;
    }

    private static int parseInt(String s, int def) {
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException e) {
            return def;
        }
    }

    private static double parseD(String s) {
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    // ------------------------------------------------------------------ 탭 완성

    @Override
    public List<String> onTabComplete(CommandSender s, Command cmd, String label, String[] a) {
        List<String> out = new ArrayList<>();
        switch (cmd.getName()) {
            case "augment" -> {
                if (a.length == 1) out.addAll(List.of("도감", "선택", "제단", "책", "도움"));
                else if (a.length == 2 && a[0].equals("도감")) out.addAll(List.of("실버", "골드", "프리즘"));
            }
            case "augadmin" -> {
                if (!s.hasPermission("augsky.admin")) return out;
                if (a.length == 1) {
                    out.addAll(List.of("무기", "아이템", "증강", "갑옷", "선택지", "소환", "제단", "균열", "둥지", "맵생성", "섬", "섬검사",
                            "리로드", "리소스팩", "정보"));
                } else {
                    switch (a[0]) {
                        case "무기", "weapon" -> {
                            if (a.length == 2) out.addAll(plugin.weapons().all().keySet());
                            if (a.length == 3) players(out);
                        }
                        case "아이템", "item" -> {
                            if (a.length == 2) out.addAll(plugin.items().all().keySet());
                            if (a.length == 4) players(out);
                        }
                        case "증강", "augment" -> {
                            if (a.length == 2) out.addAll(List.of("추가", "제거", "초기화", "목록"));
                            if (a.length == 3) players(out);
                            if (a.length == 4) out.addAll(plugin.augments().registry().all().keySet());
                        }
                        case "선택지", "offer" -> {
                            if (a.length == 2) players(out);
                            if (a.length == 3) out.addAll(List.of("실버", "골드", "프리즘"));
                        }
                        case "소환", "spawn" -> {
                            if (a.length == 2) out.addAll(plugin.mobs().registry().all().keySet());
                            if (a.length == 3) players(out);
                        }
                        case "제단", "altar" -> out.addAll(List.of("실버", "골드", "프리즘"));
                        case "섬", "island" -> {
                            if (a.length == 2) out.addAll(MapBuilder.kinds());
                        }
                        case "맵생성", "buildmap" -> {
                            out.add("강제");
                            for (World w : Bukkit.getWorlds()) out.add(w.getName());
                        }
                        case "갑옷", "armor" -> out.addAll(plugin.armor().all().keySet());
                        case "균열", "rift" -> out.addAll(plugin.mobs().registry().rifts().keySet());
                        case "둥지", "lair" -> {
                            for (var d : plugin.mobs().registry().all().values()) if (d.boss()) out.add(d.id());
                        }
                        default -> {
                        }
                    }
                }
            }
            default -> {
            }
        }
        String last = a.length == 0 ? "" : a[a.length - 1].toLowerCase(Locale.ROOT);
        out.removeIf(x -> !x.toLowerCase(Locale.ROOT).startsWith(last));
        return out;
    }

    private static void players(List<String> out) {
        for (Player p : Bukkit.getOnlinePlayers()) out.add(p.getName());
    }

}
