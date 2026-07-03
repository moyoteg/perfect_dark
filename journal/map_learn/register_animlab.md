# Stage registration plan: animlab

Already registered: **False**

## 1. `src/include/files.h`

```c
#define FILE_BG_ANIMLAB_SEG       0x07ec
#define FILE_BG_ANIMLAB_TILES     0x07ed
#define FILE_BG_ANIMLAB_PADS      0x07ee
#define FILE_USETUPANIMLAB         0x07ef
#define FILE_UMP_SETUPANIMLAB      0x07f0
```

## 2. `src/assets/ntsc-final/files/list.c`

```c
/*0x07ec*/ "bgdata/bg_animlab.seg",
/*0x07ed*/ "bgdata/bg_animlab_tilesZ",
/*0x07ee*/ "bgdata/bg_animlab_padsZ",
/*0x07ef*/ "UsetupanimlabZ",
/*0x07f0*/ "Ump_setupanimlabZ",
```

## 3. `src/game/stagetable.c`

```c
/*0x07ec*/ STAGE_ANIMLAB, 2, 255, 100, 100, 0, FILE_BG_ANIMLAB_SEG, FILE_BG_ANIMLAB_TILES, FILE_BG_ANIMLAB_PADS, FILE_USETUPANIMLAB, FILE_UMP_SETUPANIMLAB, 1, 1, 100, 0, 0, -1, 255, 0x3e19999a, -1, 400, 0, 1, SFX_ALARM_DEFAULT, 0,
```

## 4. `src/game/mplayer/setup.c` (`g_MpArenas[]`)

```c
{ STAGE_ANIMLAB, 0, 0x7FFF }, // animlab custom arena
```

> After editing, run `make -j8` and `pdmap build {name} --deploy`.
> For quick test without menu registration, use `--deploy-as uff` instead.
