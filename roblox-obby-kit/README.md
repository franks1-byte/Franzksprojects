# Obby Kit (Roblox, Luau)

Ready-made scripts for an obstacle course ("obby") game, with saved progress.

## Features
- **Checkpoints** that save your stage (DataStore), with no stage skipping allowed
- **Kill bricks**
- **Coins** that respawn after 10 seconds, shown on the leaderboard
- **Moving platforms** driven by attributes, no extra code needed
- **Spinning obstacles**
- **Stage banner** UI that slides in when you reach a new stage

## Setup in Roblox Studio
1. Copy `ObbyServer.server.luau` into a **Script** in `ServerScriptService`.
2. Copy `StageHud.client.luau` into a **LocalScript** in `StarterPlayer > StarterPlayerScripts`.
3. In **Workspace**, create these folders:
   - `Checkpoints`: Parts named `1`, `2`, `3`, … in order
   - `KillBricks`: red parts
   - `Coins`: small yellow parts (uncheck **CanCollide**)
   - `Movers` (optional): add the attributes `Offset` (Vector3) and `Duration` (number)
   - `Spinners` (optional): add the attribute `Speed` (number, degrees per second)
4. Turn on **Game Settings → Security → Enable Studio Access to API Services** so saving works while testing.
5. Press Play.

Works with Rojo too, since the files follow its `.server.luau` / `.client.luau` naming.
