package kr.augsky.vfx;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.function.BiConsumer;
import java.util.function.BiFunction;
import java.util.function.Consumer;

/** 전용 연출을 짧게 적는 도구: Sig.of().cast(...).on(Ev.Nova.class, ...).replace(Ev.Nova.class) */
final class Sig implements Signature {
    private Consumer<CastFx> cast = fx -> { };
    private final Map<Class<?>, BiFunction<CastFx, Ev, Track>> on = new HashMap<>();
    private final Set<Class<?>> repl = new HashSet<>();
    private boolean harmless;

    static Sig of() {
        return new Sig();
    }

    Sig cast(Consumer<CastFx> c) {
        cast = c;
        return this;
    }

    @SuppressWarnings("unchecked")
    <E extends Ev> Sig on(Class<E> k, BiConsumer<CastFx, E> f) {
        on.put(k, (fx, e) -> {
            f.accept(fx, (E) e);
            return Track.NOOP;
        });
        return this;
    }

    @SuppressWarnings("unchecked")
    <E extends Ev> Sig track(Class<E> k, BiFunction<CastFx, E, Track> f) {
        on.put(k, (fx, e) -> f.apply(fx, (E) e));
        return this;
    }

    @SafeVarargs
    final Sig replace(Class<? extends Ev>... ks) {
        for (Class<? extends Ev> k : ks) repl.add(k);
        return this;
    }

    Sig noDamage() {
        harmless = true;
        return this;
    }

    @Override
    public void cast(CastFx fx) {
        cast.accept(fx);
    }

    @Override
    public boolean replaces(Class<? extends Ev> kind) {
        return repl.contains(kind);
    }

    @Override
    public Track on(CastFx fx, Ev ev) {
        BiFunction<CastFx, Ev, Track> f = on.get(ev.getClass());
        return f == null ? Track.NOOP : f.apply(fx, ev);
    }

    @Override
    public boolean harmless() {
        return harmless;
    }
}
