package kr.augsky.vfx;

import kr.augsky.util.Fx;
import org.bukkit.Location;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;

/** 기술 부품이 이미 계산한 모양을 그대로 넘기는 사건들. 연출은 이것만 보고 그린다 (판정은 건드리지 않는다) */
public sealed interface Ev {
    record Cone(Location base, Vector dir, double half, double range, Fx.Spec yaml) implements Ev {}

    record Nova(Location center, double radius, int expand, Fx.Spec yaml) implements Ev {}

    record Projectile(Location start, Vector vel, boolean hasDisplay, boolean ground, double hitRadius, int count,
                      Fx.Spec yaml, double explodeRadius) implements Ev {}

    record Explode(Location at, double radius, Fx.Spec yaml) implements Ev {}

    record Beam(Location start, Vector dir, Location end, double width, boolean throughWalls, Fx.Spec yaml,
                Fx.Spec core) implements Ev {}

    record Dash(Location start, Vector dir, double distance, int ticks, Fx.Spec yaml) implements Ev {}

    record Leap(Location start, Vector vel, Fx.Spec yaml) implements Ev {}

    record Blink(Location from, Location to, Fx.Spec yaml) implements Ev {}

    record Rain(Location center, double radius, int count, int interval, double impactRadius, double height,
                double speed) implements Ev {}

    record Drop(Location start, Location ground, Vector vel, double impactRadius, boolean hasDisplay, Fx.Spec yaml,
                Fx.Spec impactYaml, int count) implements Ev {}

    record Strike(Location point, String visual, double impactRadius, Fx.Spec yaml, LivingEntity on) implements Ev {}

    record Chain(Location from, Location to, int n, Fx.Spec yaml) implements Ev {}

    record Zone(Location center, double radius, int duration, boolean follow, Fx.Spec yaml, Fx.Spec ring,
                boolean heals, boolean harms) implements Ev {}

    record Orbit(int count, double radius, double y, int duration, boolean hasDisplay, Fx.Spec yaml) implements Ev {}

    /** ends: 소용돌이가 끝날 때 터질 자리 (끝 부품들의 모양) */
    record Vortex(Location center, double radius, int duration, Fx.Spec yaml, java.util.List<Footprint> ends) implements Ev {}

    record Buff(LivingEntity who, Fx.Spec yaml) implements Ev {}

    record Party(Location center, double radius) implements Ev {}

    record Ally(LivingEntity who, Fx.Spec yaml) implements Ev {}

    record Mark(LivingEntity target, Fx.Spec yaml) implements Ev {}

    record Summon(Location at) implements Ev {}

    record Hit(LivingEntity target, Location origin, boolean tick) implements Ev {}

    /** delay 부품: ticks 뒤에 body 가 나간다. footprint 는 그때 맞을 자리 (없으면 빈 목록) */
    record Windup(int ticks, java.util.function.Supplier<java.util.List<Footprint>> footprints) implements Ev {}
}
