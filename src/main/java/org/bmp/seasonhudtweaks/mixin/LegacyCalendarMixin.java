package org.bmp.seasonhudtweaks.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Group;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(targets = "club.iananderson.seasonhud.impl.seasons.Calendar", remap = false)
abstract class LegacyCalendarMixin {
    @Group(name = "calendarConfig", min = 1, max = 1)
    @Redirect(
            method = "calendarFound()Z",
            at = @At(value = "INVOKE", target = "Lclub/iananderson/seasonhud/config/Config;getNeedCalendar()Z"),
            require = 0,
            allow = 1
    )
    private static boolean seasonhudtweaks$requireCalendar() {
        return true;
    }

    @Group(name = "calendarConfig")
    @Redirect(
            method = "calendarFound()Z",
            at = @At(value = "INVOKE", target = "Ljava/lang/Boolean;booleanValue()Z"),
            require = 0,
            allow = 1
    )
    private static boolean seasonhudtweaks$requireLegacyCalendar(Boolean configured) {
        return true;
    }
}
