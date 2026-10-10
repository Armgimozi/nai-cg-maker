package kr.augsky.vfx;

import kr.augsky.skill.Mechanics;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.function.Supplier;

/**
 * 표시 엔티티 하나로 만든 연출 조각. 설정 → go() 로 띄우고, 키프레임은 나이(틱) 기준으로 예약한다.
 * 저장되지 않고(persistent false), 태그가 붙고, 수명이 다하면 Vfx 가 지운다.
 * 아이템 조각(팩 모델)은 팩을 받은 사람에게만 보이고, 나머지 사람에게는 fallback 입자를 보낸다.
 */
public final class Sprite {
    public enum Kind { ITEM, BLOCK, TEXT }

    /** 사라지는 방식. 고리·별은 살짝 커지며 흐려지고, 참격은 계속 돌며 흐려지고, 기둥·광선은 가늘어진다 */
    public enum End { FADE, SLASH, THIN, SHRINK, NONE }

    /** 시전자에게 보일지: 자동(얼굴 규칙) / 항상 / 숨김 / 시전자만 */
    public enum View { AUTO, SHOW, HIDE, ONLY }

    static final Quaternionf FLIP = new Quaternionf().rotateY((float) Math.PI);
    static final int AX_X = 1, AX_Y = 2, AX_Z = 4;

    final CastFx fx;
    final Vfx vfx;
    final Kind kind;
    Display e;
    String model;
    org.bukkit.inventory.ItemStack stack;
    Color ta = Color.WHITE, tb = Color.WHITE, tc = Color.fromRGB(0x222222);
    BlockData block;
    Component text;
    Location at;
    final Vector3f tr = new Vector3f();
    final Quaternionf rot = new Quaternionf();
    final Vector3f sc = new Vector3f(1, 1, 1);
    Display.Billboard bill = Display.Billboard.FIXED;
    float range = 1.0f;
    int life = 20, endLen = 3, thinAxes = AX_X | AX_Z;
    End end = End.FADE;
    View view = View.AUTO;
    double reveal;
    boolean revealed, decal, vertical, tele, centerBlock, worldLight;
    /** 시전자에게는 흐린 복제를 대신 보여 주므로 원본은 시전자에게 숨긴다 */
    boolean noCaster;
    /** 가로 폭 배율 (시전자용 가는 기둥 복제). 키프레임은 원본과 같은 값을 쓰고 여기서만 줄인다 */
    float xzMul = 1f;
    double radius = 1;
    Runnable fallback;
    int age, prio = -1;
    boolean dead, spawned, killed;
    final TreeMap<Integer, List<Consumer<Sprite>>> steps = new TreeMap<>();
    /** 모양을 바꾸는 예약 (모델 바꾸기·색 바꾸기). 프리즘 복제는 이것을 따라 하지 않는다 */
    final TreeMap<Integer, List<Consumer<Sprite>>> paints = new TreeMap<>();
    Supplier<Location> follow;
    int followEvery = 1;
    Vector vel;
    double grav;
    int moveEvery = 2;
    Location pos;
    boolean settled;
    float spinDeg;
    Vector3f spinAxis;
    final Set<UUID> shown = new HashSet<>();
    int hueEvery;
    double hueOff;
    /** 함께 다루는 짝 조각 (태양의 코로나 등) */
    public Sprite memo;
    /** 광선 조각: 시작점에서 segDir 로 segLen (얼굴 규칙을 선분 거리로 잰다) */
    double segLen;
    Vector segDir;
    /**
     * 하늘에 뜬 판(구름·소용돌이): 보는 눈이 판 평면과 이루는 각의 사인이 이보다 작으면(거의 옆에서 보면) 숨긴다.
     * 옆에서 본 판은 하늘을 가로지르는 흰 줄 하나로만 보였다
     */
    double edgeOn;
    /** 시전자 눈에서 이 거리 안이면 시전자에게 숨긴다 (튀는 파편 등). 0 = 쓰지 않음 */
    double selfNear;

    private Sprite(CastFx fx, Kind kind, Location at) {
        this.fx = fx;
        this.vfx = fx.vfx;
        this.kind = kind;
        this.at = at.clone();
    }

    // ------------------------------------------------------------------ 만들기

    /** 팩 모델 조각. 크기 1 = 모델 원래 크기 (Geo 참고) */
    public static Sprite item(CastFx fx, String model, Location at) {
        Sprite s = new Sprite(fx, Kind.ITEM, at);
        s.model = model;
        Geo g = Geo.of(model);
        s.end = g.end();
        s.thinAxes = g.thin();
        s.decal = g.flat();
        s.vertical = g.vertical();
        if (g.billboard()) s.bill = Display.Billboard.CENTER;
        if (g.vertical()) s.bill = Display.Billboard.VERTICAL;
        s.ta = fx.a();
        s.tb = fx.b();
        s.tc = fx.rim();
        return s;
    }

