package kr.labyrinth.ui.menus;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ResolvableProfile;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.pvp.PvpConfig;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/** /미궁 — 메인 메뉴: 프로필 + 광산·입장·파티·PvP 규칙·스탯·직업·칭호·장신구·대장간·상점·기록·마을 바로가기. */
public final class MainMenu extends LabMenu {

    public MainMenu(Services services) {
        super(services, "main", 6, "<gradient:#c9a2ff:#7fd8ff>미궁 라비린스</gradient>");
    }

    static ItemStack head(Player p, String name, List<String> lore) {
        ItemStack s = Button.icon(Material.PLAYER_HEAD, name, lore);
        try {
            s.setData(DataComponentTypes.PROFILE, ResolvableProfile.resolvableProfile(p.getPlayerProfile()));
        } catch (Throwable ignored) {
            // 프로필이 없어도 머리만 기본 모양
        }
        return s;
    }

    @Override
    protected void draw(Player p) {
        PlayerData d = services.data().get(p);
        ClassDef cls = services.classes().classOf(p);
        AchievementDef title = services.titles().equipped(p);
        boolean max = d.level() >= services.levels().maxLevel();
        double xp = max ? 1 : services.levels().progress(p);
        List<String> lore = new ArrayList<>();
        lore.add("<gray>레벨 <#ffd84f>" + d.level() + "</#ffd84f> <dark_gray>|</dark_gray> <#b8f05a>"
                + UiTheme.bar(xp, 12, "▮", "▯") + " " + (max ? "MAX" : Text.pct(xp)));
        lore.add("<gray>직업 " + (cls == null ? "<dark_gray>없음 — 직업 메뉴에서 선택" : "<" + cls.color() + ">" + cls.name()));
        lore.add("<gray>칭호 " + (title == null ? "<dark_gray>없음" : title.title()));
        lore.add("<gray>골드 <#f2c14e>" + Text.num(d.gold()) + "</#f2c14e> <dark_gray>|</dark_gray> 해금 <#7fd8ff>지하 " + d.unlockedFloor() + "층");
        lore.add("<gray>스탯 포인트 " + (d.statPoints() > 0 ? "<#7fe07f>" + d.statPoints() + " 남음" : "<dark_gray>0"));
        lore.add("");
        lore.add("<gray>서버 난이도: " + (services.settings().isDifficultySet()
                ? "<white>" + services.settings().difficulty().name() : "<#ff6b6b>미설정"));
        deco(4, head(p, "<white><b>" + Text.escape(p.getName()) + "</b>", lore));

        if (services.mine().enabled()) {
            boolean inMine = services.mine().isMineWorld(p.getWorld());
            set(13, model("copper_pickaxe", Material.IRON_PICKAXE, "<#e8c58a><b>광산</b>",
                    List.of("<gray>몬스터 없는 광산에서 광석을 캡니다.", "<gray>여섯 층 모두 열려 있고, 광맥은 모두가 함께 씁니다.",
                            "", "<#ffd36b>클릭: " + (inMine ? "승강기" : "광산으로") + " <dark_gray>(/미궁 광산)")),
                    ctx -> { click(ctx.player()); ctx.player().closeInventory(); services.mine().openMine(ctx.player()); });
        }
        set(20, model("labyrinth_essence", Material.ENDER_EYE, "<#7fd8ff><b>미궁 입장</b>",
                List.of("<gray>층을 골라 미궁으로 내려갑니다.", "<gray>파티라면 파티장이 시작합니다.", "", "<#ffd36b>클릭: 입장 메뉴")),
                ctx -> { click(ctx.player()); services.menus().openEntrance(ctx.player()); });
        int partySize = services.party().size(p);
        set(22, Button.icon(Material.CAKE, "<#c9a2ff><b>파티</b>",
                List.of(partySize > 1 ? "<gray>현재 파티 <white>" + partySize + "명" : "<gray>혼자입니다.",
                        "<gray>인원이 많을수록 미궁이 강해지고 보상도 늘어납니다.", "", "<#ffd36b>클릭: 파티 관리")),
                ctx -> { click(ctx.player()); services.menus().openParty(ctx.player()); });
        set(24, Button.icon(Material.IRON_SWORD, "<#ff6b6b><b>PvP 규칙</b>", pvpLore()),
                ctx -> { click(ctx.player()); services.menus().openParty(ctx.player()); });

        set(29, model("berserker_emblem", Material.BLAZE_POWDER, "<#ffd84f><b>스탯</b>",
                List.of("<gray>남은 포인트 " + (d.statPoints() > 0 ? "<#7fe07f>" + d.statPoints() : "<dark_gray>0"),
                        "<gray>힘·민첩·지능·체력·정신·행운을 올립니다.", "", "<#ffd36b>클릭: 스탯 분배")),
                ctx -> { click(ctx.player()); services.menus().openStats(ctx.player()); });
        set(31, model(cls == null ? "guardian_emblem" : cls.iconItem(), Material.SHIELD, "<#7fb2ff><b>직업</b>",
                List.of("<gray>현재 " + (cls == null ? "<dark_gray>없음" : "<" + cls.color() + ">" + cls.name()),
                        "<gray>6가지 역할군 · 스킬 설명", "", "<#ffd36b>클릭: 직업 메뉴")),
                ctx -> { click(ctx.player()); services.menus().openClass(ctx.player()); });
        set(33, model("first_seal", Material.NAME_TAG, "<#ffd36b><b>칭호</b>",
                List.of("<gray>내 칭호 <white>" + d.achievements().size() + "</white> · 칭호마다 서버에서 단 한 명",
                        "<gray>장착한 칭호는 채팅·탭·이름표에 표시됩니다.", "", "<#ffd36b>클릭: 칭호 목록")),
                ctx -> { click(ctx.player()); services.menus().openTitles(ctx.player()); });

        set(38, Button.icon(Material.AMETHYST_SHARD, "<#c79bff><b>장신구</b>",
                List.of("<gray>반지·목걸이 2칸을 장착합니다.", "", "<#ffd36b>클릭: 장신구 칸")),
                ctx -> { click(ctx.player()); services.menus().openAccessories(ctx.player()); });
        set(40, model("forge_core", Material.ANVIL, "<#ff9a4d><b>대장간</b>",
                List.of("<gray>몬스터 재료로 장비를 만듭니다.", "<dark_gray>(마을의 대장장이 두르간에게서도 열 수 있습니다)", "", "<#ffd36b>클릭: 제작 목록")),
                ctx -> { click(ctx.player()); services.menus().openBlacksmith(ctx.player()); });
        set(42, model("healing_potion", Material.POTION, "<#8fd16a><b>상점</b>",
                List.of("<gray>물약·주문서를 삽니다.", "", "<#ffd36b>클릭: 떠돌이 상인 핀의 상점")),
                ctx -> { click(ctx.player()); services.menus().openMerchant(ctx.player()); });

        set(49, Button.icon(Material.WRITABLE_BOOK, "<#ffd36b><b>서버 최초 기록</b>",
                List.of("<gray>각 층을 처음 돌파한 파티와 최단 기록.", "", "<#ffd36b>클릭: 기록 보기")),
                ctx -> { click(ctx.player()); new RecordsMenu(services, MainMenu::reopen).open(ctx.player()); });
        set(47, Button.icon(Material.KNOWLEDGE_BOOK, "<#ffd36b><b>미궁 도감</b>",
                List.of("<gray>모든 무기·방어구·장신구·재료와", "<gray>몬스터·보스, 그리고 어디서 얻는지.", "", "<#ffd36b>클릭: 도감 열기 <dark_gray>(/도감)")),
                ctx -> { click(ctx.player()); new CodexMenu(services).open(ctx.player()); });
        if (services.dungeon().currentInstance(p).isPresent()) {
            set(51, Button.icon(Material.FILLED_MAP, "<#7fd8ff><b>탐험 지도</b>",
                    List.of("<gray>지금 층에서 파티가 지나온 길을", "<gray>채팅에 그립니다. <dark_gray>(/미궁 지도)", "",
                            "<dark_gray>지도를 들고 우클릭해도 됩니다.", "", "<#ffd36b>클릭: 지도 보기")),
                    ctx -> { click(ctx.player()); ctx.player().closeInventory(); services.dungeon().showMap(ctx.player()); });
        } else {
            boolean village = kr.labyrinth.village.VillageService.present();
            set(51, Button.icon(Material.LANTERN, "<#ffd36b><b>마을</b>",
                    village ? List.of("<gray>등불 광장으로 돌아갑니다.", "<dark_gray>(미궁 안에서는 먼저 /미궁 귀환)", "", "<#ffd36b>클릭: 광장으로 <dark_gray>(/미궁 마을)")
                            : List.of("<dark_gray>이 월드에는 마을이 없습니다.", "<dark_gray>(서버팩의 world 폴더를 쓰세요)")),
                    ctx -> {
                        click(ctx.player());
                        ctx.player().closeInventory();
                        kr.labyrinth.village.VillageService.teleportCommand(ctx.player());
                    });
        }
        set(45, UiTheme.close(), ctx -> ctx.player().closeInventory());
        if (kr.labyrinth.core.ServerSetup.canOpenSetup(p)) {
            set(53, Button.icon(Material.COMMAND_BLOCK, "<#ff6b6b><b>서버 설정</b> <gray>(난이도)",
                    List.of("<gray>서버 난이도 · 입구 방식", "", "<#ffd36b>클릭: 초기 설정 메뉴")),
                    ctx -> { click(ctx.player()); services.menus().openSetup(ctx.player()); });
        }
    }

