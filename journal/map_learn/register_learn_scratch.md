# Stage registration plan: learn_scratch

Already registered: **False**

## 1. `src/include/files.h`

```c
#define FILE_BG_LEARN_SCRATCH_SEG       0x07ec
#define FILE_BG_LEARN_SCRATCH_TILES     0x07ed
#define FILE_BG_LEARN_SCRATCH_PADS      0x07ee
#define FILE_USETUPLEARN_SCRATCH         0x07ef
#define FILE_UMP_SETUPLEARN_SCRATCH      0x07f0
```

## 2. `src/assets/ntsc-final/files/list.c`

```c
/*0x07ec*/ "bgdata/bg_learn_scratch.seg",
/*0x07ed*/ "bgdata/bg_learn_scratch_tilesZ",
/*0x07ee*/ "bgdata/bg_learn_scratch_padsZ",
/*0x07ef*/ "Usetuplearn_scratchZ",
/*0x07f0*/ "Ump_setuplearn_scratchZ",
```

## 3. `src/game/stagetable.c`

```c
/*0x07ec*/ STAGE_LEARN_SCRATCH, 2, 255, 100, 100, 0, FILE_BG_LEARN_SCRATCH_SEG, FILE_BG_LEARN_SCRATCH_TILES, FILE_BG_LEARN_SCRATCH_PADS, FILE_USETUPLEARN_SCRATCH, FILE_UMP_SETUPLEARN_SCRATCH, 1, 1, 100, 0, 0, -1, 255, 0x3e19999a, -1, 400, 0, 1, SFX_ALARM_DEFAULT, 0,
```

## 4. `src/game/mplayer/setup.c` (`g_MpArenas[]`)

```c
{ STAGE_LEARN_SCRATCH, 0, 0x7FFF }, // learn_scratch custom arena
```

> After editing, run `make -j8` and `pdmap build {name} --deploy`.
> For quick test without menu registration, use `--deploy-as uff` instead.
