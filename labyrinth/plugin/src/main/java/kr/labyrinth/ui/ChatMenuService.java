package kr.labyrinth.ui;

import kr.labyrinth.Services;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.DerivedStats;
import kr.labyrinth.stats.Stat;
import org.bukkit.entity.Player;

/**
 * 기본 메뉴 구현: GUI 대신 클릭 가능한 채팅 메시지. ui 담당의 GUI 가 붙기 전에도 게임이 진행되게 한다.
 */
public class ChatMenuService implements MenuService {

    protected final Services services;

    public ChatMenuService(Services services) { this.services = services; }

    private static String button(String label, String command, String hover) {
        return "<click:run_command:'" + command + "'><hover:show_text:'" + hover + "'>" + label + "</hover></click>";
    }

    @Override
    public void openMain(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<gradient:#c9a2ff:#7fd8ff><b>━━━━ 미궁 라비린스 ━━━━</b></gradient>"));
        p.sendMessage(Text.mm("<gray>Lv.<white>" + d.level() + "</white>  골드 <gold>" + Text.num(d.gold())
                + "</gold>  해금 <aqua>지하 " + d.unlockedFloor() + "층</aqua>"));
        p.sendMessage(Text.mm(button("<green>[입장]</green>", "/lab enter", "층 선택") + "  "
                + button("<yellow>[스탯]</yellow>", "/stats", "스탯 분배") + "  "
                + button("<aqua>[직업]</aqua>", "/class", "직업") + "  "
                + button("<light_purple>[칭호]</light_purple>", "/title", "칭호") + "  "
                + button("<white>[파티]</white>", "/party", "파티")));
    }

    @Override
    public void openStats(Player p) {
        PlayerData d = services.data().get(p);
        DerivedStats s = services.stats().get(p);
        p.sendMessage(Text.mm("<gradient:#ffd84f:#ff9f43><b>━━━━ 스탯 ━━━━</b></gradient>  <gray>남은 포인트 <yellow>"
                + d.statPoints() + "</yellow>"));
        for (Stat st : Stat.values()) {
            String plus = d.statPoints() > 0
                    ? " " + button("<green>[+1]</green>", "/stats add " + st.name() + " 1", st.displayName() + " +1")
                    + " " + button("<dark_green>[+5]</dark_green>", "/stats add " + st.name() + " 5", st.displayName() + " +5")
                    : "";
            p.sendMessage(Text.mm("<" + st.color() + ">" + st.displayName() + " <gray>(" + st.name() + ")</gray> <white>"
                    + s.stat(st) + "</white> <dark_gray>(투자 " + d.allocated(st) + ")</dark_gray>" + plus));
        }
        p.sendMessage(Text.mm("<gray>공격력 <white>" + Text.num(s.attackPower()) + "</white> · 최대 HP <white>"
                + Text.num(s.maxHp()) + "</white> · 최대 MP <white>" + Text.num(s.maxMp()) + "</white> · 방어 <white>"
                + Text.num(s.defense()) + "</white>"));
        p.sendMessage(Text.mm("<gray>치명타 <white>" + Text.pct(s.critChance()) + "</white> ×" + String.format("%.2f", s.critDamage())
                + " · 회피 <white>" + Text.pct(s.evasion()) + "</white> · 피해감소 <white>" + Text.pct(s.damageReduction())
                + "</white> · 재사용감소 <white>" + Text.pct(s.cooldownReduction()) + "</white>"));
        // 겉모습 (look_spec §6.2): 판금·가죽·천 부위 수 → 4부위 효과 · 이동 속도 · 재사용 대기 배율
        var looks = services.settings().armorLooks();
        int shield = Math.max(0, s.lookCount(kr.labyrinth.content.ArmorLook.HEAVY)
                - s.bodyLooks().getOrDefault(kr.labyrinth.content.ArmorLook.HEAVY, 0));
        p.sendMessage(Text.mm(kr.labyrinth.ui.menus.StatsMenu.lookSummary(looks, s.bodyLooks(), shield, s.fullLook())
                + " <gray>· 이동 속도 <white>" + kr.labyrinth.ui.menus.StatsMenu.signedPct(s.moveSpeed())
                + "</white> · 재사용 대기 <white>×" + String.format(java.util.Locale.ROOT, "%.2f", s.cooldownMult()) + "</white>"));
    }

