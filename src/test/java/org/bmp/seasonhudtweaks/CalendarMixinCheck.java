package org.bmp.seasonhudtweaks;

import java.net.URL;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.zip.ZipFile;
import net.minecraft.launchwrapper.Launch;
import net.minecraft.launchwrapper.LaunchClassLoader;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.FieldInsnNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.spongepowered.asm.launch.MixinTweaker;
import org.spongepowered.asm.mixin.MixinEnvironment;
import org.spongepowered.asm.mixin.Mixins;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigSource;
import org.spongepowered.asm.mixin.transformer.IMixinTransformer;

public final class CalendarMixinCheck {
    private static final String SEASONHUD = "club.iananderson.seasonhud";

    public static void main(String[] args) throws Exception {
        String mixin = args[2];
        if (mixin.equals("overlay")) {
            verifyOverlay(args[0], args[1]);
            return;
        }
        boolean legacy = mixin.equals("LegacyCalendarMixin");
        String target = SEASONHUD + (mixin.equals("CalendarMixin")
                ? ".impl.accessory.mods.Calendar" : ".impl.seasons.Calendar");
        String methodName = legacy ? "calendarFound" : "validNeedCalendar";
        String classFile = target.replace('.', '/') + ".class";

        Launch.blackboard = new HashMap<>();
        Launch.blackboard.put("Tweaks", new ArrayList<>());
        Launch.blackboard.put("TweakClasses", new ArrayList<>());
        Launch.classLoader = new LaunchClassLoader(new URL[] {
                Paths.get(args[0]).toUri().toURL(), Paths.get(args[1]).toUri().toURL()
        });
        Thread.currentThread().setContextClassLoader(Launch.classLoader);
        new MixinTweaker();
        MixinEnvironment environment = MixinEnvironment.getDefaultEnvironment();
        environment.setSide(MixinEnvironment.Side.CLIENT);
        Mixins.addConfiguration("seasonhudtweaks.mixins.json", (IMixinConfigSource) null);

        IMixinTransformer transformer = (IMixinTransformer) environment.getActiveTransformer();

        try (ZipFile upstream = new ZipFile(args[1])) {
            ClassNode original = new ClassNode();
            new ClassReader(upstream.getInputStream(upstream.getEntry(classFile))).accept(original, 0);
            ClassNode transformed = new ClassNode();
            original.accept(transformed);
            transformer.transformClass(environment, target, transformed);
            int expected = legacy ? 1 : 2;
            String getter = legacy && calls(original, methodName, "getNeedCalendar") == 0
                    ? "booleanValue" : "getNeedCalendar";
            require(calls(original, methodName, getter) == expected, "Unexpected upstream gate");
            require(calls(transformed, methodName, getter) == 0, "Unpatched calendar gate");
            require(calls(transformed, methodName, "seasonhudtweaks$requireCalendar")
                    + calls(transformed, methodName, "seasonhudtweaks$requireLegacyCalendar") == expected,
                    "Expected " + expected + " redirects in " + target);
            require(calls(original, "validDetailedMode", "getCalendarDetailMode")
                    == calls(transformed, "validDetailedMode", "getCalendarDetailMode"), "Changed detailed mode");
        }
        System.out.println("Verified " + mixin + " against " + args[1]);
    }

    private static void verifyOverlay(String addonPath, String upstreamPath) throws Exception {
        try (ZipFile addon = new ZipFile(addonPath); ZipFile upstream = new ZipFile(upstreamPath)) {
            String gate = "org/bmp/seasonhudtweaks/forge/SeasonOverlayGate.class";
            ClassNode gateClass = new ClassNode();
            new ClassReader(addon.getInputStream(addon.getEntry(gate))).accept(gateClass, 0);
            long overlays = gateClass.methods.stream()
                    .filter(method -> method.name.equals("beforeOverlay"))
                    .flatMap(method -> java.util.Arrays.stream(method.instructions.toArray()))
                    .filter(instruction -> instruction instanceof FieldInsnNode)
                    .map(instruction -> (FieldInsnNode) instruction)
                    .filter(field -> field.owner.startsWith("club/iananderson/seasonhud/client/"))
                    .peek(field -> {
                        try {
                            ClassNode upstreamClass = new ClassNode();
                            new ClassReader(upstream.getInputStream(upstream.getEntry(field.owner + ".class")))
                                    .accept(upstreamClass, ClassReader.SKIP_CODE);
                            require(upstreamClass.fields.stream().anyMatch(candidate ->
                                    candidate.name.equals(field.name) && candidate.desc.equals(field.desc)),
                                    "Missing SeasonHud overlay " + field.owner + "." + field.name);
                        } catch (java.io.IOException error) {
                            throw new java.io.UncheckedIOException(error);
                        }
                    }).count();
            require(overlays == 3, "Expected three SeasonHud overlays");
            require(calls(gateClass, "beforeOverlay", "setCanceled") == 1, "Overlay event is not canceled");
        }
        System.out.println("Verified Forge overlay integration against " + upstreamPath);
    }

    private static long calls(ClassNode owner, String methodName, String callName) {
        return owner.methods.stream()
                .filter(method -> method.name.equals(methodName))
                .flatMap(method -> java.util.Arrays.stream(method.instructions.toArray()))
                .filter(instruction -> instruction instanceof MethodInsnNode
                        && ((MethodInsnNode) instruction).name.endsWith(callName))
                .count();
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
