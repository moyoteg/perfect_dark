# Stage registration plan: agent_office

Already registered: **False**

## 1. `src/include/files.h`

```c
#define FILE_BG_AGENT_OFFICE_SEG       0x07f1
#define FILE_BG_AGENT_OFFICE_TILES     0x07f2
#define FILE_BG_AGENT_OFFICE_PADS      0x07f3
#define FILE_USETUPAGENT_OFFICE         0x07f4
#define FILE_UMP_SETUPAGENT_OFFICE      0x07f5
```

## 2. `src/assets/ntsc-final/files/list.c`

```c
/*0x07f1*/ "bgdata/bg_agent_office.seg",
/*0x07f2*/ "bgdata/bg_agent_office_tilesZ",
/*0x07f3*/ "bgdata/bg_agent_office_padsZ",
/*0x07f4*/ "Usetupagent_officeZ",
/*0x07f5*/ "Ump_setupagent_officeZ",
```

## 3. `src/game/stagetable.c`

```c
/*0x07f1*/ STAGE_AGENT_OFFICE, 2, 255, 100, 100, 0, FILE_BG_AGENT_OFFICE_SEG, FILE_BG_AGENT_OFFICE_TILES, FILE_BG_AGENT_OFFICE_PADS, FILE_USETUPAGENT_OFFICE, FILE_UMP_SETUPAGENT_OFFICE, 1, 1, 100, 0, 0, -1, 255, 0x3e19999a, -1, 400, 0, 1, SFX_ALARM_DEFAULT, 0,
```

## 4. `src/game/mplayer/setup.c` (`g_MpArenas[]`)

```c
{ STAGE_AGENT_OFFICE, 0, 0x7FFF }, // agent_office custom arena
```

> After editing, run `make -j8` and `pdmap build {name} --deploy`.
> For quick test without menu registration, use `--deploy-as uff` instead.
