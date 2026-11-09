package org.bmp.seasonhudtweaks.forge;

import club.iananderson.seasonhud.client.JourneyMap;
import club.iananderson.seasonhud.client.SeasonHUDOverlay;
import club.iananderson.seasonhud.client.XaeroMinimap;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Field;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderGameOverlayEvent;
import net.minecraftforge.client.gui.IIngameOverlay;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid = "seasonhudtweaks", value = Dist.CLIENT)
public final class SeasonOverlayGate {
    private SeasonOverlayGate() {
    }

    @SubscribeEvent
    public static void beforeOverlay(RenderGameOverlayEvent.PreLayer event) {
        IIngameOverlay overlay = event.getOverlay();
        if ((overlay == SeasonHUDOverlay.HUD_SEASON
                || overlay == XaeroMinimap.XAERO_SEASON
                || overlay == JourneyMap.JOURNEYMAP_SEASON)
                && !CalendarAccess.hasCalendar()) {
            event.setCanceled(true);
        }
    }

    // Link the Forge 1.17.1 runtime names once, when the first season overlay renders.
    private static final class CalendarAccess {
        private static final MethodType OBJECT_GETTER = MethodType.methodType(Object.class, Object.class);
        private static final MethodHandle PLAYER;
        private static final MethodHandle INVENTORY;
        private static final MethodHandle CONTAINS_CALENDAR;

        static {
            try {
                MethodHandles.Lookup lookup = MethodHandles.publicLookup();
                Class<?> minecraft = Class.forName("net.minecraft.client.Minecraft");
                Field player = minecraft.getField("f_91074_");
                PLAYER = MethodHandles.filterArguments(
                        lookup.unreflectGetter(player).asType(OBJECT_GETTER),
                        0, lookup.unreflect(minecraft.getMethod("m_91087_")).asType(MethodType.methodType(Object.class)));
                var inventory = player.getType().getMethod("m_150109_");
                INVENTORY = lookup.unreflect(inventory).asType(OBJECT_GETTER);

                Object calendar = Class.forName("sereneseasons.api.SSItems").getField("calendar").get(null);
                Object calendarStack = calendar.getClass().getMethod("m_7968_").invoke(calendar);
                Class<?> itemStack = Class.forName("net.minecraft.world.item.ItemStack");
                CONTAINS_CALENDAR = MethodHandles.insertArguments(
                        lookup.unreflect(inventory.getReturnType().getMethod("m_36063_", itemStack)),
                        1, calendarStack).asType(MethodType.methodType(boolean.class, Object.class));
            } catch (ReflectiveOperationException error) {
                throw new IllegalStateException("Cannot link the Forge 1.17.1 calendar check", error);
            }
        }

        private static boolean hasCalendar() {
            try {
                Object player = (Object) PLAYER.invokeExact();
                return player != null && (boolean) CONTAINS_CALENDAR.invokeExact((Object) INVENTORY.invokeExact(player));
            } catch (Throwable error) {
                throw new IllegalStateException("Cannot read the player's calendar", error);
            }
        }
    }
}