    /** 실제 아이템(무기 잔상 등). 팩이 없어도 바닐라 모양으로 보이므로 모두에게 보낸다 */
    public static Sprite stack(CastFx fx, org.bukkit.inventory.ItemStack it, Location at) {
        Sprite s = new Sprite(fx, Kind.ITEM, at);
        s.stack = it;
        s.end = End.SHRINK;
        return s;
    }

    public static Sprite block(CastFx fx, BlockData data, Location at) {
        Sprite s = new Sprite(fx, Kind.BLOCK, at);
        s.block = data;
        s.centerBlock = true;
        s.end = End.SHRINK;
        return s;
    }

    public static Sprite text(CastFx fx, Component text, Location at) {
        Sprite s = new Sprite(fx, Kind.TEXT, at);
        s.text = text;
        s.end = End.SHRINK;
        return s;
    }

    // ------------------------------------------------------------------설정 (go 전)

    public Sprite frame(Shapes.Frame f) {
        rot.set(f.quat());
        return this;
    }

    public Sprite rot(Quaternionf q) {
        rot.set(q);
        return this;
    }

    public Sprite size(double s) {
        sc.set((float) s);
        return this;
    }

    public Sprite size(double x, double y, double z) {
        sc.set((float) x, (float) y, (float) z);
        return this;
    }

    public Sprite offset(double x, double y, double z) {
        tr.set((float) x, (float) y, (float) z);
        return this;
    }

    public Sprite tint(Color a, Color b, Color c) {
        if (a != null) ta = a;
        if (b != null) tb = b;
        if (c != null) tc = c;
        return this;
    }

    public Sprite tint(CastFx.Cols c) {
        return tint(c.a(), c.b(), c.rim());
    }

    public Sprite bill(Display.Billboard b) {
        bill = b;
        return this;
    }

    public Sprite life(int t) {
        // 실수로 영영 남지 않게 30초에서 자른다
        life = Math.max(1, Math.min(600, t));
        return this;
    }

    public Sprite end(End e, int len) {
        end = e;
        endLen = Math.max(1, len);
        return this;
    }

    public Sprite end(End e) {
        end = e;
        return this;
    }

    public Sprite view(View v) {
        view = v;
        return this;
    }

    /** 투사체 머리: 시전자 눈에서 d 칸 멀어진 뒤에야 시전자에게 보인다 (눈앞에서 번쩍이지 않게) */
    public Sprite reveal(double d) {
        reveal = d;
        return this;
    }

    public Sprite radius(double r) {
        radius = r;
        return this;
    }

    public Sprite range(double r) {
        range = (float) r;
        return this;
    }

    public Sprite tele() {
        tele = true;
        prio = 3;
        return this;
    }

    public Sprite worldLight() {
        worldLight = true;
        return this;
    }

    public Sprite fallback(Runnable r) {
        fallback = r;
        return this;
    }

    // ------------------------------------------------------------------ 띄우기

    public boolean ok() {
        return spawned && !dead && e != null;
    }