    @Override
    public void openClass(Player p) {
        ClassDef cur = services.classes().classOf(p);
        p.sendMessage(Text.mm("<aqua><b>━━━━ 직업 ━━━━</b></aqua>  <gray>현재: " + (cur == null ? "없음"
                : "<" + cur.color() + ">" + cur.name())));
        for (ClassDef c : services.content().classes().values()) {
            p.sendMessage(Text.mm("<" + c.color() + ">● " + c.name() + "</" + c.color() + "> <dark_gray>(" + c.role() + ")</dark_gray> ")
                    .append(Text.mm(c.description())));
        }
        var rule = services.settings().classChange();
        p.sendMessage(Text.mm("<gray>/직업 선택 <직업> — 첫 직업은 무료"
                + (rule.requireItem() ? ", 그 뒤로는 바꿀 때마다 두루마리 1장" : "")
                + (rule.cooldownHours() > 0 ? ", 바꾼 뒤 " + kr.labyrinth.classes.ClassChangeRule.hours(rule.cooldownHours()) + " 대기" : "")));
    }

    @Override
    public void openParty(Player p) {
        p.performCommand("party info");
    }

    @Override
    public void openTitles(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<light_purple><b>━━━━ 칭호 ━━━━</b></light_purple>  <gray>칭호마다 서버에서 단 한 명"));
        for (var def : services.content().achievements().values()) {
            var r = services.records().get(kr.labyrinth.titles.TitleView.recordKey(def.id())).orElse(null);
            var o = r == null ? null : new kr.labyrinth.titles.TitleView.Owner(r.names().isEmpty() ? "?" : r.names().get(0), r.time());
            p.sendMessage(Text.mm(kr.labyrinth.titles.TitleView.listLine(def, o, d.hasAchievement(def.id()), services.content())));
        }
    }

    @Override
    public void openEntrance(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<green><b>━━━━ 미궁 입장 ━━━━</b></green>"));
        for (FloorDef f : services.content().floors().values()) {
            boolean open = f.number() <= d.unlockedFloor();
            String label = (open ? "<green>" : "<dark_gray>") + "[지하 " + f.number() + "층] " + Text.strip(f.name());
            p.sendMessage(Text.mm(open ? button(label, "/lab enter " + f.number(), "입장") : label + " <red>잠김"));
        }
    }

    @Override
    public void openSetup(Player p) {
        p.sendMessage(Text.mm("<gradient:#c9a2ff:#7fd8ff><b>━━━━ 미궁 라비린스 초기 설정 ━━━━</b></gradient>"));
        p.sendMessage(Text.mm("<gray>서버 난이도를 골라 주세요. 나중에 <white>/미궁 난이도</white> 로 바꿀 수 있습니다."));
        StringBuilder sb = new StringBuilder();
        for (Difficulty d : services.settings().difficulties().values()) {
            // 난이도 배율 한 벌 (관리자가 층 램프를 직접 적었을 때만 1층 값→원래 값, 지하 N층부터 최대)
            Difficulty first = d.atFloor(1);
            String ramp = d.ramp() == null ? "" : " (지하 " + d.ramp().fullFloor() + "층부터 최대)";
            sb.append(button("<yellow>[" + d.name() + "]</yellow>", "/lab difficulty " + d.id(),
                    "몹 HP ×" + range(first.hp(), d.hp()) + " · 피해 ×" + range(first.damage(), d.damage()) + ramp
                            + " · 드롭 ×" + num(d.drop()))).append("  ");
        }
        p.sendMessage(Text.mm(sb.toString()));
    }

    private static String num(double v) {
        return java.math.BigDecimal.valueOf(Math.round(v * 100) / 100.0).stripTrailingZeros().toPlainString();
    }

    /** 직접 적은 층 램프 범위 "1.5→1.8" (램프가 없어 같으면 하나). */
    private static String range(double from, double to) {
        String a = num(from), b = num(to);
        return a.equals(b) ? b : a + "→" + b;
    }

    @Override
    public void openAccessories(Player p) {
        Text.send(p, "<gray>장신구 칸은 <white>/미궁 장신구</white> 메뉴에서 관리합니다.");
    }
}
