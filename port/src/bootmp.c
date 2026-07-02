#include <ultra64.h>
#include "constants.h"
#include "bss.h"
#include "data.h"
#include "types.h"
#include "system.h"
#include "bootmp.h"

#ifndef PLATFORM_N64

extern u8 g_MpFeaturesUnlocked[80];
extern s32 g_LaptopSentryAmmoScale;

static struct stagetableentry *bootMpFindStageEntry(s32 stagenum)
{
	struct stagetableentry *stage = g_Stages;
	struct stagetableentry *end = (struct stagetableentry *)(uintptr_t)stage + ARRAYCOUNT(g_Stages);

	while (stage < end) {
		if (stage->id == stagenum) {
			return stage;
		}

		stage++;
	}

	return NULL;
}

bool bootMpHasQuickStartCliFlags(void)
{
	return sysArgCheck("--num-sims")
		|| sysArgCheck("--teams-battle")
		|| sysArgCheck("--unlimited-sentries")
		|| sysArgCheck("--laptop-sentry-infinite-ammo")
		|| sysArgCheck("--laptop-sentry-x4")
		|| sysArgCheck("--solo")
		|| sysArgCheck("--sim-difficulty")
		|| sysArgCheck("--time-limit")
		|| sysArgCheck("--score-limit")
		|| sysArgCheck("--team-score-limit")
		|| sysArgCheck("--scenario-0")
		|| sysArgCheck("--scenario-1")
		|| sysArgCheck("--scenario-2")
		|| sysArgCheck("--scenario-3")
		|| sysArgCheck("--scenario-4")
		|| sysArgCheck("--scenario-5");
}

bool bootMpStageSupportsCombatSim(s32 stagenum)
{
	struct stagetableentry *entry;

	if (STAGE_IS_PDMAP_BOX_ARENA(stagenum)) {
		return true;
	}

	entry = bootMpFindStageEntry(stagenum);
	if (entry && entry->mpsetupfileid != 0) {
		return true;
	}

	return false;
}

bool bootMpShouldApplyBootStageQuickStart(s32 stagenum)
{
	const s32 bootstage = sysArgGetInt("--boot-stage", -1);

	if (bootstage < 0 || bootstage != stagenum) {
		return false;
	}

	if (STAGE_IS_MENU(stagenum)) {
		return false;
	}

	if (!bootMpHasQuickStartCliFlags()) {
		return false;
	}

	return bootMpStageSupportsCombatSim(stagenum);
}

void bootMpApplySentryCliFlags(void)
{
	if (sysArgCheck("--laptop-sentry-x4")) {
		g_LaptopSentryAmmoScale = 4;
	}
	if (sysArgCheck("--unlimited-sentries")) {
		g_UnlimitedLaptopSentries = true;
	}
	if (sysArgCheck("--laptop-sentry-infinite-ammo")) {
		g_LaptopSentryInfiniteAmmo = true;
	}
}

void bootMpApplyQuickStartSetup(s32 stagenum)
{
	s32 simdiff;

	/* Player 1 only; simulants added via quick-team. */
	g_MpSetup.chrslots = 0x01;
	g_MpSetup.stagenum = stagenum;
	g_MpSetup.options = 0;
	g_MpSetup.scenario = 0;

	if (sysArgCheck("--scenario-0")) g_MpSetup.scenario = 0;
	if (sysArgCheck("--scenario-1")) g_MpSetup.scenario = 1;
	if (sysArgCheck("--scenario-2")) g_MpSetup.scenario = 2;
	if (sysArgCheck("--scenario-3")) g_MpSetup.scenario = 3;
	if (sysArgCheck("--scenario-4")) g_MpSetup.scenario = 4;
	if (sysArgCheck("--scenario-5")) g_MpSetup.scenario = 5;

	g_MpSetup.weapons[0] = MPWEAPON_FALCON2;
	g_MpSetup.weapons[1] = MPWEAPON_CMP150;
	g_MpSetup.weapons[2] = MPWEAPON_AR34;
	g_MpSetup.weapons[3] = MPWEAPON_MAGSEC4;
	g_MpSetup.weapons[4] = MPWEAPON_NONE;
	g_MpSetup.weapons[5] = MPWEAPON_SHIELD;

	g_Vars.mpquickteam = MPQUICKTEAM_PLAYERSANDSIMS;
	g_Vars.mpquickteamnumsims = sysArgGetInt("--num-sims", 8);
	if (g_Vars.mpquickteamnumsims < 0) {
		g_Vars.mpquickteamnumsims = 0;
	}
	if (g_Vars.mpquickteamnumsims > MAX_BOTS) {
		g_Vars.mpquickteamnumsims = MAX_BOTS;
	}
	if (sysArgCheck("--solo")) {
		g_Vars.mpquickteamnumsims = 0;
	}

	simdiff = sysArgGetInt("--sim-difficulty", BOTDIFF_NORMAL);
	if (simdiff < BOTDIFF_MEAT) {
		simdiff = BOTDIFF_MEAT;
	}
	if (simdiff > BOTDIFF_DARK) {
		simdiff = BOTDIFF_DARK;
	}
	g_Vars.mpsimdifficulty = simdiff;

	/* Unlock full simulant count (stock profile caps at 4). */
	g_MpFeaturesUnlocked[MPFEATURE_8BOTS] |= 1;
	g_MpFeaturesUnlocked[MPFEATURE_BOTDIFF_HARD] |= 1;
	g_MpFeaturesUnlocked[MPFEATURE_BOTDIFF_PERFECT] |= 1;
	g_MpFeaturesUnlocked[MPFEATURE_BOTDIFF_DARK] |= 1;

	if (sysArgCheck("--teams-battle")) {
		g_MpSetup.options |= MPOPTION_TEAMSENABLED;
	}

	if (sysArgCheck("--time-limit")) {
		s32 timelimit = sysArgGetInt("--time-limit", g_MpSetup.timelimit);

		if (timelimit < 0) {
			timelimit = 0;
		}
		if (timelimit > 60) {
			timelimit = 60;
		}
		g_MpSetup.timelimit = timelimit;
	}
	if (sysArgCheck("--score-limit")) {
		s32 scorelimit = sysArgGetInt("--score-limit", g_MpSetup.scorelimit);

		if (scorelimit < 0) {
			scorelimit = 0;
		}
		if (scorelimit > 100) {
			scorelimit = 100;
		}
		g_MpSetup.scorelimit = scorelimit;
	}
	if (sysArgCheck("--team-score-limit")) {
		s32 teamscorelimit = sysArgGetInt("--team-score-limit", g_MpSetup.teamscorelimit);

		if (teamscorelimit < 0) {
			teamscorelimit = 0;
		}
		if (teamscorelimit > 400) {
			teamscorelimit = 400;
		}
		g_MpSetup.teamscorelimit = teamscorelimit;
	}

	bootMpApplySentryCliFlags();

	/* matrix_battle_64 defaults: long matches (stock func0f187fec is 10 min / 20 team kills). */
	if (stagenum == STAGE_TEST_UFF
			&& sysArgCheck("--teams-battle")
			&& !sysArgCheck("--time-limit")
			&& !sysArgCheck("--score-limit")
			&& !sysArgCheck("--team-score-limit")) {
		g_MpSetup.timelimit = 59;
		g_MpSetup.scorelimit = 100;
		g_MpSetup.teamscorelimit = 400;
	}
}

#endif
