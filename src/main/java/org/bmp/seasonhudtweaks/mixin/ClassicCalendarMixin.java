package org.bmp.seasonhudtweaks.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

// Keeps existing Forge 1.16.5 packs on SeasonHud 1.13.17 working.
@Pseudo
@Mixin(targets = "club.iananderson.seasonhud.impl.seasons.Calendar", remap = false)
abstract class ClassicCalendarMixin {
    @Redirect(
            method = "validNeedCalendar()Z",
            at = @At(value = "INVOKE", target = "Lclub/iananderson/seasonhud/config/SeasonHudServer;getNeedCalendar()Z"),
            require = 2,
            allow = 2
    )
    private static boolean seasonhudtweaks$requireCalendar() {
        return true;
    }
}
