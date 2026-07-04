#ifndef IN_GAME_MPLAYER_CHRSLOTS_H
#define IN_GAME_MPLAYER_CHRSLOTS_H
#include "constants.h"
#include "types.h"

extern struct mpsetup g_MpSetup;

/**
 * chrslots is a u32 bitfield for chr indices 0-31.
 * With MAX_PLAYERS=8 (port-net), bits 0-7 are players and 8-31 are sims.
 * On the PC port, chrslots_hi extends simulant tracking to indices 32-63
 * (sim slots beyond the first 24) so matrix battle arenas can field more fighters.
 */
#define MP_PLAYER_SLOT_MASK ((1U << MAX_PLAYERS) - 1U)

static inline bool mpChrSlotIsSet(s32 index)
{
	if (index < 32) {
		return (g_MpSetup.chrslots & (1U << index)) != 0;
	}
#ifndef PLATFORM_N64
	if (index < 64) {
		return (g_MpSetup.chrslots_hi & (1U << (index - 32))) != 0;
	}
#endif
	return false;
}

static inline void mpChrSlotEnable(s32 index)
{
	if (index < 32) {
		g_MpSetup.chrslots |= 1U << index;
	}
#ifndef PLATFORM_N64
	else if (index < 64) {
		g_MpSetup.chrslots_hi |= 1U << (index - 32);
	}
#endif
}

static inline void mpChrSlotDisable(s32 index)
{
	if (index < 32) {
		g_MpSetup.chrslots &= ~(1U << index);
	}
#ifndef PLATFORM_N64
	else if (index < 64) {
		g_MpSetup.chrslots_hi &= ~(1U << (index - 32));
	}
#endif
}

static inline bool mpHasAnySimulantSlots(void)
{
	if ((g_MpSetup.chrslots & ~MP_PLAYER_SLOT_MASK) != 0) {
		return true;
	}
#ifndef PLATFORM_N64
	if (g_MpSetup.chrslots_hi != 0) {
		return true;
	}
#endif
	return false;
}

static inline void mpChrSlotClearAllSimulants(void)
{
	g_MpSetup.chrslots &= MP_PLAYER_SLOT_MASK;
#ifndef PLATFORM_N64
	g_MpSetup.chrslots_hi = 0;
#endif
}

/** Clear only human player bits; leave simulant bits intact. */
static inline void mpChrSlotClearPlayers(void)
{
	g_MpSetup.chrslots &= ~MP_PLAYER_SLOT_MASK;
}

#endif
