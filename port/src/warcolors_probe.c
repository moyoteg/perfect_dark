#include <ultra64.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "constants.h"
#include "bss.h"
#include "game/bg.h"
#include "game/pad.h"
#include "game/setup.h"
#include "lib/collision.h"
#include "types.h"
#include "system.h"
#include "warcolors_probe.h"

#ifndef PLATFORM_N64

#include "files.h"
#include "romdata.h"
#include "lib/rzip.h"
#include "platform.h"

/* Retail Ump_setupmp13Z intro spawn pads 001C–0027 and floor weapon pads 00BD–00C6. */
static const s16 g_WarColorsProbePadIndices[] = {
	28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
	189, 190, 191, 192, 193, 194, 195, 196, 197, 198,
};

struct warcolors_pad_patch {
	s16 padnum;
	s16 newy;
};

static struct warcolors_pad_patch g_WarColorsPadPatches[219];
static s32 g_WarColorsNumPatches;
static s32 g_WarColorsPadFileSize;

/* RareZip 0x1173 envelope used by bg_mp13_padsZ (see tools/pdmap/seg.py zip1172). */
static u8 *warColorsZip1173(const u8 *raw, s32 rawlen, s32 *outlen)
{
#ifdef PLATFORM_WIN32
	char tmpname[L_tmpnam + 1];
#else
	char tmpname[] = "/tmp/pd-warcolors-pads-XXXXXX";
	int tmpfd;
#endif
	char cmd[512];
	FILE *in;
	FILE *out;
	u8 hdr[5];
	u8 *payload;
	u8 *result;
	s32 paylen;

#ifndef PLATFORM_WIN32
	tmpfd = mkstemp(tmpname);
	if (tmpfd < 0) {
		return NULL;
	}
	close(tmpfd);
#else
	tmpnam(tmpname);
#endif

	in = fopen(tmpname, "wb");
	if (!in) {
		return NULL;
	}
	fwrite(raw, 1, rawlen, in);
	fclose(in);

#ifdef PLATFORM_WIN32
	snprintf(cmd, sizeof(cmd), "gzip -f -c --no-name --best \"%s\"", tmpname);
#else
	snprintf(cmd, sizeof(cmd), "gzip -f -c --no-name --best %s", tmpname);
#endif
	out = popen(cmd, "r");
	if (!out) {
		remove(tmpname);
		return NULL;
	}

	fread(hdr, 1, 10, out);
	payload = malloc(rawlen + 64);
	if (!payload) {
		pclose(out);
		remove(tmpname);
		return NULL;
	}
	paylen = fread(payload, 1, rawlen + 64, out);
	pclose(out);
	remove(tmpname);

	if (paylen <= 0) {
		free(payload);
		return NULL;
	}

	result = malloc(5 + paylen);
	if (!result) {
		free(payload);
		return NULL;
	}

	result[0] = 0x11;
	result[1] = 0x73;
	result[2] = (rawlen >> 16) & 0xff;
	result[3] = (rawlen >> 8) & 0xff;
	result[4] = rawlen & 0xff;
	memcpy(result + 5, payload, paylen);
	free(payload);

	*outlen = 5 + paylen;
	return result;
}

static bool warColorsResolveProbeRooms(struct coord *pos, RoomNum *rooms)
{
	RoomNum inrooms[24];
	RoomNum aboverooms[22];
	RoomNum *roomsptr = NULL;
	s32 floorroom;

	rooms[0] = -1;
	rooms[1] = -1;

	bgFindRoomsByPos(pos, inrooms, aboverooms, 20, NULL);

	if (inrooms[0] != -1) {
		roomsptr = inrooms;
	} else if (aboverooms[0] != -1) {
		roomsptr = aboverooms;
	}

	if (roomsptr != NULL) {
		floorroom = cdFindFloorRoomAtPos(pos, roomsptr);

		if (floorroom > 0) {
			rooms[0] = floorroom;
		} else {
			rooms[0] = roomsptr[0];
		}
		rooms[1] = -1;
		return true;
	}

	return false;
}

