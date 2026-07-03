# Stage registration plan: my_arena

Already registered: **True**

## 1. `src/include/files.h`

```c
#define FILE_BG_MY_ARENA_SEG       0x07ec
#define FILE_BG_MY_ARENA_TILES     0x07ed
#define FILE_BG_MY_ARENA_PADS      0x07ee
#define FILE_USETUPMY_ARENA         0x07ef
#define FILE_UMP_SETUPMY_ARENA      0x07f0
```

## 2. `src/assets/ntsc-final/files/list.c`

```c
/*0x07ec*/ "bgdata/bg_my_arena.seg",
/*0x07ed*/ "bgdata/bg_my_arena_tilesZ",
/*0x07ee*/ "bgdata/bg_my_arena_padsZ",
/*0x07ef*/ "Usetupmy_arenaZ",
/*0x07f0*/ "Ump_setupmy_arenaZ",
```

## 3. `src/game/stagetable.c`

```c
/*0x07ec*/ STAGE_MY_ARENA, 2, 255, 100, 100, 0, FILE_BG_MY_ARENA_SEG, FILE_BG_MY_ARENA_TILES, FILE_BG_MY_ARENA_PADS, FILE_USETUPMY_ARENA, FILE_UMP_SETUPMY_ARENA, 1, 1, 100, 0, 0, -1, 255, 0x3e19999a, -1, 400, 0, 1, SFX_ALARM_DEFAULT, 0,
```

## 4. `src/game/mplayer/setup.c` (`g_MpArenas[]`)

```c
{ STAGE_MY_ARENA, 0, 0x7FFF }, // my_arena custom arena
```

> After editing, run `make -j8` and `pdmap build {name} --deploy`.
> For quick test without menu registration, use `--deploy-as uff` instead.
