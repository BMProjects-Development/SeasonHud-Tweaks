package org.bmp.seasonhudtweaks.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Pseudo
@Mixin(targets = "club.iananderson.seasonhud.impl.accessory.mods.Calendar", remap = false)
abstract class CalendarMixin {
    @Redirect(
            method = "validNeedCalendar",
            at = @At(value = "INVOKE", target = "Lclub/iananderson/seasonhud/config/SeasonHudServer;getNeedCalendar()Z"),
            require = 2,
            allow = 2
    )
    private static boolean seasonhudtweaks$requireCalendar() {
        // Use SeasonHud's inventory and accessory checks even when the server option is off.
        return true;
    }
}