static f32 warColorsProbeGroundAtPad(struct pad *pad, RoomNum *rooms)
{
	struct coord probepos;
	f32 groundy;

	probepos.x = pad->pos.x;
	probepos.z = pad->pos.z;
	probepos.y = pad->pos.y + 2000.0f;
	if (probepos.y < 500.0f) {
		probepos.y = 500.0f;
	}

	if (!warColorsResolveProbeRooms(&pad->pos, rooms)) {
		rooms[0] = pad->room;
		rooms[1] = -1;
	}

	groundy = cdFindGroundInfoAtCyl(&probepos, 30, rooms,
			NULL, NULL, NULL, NULL, NULL, NULL);

	return groundy;
}

/* Patch packed INTPOS Y in N64 pad blob (pre-preprocess) for external deploy. */
static bool warColorsPatchN64PadY(u8 *n64data, s32 n64len, s16 padnum, f32 newy)
{
	s32 num_pads;
	u16 *offsets;
	s32 srcpos;
	u32 n64_padheader;
	u32 flags;
	s16 *pos;

	if (!n64data || n64len < 0x18 || padnum < 0) {
		return false;
	}

	num_pads = PD_BE32(*(s32 *)n64data);
	if (padnum >= num_pads) {
		return false;
	}

	offsets = (u16 *)(n64data + sizeof(s32) * 5);
	srcpos = PD_BE16(offsets[padnum]);
	if (srcpos < 0x18 || srcpos + 8 >= n64len) {
		return false;
	}

	n64_padheader = PD_BE32(*(u32 *)(n64data + srcpos));
	flags = (n64_padheader >> 14) & 0x3ffff;
	if ((flags & PADFLAG_INTPOS) == 0) {
		return false;
	}

	pos = (s16 *)(n64data + srcpos + 4);
	pos[1] = PD_BE16((s16) newy);
	return true;
}

static bool warColorsPatchPackedPadY(s16 padnum, f32 newy)
{
	u8 *ptr;
	u32 *header;
	s16 *pos;

	if (!g_StageSetup.padfiledata || padnum < 0) {
		return false;
	}

	ptr = (u8 *)&g_StageSetup.padfiledata[g_PadOffsets[padnum]];
	header = (u32 *)ptr;

	if (((*header >> 14) & PADFLAG_INTPOS) == 0) {
		return false;
	}

	pos = (s16 *)(ptr + 4);
	pos[1] = (s16) newy;
	return true;
}

static void warColorsProbeOnePad(s16 padnum, bool patch)
{
	struct pad pad;
	RoomNum rooms[8];
	f32 groundy;
	f32 newy;
	bool patched = false;

	padUnpack(padnum, PADFIELD_POS | PADFIELD_ROOM, &pad);

	groundy = warColorsProbeGroundAtPad(&pad, rooms);

	if (patch && groundy > -100000.0f) {
		newy = groundy + 10.0f;
		patched = warColorsPatchPackedPadY(padnum, newy);
		if (patched && g_WarColorsNumPatches < (s32) ARRAYCOUNT(g_WarColorsPadPatches)) {
			g_WarColorsPadPatches[g_WarColorsNumPatches].padnum = padnum;
			g_WarColorsPadPatches[g_WarColorsNumPatches].newy = (s16) newy;
			g_WarColorsNumPatches++;
		}
		if (patched) {
			pad.pos.y = newy;
		}
	}

	sysLogPrintf(LOG_WARNING,
			"PROBE_PAD index=%d x=%.0f y=%.0f z=%.0f ground=%.0f room=%d usable=%d patched=%d",
			padnum,
			pad.pos.x, pad.pos.y, pad.pos.z,
			groundy,
			rooms[0],
			groundy > -100000.0f ? 1 : 0,
			patched ? 1 : 0);
}

