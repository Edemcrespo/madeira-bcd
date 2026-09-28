# Handoff: state of the madeira-bcd fork (2026-09-27)

> **Türkçe özet:** Bu dosya, Claude ile bu depoda yapılan bütün işin devir
> notudur; başka bir asistan (ör. ChatGPT Codex) buradan devam edebilsin diye
> yazıldı. Kullanıcıya Türkçe yanıt verilir. Teknik ayrıntıların tamamı
> `docs/madeira-bcd.md` içinde; bu dosya "nerede kaldık, kurallar neler,
> sırada ne var" sorularını cevaplar.

This file is for whoever continues the work (another coding agent or a
person). Read it first, then `docs/madeira-bcd.md` (every change this fork
makes, with the reason and the evidence), `docs/WOW64.md`, `docs/BUILDING.md`.

---

## 1. What this repository is

`bahacan16/madeira-bcd` is a personal fork of `willfaust/Madeira`: Wine + FEX
(x86-64 JIT, ARM64EC) + DXMT (D3D11/D3D9 over Metal) + `madeira_d3d12` (a D3D12
runtime over Metal that converts DXIL with Apple's Metal Shader Converter and
DXBC with DXMT's airconv) packaged as an iOS app. The owner runs Windows games
on an **iPhone 17 Pro Max, iOS 27.0**, sideloaded with Feather. Personal use
only; the bundle id stays `com.willfaust.mythicemu`.

Upstream PRs merged into the fork (not yet merged upstream):
* **#28 (125hz)** WoW64 32-bit guests + DXMT D3D9. Needs the companion
  submodule forks: `wine` -> `125hz/wine` branch `pr/wow64-core`,
  `research/dxmt` -> `125hz/dxmt` branch `pr/d3d9` (see `.gitmodules`).
  The prebuilt DLLs from #28/#29 (i386 farm, ntdll, xtajit64) were committed
  with the owner's explicit approval.
* **#29 (125hz)** named touch-control layouts.

## 2. Working conventions the owner expects

* **Reply in Turkish.** Owner's clock is UTC+3.
* Work autonomously: diagnose from the log, fix, build, hand over an IPA link.
  The owner dislikes being asked things the agent can decide itself.
* The owner explicitly authorized **automatically starting this workflow after
  every crash/error report** (2026-09-27). Do not stop after pushing a fix;
  dispatch the development-branch workflow, inspect its result, and hand over
  the IPA run/artifact link. Keep this handoff append-only in substance so
  Claude and Codex can alternate without losing earlier findings.
* **Build monitoring preference (owner, 2026-09-27):** After dispatch, verify
  that the run started, then check its status **once about 10 minutes later**.
  Do not poll every step or send running-status screenshots; those wasted
  tokens during build 186. If still running, check again at a sensible longer
  interval, and report the final result and artifact link. Send a screenshot
  only when the owner asks for one.
* Develop on branch **`claude/madeira-bcd-repo-ymg5cb`**, push there.
* Build: dispatch `.github/workflows/build-ipa.yml` on that branch
  (workflow_dispatch). When it is green, fast-forward `main`
  (`git push origin <sha>:main`); if that starts an automatic push build on
  `main`, cancel it (it is a duplicate).
* Version = `0.1.<run_number>` (Info.plist stamped in CI). The artifact is
  `madeira-0.1.<N>-unsigned-ipa`; link format
  `https://github.com/bahacan16/madeira-bcd/actions/runs/<run id>`.
  Downloading artifacts needs a signed-in GitHub account (GitHub rule).
* CI failures: read annotations with
  `curl -s https://api.github.com/repos/bahacan16/madeira-bcd/check-runs/<job id>/annotations`;
  full logs via the Actions UI / API job logs.
* Commit messages: say what was wrong, the evidence, and the fix (see
  `git log`). Keep `docs/madeira-bcd.md` updated for every change.
* A 12-hour "upstream sync" routine existed on the Claude side (merge
  `willfaust/Madeira` main into the dev branch, keep 125hz's submodule
  commits). It will not run elsewhere; do it by hand if needed:
  `git fetch upstream main` (remote = willfaust/Madeira), merge, keep this
  fork's additions, build, fast-forward main.

## 3. Hard rules (do not break)

* **Never commit Microsoft VC++ runtime DLLs** (`app/Madeira/x86_64-vcruntime/*.dll`
  is gitignored; CI fetches them).
* **Apple's Metal Shader Converter** installer lives ONLY as an asset of a
  **DRAFT** release tagged **`msc-private`** (`Metal_Shader_Converter_4.0_beta_2.pkg`).
  CI extracts headers + the iOS library at build time into gitignored
  `build/madeira-d3d12/msc-include/`. Never commit the pkg, headers or library,
  never publish that release. Since build 181 CI **fails** if the release is
  missing (build 180 silently shipped a stub: black screen in every D3D12 game).
* Do not publish IPAs as public releases without the owner's decision (the IPA
  contains Microsoft redistributables and Apple's converter library).
* Do not commit externally supplied binaries (exception already granted: the
  125hz PR #28/#29 DLLs).
* The owner's Ghost of Tsushima / Crysis copies are cracked (RUNE / Steam
  emulator). Fix Madeira-side bugs only; **do not help configure crack or
  Steam-emulator files** (e.g. `steam_api.ini`).
* A GitHub PAT was once pasted in chat; the owner was told to revoke it. Never
  use tokens from chat. A signing `.p12` (+password) and `.mobileprovision`
  were shared read-only; never commit or use them.

## 4. Current focus: Ghost of Tsushima (D3D12, Nixxes port)

### Progress so far (each item is a commit; details in docs/madeira-bcd.md)
Save folder -> D3D12 use-after-free -> display config crash -> GPU driver info
(NVAPI entry points + a registry display adapter, "Report an NVIDIA GPU"
per-game switch) -> `GetAdapterLuid` -> `GetDeviceRemovedReason` -> DXBC
static samplers (black screen) -> intros + main menu work -> New Game OOM
(30k Metal libraries) fixed by lazy pipelines + shared libraries + a
persistent disk shader cache -> game reaches gameplay (~20-40 FPS) ->
**GPU timeout a few seconds into gameplay** (the remaining blocker).

### The GPU timeout (fixed in build 181, confirmed on device)
Every run: 2-5 s into gameplay FPS sinks from ~40 to ~20, then Metal ends a
command buffer with `MTLCommandBufferError` code 2 (timeout), ignores the queue,
and the game tears itself down (its workers then fault copying freed memory,
its crash handler `crs-handler.exe` crashes — both are consequences).
Found with the fault-attribution machinery (below): the kernel (DXIL hash
`34c565ac8322ab2a`, 3948 bytes, `Dispatch(221,1,1)`, 64 threads/group) is a
vertex-normal recompute. Each thread reads a `[first,last)` adjacency range
from a StructuredBuffer at its thread id and loops `until i == last`. The
dispatch is rounded up to the group size, so the extra threads read past the
buffer. D3D12 returns 0 there; the converter did not bounds-check
(`IRCompatibilityFlagBoundsCheck` was off), read garbage and looped forever.
**Build 181 converts with `IRCompatibilityFlagBoundsCheck`**
(`research/madeira-d3d12/src/unix/madeira_ir_unix.mm`; opt out with
`MADEIRA_IR_NO_BOUNDS_CHECK=1`). The shader-cache key changed, so the first
launch re-converts everything (the "Compiling shaders" screen takes a few
minutes and looks frozen — do not close it).

**Next step:** have the owner run build 181 (AVX on, "Report an NVIDIA GPU"
on, press Enter at the dark launcher, New Game) and check the log: there
should be no `GPU fault` line and FPS should stay flat.

### Build 181 result (log 2026-09-27 14:55, 800x600): the GPU timeout is GONE
No `GPU fault` line at all; the scene renders (banners, grass) at 50-60 FPS
before gameplay. The new wall is on the CPU: when gameplay starts,
`ExecuteCommandLists` per frame goes 25 ms -> 273 ms -> 2.3 s while the GPU
is 2-7 % busy (Metal HUD: "Detected high CPU encoding cost with encoders
spending an average of 100% of frame time encoding"; "Compiled Shaders 693 |
12.5 s"). Cause: lazy pipelines (`mad_pso_realize`) are compiled by Metal at
their first draw, on the submitting thread, one at a time, under one global
lock; the first gameplay seconds need hundreds. After ~2 s frames the game
stops itself at the same `int3` it uses for fatal errors (guest RIP ...9acd,
call chain ...b950 / ...63e5) — most likely its own hang watchdog.

**Build 183** (commit "build a batch's new pipelines in parallel"): a per-pipeline lock replaces the
global one, and before a batch is replayed the lazy pipelines its lists bind
are built on up to 4 threads (`mad_prebuild_lists`, madeira.cfg
`pso-parallel = 0` to disable; log line `pso-parallel: built N pipelines`).
Expected: the stall shrinks roughly by the core count. If frames still take
seconds, next steps (in order of payoff):
1. **Persist compiled pipelines across launches** with `MTLBinaryArchive`
   (or Metal 4 `MTL4Archive`): add winemetal calls to create/load an archive,
   add pipeline descriptors to it, serialize it next to the shader cache
   (`%LOCALAPPDATA%\Madeira\ShaderCache\<identity>\`), and pass it as
   `binaryArchives` when creating pipelines. Second launch then compiles
   nothing. Needs changes in `research/dxmt/src/winemetal` (done at build
   time through a `tools/patch-dxmt-*.py`, like the fault-info patch).
2. Start building a lazy pipeline in the background at `CreatePipelineState`
   time at low priority, capped by Metal memory (eager creation of all
   ~14k pipelines hit 5.1 GB and jetsam before; do not go back to that).

### Build 183 result (log 2026-09-27 15:34)
Main menu much smoother (ExecuteCommandLists ~2 ms/frame, 45-48 FPS; parallel
builds working: `pso-parallel: built 20..69 pipelines on 4 threads`). Gameplay
start still froze: presents stopped right after the first large prebuild
batches, then the game tore itself down (workers faulted on memory another
worker freed — the usual teardown symptom). Two problems visible in the log:
* each prebuild batch CREATED 3 Wine threads: every one costs an 8 MB stack
  (floored), a TEB and FEX thread state — a storm of `init_thread_stack` lines
  and failing 8 MB reserves (`[va-scan] FAILED ... size=0x800000`).
* the 64-bit high-band fallback only searched 0x7200000000..0x73ffff0000,
  which is already occupied on device (every `[wow-window] #N ... NOT placed`),
  and a 1 MB FEX allocation still got STATUS_NO_MEMORY.
Also note: this run had 16,968 shader-cache misses because the cache key
includes the madeira_d3d12 build stamp — every new build re-converts every
shader once (first launch after an update is slow; second launch is not).

**Build 184**: a persistent pool of 3 prebuild threads (created once), and the
high-band fallback searches everything above the 32-bit windows up to the
user-space limit (still bounded by a caller's limit_high). If gameplay still
freezes, check whether presents stop while `pso-parallel` batches run
(pipeline compile time) or with no batches (then it is something else: look
at the game's worker threads / waits).

### Build 184 result (log 2026-09-27 17:02): crash DURING "Compiling shaders" (97 %)
No GPU fault, no pipeline stall. The crash is the same memory race seen in
every earlier run, now clearly independent of the GPU: the view history shows
a 1 MB + 64 KB block (`0x110000`) CREATED by the main thread 69 s earlier and
DELETED by a JobWorker 4 ms before the main thread (or another worker) faults
memcpy'ing 1 MB out of it (source = block + 0x40). Same size and shape in
four runs. That is one thread releasing a buffer another is still reading —
on Windows the game waits for its jobs first, so a wait here returned early
or a signal arrived too soon. Prime suspect: Madeira's in-process fast path
for events/waits ("fastsync", `MADEIRA_FASTSYNC`, auto-enabled after 20k ops/10 s,
see `build/ntdll-unix` sync code).

**Build 185**: per-game switch "Safe thread sync (no fastsync)" in the game's
Launch options (sets `MADEIRA_FASTSYNC=0` for that launch). Test GoT with it ON.
If the race disappears, the bug is in fastsync (look for a wake that is
delivered before the waiter's condition is really satisfied, or a
`WaitForMultipleObjects(waitAll)` / auto-reset event edge case). If it still
crashes, add a watch: `vmwatch` in madeira.cfg cannot help (addresses differ
per run); instead log the guest call stack of the thread that frees a
0x110000 view (NtFreeVirtualMemory caller RIP) and of the reader.

### Build 185 attempted test (2026-09-27 18:21, log `GhostOfTsushima.exe-2026-09-27_18-21-33.txt`)
The game crashed again, but **this was not a fastsync-off test**: at log line
269 Wine says `[fastsync] ... mode=auto`, at line 15147 it says `AUTO-ENABLED`,
and subsequent `[perf]` lines count tens of thousands of fastsync hits. No
`[madeira-env]` line sets `MADEIRA_FASTSYNC`. The owner subsequently confirmed
that the per-game switch had not been enabled for this run.
`LaunchRequest.apply()` in `app/Madeira/HomeView.swift` does set the variable
to `0` when its saved
`safeSync` preference is true; the game's launched exe was the expected x64
`GhostOfTsushima.exe`, with AVX and NVIDIA reporting enabled. Re-check the
game's **Launch options > Safe thread sync (no fastsync)**, use **Save and play**
and confirm the next log says `[fastsync] ... mode=off` (the exact mode string
should be checked against the log). A fallback is `env.MADEIRA_FASTSYNC = 0`
in `Documents/madeira.cfg` for the experiment. Do not treat this run as
evidence for or against the fastsync hypothesis.

The original failure reproduced: a worker (tid `00f0`) deleted the
`0x706ed30000+0x110000` view **2 ms** before tid `00f8` read from
`0x706ed3c000` during a 1 MB copy (`c0000005`; `[fault-rgn]` lines
36299-36316). No new GPU timeout was logged. The process later ran the game
crash handler; its own faults are secondary. Next action is a true fastsync-off
run. If the same freed-while-read signature remains with `mode=off`, collect
the freeing and reading guest call stacks as proposed above.

### Build 185 valid fastsync-off test (2026-09-27 18:29, log `GhostOfTsushima.exe-2026-09-27_18-29-58.txt`)
The owner enabled the switch and got about **3–5 more seconds of gameplay**
before another crash (one run, so this is not established as an improvement).
Log line 273 says `[fastsync] ... mode=off (pre-ml952) peek=off`; all reported
`[perf]` fastsync hit/miss/peek counters remain zero. Thus fastsync was really
disabled, and disabling it alone did **not** prevent this crash. Do not
continue to treat the fastsync fast path as the sole cause.

At lines 36966–37076, the source address `0x70f0dd0040` belongs to a
`0x70f0dd0000+0x210000` Wine view created by tid `0024` about 8.6 s earlier
and **deleted by tid `00f8` 7–8 ms before the faults**. Threads `00ec`,
`00f0` and `0024` fault on reads from that source during 2 MB copies in
`ntdll.dll+0x64074` (different destinations). There was no new Metal command
buffer failure; the later `crs-handler.exe` faults are secondary. The log
proves a freed-while-read overlap, but does not yet prove whether the early
free is a game scheduling error, a different Madeira wait/signal problem,
or some other translation/VM behavior.

**Next diagnostic change (after this result):** `virtual_ios.c` captures the
release site on `NtFreeVirtualMemory(MEM_RELEASE)` for 1 MB+ guest-band views
and attaches it to the existing deletion-history record. On the next fault,
`[free-origin]` prints the native return address, FEX live and saved x64 RIP,
saved x64 RSP, and up to eight candidate return addresses within the main
exe (with RVAs) scanned from the saved guest stack. These are candidates,
not a verified unwind; compare them with the reader's existing `[callret]`
trace. The data prints only when a later fault overlaps the freed view.
Build and test this instrumented revision next; then identify the releasing
call site before changing scheduling or memory-lifetime semantics.
The diagnostic code and these notes were pushed together as commit
`6d758e544cffeff98ad8a7720b96690ec053cdc7` on the development branch.

**Build dispatch status (2026-09-27, Codex):** The owner authorized automatic
workflow dispatch after every error report, now recorded above. The GitHub
connector can push commits but does not expose `workflow_dispatch`; the
cloud-browser GitHub login reached the two-factor app-code step, then GitHub
returned “Your browser did something unexpected” after verification. A fresh
workflow tab remained signed out. No new workflow run or IPA has been created
yet; do **not** report build 186 as started. The development branch now includes
the diagnostic commit plus the handoff authorization note (`2e4de7f8`), while
`main` remains at the previous tested commit. Resume with an authenticated
GitHub Actions dispatch on `claude/madeira-bcd-repo-ymg5cb`, inspect the run,
and fast-forward `main` only after a successful build.

**Update 2026-09-27 18:53 (UTC+3):** The owner completed GitHub sign-in in the
cloud browser. Codex dispatched `build-ipa.yml` from
`claude/madeira-bcd-repo-ymg5cb` at commit
`0c925759891f7e63a2267faec2f63f63b34fbeb0`.
Workflow **#186**, run **36331180977**:
`https://github.com/bahacan16/madeira-bcd/actions/runs/36331180977`.
Initial status `in_progress`; await result and artifact before declaring an IPA
ready or advancing `main`.

**Build 186 result (2026-09-27 19:09 UTC+3): SUCCESS.** Run
`36331180977` completed successfully from commit `0c925759`; the `Archive
(unsigned)`, `Package unsigned IPA`, and artifact upload steps all passed.
Artifact **`madeira-0.1.186-unsigned-ipa`**, id `10935873381`, about 141 MB;
download it from the run page above while signed in to GitHub. This validates
compilation and packaging, **not** the on-device crash. The next device test
should retain AVX/NVIDIA settings and `Safe thread sync (no fastsync)` ON so
the new `[free-origin]` records can be compared with the build 185 mode-off
log. If it crashes, upload the complete session log. Compare the freed view,
release-site candidates and reader `[callret]` frames; do not infer an exact
caller from the stack scan alone.
After success, Codex fast-forwarded `main` to the development branch's
`1ec7af666a0cb4033c9ed51fb67045ea8ce129f8` documentation commit;
both refs matched. The final handoff update itself is documentation-only and
should also be fast-forwarded to `main`.

**About the Metal HUD suggestion "adopt MTL4Compiler"**: Metal 4
(iOS/macOS 26+) has `MTL4Compiler` (explicit compiler objects, async
compilation with QoS, `MTL4Archive`, flexible render pipeline states that
share compiled vertex/fragment code). Madeira's bridge (DXMT winemetal) is
written against the classic `MTLDevice newRenderPipelineState...` API and the
converter emits classic metallibs; moving to MTL4 means rewriting the
winemetal pipeline/command-buffer layer, a large job. The same benefits for
this problem (no main-thread compile stalls, reuse across launches) are
available with less risk via parallel builds (done) and `MTLBinaryArchive`
(item 1 above). The HUD's other hints ("high number of interleaved blit
encoders", "render passes with similar attachments") are performance notes,
not errors.

Note: `C:\madeira-cs\fault-shaders.txt` keeps hash 34c565ac8322ab2a, so every
launch logs that shader's bytecode once (harmless, ~8 log lines); delete the
file in the Wine prefix to stop it.

### Open issues, roughly in priority order (updated 2026-09-28 morning)
Build 203 was tested on the device (log `GhostOfTsushima.exe-2026-09-28_07-42-33.txt`):
the C++ fix was NOT applied (`[pc2fh] ... padding in use`), the water pipelines
failed at the vertex shader, the launcher stayed dark, the owner saw broken
rocks and occasional dark patches in the air. Build 204 fixes the first three
(see "Build 204" below); the rocks need a close-up screenshot.
1. **Verify 204 on the device** (`pso time (...)` lines say how much of
   "Compiling shaders" is Madeira's): `[pc2fh]` at start-up and no VCRUNTIME140_1
   crash after saving; `shader cache ON ... identity 'madeira_d3d12 bc1
   converter <hex>'` and mostly hits on the second launch; `[madeira-ir] MSC
   4.0.1 compatibility: position invariance on, strict NaN/Inf on, ...`;
   water: `DXIL tessellation: vs ...`, `[winemetal] DXIL tessellation pipeline
   OK`, `DXIL tessellation: N drawn` -- or the reason it stayed a placeholder.
2. **Remaining slight artefacts** (owner, after build 194): nature unknown until
   the screenshot. 198's flags are the best guess; if they persist, capture
   (CAP) a frame showing them.
3. **Performance**: 10-17 FPS in gameplay at 800x600. Frame 57-96 ms, GPU
   22-36 ms of it (33-60 % busy), ExecuteCommandLists 10-17 ms on the game's
   render thread, ~230 encoders a frame with a full fence chain (fence-chain
   1; mode 6 has a known flicker hole). Mostly the game's own x86 threads
   under FEX (TSO on, half barriers). Ideas: fewer useResource calls per draw
   (up to 64 + heaps), MTLBinaryArchive for pipelines, attachment store
   traffic (~500 MB a frame, 300-420 MB never read again).
4. **"Compiling shaders" on a warm cache**: ~650-700 stages/s (build 190 log,
   ~1.4 ms each) -- still one small file per shader plus ~11k Metal library
   creations. 197 halved the reads (one per hit). Build 203's `pso time (...)`
   lines split pipeline creation into conversion+cache, library creation and
   the rest; decide from them. If library creation dominates: create a plain
   pipeline's MTLLibrary/MTLFunction lazily in `mad_pso_realize` (the cache
   file is the backing store; D3D12 lets the app free its bytecode, so keep
   the cache key, never a pointer). If conversion dominates: one packed cache
   file with an index instead of ~30k files.
5. The launcher window stayed dark until Enter / gamepad X was pressed -- fixed
   in 204 (the direct-launch GDI overlay was never given its host layer).
6. `DXGIFactory::EnumAdapterByLuid` not implemented (Streamline only);
   non-occlusion queries resolve to zero; `ResolveQueryData` into GPU-only
   buffers is not delivered.
7. 32-bit games through WoW64: Crysis runs with small problems (not looked
   at yet); Crysis 3 (32-bit) exhausts the 4 GB guest window (advise Bin64 /
   lower settings).

## 5. Debugging toolkit built during this work

Log = the file the owner uploads (`GhostOfTsushima.exe-<date>.txt`). Useful greps:

| grep | meaning |
|---|---|
| `GPU fault encoders: code N` | failed command buffer; code 2 = timeout, 3/4 = page fault/ignored; `[FAULTED] C#<seq> <kernel> fn=...` names the encoder |
| `GPU fault dispatch C#` | bindings of the faulted dispatch (root params, descriptors resolved to resources, `RUNS PAST THE END`) |
| `[b64 <hash>]` | bytecode of a faulting compute shader, logged at the NEXT launch (also `C:\madeira-cs\fault_<hash>.dxil`) |
| `shader cache: N hits` / `shared shader libraries` | disk cache / library sharing |
| `currentAllocatedSize`, `[footprint]`, `[proc-mem]` | Metal memory and process footprint (limit 8192 MB) |
| `[fault-rgn]   history:` | who created/deleted the view at a faulting address (1 MB+ views) |
| `[stack-quarantine]` | a dead thread's stack was touched while quarantined |
| `[va-scan] FAILED ... STATUS_NO_MEMORY` | address-space exhaustion |
| `[wow-window] ... placed above them` | 64-bit views placed above the 32-bit slots |
| `skips by site` | draws/dispatches skipped (L<line> in madeira_d3d12.c) |

Disassembling a captured shader:
```
grep -a "^\[b64 <hash>\]" log.txt | sed 's/^\[b64 [0-9a-f]*\] //' | tr -d '\n' | base64 -d > s.dxil
pip install llvmlite
python3 tools/dxil-disasm.py s.dxil > s.ll
```

madeira.cfg keys added here: `shader-cache` (default 1), `pso-lazy` (1),
`gpu-fault-info` (1), `gpu-fault-skip` (1), `encoder-labels` (0),
`vmwatch = 0x<addr>` (existing). Env: `MADEIRA_IR_NO_BOUNDS_CHECK=1`.

Metal Shader Converter headers for reading (never commit): download the pkg
from the draft release through the API, unpack xar -> Payload (pbzx/cpio) ->
`usr/local/include/metal_irconverter{,_runtime}/`. Key facts learned there:
descriptor heap bind point 0, sampler heap 1, top-level argument buffer 2;
UAV counters are an R32Uint texture-buffer view in the descriptor's texture
id word with the element offset in metadata bits 32..39
(`IRRuntimeCreateAppendBufferView`); buffer metadata = size | texview offset
<<32 | typed<<63.

Local compile check of `madeira_d3d12` (no device needed): llvm-mingw
`arm64ec-w64-mingw32-clang -shared -O2 -Wall madeira_d3d12.c d3d12.def -I...
-lwinemetal -luuid -lole32` with an import lib generated from
`research/dxmt/src/winemetal` exports (gendef/dlltool). The Wine unix side
(`build/ntdll-unix/*_ios.c`) only compiles in CI (Darwin/Mach headers).

## 6. Where things live

* `research/madeira-d3d12/src/pe/madeira_d3d12.c` — the D3D12 runtime (PE,
  ARM64EC). Most GoT fixes are here.
* `research/madeira-d3d12/src/unix/madeira_ir_unix.mm` — shader conversion
  service (Metal Shader Converter / airconv), unix side.
* `research/dxmt` (submodule, 125hz fork) — winemetal bridge; patched at build
  time by `tools/patch-dxmt-*.py` (the submodule itself is not modified).
* `build/ntdll-unix/virtual_ios.c`, `thread_ios.c` — Wine VM/threads on iOS
  (address-space windows, swap tier, view history, stack quarantine).
* `build/win32u-unix/sysparams_ios.c` — display devices / virtual GPU registry.
* `app/Madeira/*.swift` — the app (library, per-game settings incl. AVX and
  "Report an NVIDIA GPU").
* `.github/workflows/build-ipa.yml` — the whole build.

### Build 186 (ChatGPT/Codex) and 187 (Claude), 2026-09-27 evening
* Build 185 with "Safe thread sync" ON (fastsync `mode=off`) still crashed the
  same way, so fastsync is NOT the cause (Codex's notes above).
* Build 186 (Codex) only added free-origin tracing (`[free-origin]` lines
  under `[fault-rgn] history`). Its device run crashed at ~80 % of "Compiling
  shaders" with a different signature: Metal's completion handler
  (`IOGPUMetalCommandBufferStorageDealloc` -> `objc_release`) released a
  corrupted object (`x0=0x10701`), and a Wine thread crashed in `objc_release`
  on the same value. Reading: the same freed-while-used race — the game keeps
  touching a block after it was released, the VA has meanwhile been given to
  Metal/malloc, and Metal's objects get scribbled on. No `[free-origin]`
  output in that run (no guest fault on a freed view).
* **Build 187 (mitigation, not a root-cause fix)**: DELAYED RELEASE in
  `NtFreeVirtualMemory` (`build/ntdll-unix/virtual_ios.c`, `ios_fd_*`): a
  whole-view MEM_RELEASE of a private 1-16 MB guest-band allocation returns
  success at once but the mapping stays committed for `MADEIRA_FREE_DELAY_MS`
  (default 2000; 0 = off), max 128 MB in flight, then is really released.
  Late readers find valid memory and nobody else gets that VA meanwhile.
  Log: `[free-delay] #N release of ... held for 2000 ms`.
  If GoT gets through gameplay with it, the underlying race (job refcount /
  wait ordering under FEX) is still worth finding with the free-origin trace
  (set `MADEIRA_FREE_DELAY_MS=0` in madeira.cfg `env.` to reproduce).

### Build 187 result (log 2026-09-27 20:20, 1024x768, Adaptive Power was on)
* **The freed-while-used crash is gone.** The whole opening scene played for
  ~3 minutes, horse riding and control hand-over worked, the owner played ~2
  minutes with the touchpad, opened the menu and saved. `[free-delay]` held
  8 releases (1-8 MB each). Footprint peaked at 7.34 GB (limit 8 GB).
* HUD: GPU 14-44 ms/frame, 10-32 FPS; Metal warns about many render passes
  with similar attachments, interleaved blit encoders and runtime pipeline
  compiles (1000-1600 pipelines compiled during play). The log's render pass
  report: `ended by: targets 298, clear 77, dispatch 370 ... attachment
  load+store ~14848 MB` per 600 lists -- merging passes is a real FPS lever.
* Black squares (fixed screen positions, ~64 px) and a green block pattern in
  the lower part of the image remain. Still unexplained; a Metal frame
  capture (Mac + Xcode) is the fastest way to name the pass.
* **New crash after the save**: main thread AV READ of 0x16694 in
  VCRUNTIME140_1 (x64, `__CxxFrameHandler4`): `mov r12d,[rax+rbx]` with
  rbx = ThrowInfo->pCatchableTypeArray RVA and rax = `_GetThrowImageBase()`
  = 0. So a C++ exception arrived with ThrowImageBase (parameter 3) = 0.
  The stale guest state had rax = 0x11fb3e6a0, a JIT-pool alias inside
  msvcp140.dll's pool copy -- i.e. the ThrowInfo pointer was probably a pool
  VA, which `RtlPcToFileHeader` cannot map to a module. (The later crash of
  thread 0x50 is crs-handler.exe, the game's crash reporter, reacting.)
  The PE ntdll (`app/Madeira/arm64ec-windows/ntdll.dll`) is a tracked
  upstream binary and is NOT compiled by CI, so `RtlPcToFileHeader` cannot be
  fixed there.
* **Build 188**: unix `NtRaiseException` (`build/ntdll-unix/thread_ios.c`)
  repairs 64-bit C++ throws (0xE06D7363, 4 parameters) before dispatch: a
  pool-alias ThrowInfo is mapped back to the PE VA and its module base is
  filled in; a base of 0 is filled from the owning MEM_IMAGE allocation.
  Log: `[cxx-throw] #N ThrowInfo ... base ... -> ...: <how>` (first 32) and
  `[cxx-throw] ok ...` for the first 4 normal throws. If the crash returns
  WITHOUT a `[cxx-throw] #` line, parameter 3 was fine and the vcruntime
  per-thread data (`_ThrowImageBase` in the FLS ptd) is the suspect instead.

### Build 189: contact sheets for the black squares (no Mac needed)
The owner will not have a Mac soon, so visual bugs must be diagnosed from the
phone. Build 189 adds CAP contact sheets (docs/madeira-bcd.md): press CAP in
the overlay while the black squares are visible; `Documents/capture/` then
holds `f<frame>_sheet00.png ...` (20 numbered thumbnails each) and
`f<frame>_sheets_index.txt`; the log has the same `[capture-sheet]` lines.
Ask the owner for the sheets (as images) plus the log. Reading them: find the
first thumbnail (in encoder order) where the squares appear, magenta = NaN/Inf.
If it is a `cs <hash>` thumbnail, that dispatch produced them: next step is
`capture-cs` / the fault-shader machinery on that hash (dump its DXIL with
`tools/dxil-disasm.py`). Build 189 also carries build 188's C++ throw repair.

### Build 190 capture result (log 2026-09-27 21:15, main menu, 800x600)
Contact sheets work (283 thumbnails, 15 sheets). Findings:
* The main depth-stencil (800x600 D32S8, "DepthTarget") is clean after the
  G-buffer passes (#249, enc#179408, depth 0..0.057) and has **14336 NaN
  texels in a regular grid of small squares** at the next pass (#252,
  enc#179423 `PsMain`, which does not write depth: `w0`). The stencil plane
  (#253) shows the same grid plus garbage blocks = the green block pattern.
  The black squares in `PsMain`'s output (#251) sit exactly on that grid.
  Between the two passes only compute dispatches run (cs_main 100x75x1,
  13x10x1, 1x1x1, 11 indirect, 1x16x16), none with a bounded texture UAV.
* The previous frame's HDR image (#148, RGBA16F, probably TAA history)
  carries the same NaN squares, so they also feed back frame to frame.
* The 5th G-buffer target (RG16F, dx34, likely velocity) is NaN/Inf over the
  whole sky (#167/#174/#202); its clear is not visible (clear-only passes
  are not captured).
* Hypothesis: memory aliasing. DEFAULT heaps are Metal placement heaps
  (ml1145, `heap-backing = 1`); GoT uses many RT/DS-only heaps (flags 0x84).
  A resource placed over the depth memory and written by one of those
  dispatches (or a copy) would corrupt it in a grid, since Metal's tiled
  layouts differ by format. Build 191 adds the alias report to prove or
  refute it: look at the `| r#N heapH +a..b, OVERLAPS: ...` tail of the
  depth's `[capture-sheet]` lines, then `[capture-uavbuf]` / `[capture-op]`
  for a writer of an overlapping resource. If depth overlaps nothing, the
  NaN depth is a second DepthTarget (compare r# of #249 and #252).
* The second CAP of build 190 hung the game: thumbnailing a BC1 texture
  (captured as a UAV target) read past its copy while holding the capture
  lock. Fixed in 191 (BC skipped, reads bounds-checked).

### Build 191 results (logs 2026-09-27 21:46 and 21:48)
* Run 1 died before the main menu with the SAME C++ exception crash as after
  the save in build 187 (AV READ of 0x16694 in VCRUNTIME140_1, handler
  GhostOfTsushima.exe+0xd15f0c). No `[cxx-throw]` line: build 188's repair in
  unix `NtRaiseException` is never reached, because ARM64EC
  `RtlRaiseException` (wine/dlls/ntdll/signal_arm64ec.c) dispatches in user
  mode unless `peb->BeingDebugged`; only the second chance goes to the
  syscall. The PE ntdll is a tracked binary, so the fix has to live somewhere
  else (open; needs a deeper look -- where does the zero ThrowImageBase come
  from: the record, or vcruntime's per-thread `_ThrowImageBase`?).
* Run 2: pressing CAP crashed in `mad_texel_rgb` (madeira_d3d12+0x19478,
  default case): the capture copy's Metal-allocated shared memory was not
  mapped any more (prot 0). Build 192 backs capture copies with our own
  VirtualAlloc memory (no-copy Metal buffer) and locks the list in
  `mad_capture_buffer` too.
* **The aliasing hypothesis is refuted**: not a single `[placed]` line --
  GoT never calls CreatePlacedResource; its heaps stay empty, the depth is a
  committed resource. New leading hypothesis: a compute UAV descriptor holds a
  texture resource id that now belongs to the depth texture (a stale id of a
  released texture, reused by Metal), so a dispatch writes into depth. Build
  192 logs `[capture-uavtex]` for every UAV texture id (bounded ranges and
  the first 64 of unbounded ones) that resolves to no live texture or to a
  render-target / depth texture.

### Build 192 result (log 2026-09-27 22:18): black squares ROOT CAUSE found
Two CAPs worked (no crash). Frame 2311: the depth r#465 is clean at
enc#197148 (`ps_Copy`) and has 14336 NaN at enc#197163; `[capture-op]` in
between: `copy texture r#465 -> ... r#241` (stencil plane to an 800x600 R8
texture) and `copy texture r#241 -> r#465 mip 0 slice 1` -- D3D12
subresource 1 of a one-layer D32S8 resource is the STENCIL PLANE, which
Madeira decoded as array slice 1, so the copy wrote past the texture over
its depth and stencil memory. Build 193 decodes planes and copies aspects
properly (docs/madeira-bcd.md "Depth-stencil planes in copies"). Also seen:
UAV descriptors holding texture ids that resolve to no live texture (0x6cdc..
0x6cde, many shaders) and cs 3bc86a8a91b059a4 u8 resolving to the depth
(probably unused table slots; watch after the fix).
* Longer play in the same build-192 run (log 2026-09-27 22:18, part 2): no
  crash, footprint peak 6.6 GB. When the owner switched apps, iOS refused the
  GPU work ("Insufficient Permission (to submit GPU work from background)",
  code 7); Madeira took that for a GPU fault and switched the fault
  diagnostics on for good (every compute dispatch in its own encoder = slower
  for the rest of the run). Build 194 ignores that error for diagnostics.

### Build 194 result (log 2026-09-27 22:49): black squares FIXED
Owner: ~90 % of the corruption gone, only slight artefacts left. The capture
shows no NaN in the depth any more; the stencil round trip runs as
`aspect copy r#465 stencil -> r#241 colour` and back. Remaining NaN: the
RG16F G-buffer target r#483 (likely velocity) is cleared BY THE GAME with a
NaN colour (`[capture-op] clear RT (-nan ...)`), so that one is intentional.
The C++ exception crash (VCRUNTIME140_1, AV READ of 0x16694) happened again
at the end of the run -- the next main task. Owner has been told to raise the
effort level for it.

### C++ exception crash: ROOT CAUSE and build 196 fix
Analysed with Microsoft's 14.44 runtime (msvc-runtime wheel from PyPI, only
for disassembly, never committed): the fault is `mov r12d,[rax+rbx]` at
VCRUNTIME140_1+0x17b4 in FH4's FindHandler, rax = `_GetThrowImageBase()` = 0.
FH4 copies the throw image base from ExceptionInformation[3] at entry. MS's
`_CxxThrowException` would have switched the magic to 0x01994000 (pure) on a
zero base, so the record came from WINE's builtin runtime: Madeira keeps
Wine's ARM64EC vcruntime140 + msvcp140 (WineProcessBridge.m exemptions) but
overlays MS vcruntime140_1/concrt140. At RVA 0x166a0 of the shipped
arm64ec-windows/msvcp140.dll sits a ThrowInfo whose CatchableTypeArray RVA is
0x16694 -- the fault address -- type `std::runtime_error`; build 187's stale
rax was exactly that ThrowInfo's pool alias. Wine code computes the pointer
PC-relative in its JIT-pool copy, RtlPcToFileHeader(pool VA) returns 0.
Build 196 patches RtlPcToFileHeader's pool copy to reverse-translate first
(`[pc2fh]` log line at start-up). (Run 195 was the automatic build of the
main push of build 194's commits -- same content as 194; the fix is 196.) The same crash hits every game that mixes
Wine's msvcp140 with MS's vcruntime140_1 and catches a Wine-thrown exception.
Verified offline against the shipped ntdll.dll with a harness (patch lands on
RVA 0x35ea0, trampoline at RVA 0x8ffc0, idempotent).

### Build 197: the shader cache survives new builds
Every build used to start the device's shader cache from nothing (its key
held the DLL's compile time), so each new build sat on "Compiling shaders"
while ~29,000 stages converted again, and a DXIL miss ran the converter
twice. Build 197 keys the cache by a converter identity the CI computes from
everything that can change a conversion (docs/madeira-bcd.md, "Persistent
shader cache") and converts a miss once. The first launch of 197 still
converts everything (new identity); from then on a build that does not touch
the converter, DXMT's airconv, LLVM or the MSC library starts with a warm
cache. Log: `shader cache ON: ... identity 'madeira_d3d12 bc1 converter
<16 hex>' (vsps-fill 1, no-bounds-check 0, ags-roundtrip 0; ...)`; the
`shader cache: N hits, M misses` lines should show almost only hits on the
second launch.

### Build 198: converter flags for the remaining slight artefacts
Build 194's remaining artefacts are "slight" (screenshot pending). Two MSC
defaults differ from D3D12 in ways that produce exactly that kind of damage,
and the build-194 capture shows the game depends on both: ~350 draws a frame
redraw geometry with depth test EQUAL (D3D12 func 3, `dtest=1/func3/w0` in
`[draw-dump]`: cloth, moving objects, hair) -- without position invariance
Metal may compute those positions differently from the depth pre-pass --
and the game clears its RG16F velocity target to NaN on purpose, while MSC
4.0 optimises on the assumption that no value is NaN. Build 198 converts
with position invariance, strict NaN/Inf and sampler LOD bias
(docs/madeira-bcd.md). Each is a madeira.cfg switch (`msc-position-invariance`,
`msc-strict-nan`, `msc-sampler-lod-bias` = 0) for an A/B run; each switch
change re-converts every shader once. If the artefacts are gone but FPS
dropped, try `msc-strict-nan = 0` first (the likely costliest).

### Build 199: DXIL tessellation (the missing water)
Every run logged 12-16 "tessellation pipeline could not be built; returning a
placeholder whose draws are skipped" -- all of them Ghost of Tsushima's WATER
pipelines (`ls_Main_techWaterBlend`, `ps_Main_techWaterMain`,
`ps_WaterHeight_techWaterHeight`): DXIL hull+domain shaders, and the runtime
only had DXMT's emulation for DXBC ones. Build 199 builds them through the
Metal Shader Converter's own tessellation emulation (docs/madeira-bcd.md). Not
testable off the device: check the log for `DXIL tessellation: vs ...` (pipeline
converted), `[winemetal] DXIL tessellation pipeline OK` (Metal accepted it) or
`... REFUSED` / `Metal refused it` (with the reason), and `DXIL tessellation:
N drawn` in the ml1050 lines. If water scenes misbehave (GPU fault, hang),
`dxil-tess = 0` in madeira.cfg restores the placeholders. The workflow now
FAILS when madeira_d3d12.dll does not build (it used to ship upstream's old
tracked DLL and stay green).

### Build 201: housekeeping on the phone's storage
* ml931 wrote the first 400 compute shaders of every launch to
  `C:\madeira-cs\cs_<pipeline pointer>_<size>.dxil`; the pointer differs per
  run, so every launch added up to ~16 MB that nothing removed. Now opt-in
  (`cs-dump = 1`); the old dumps are deleted in the background (log: `removed
  N old compute-shader dumps`).
* The unix DXBC cache (`Documents/shadercache/*.mdsc`) got a fresh set per
  build and never lost the old ones; entries of earlier builds are removed
  once per build (log: `DXBC shader cache: removed N entries`).

### Build 209: the 208 test (log 2026-09-28 09:31, video, 1564x720 "Fill")
* **Smears with a still camera** (video, first 10 s: directional streaks and
  blocky patches behind the cart, the "dark patches in the air"). The log had
  `ClearUnorderedAccessViewUint on texture 'Texture' (view format 2 ...
  values 0xbf800000 0x4cbebc20 0 0) is not supported; skipped`: an RGBA32
  clear to (-1, 1e8, 0, 0), typical of a min/max depth or velocity tile
  buffer, left uncleared. Texture UAV clears only took texels that repeat
  every 4 bytes; the pattern buffers now repeat a 16-byte period, so 8- and
  16-byte texels are cleared exactly (log: `UAV clear value ... exact pattern
  buffer`). If the smears stay, the next suspects are the 4 clears on "a
  texture view the runtime does not know" and the 4 skipped indirect draws on a
  geometry-shader pipeline.
* **C++ fix still not applied**: `[pc2fh] no zero padding in the last .text
  page (000880c0..0008c000)`. On the device the tail of ntdll's last .text
  page holds file bytes (raw size 0x80000 > VirtualSize 0x780a5), not zeros.
  That range is outside every section, so the trampoline now goes at its
  start regardless of content; the pool copy is only refused when its bytes
  differ from the image's (another patch). Host test with a garbage tail:
  patched at RVA 0x880c0, idempotent, refused with foreign pool bytes.
* Water: DXIL tessellation now draws (`DXIL tessellation: ~1900 drawn`, no
  REFUSED). GPU time at 1564x720 is 52-56 ms a frame (overlay), so at that
  size the GPU is the limit (~15 FPS).

### Build 204: the three failures of the 203 test
* **C++ exception fix not applied.** `[pc2fh]` refused with "padding in use":
  the trampoline went at the end of the section gap, which this binary uses.
  It now goes in the first 48 zero bytes after `.text`'s end inside the last
  executable 16 KB page (verified offline against the real
  vcruntime140_1.dll: RVA 0x880d0). Log: `[pc2fh] ... now maps`.
* **Water: VS conversion.** `converted library has no function
  'ls_Main_techWaterMain'` / `no stage-in library`: the tessellation VS is now
  converted library-only (the function is looked up by the object-shader name
  in winemetal) and always gets the input layout for its stage-in function.
* **Dark launcher.** The launcher is an ordinary GDI window (790x445
  StretchDIBits, `[winios] present hwnd=... surf=896x512`), and its bits did
  reach Winios -- but `ContentView.swift` never called
  `winios_set_game_layer` / `winios_set_game_rect` (upstream's Swift side of
  the direct-launch overlay was never merged), so the overlay host was never
  created: no `[overlay] created host=` line in any log. MetalBackedView now
  publishes the layer once and the game rect on every change (with the two
  relayout hooks). The launcher should show and take taps; the overlay also
  arms win32u's 16 ms message poll while it is visible. `MADEIRA_DIRECT_OVERLAY=0`
  turns the overlay off.