    /** PvP = 따로 신청하는 대전 없이 파티 규칙 하나 (GDD §18). */
    private List<String> pvpLore() {
        PvpConfig pc = services.targets().pvpConfig();
        List<String> lore = new ArrayList<>();
        if (pc.enabled()) {
            lore.add("<gray>같은 <#7fe07f>파티원</#7fe07f>끼리는 어디서든 서로 다치지 않습니다.");
            lore.add("<gray>그 밖의 플레이어는 야생·미궁 어디서든 공격할 수 있고,");
            lore.add("<gray>스킬·화살·물약도 똑같이 맞습니다." + (pc.safeZoneVillage() ? " <dark_gray>(마을 안은 금지)" : ""));
            lore.add("<gray>스킬을 몰아 맞으면 쓰러질 수 있습니다."
                    + (pc.maxHitRatio() < 1 ? " <dark_gray>(한 번에 최대 HP " + Text.pct(pc.maxHitRatio()) + ")" : ""));
            lore.add("<gray>판금·방패·체력은 PvP 에서도 더 버팁니다.");
            lore.add("<gray>기절·속박은 짧고, 연달아 맞으면 더 짧아집니다.");
            lore.add("<gray>PvP 중 회복 <white>" + Text.pct(pc.healing()) + "</white> · 물약 <white>"
                    + Text.pct(pc.healing() * pc.potion()) + "</white> <dark_gray>(오래 싸우면 더 줄어듦)");
            if (pc.partyNameColor()) lore.add("<gray>내 파티원 이름은 <#7fe07f>초록색</#7fe07f>으로 보입니다.");
            var death = services.settings().death();
            if (death.keepInventory()) {
                lore.add("<gray>미궁 밖에서 쓰러지면 소지품" + (death.keepLevel() ? "·경험치 레벨" : "") + "은 지킵니다.");
            }
            String penalty = kr.labyrinth.core.DeathPenaltyRules.menuLine(services.settings().deathPenalty());
            if (penalty != null) lore.add("<gray>" + penalty);
        } else {
            lore.add("<gray>이 서버는 PvP 가 꺼져 있어");
            lore.add("<gray>플레이어끼리는 서로 다치지 않습니다.");
        }
        lore.add("");
        lore.add("<#ffd36b>클릭: 파티 관리");
        return lore;
    }

    /** 0.70 → "0.7", 1.0 → "1". */
    static String decimal(double v) {
        return java.math.BigDecimal.valueOf(Math.round(v * 100) / 100.0).stripTrailingZeros().toPlainString();
    }

    static void reopen(Player p) { Services.get().menus().openMain(p); }
}
