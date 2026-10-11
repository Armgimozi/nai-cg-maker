package kr.augsky.vfx;

import kr.augsky.util.Fx;
import org.bukkit.Color;
import org.bukkit.Material;
import org.bukkit.Particle;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * 속성별 색·입자·소리. a = 바깥 빛(채도 높은 중간색, 낮 하늘에서도 보이게), b = 안쪽 밝은 띠(파스텔),
 * dark = 낮에 윤곽을 잡아 주는 테두리색. 색이 겹치는 속성(번개/서리, 독/숲, 빛/황금)은 일부러 떨어뜨려 두었다.
 */
public record Palette(String id, Color a, Color b, Color dark, Fx.Spec spark, Fx.Spec mote, Fx.Spec accent,
                      Material[] debris, Snd[] cast, Snd[] impact, boolean rainbow) {

    public record Snd(String key, float vol, float pitch) {}

    private static final Map<String, Palette> ALL = new HashMap<>();

    private static Snd s(String k, double v, double p) {
        return new Snd(k, (float) v, (float) p);
    }

    private static Color c(int rgb) {
        return Color.fromRGB(rgb);
    }

    private static void put(String id, int a, int b, int dark, String spark, String mote, String accent,
                            Material[] debris, Snd[] cast, Snd[] impact) {
        ALL.put(id, new Palette(id, c(a), c(b), c(dark), Fx.parse(spark), Fx.parse(mote), Fx.parse(accent),
                debris, cast, impact, false));
    }

    private static Material[] m(Material... ms) {
        return ms;
    }

    private static Snd[] snd(Snd... ss) {
        return ss;
    }

    static {
        put("frost", 0x3aa8ff, 0xdff8ff, 0x123a8a, "SNOWFLAKE", "END_ROD", "ITEM_SNOWBALL",
                m(Material.PACKED_ICE, Material.BLUE_ICE, Material.SNOW_BLOCK),
                snd(s("block.amethyst_block.chime", 1.0, 0.6)),
                snd(s("block.glass.break", 0.7, 1.6), s("block.powder_snow.break", 1.0, 0.8)));
        put("flame", 0xff6a10, 0xffd35c, 0x4a1206, "FLAME", "SMALL_FLAME", "LAVA",
                m(Material.MAGMA_BLOCK, Material.NETHERRACK, Material.BLACKSTONE),
                snd(s("entity.blaze.shoot", 0.6, 1.0)),
                snd(s("item.firecharge.use", 0.7, 1.0), s("block.fire.extinguish", 0.4, 0.6)));
        put("abyss", 0x9a3aff, 0xe6b0ff, 0x14001e, "REVERSE_PORTAL", "PORTAL", "DUST:#1a0028:1.4",
                m(Material.CRYING_OBSIDIAN, Material.OBSIDIAN),
                snd(s("entity.enderman.teleport", 0.6, 0.6)),
                snd(s("block.respawn_anchor.deplete", 0.6, 1.2)));
        put("shadow", 0x6a5a9a, 0xc0b8f0, 0x08080c, "LARGE_SMOKE", "SMOKE", "SQUID_INK",
                m(Material.BLACKSTONE, Material.DEEPSLATE),
                snd(s("entity.illusioner.mirror_move", 0.7, 1.0)),
                snd(s("entity.illusioner.mirror_move", 0.5, 1.5)));
        put("ender", 0x1ac8a0, 0xc8fff0, 0x0a3a3a, "PORTAL", "REVERSE_PORTAL", "END_ROD",
                m(Material.END_STONE),
                snd(s("entity.enderman.teleport", 0.6, 1.0)),
                snd(s("entity.enderman.teleport", 0.5, 1.4)));
        put("storm", 0xfff04a, 0x5ae8ff, 0x2a2a70, "ELECTRIC_SPARK", "END_ROD", "FIREWORK",
                m(Material.STONE, Material.COBBLED_DEEPSLATE),
                snd(s("entity.lightning_bolt.impact", 0.5, 1.6)),
                snd(s("entity.lightning_bolt.impact", 0.6, 1.2), s("block.respawn_anchor.charge", 0.3, 2.0)));
        put("holy", 0xffb81a, 0xfffbe8, 0x8a5a10, "END_ROD", "WAX_OFF", "WAX_ON",
                m(Material.QUARTZ_BLOCK, Material.GOLD_BLOCK),
                snd(s("block.beacon.power_select", 0.6, 1.5)),
                snd(s("block.bell.use", 0.5, 1.6), s("block.amethyst_block.resonate", 0.6, 1.2)));
        put("gold", 0xe8b020, 0xfff4c0, 0x6a4a10, "WAX_ON", "END_ROD", "WAX_ON",
                m(Material.GOLD_BLOCK, Material.RAW_GOLD_BLOCK),
                snd(s("block.amethyst_block.chime", 0.8, 1.2)),
                snd(s("block.amethyst_block.chime", 0.8, 1.6)));
        put("sun", 0xff9a10, 0xfff3a0, 0xa03a00, "FLAME", "WAX_ON", "END_ROD",
                m(Material.MAGMA_BLOCK, Material.SHROOMLIGHT),
                snd(s("entity.blaze.shoot", 0.6, 0.6)),
                snd(s("block.beacon.activate", 0.5, 1.4), s("item.firecharge.use", 0.6, 0.8)));
        put("blood", 0xd0002f, 0xff6a7e, 0x3a0010, "DUST:#c4002f:1.4", "DAMAGE_INDICATOR", "BLOCK:redstone_block",
                m(Material.NETHER_WART_BLOCK, Material.REDSTONE_BLOCK),
                snd(s("entity.player.attack.sweep", 0.6, 0.5)),
                snd(s("item.trident.hit", 0.6, 0.6), s("entity.player.attack.crit", 0.5, 0.7)));
        put("nature", 0x3ad040, 0xc8ff9a, 0x1e4a10, "HAPPY_VILLAGER", "COMPOSTER", "BLOCK:azalea_leaves",
                m(Material.MOSS_BLOCK, Material.DIRT, Material.AZALEA_LEAVES),
                snd(s("block.azalea_leaves.place", 1.0, 1.0)),
                snd(s("block.grass.break", 0.8, 1.0), s("block.azalea_leaves.break", 0.7, 0.8)));
        put("venom", 0xb8ff1a, 0xeaff9a, 0x4a1a6a, "DUST:#b8ff1a:1.2", "ITEM_SLIME", "SNEEZE",
                m(Material.SLIME_BLOCK, Material.MOSS_BLOCK),
                snd(s("entity.llama.spit", 0.8, 1.0)),
                snd(s("block.slime_block.place", 0.8, 1.0), s("block.honey_block.break", 0.6, 0.7)));
        put("ocean", 0x10b8d0, 0xc8ffff, 0x0a4a6a, "SPLASH", "BUBBLE_POP", "FALLING_WATER",
                m(Material.PRISMARINE, Material.PRISMARINE_BRICKS),
                snd(s("entity.player.splash.high_speed", 0.6, 1.0)),
                snd(s("entity.generic.splash", 0.7, 1.0), s("block.bubble_column.upwards_inside", 0.8, 1.0)));
        put("earth", 0xc88a3a, 0xf0d090, 0x4a3218, "BLOCK:coarse_dirt", "DUST_PLUME", "BLOCK_CRUMBLE:dirt",
                m(Material.DIRT, Material.COARSE_DIRT, Material.STONE),
                snd(s("item.mace.smash_ground", 0.6, 1.0)),
                snd(s("item.mace.smash_ground", 0.7, 0.8), s("block.rooted_dirt.break", 0.8, 0.7)));
        put("wind", 0x5ae8c0, 0xffffff, 0x2a6a70, "CLOUD", "SMALL_GUST", "GUST",
                m(),
                snd(s("entity.breeze.wind_burst", 0.6, 1.2)),
                snd(s("entity.breeze.whirl", 0.6, 1.2)));
        put("star", 0x6a5aff, 0xffffff, 0x1a1a5a, "END_ROD", "FIREWORK", "DUST:#ffd86a:1.0",
                m(Material.AMETHYST_BLOCK, Material.END_STONE),
                snd(s("entity.firework_rocket.twinkle", 0.6, 1.0)),
                snd(s("block.amethyst_block.chime", 0.9, 1.5)));
        put("crystal", 0xb06aff, 0xffd0ff, 0x5a2a8a, "DUST:#c58cff:1.2", "END_ROD", "ITEM:amethyst_shard",
                m(Material.AMETHYST_BLOCK, Material.BUDDING_AMETHYST),
                snd(s("block.amethyst_block.resonate", 0.7, 1.0)),
                snd(s("block.amethyst_cluster.break", 0.8, 1.0)));
        // 종말: 보랏빛 몸 + 영혼 청록 안쪽 띠 (청록이 바깥이면 낮 잔디 위에서 얼음·빛 속성처럼 보인다)
        put("doom", 0x8a2aff, 0x4af0ff, 0x14001e, "SOUL_FIRE_FLAME", "SCULK_SOUL", "DUST:#3a0066:1.6",
                m(Material.CRYING_OBSIDIAN, Material.BLACKSTONE, Material.SCULK),
                snd(s("entity.wither.shoot", 0.5, 0.4)),
                snd(s("particle.soul_escape", 1.0, 0.8), s("block.sculk.break", 0.5, 0.6)));
        // 창세 지팡이: 프리즘 무기지만 흰 금빛 + 초록 생명으로 다른 프리즘 무기와 구분한다
        put("genesis", 0xffd86a, 0xfffbe8, 0x2a6a20, "END_ROD", "WAX_OFF", "HAPPY_VILLAGER",
                m(Material.QUARTZ_BLOCK, Material.MOSS_BLOCK, Material.GOLD_BLOCK),
                snd(s("block.beacon.power_select", 0.6, 1.3)),
                snd(s("block.amethyst_block.resonate", 0.7, 1.4)));
        ALL.put("prism", new Palette("prism", c(0xff6b9d), c(0xffffff), c(0x2a2a4a), Fx.parse("END_ROD"),
                Fx.parse("FIREWORK"), Fx.parse("DUST:#ffffff:1.2"),
                m(Material.AMETHYST_BLOCK, Material.QUARTZ_BLOCK, Material.GLASS),
                snd(s("block.amethyst_block.resonate", 0.8, 1.0)),
                snd(s("block.beacon.power_select", 0.5, 2.0), s("block.amethyst_block.chime", 0.8, 1.4)), true));
        for (String base : new String[]{"iron", "stone", "wood", "bone", "copper"}) {
            int rgb = switch (base) {
                case "stone" -> 0xa8a8a8;
                case "wood" -> 0xd9a86a;
                case "bone" -> 0xece6c8;
                case "copper" -> 0xe8916a;
                default -> 0xd8dde3;
            };
            Material deb = switch (base) {
                case "stone" -> Material.STONE;
                case "wood" -> Material.OAK_PLANKS;
                case "bone" -> Material.BONE_BLOCK;
                case "copper" -> Material.COPPER_BLOCK;
                default -> Material.IRON_BLOCK;
            };
            put(base, rgb, 0xffffff, 0x1c1f24, "CRIT", "CRIT", "SWEEP_ATTACK", m(deb),
                    snd(s("entity.player.attack.sweep", 0.5, 1.2)), snd(s("entity.player.attack.strong", 0.5, 1.0)));
        }
    }

    public static Palette of(String element) {
        if (element == null) return ALL.get("iron");
        String e = element.toLowerCase(Locale.ROOT);
        if (e.equals("void")) e = "abyss";
        Palette p = ALL.get(e);
        return p != null ? p : ALL.get("iron");
    }

    /** 몬스터 id(와 스킬 id)로 속성을 고른다. 보스 셋은 이름으로 바로 정한다 */
    public static Palette forMob(String mobId, String skillId) {
        String k = ((mobId == null ? "" : mobId) + " " + (skillId == null ? "" : skillId)).toLowerCase(Locale.ROOT);
        if (k.contains("frost_tyrant")) return of("frost");
        if (k.contains("inferno_colossus")) return of("flame");
        if (k.contains("void_sovereign")) return of("abyss");
        String[][] map = {
                {"frost|ice|blizzard|snow|frozen", "frost"},
                {"lava|magma|cinder|inferno|ember|fire|flame|meteor|imp|bomb", "flame"},
                {"void", "abyss"},
                {"venom|spider|poison", "venom"},
                {"crystal", "crystal"},
                {"moss", "nature"},
                {"shadow|blink", "shadow"},
                {"bone|sniper|piercing", "bone"},
                {"miner", "stone"},
        };
        for (String[] row : map) {
            for (String w : row[0].split("\\|")) if (k.contains(w)) return of(row[1]);
        }
        return of("iron");
    }

    // ------------------------------------------------------------------ 색 도우미

    public static Color hue(double h, double sat, double val) {
        java.awt.Color c = java.awt.Color.getHSBColor((float) (((h % 1) + 1) % 1), (float) sat, (float) val);
        return Color.fromRGB(c.getRed(), c.getGreen(), c.getBlue());
    }

    public static Color hue(double h) {
        return hue(h, 0.62, 1.0);
    }

    public static double luma(Color c) {
        return (0.2126 * c.getRed() + 0.7152 * c.getGreen() + 0.0722 * c.getBlue()) / 255.0;
    }

    public static boolean nearWhite(Color c) {
        return c.getRed() > 225 && c.getGreen() > 225 && c.getBlue() > 225;
    }

    /**
     * 낮의 가장자리 테 색: 거의 검은 dark 를 그대로 쓰면 잔디 위 판이 검은 윤곽 스티커처럼 보인다.
     * 주색을 어둡게 한 색(주색 55% + dark 45%)이면 낮 하늘 앞에서도 또렷하고 바닥에서는 같은 빛의 그늘로 보인다
     */
    public static Color rimOf(Color a, Color dark) {
        return mix(a, dark, 0.45);
    }

    public static Color mix(Color x, Color y, double t) {
        t = Math.max(0, Math.min(1, t));
        return Color.fromRGB((int) (x.getRed() + (y.getRed() - x.getRed()) * t),
                (int) (x.getGreen() + (y.getGreen() - x.getGreen()) * t),
                (int) (x.getBlue() + (y.getBlue() - x.getBlue()) * t));
    }

    /** YAML 입자에 적힌 색. DUST, DUST_COLOR_TRANSITION, ENTITY_EFFECT 만 색이 있다 */
    public static Color[] yamlColors(Fx.Spec s) {
        if (s == null || s.data() == null) return null;
        if (s.data() instanceof Particle.DustTransition t) return new Color[]{t.getColor(), t.getToColor()};
        if (s.data() instanceof Particle.DustOptions d) return new Color[]{d.getColor()};
        if (s.data() instanceof Color c) return new Color[]{c};
        return null;
    }
}
