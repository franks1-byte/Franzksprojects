# Coin Collector (Unity, C#)

A 3D third-person game script pack: collect every coin before the timer runs out.

## Scripts
| Script | What it does |
|---|---|
| `PlayerController.cs` | Camera-relative WASD movement, sprint (Shift), jump (Space) with a ground check |
| `ThirdPersonCamera.cs` | Orbit camera (hold right mouse), scroll zoom, wall collision |
| `Coin.cs` | Spinning, bobbing pickup with optional sound and particle effect |
| `GameManager.cs` | Score, countdown timer, win/lose screen, press R to restart |

## Scene setup (about 5 minutes)
1. Create a new **3D (URP)** project and copy the `Assets/Scripts` folder in.
2. **Ground:** add a Plane, scaled up.
3. **Player:** add a Capsule, set its **Tag** to `Player`, and add `PlayerController` (it adds a Rigidbody automatically).
4. **Camera:** select Main Camera, add `ThirdPersonCamera`, and drag the Player into **Target**.
5. **Coins:** add a Cylinder (scale `1, 0.1, 1`, rotate X 90°) with a yellow material. Tick **Is Trigger** on its collider and add `Coin`. Make it a prefab and scatter copies around.
6. **UI:** add a Canvas with two TextMeshPro texts (score, timer) and a Panel with a title text for the end screen.
7. **GameManager:** add an empty GameObject with `GameManager` and drag in the UI references.
8. Press Play!

Written for Unity 6 (`rb.linearVelocity`). On Unity 2022 or older, change it to `rb.velocity`.
