## Experimental netplay branch

This branch contains a **highly experimental** implementation of network play.

Currently only Combat Sim is partially working with experimental 8 player support and really bad netcode.  
Expect nothing to work right.

### Perfect Dark Kit (`port-net-mods/kit`)

This fork merges netplay with the All-in-One mod stack and custom arenas. **All players need the same binary, ROM, and `mods/mod_allinone` tree.**

**Headless / CI smoke:** `./scripts/netplay-smoke.sh`  
**Living test log:** [`docs/NETPLAY_TEST_LOG.md`](NETPLAY_TEST_LOG.md)  
**Automation spec:** [`docs/NETPLAY_AUTOMATION_SPEC.md`](NETPLAY_AUTOMATION_SPEC.md)

#### CLI shortcuts (for testing)

| Flag | Effect |
|------|--------|
| `--host` | Auto-host after intro (skips to Combat Sim network flow) |
| `--connect ADDR` | Auto-join; use `ADDR:PORT` or pair with `--port N` |
| `--port N` | Host listen port; default client port if `ADDR` has no `:port` |
| `--maxclients N` | Cap connected clients |
| `--net-auto-start` | Host auto-starts Combat Sim when a client reaches lobby (smoke/CI only) |
| `--net-stage N` | Arena stage id for `--net-auto-start` (e.g. `0x80` = my_arena) |
| `--net-join-timeout-ms N` | Client join deadline when server is unreachable (smoke/CI) |

Headless custom-arena match smoke (no menu input):

```bash
./scripts/netplay-smoke.sh   # steps 1–7: boot stages, host/join, my_arena net match
```

Manual LAN session (pick arena in Combat Sim menu):

```bash
# Host (machine A)
./build/pd.arm64 --host --port 27100 --moddir mods/mod_allinone

# Client (machine B) — same build + mods + ROM
./build/pd.arm64 --connect 192.168.1.50 --port 27100 --moddir mods/mod_allinone
```

Pick a custom arena in Combat Sim before starting; stage assets must exist in every player's `mod_allinone`.

### Hosting

1. Forward the server port (`27100` by default, can be changed in `pd.ini`).
    * You can also use something like ZeroTier or Hamachi if you can't port forward.
3. Choose `Network Game` -> `Host Game`, configure the player cap, press `Start Game`.
4. Configure Combat Sim as desired, but do not start it yet. Keep in mind:
    * You can save and load the settings as normal.
    * Your player will have the config of Combat Sim player 1.
5. Wait for everyone to join. You can use the console (press `~`) to chat in the meantime.
6. Hit Enter/Start. During the game no more players will be able to join.
7. After game is over, you will be kicked back to Combat Sim settings, at which point people can join again and the process repeats from step 3.

### Joining

1. Your player will have the config of Combat Sim player 1, so set that up beforehand in the Combat Sim menu.
2. Choose `Network Game` -> `Join Game`, enter the address (and port if it's not 27100), press `Start Game`.
3. If the message says `Waiting for host`, wait until the host configures the game. You can use the console (press `~`) to chat in the meantime or `ESC` to disconnect.
4. The game will start automatically.
5. After the game is over, press Enter/Start on the stats screen and you will be kicked back to the `Waiting for host` screen, at which point the process repeats from step 3.

### Misc

* Everyone has to have the same ROM. The game only compares the file name, but different regions in one game will definitely break everything.
* Press `~` to bring up the console, press `F9` for network stats.
* You can chat at any time during a net game by entering messages in the console and hitting Enter.
* Server port and other network settings can be configured in `pd.ini`.
* For a 4+ player game I would recommend changing `Net.Server.UpdateFrames` to `2` in `pd.ini` on the server to lower the bandwidth usage.
* You can paste stuff into the `Enter Address` prompt by hitting `CTRL+V`.
* Expect nothing to work right.

### Known issues

* Clients see rocket rotation incorrectly.
* Clients can't use Slayer fly-by-wire rockets and they will not correctly sync if the server uses them.
* Clients can't use the alt fire mode on the FarSight and probably a couple other guns.
* Cloaking device is not synced.
* Most likely only Combat works properly.
* Sims don't work in netgames.
* Bandwidth consumption on the server is pretty large on the default settings, especially with 8 players.
 
