#ifndef IN_PORT_WARCOLORS_PROBE_H
#define IN_PORT_WARCOLORS_PROBE_H

#include <ultra64.h>

#ifndef PLATFORM_N64

/* After setupPreparePads on STAGE_EXTRA26, log Conker floor Y for spawn/weapon pads. */
void warColorsSetPadFileSize(s32 size);
void warColorsProbePadsIfRequested(void);

#endif

#endif
