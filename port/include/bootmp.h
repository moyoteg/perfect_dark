#ifndef IN_PORT_BOOTMP_H
#define IN_PORT_BOOTMP_H

#include <ultra64.h>

#ifndef PLATFORM_N64

/* CLI-driven MP quick-start for --test-map and --boot-stage (PC port). */
bool bootMpHasQuickStartCliFlags(void);
bool bootMpStageSupportsCombatSim(s32 stagenum);
bool bootMpShouldApplyBootStageQuickStart(s32 stagenum);
void bootMpApplySentryCliFlags(void);
void bootMpApplyQuickStartSetup(s32 stagenum);

#endif

#endif
