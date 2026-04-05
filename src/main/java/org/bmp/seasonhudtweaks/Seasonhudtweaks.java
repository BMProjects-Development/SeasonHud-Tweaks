package org.bmp.seasonhudtweaks;

import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

@Mod("seasonhudtweaks")
public class Seasonhudtweaks {

    private static final Logger LOGGER = LogManager.getLogger();

    public Seasonhudtweaks() {

        MinecraftForge.EVENT_BUS.register(this);
    }

}