static bool warColorsWritePatchedPadsFile(void)
{
	const char *outpath = sysArgGetString("--write-corrected-pads");
	u8 *zipped_rom;
	u8 *n64buf;
	u8 scratch[0x50];
	u8 *outzip;
	s32 zipsize;
	s32 n64len;
	s32 ziplen;
	s32 i;
	FILE *out;
	bool ok;

	if (!outpath || g_WarColorsNumPatches <= 0) {
		sysLogPrintf(LOG_WARNING, "PROBE_PAD write: nothing to patch");
		return false;
	}

	/* Always patch the ROM N64 envelope, not the host-preprocessed runtime blob. */
	zipped_rom = romdataFileGetData(FILE_BG_MP13_PADS);
	zipsize = romdataFileGetSize(FILE_BG_MP13_PADS);
	if (!zipped_rom || zipsize <= 0) {
		sysLogPrintf(LOG_WARNING, "PROBE_PAD write: could not read ROM mp13 pads");
		return false;
	}

	n64buf = sysMemZeroAlloc(65536);
	if (!n64buf) {
		return false;
	}

	n64len = rzipInflate(zipped_rom, n64buf, scratch);
	if (n64len <= 0) {
		sysMemFree(n64buf);
		sysLogPrintf(LOG_WARNING, "PROBE_PAD write: inflate failed");
		return false;
	}

	for (i = 0; i < g_WarColorsNumPatches; i++) {
		if (!warColorsPatchN64PadY(n64buf, n64len,
					g_WarColorsPadPatches[i].padnum,
					g_WarColorsPadPatches[i].newy)) {
			sysLogPrintf(LOG_WARNING, "PROBE_PAD write: N64 patch failed pad=%d",
					g_WarColorsPadPatches[i].padnum);
		}
	}

	outzip = warColorsZip1173(n64buf, n64len, &ziplen);
	sysMemFree(n64buf);
	if (!outzip) {
		sysLogPrintf(LOG_WARNING, "PROBE_PAD write: zip failed");
		return false;
	}

	out = fopen(outpath, "wb");
	if (!out) {
		free(outzip);
		sysLogPrintf(LOG_WARNING, "PROBE_PAD write: fopen failed for %s", outpath);
		return false;
	}

	ok = (fwrite(outzip, 1, ziplen, out) == (size_t)ziplen);
	fclose(out);
	free(outzip);

	sysLogPrintf(LOG_WARNING, "PROBE_PAD write: %s (%s, %d bytes, %d N64 patches)",
			ok ? "ok" : "fail", outpath, ziplen, g_WarColorsNumPatches);
	return ok;
}

void warColorsSetPadFileSize(s32 size)
{
	g_WarColorsPadFileSize = size;
}

static s32 warColorsNumPadsInFile(void)
{
	if (g_PadsFile) {
		return g_PadsFile->numpads;
	}

	if (!g_StageSetup.padfiledata) {
		return 0;
	}

	return PD_BE32(*(s32 *)g_StageSetup.padfiledata);
}

void warColorsProbePadsIfRequested(void)
{
	s32 i;
	s32 count;
	s32 numpads;
	bool patch;
	bool probeall;
	const char *writepath;
	const s16 *indices;
	s32 numindices;

	if (!sysArgCheck("--probe-war-colors-pads")
			&& !sysArgCheck("--probe-war-colors-all")) {
		return;
	}

	if (g_Vars.stagenum != STAGE_EXTRA26) {
		sysLogPrintf(LOG_WARNING, "PROBE_PAD stage=%02x (expected 5b)", g_Vars.stagenum);
		exit(2);
	}

	writepath = sysArgGetString("--write-corrected-pads");
	patch = (writepath != NULL);
	probeall = sysArgCheck("--probe-war-colors-all");
	numpads = warColorsNumPadsInFile();

	if (probeall) {
		indices = NULL;
		numindices = numpads;
	} else {
		indices = g_WarColorsProbePadIndices;
		numindices = (s32) ARRAYCOUNT(g_WarColorsProbePadIndices);
	}

	sysLogPrintf(LOG_WARNING, "PROBE_PAD begin count=%d patch=%d all=%d numpads=%d filesize=%d",
			numindices, patch ? 1 : 0, probeall ? 1 : 0, numpads,
			g_WarColorsPadFileSize);

	for (i = 0; i < numindices; i++) {
		count = probeall ? i : indices[i];
		if (count < 0 || count >= numpads) {
			continue;
		}
		warColorsProbeOnePad(count, patch);
	}

	if (patch) {
		warColorsWritePatchedPadsFile();
	}

	sysLogPrintf(LOG_WARNING, "PROBE_PAD end");
	exit(0);
}

#endif