    public Sprite go() {
        if (spawned) return this;
        spawned = true;
        World w = at.getWorld();
        if (w == null || fx.off) {
            dead = true;
            return this;
        }
        boolean packOnly = kind == Kind.ITEM && stack == null;
        if (packOnly && (!vfx.spritesOn() || !vfx.models.has(model))) {
            if (fallback != null) fx.with(CastFx.AUD_ALL, fallback);
            dead = true;
            return this;
        }
        boolean capOk = tele ? vfx.liveCount() < Vfx.GLOBAL_SPRITES + Vfx.TELE_RESERVE
                : fx.live < fx.spriteCap() && vfx.liveCount() < Vfx.GLOBAL_SPRITES;
        if (!capOk) {
            if (fallback != null) fx.with(CastFx.AUD_ALL, fallback);
            dead = true;
            return this;
        }
        // 보스 예고 안쪽: 플레이어 바닥 문양은 어둡게, 빛 덩이(별·구슬)는 입자로만 (예고가 묻히지 않게)
        if (packOnly && !tele && !fx.tier.mob() && vfx.inTele(at)) {
            if (decal) {
                String d = vfx.models.dim(model, 2);
                if (d != null) model = d;
            } else if (bill != Display.Billboard.FIXED && !vertical) {
                if (fallback != null) fx.with(CastFx.AUD_ALL, fallback);
                dead = true;
                return this;
            }
        }
        List<Vfx.Viewer> aud = new ArrayList<>();
        boolean anyNoPack = false, anyNear = false;
        double vr = 64 * Math.max(1, range);
        for (Vfx.Viewer v : vfx.viewers()) {
            if (v.w != w || v.dist2(at) > vr * vr) continue;
            if (packOnly && !v.pack) {
                anyNoPack = true;
                continue;
            }
            anyNear = true;
            if (!eligible(v)) continue;
            if (!budget(v)) continue;
            aud.add(v);
        }
        if (anyNoPack && fallback != null) fx.with(CastFx.AUD_NOPACK, fallback);
        Sprite casterCopy = casterDecal(aud);
        if (casterCopy == null) casterCopy = casterColumn(aud);
        boolean casterLater = reveal > 0 && fx.cp != null;
        // 볼 사람이 없으면 띄우지 않는다. 오래 남는 조각은 가까이 올 사람을 위해 띄워 둔다
        if (aud.isEmpty() && !casterLater && (life <= 20 || !anyNear)) {
            dead = true;
            if (casterCopy != null) casterCopy.go();
            return this;
        }
        // 겹치는 바닥 문양끼리 같은 높이면 반투명 정렬이 깨져 조각이 비므로 1.2cm 씩 층을 나눈다 (예고는 0.15 위)
        if (decal && !tele && kind == Kind.ITEM) tr.y += (float) (0.012 * (vfx.decalSeq++ % 6));
        Location sp = at.clone();
        sp.setYaw(0);
        sp.setPitch(0);
        if (pos == null) pos = sp.clone();
        try {
            Consumer<Display> init = d -> {
                d.setPersistent(false);
                d.addScoreboardTag(Mechanics.FX_TAG);
                d.addScoreboardTag(Vfx.TAG);
                d.setVisibleByDefault(false);
                if (!worldLight) d.setBrightness(new Display.Brightness(15, 15));
                else {
                    // 땅에 반쯤 묻혀 솟는 블록은 제자리 빛이 0 이라 새까맣게 보였다: 한 칸 위의 빛을 쓴다
                    var lb = sp.clone().add(0, 1, 0).getBlock();
                    d.setBrightness(new Display.Brightness(lb.getLightFromBlocks(), lb.getLightFromSky()));
                }
                d.setShadowRadius(0);
                d.setShadowStrength(0);
                d.setViewRange(range);
                d.setBillboard(bill);
                d.setTeleportDuration(Math.min(59, vel != null ? moveEvery : followEvery));
                d.setInterpolationDuration(0);
                d.setTransformation(cur());
                if (d instanceof ItemDisplay id) {
                    id.setItemStack(stack != null ? stack : vfx.models.stack(model, ta, tb, tc));
                    id.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.NONE);
                } else if (d instanceof BlockDisplay bd) {
                    bd.setBlock(block);
                } else if (d instanceof TextDisplay td) {
                    td.text(text);
                    td.setBackgroundColor(Color.fromARGB(0, 0, 0, 0));
                    td.setDefaultBackground(false);
                    td.setShadowed(true);
                    td.setSeeThrough(false);
                    td.setAlignment(TextDisplay.TextAlignment.CENTER);
                    td.setLineWidth(400);
                }
                for (Vfx.Viewer v : aud) {
                    v.p.showEntity(vfx.plugin, d);
                    shown.add(v.id);
                    vfx.visCount.merge(v.id, 1, Integer::sum);
                }
            };
            Class<? extends Display> cls = switch (kind) {
                case ITEM -> ItemDisplay.class;
                case BLOCK -> BlockDisplay.class;
                case TEXT -> TextDisplay.class;
            };
            e = w.spawn(sp, cls, init::accept);
        } catch (Throwable t) {
            vfx.warn("spawn", "연출 조각을 띄우지 못함: " + t);
            dead = true;
            return this;
        }
        fx.live++;
        if (vel != null) fx.moving++;
        vfx.register(this);
        scheduleEnd();
        if (casterCopy != null) casterCopy.go();
        return this;
    }

    /**
     * 시전자 눈앞 12칸 안의 굵은 빛기둥(폭 1.4 이상)은 조준 대상을 통째로 가린다.
     * 시전자에게만 폭 40% 의 가는 기둥을 보여 준다 (높이·색·타이밍은 같다).
     */
    private Sprite casterColumn(List<Vfx.Viewer> aud) {
        if (!vertical || kind != Kind.ITEM || stack != null || view != View.AUTO || tele || fx.cp == null || radius < 1.4) return null;
        Vfx.Viewer cv = null;
        for (Vfx.Viewer v : aud) if (v.p == fx.cp) cv = v;
        if (cv == null) return null;
        Location c = center();
        double dx = c.getX() - cv.eye.getX(), dz = c.getZ() - cv.eye.getZ();
        if (dx * dx + dz * dz > 144) return null;
        aud.remove(cv);
        noCaster = true;
        // 흰 기둥은 조준한 적을 하얗게 지워 버리므로 시전자에게는 속성색으로 칠한 가는 기둥
        Color ca = Palette.nearWhite(ta) ? Palette.mix(ta, fx.pal.a(), 0.55) : ta;
        Sprite t = twin(0, 0, 0, ca, Palette.nearWhite(tb) ? Palette.mix(tb, fx.pal.a(), 0.3) : tb, model);
        t.view = View.ONLY;
        t.end = end;
        t.fallback = null;
        t.xzMul = 0.28f;
        return t;
    }

    /**
     * 시전자가 큰 바닥 문양(반지름 3 이상) 안이나 바로 곁에 서 있으면, 1인칭 바닥 전체가 굵은 빛 픽셀로 덮인다.
     * 시전자에게만 한 단계 흐린(가는 선) 복제를 보여 주고 원본은 숨긴다. 남들은 원본 그대로 본다.
     */
    private Sprite casterDecal(List<Vfx.Viewer> aud) {
        if (!decal || kind != Kind.ITEM || stack != null || view != View.AUTO || tele || fx.cp == null || radius < 3) return null;
        Vfx.Viewer cv = null;
        for (Vfx.Viewer v : aud) if (v.p == fx.cp) cv = v;
        if (cv == null) return null;
        Location c = center();
        double dx = cv.eye.getX() - c.getX(), dz = cv.eye.getZ() - c.getZ(), dy = cv.eye.getY() - c.getY();
        // 가장자리 바로 밖(2.5칸)에 서 있어도 1인칭 화면 아래쪽은 같은 판으로 덮인다
        if (dy < 0 || dy > 3.2 || dx * dx + dz * dz > (radius + 2.5) * (radius + 2.5)) return null;
        boolean rainbow = model.contains("_rainbow");
        String base = rainbow ? model.replace("_rainbow", "") : model;
        // 마법진·충격파 원판은 흐린 단계여도 선이 많아 1인칭 화면 아래 절반을 채운다: 시전자에게는 바깥 테두리 고리만
        String b0 = Models.base(base);
        String dm = null;
        if (b0.startsWith("circle") || b0.startsWith("shock") || b0.startsWith("swirl") || b0.startsWith("crack"))
            dm = vfx.models.pick("ring_faint", "ring_dim");
        // 그 밖에는 가장 흐린 단계(가는 심선만)로, 흰 심 대신 속성색을 섞어 칠한다 (1인칭 바닥이 하얗게 번쩍이지 않게)
        if (dm == null) dm = vfx.models.dim(base, 2);
        if (dm == null) dm = vfx.models.dim(base, 1);
        if (dm == null) return null;
        aud.remove(cv);
        noCaster = true;
        // 흰색으로 칠한 판(안쪽 마법진 등)은 다른 띠 색으로: 흰 선은 낮 바닥에서 가장 눈에 띈다
        Color ca = rainbow ? Palette.hue(vfx.tick * 0.02) : Palette.nearWhite(ta) && !Palette.nearWhite(tb) ? tb : ta;
        Sprite t = twin(0, -0.004, 0, ca, Palette.mix(ca, Color.WHITE, 0.35), dm);
        t.view = View.ONLY;
        t.end = end;
        t.fallback = null;
        if (rainbow) t.hue(6, 0);
        // 원본의 끝맺음은 go() 뒤에 예약되므로 복제는 자기 끝맺음을 따로 예약한다 (복제된 steps 에는 아직 없다)
        return t;
    }

    /** 얼굴 규칙: 보는 사람 눈 가까이에 큰 조각을 띄우지 않는다. 눈보다 0.6 아래의 바닥 문양은 괜찮다 */
    boolean eligible(Vfx.Viewer v) {
        boolean self = fx.cp != null && v.p == fx.cp;
        if (self && noCaster) return false;
        if (self) {
            switch (view) {
                case HIDE -> {
                    return false;
                }
                case SHOW -> {
                    return true;
                }
                default -> { }
            }
            if (reveal > 0) return Math.sqrt(v.dist2(center())) > reveal;
        } else if (view == View.ONLY) return false;
        Location c = center();
        double d = Math.sqrt(v.dist2(c));
        if (self && selfNear > 0 && d < selfNear) return false;
        // 시전자 눈앞 3.5칸 안의 작은 빛 덩이(떨어지는 별·구슬)는 조준점 옆에서 커다란 얼룩으로 보인다
        if (self && kind == Kind.ITEM && stack == null && bill == Display.Billboard.CENTER && radius < 1.5 && d < 3.5) return false;
        if (edgeOn > 0 && decal) {
            Vector3f n = new Vector3f(0, 1, 0);
            rot.transform(n);
            double dx = v.eye.getX() - c.getX(), dy = v.eye.getY() - c.getY(), dz = v.eye.getZ() - c.getZ();
            if (d > 1e-3 && Math.abs(dx * n.x + dy * n.y + dz * n.z) / d < edgeOn) return false;
        }
        if (segLen > 0 && segDir != null) {
            Vector rel = v.eye.clone().subtract(c.toVector());
            double along = Math.max(0, Math.min(segLen, rel.dot(segDir)));
            double off = rel.subtract(segDir.clone().multiply(along)).length();
            return off > radius + 0.6;
        }
        if (decal) {
            // 판 조각: 눈이 판 평면 가까이(0.6) 있고 판 안쪽이면 가린다. 바닥 문양은 눈보다 한참 아래라 보인다
            Vector3f n = new Vector3f(0, 1, 0);
            rot.transform(n);
            double dx = v.eye.getX() - c.getX(), dy = v.eye.getY() - c.getY(), dz = v.eye.getZ() - c.getZ();
            double dist = Math.abs(dx * n.x + dy * n.y + dz * n.z);
            double in = Math.sqrt(Math.max(0, d * d - dist * dist));
            if (dist < 0.6 && in < radius * 1.15 + 0.3) return false;
            return d > 0.5;
        }
        if (d < 0.8 * radius + 1.0) return false;
        if ((bill != Display.Billboard.FIXED || vertical)) {
            double dx = c.getX() - v.eye.getX(), dz = c.getZ() - v.eye.getZ();
            if (dx * dx + dz * dz < 1.44 && c.getY() > v.eye.getY() - 2.2) return false;
        }
        return true;
    }

    /** 보는 사람 한 명당 떠 있는 조각 수. 예고 > 내 기술 > 남의 궁극기 > 남의 일반 기술 순으로 남긴다 */
    boolean budget(Vfx.Viewer v) {
        int p = prio >= 0 ? prio : (fx.cp != null && v.p == fx.cp) ? 2 : fx.weight == Tier.Weight.ULT ? 1 : 0;
        int n = vfx.visCount.getOrDefault(v.id, 0);
        return switch (p) {
            case 3 -> true;
            case 2 -> n < 90;
            case 1 -> n < 60;
            default -> n < 40;
        };
    }

    Location center() {
        Location b = pos != null ? pos : at;
        return b.clone().add(tr.x, tr.y, tr.z);
    }

    Transformation cur() {
        Vector3f t = new Vector3f(tr);
        if (centerBlock) {
            Vector3f h = new Vector3f(sc).mul(0.5f);
            rot.transform(h);
            t.sub(h);
        }
        // 이펙트 모델은 아이템 디스플레이의 180도 회전을 모델에 미리 반영했다. 실제 아이템(무기 잔상)만 되돌린다
        Quaternionf right = stack != null ? new Quaternionf(FLIP) : new Quaternionf();
        return new Transformation(t, new Quaternionf(rot), new Vector3f(sc.x * xzMul, sc.y, sc.z * xzMul), right);
    }

    void apply(int dur) {
        if (e == null || !e.isValid()) return;
        e.setInterpolationDelay(0);
        e.setInterpolationDuration(Math.max(0, dur));
        e.setTransformation(cur());
    }

    // ------------------------------------------------------------------ 키프레임 (go 앞뒤 어디서나)

    /** 나이 age 에 f 실행. 첫 키프레임은 1 틱 이후 (생성과 같은 틱이면 보간이 튄다) */
    public Sprite at(int age, Consumer<Sprite> f) {
        steps.computeIfAbsent(Math.max(1, age), k -> new ArrayList<>()).add(f);
        return this;
    }

    public Sprite key(int age, int dur, Consumer<Sprite> edit) {
        return at(age, s -> {
            edit.accept(s);
            s.apply(dur);
        });
    }

    public Sprite scaleTo(int age, int dur, double x, double y, double z) {
        return key(age, dur, s -> s.sc.set((float) x, (float) y, (float) z));
    }

    public Sprite scaleTo(int age, int dur, double k) {
        return scaleTo(age, dur, k, k, k);
    }

    public Sprite grow(int age, int dur, double k) {
        return key(age, dur, s -> s.sc.mul((float) k));
    }

    public Sprite moveBy(int age, int dur, double x, double y, double z) {
        return key(age, dur, s -> s.tr.add((float) x, (float) y, (float) z));
    }

    /** 자기 up 축으로 deg 회전. 보간은 짧은 쪽으로 돌기 때문에 한 키프레임은 80도·2틱 이상으로 나눈다 */
    public Sprite spin(int from, int dur, double deg) {
        return spinAxis(from, dur, deg, new Vector3f(0, 1, 0));
    }

    public Sprite spinAxis(int from, int dur, double deg, Vector3f axis) {
        int k = Math.max(1, (int) Math.ceil(Math.abs(deg) / 80.0));
        k = Math.min(k, Math.max(1, dur / 2));
        double per = deg / k;
        int step = Math.max(1, dur / k);
        if (Math.abs(per) > 89) {
            per = Math.signum(per) * 89;
        }
        double p2 = per;
        for (int i = 0; i < k; i++) {
            key(from + i * step, step, s -> s.rot.rotateAxis((float) Math.toRadians(p2), axis.x, axis.y, axis.z));
        }
        return this;
    }

    /**
     * 회전과 크기를 함께 바꾸는 연속 동작: from 부터 until 까지 step 틱마다 f(조각, 나이) 로 새 자세를 정하고 step 틱 동안 보간한다.
     * (회전 키프레임과 크기 키프레임을 따로 예약하면 서로의 보간을 끊어 버린다)
     */
    public Sprite animate(int from, int until, int step, java.util.function.ObjIntConsumer<Sprite> f) {
        int st = Math.max(1, step);
        for (int t = Math.max(1, from); t < until; t += st) {
            int tt = t;
            key(t, st, sp -> f.accept(sp, tt));
        }
        return this;
    }

    public Sprite paint(int age, Consumer<Sprite> f) {
        paints.computeIfAbsent(Math.max(1, age), k -> new ArrayList<>()).add(f);
        return this;
    }

    void swapNow(String newModel) {
        if (newModel != null && stack == null && e instanceof ItemDisplay id && vfx.models.has(newModel)) {
            model = newModel;
            id.setItemStack(vfx.models.stack(newModel, ta, tb, tc));
        }
    }

    public Sprite swap(int age, String newModel) {
        if (newModel == null) return this;
        return paint(age, s -> {
            if (s.stack == null && s.e instanceof ItemDisplay id && s.vfx.models.has(newModel)) {
                s.model = newModel;
                id.setItemStack(s.vfx.models.stack(newModel, s.ta, s.tb, s.tc));
            }
        });
    }

    public Sprite retint(int age, Color a, Color b, Color c) {
        return paint(age, s -> {
            s.tint(a, b, c);
            if (s.stack == null && s.e instanceof ItemDisplay id) id.setItemStack(s.vfx.models.stack(s.model, s.ta, s.tb, s.tc));
        });
    }

    /** 흰 빛 → 안쪽색 → 바깥색 (충격이 식어 가는 느낌) */
    public Sprite heat(Color a, Color b, Color rim) {
        tint(Color.WHITE, Color.WHITE, b);
        retint(2, b, Color.WHITE, a);
        retint(4, a, b, rim);
        return this;
    }

    /** 프리즘: period 틱마다 색상환을 돈다 (한 시전 8개까지) */
    public Sprite hue(int period, double offset) {
        if (fx.hueSprites >= 8) return this;
        fx.hueSprites++;
        hueEvery = Math.max(2, period);
        hueOff = offset;
        return this;
    }

    public Sprite follow(Supplier<Location> where, int every) {
        follow = where;
        followEvery = Math.max(1, every);
        if (e != null && e.isValid()) e.setTeleportDuration(Math.min(59, followEvery));
        return this;
    }

    /** 파편처럼 던진다: 속도, 중력(틱당), 갱신 간격, 회전(도/갱신) */
    public Sprite fly(Vector v, double g, int every, float spin, Vector3f axis) {
        vel = v.clone();
        grav = g;
        moveEvery = Math.max(1, every);
        spinDeg = Math.max(-80, Math.min(80, spin));
        spinAxis = axis;
        return this;
    }

    // ------------------------------------------------------------------ 끝맺음

    private void scheduleEnd() {
        if (end == End.NONE || life <= 2) return;
        int len = Math.min(endLen, Math.max(1, life - 1));
        int s0 = life - len;
        switch (end) {
            case FADE -> {
                // 흐린 단계 모델은 그때의 모델 기준으로 고른다 (넘김 그림이 끝난 뒤일 수 있다).
                // 흐린 모델이 없으면 더 크게 퍼지며 사라진다 (안으로 빨려 드는 느낌을 피한다)
                key(s0, len, s -> s.sc.mul(s.dimmable() ? 1.12f : 1.25f));
                fadeSwaps(s0, len);
            }
            case SLASH -> {
                key(s0, len, s -> {
                    s.rot.rotateY((float) Math.toRadians(18 * s.slashDir));
                    s.sc.mul(1.06f);
                });
                fadeSwaps(s0, len);
            }
            case THIN -> key(s0, len, s -> {
                if ((s.thinAxes & AX_X) != 0) s.sc.x *= 0.03f;
                if ((s.thinAxes & AX_Y) != 0) s.sc.y *= 0.03f;
                if ((s.thinAxes & AX_Z) != 0) s.sc.z *= 0.03f;
            });
            case SHRINK -> key(s0, len, s -> s.sc.mul(0.02f));
            default -> { }
        }
    }

    boolean dimmable() {
        return kind == Kind.ITEM && stack == null && vfx.models.dim(model, 1) != null;
    }

    private void fadeSwaps(int s0, int len) {
        if (kind != Kind.ITEM || stack != null) return;
        paint(s0, s -> s.swapNow(s.vfx.models.dim(s.model, 1)));
        if (len >= 2) paint(s0 + Math.max(1, len / 2), s -> s.swapNow(s.vfx.models.dim(s.model, 1)));
    }

    /** 참격이 사라지며 계속 도는 방향 (+1 / -1) */
    int slashDir = 1;

    public Sprite slashDir(int d) {
        slashDir = d >= 0 ? 1 : -1;
        return this;
    }

    // ------------------------------------------------------------------ 매 틱 (Vfx 가 부른다)

    boolean step() {
        if (dead || killed) return false;
        if (e == null || !e.isValid()) return false;
        age++;
        while (!paints.isEmpty() && paints.firstKey() <= age) {
            for (Consumer<Sprite> c : paints.pollFirstEntry().getValue()) c.accept(this);
        }
        while (!steps.isEmpty() && steps.firstKey() <= age) {
            Map.Entry<Integer, List<Consumer<Sprite>>> en = steps.pollFirstEntry();
            for (Consumer<Sprite> c : en.getValue()) c.accept(this);
            if (dead) return false;
        }
        if (follow != null && age % followEvery == 0) {
            Location l = follow.get();
            if (l == null || l.getWorld() != e.getWorld()) return false;
            l = l.clone();
            l.setYaw(0);
            l.setPitch(0);
            pos = l;
            e.teleport(l);
        }
        if (vel != null && !settled && age % moveEvery == 0) move();
        if (hueEvery > 0 && stack == null && age % hueEvery == 0 && e instanceof ItemDisplay id) {
            double h = hueOff + vfx.tick * 0.02;
            ta = Palette.hue(h);
            tb = Palette.hue(h + 0.12, 0.35, 1.0);
            id.setItemStack(vfx.models.stack(model, ta, tb, tc));
        }
        if (reveal > 0 && !revealed && fx.cp != null && fx.cp.isOnline()) {
            Vfx.Viewer v = vfx.viewer(fx.cp);
            if (v != null && v.w == e.getWorld() && Math.sqrt(v.dist2(center())) > reveal) {
                revealed = true;
                show(v);
            }
        }
        if (life > 20 && age % 10 == 0) refresh();
        else if ((follow != null || vel != null) && age % 2 == 0) recheckSelf();
        return age < life;
    }

    private void move() {
        Location next = pos.clone().add(vel.clone().multiply(moveEvery));
        if (next.getWorld() == null) return;
        var b = next.getBlock();
        if (b.getType().isSolid() && !b.isPassable()) {
            // 바닥에 닿으면 멈춰 내려앉는다 (섬 안으로 파고들거나 공허로 떨어지지 않게)
            settled = true;
            return;
        }
        pos = next;
        vel.setY(vel.getY() - grav * moveEvery);
        vel.multiply(0.96);
        Location l = pos.clone();
        l.setYaw(0);
        l.setPitch(0);
        e.teleport(l);
        if (spinDeg != 0 && spinAxis != null) {
            rot.rotateAxis((float) Math.toRadians(spinDeg), spinAxis.x, spinAxis.y, spinAxis.z);
            apply(moveEvery);
        }
    }

    private void show(Vfx.Viewer v) {
        if (e == null || shown.contains(v.id) || !vfx.plugin.isEnabled()) return;
        v.p.showEntity(vfx.plugin, e);
        shown.add(v.id);
        vfx.visCount.merge(v.id, 1, Integer::sum);
    }

    private void hide(Player p) {
        if (e == null || !shown.remove(p.getUniqueId())) return;
        vfx.visCount.computeIfPresent(p.getUniqueId(), (k, n) -> n > 1 ? n - 1 : null);
        if (vfx.plugin.isEnabled()) p.hideEntity(vfx.plugin, e);
    }

    /** 오래 떠 있는 조각: 새로 다가온 사람에게 보여 주고, 너무 가까워진 사람에게서는 숨긴다 */
    private void refresh() {
        double vr = 64 * Math.max(1, range);
        for (Vfx.Viewer v : vfx.viewers()) {
            if (v.w != e.getWorld()) continue;
            boolean in = v.dist2(center()) < vr * vr;
            boolean can = in && (kind != Kind.ITEM || stack != null || v.pack) && eligible(v);
            if (shown.contains(v.id)) {
                if (!can && in) hide(v.p);
            } else if (can && (reveal <= 0 || revealed || v.p != fx.cp) && budget(v)) {
                show(v);
            }
        }
    }

    /** 움직이는 조각: 시전자 눈앞으로 다가오면 숨기고, 멀어지면 다시 보인다 (떨어지는 별이 조준점 앞을 지나가는 등) */
    private void recheckSelf() {
        if (fx.cp == null || !fx.cp.isOnline() || view == View.SHOW || view == View.HIDE) return;
        if (reveal > 0 && !revealed) return;
        Vfx.Viewer v = vfx.viewer(fx.cp);
        if (v == null || v.w != e.getWorld()) return;
        if (kind == Kind.ITEM && stack == null && !v.pack) return;
        boolean can = eligible(v);
        if (shown.contains(v.id)) {
            if (!can) hide(v.p);
        } else if (can && budget(v)) {
            show(v);
        }
    }

    /** 지운다. 보이던 사람 목록을 먼저 정리해 서버의 사람별 표시 기록이 쌓이지 않게 한다 */
    void kill() {
        if (killed) return;
        killed = true;
        dead = true;
        if (e != null) {
            if (vfx.plugin.isEnabled()) {
                for (UUID id : shown) {
                    Player p = Bukkit.getPlayer(id);
                    if (p != null) {
                        try {
                            p.hideEntity(vfx.plugin, e);
                        } catch (Throwable ignored) {
                            // 꺼지는 중이면 그냥 지운다
                        }
                    }
                    vfx.visCount.computeIfPresent(id, (k, n) -> n > 1 ? n - 1 : null);
                }
            }
            shown.clear();
            try {
                e.remove();
            } catch (Throwable ignored) {
                // 이미 지워진 엔티티
            }
            vfx.unregister(this);
            fx.live = Math.max(0, fx.live - 1);
            if (vel != null) fx.moving = Math.max(0, fx.moving - 1);
        }
    }

    /** 수명을 앞당겨 len 틱 동안 끝맺고 사라진다 */
    public void finish(int len) {
        if (!ok()) return;
        life = age + Math.max(1, len);
        steps.clear();
        paints.clear();
        endLen = Math.max(1, len);
        scheduleEndFrom(age + 1);
    }

    private void scheduleEndFrom(int from) {
        int keep = life;
        int len = Math.max(1, keep - from);
        endLen = len;
        int s0 = from;
        switch (end) {
            case THIN -> key(s0, len, s -> {
                if ((s.thinAxes & AX_X) != 0) s.sc.x *= 0.03f;
                if ((s.thinAxes & AX_Y) != 0) s.sc.y *= 0.03f;
                if ((s.thinAxes & AX_Z) != 0) s.sc.z *= 0.03f;
            });
            case SHRINK -> key(s0, len, s -> s.sc.mul(0.02f));
            default -> {
                key(s0, len, s -> s.sc.mul(1.1f));
                fadeSwaps(s0, len);
            }
        }
    }

    /** 위치 기준 판정에 쓰는 현재 위치 */
    public Location where() {
        return center().clone();
    }

    public Material blockType() {
        return block == null ? null : block.getMaterial();
    }

    /** 같은 모양으로 살짝 어긋난 복제 (프리즘 무지개 갈라짐) */
    Sprite twin(double dx, double dy, double dz, Color a, Color b, String m) {
        Sprite s = new Sprite(fx, kind, at);
        s.model = m;
        s.ta = a;
        s.tb = b;
        s.tc = tc;
        s.tr.set(tr).add((float) dx, (float) dy, (float) dz);
        s.rot.set(rot);
        s.sc.set(sc);
        s.bill = bill;
        s.range = range;
        s.life = life;
        // 원본의 끝맺음 변형은 steps 에 이미 들어 있다. 모델·색 바꾸기(paints)는 따라 하지 않는다
        s.end = End.NONE;
        s.endLen = endLen;
        s.thinAxes = thinAxes;
        s.view = view;
        s.decal = decal;
        s.vertical = vertical;
        s.radius = radius;
        s.slashDir = slashDir;
        s.follow = follow;
        s.followEvery = followEvery;
        for (var en : steps.entrySet()) s.steps.put(en.getKey(), new ArrayList<>(en.getValue()));
        return s;
    }
}
