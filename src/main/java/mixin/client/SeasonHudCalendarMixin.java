package mixin.client;

import club.iananderson.seasonhud.impl.accessory.mods.Calendar;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import sereneseasons.api.SSItems;

@Mixin(value = Calendar.class, remap = false)
public class SeasonHudCalendarMixin {
    @Inject(method = "validNeedCalendar", at = @At("RETURN"), cancellable = true, remap = false)
    private static void endlessrise$requireSereneSeasonsCalendarInInventory(PlayerEntity player, CallbackInfoReturnable<Boolean> cir) {
        cir.setReturnValue(cir.getReturnValueZ() && hasSereneSeasonsCalendar(player));
    }

    private static boolean hasSereneSeasonsCalendar(PlayerEntity player) {
        Item calendarItem = SSItems.calendar;
        if (player == null || calendarItem == null) {
            return false;
        }

        if (Calendar.findCuriosCalendar(player, calendarItem)) {
            return true;
        }

        for (ItemStack stack : player.inventory.items) {
            if (stack.getItem() == calendarItem) {
                return true;
            }
        }

        for (ItemStack stack : player.inventory.offhand) {
            if (stack.getItem() == calendarItem) {
                return true;
            }
        }

        return false;
    }
}