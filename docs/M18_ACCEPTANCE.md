# M18 acceptance / implementation evidence — 2026-11-26

Owner authorizes cumulative M18 based on M17 177b89f. That exact M17 commit has CI, Windows portable build and true portable runtime PASS. Native and independent M16/M17 quality gates remain open. M21 Debugging & Stabilisierung is now a binding final pre-1.0 milestone in ROADMAP.md; no S–D feature removal.

## Implemented integration paths

- M18a: shared explicit single-video URL import, legacy M5 Twitch wrapper delegated to new engine. YouTube / Shorts, Twitch VOD / clip, Kick VOD / clip, Vimeo, Dailymotion and HTTPS direct media have parser contracts, NOT live provider certification. Metadata preflight, resolution and optional audio-only selection, native/MKV/MP4 remux, optional existing subtitles, target folder and explicit open-after choice. Unknown metadata stays unknown. Staging/lock/resume, no overwrite, bounded transfer and disk checks, FFmpeg probe/decoded samples, source receipt. Raw provider output/cookies/tokens not persisted. Local HTTPS CONNECT guard resolves and pins public addresses, rejects nonpublic/mixed DNS, and blocks other ports/protocols. Trusted yt-dlp native downloader with no config/plugins/credentials/remote components; not an OS process sandbox, not a proof against all external-runtime escapes. Real provider redirects and adversarial tests are hard release gates. Public only, no access-control bypass, no automatic publishing.
- M18b #48: explicit per-channel permission, session-only scheduler opt-in, first observation baselines existing IDs, bounded listing (20), interval 15–1440 min, 1–5 new items per check, per-video size cap, dedup state and receipt recovery; pause/remove registration without deleting media. No auto startup. Provider channel listing can be unsupported; error and next regular check.
- #34 OBS timing markers using optional local OBS WebSocket v5, explicit session name and recording/stream elapsed time. Manual offset when binding a session to a source. No automatic clock synchronization.
- #35 local Stream Deck command spool (marker, play/pause, in/out/create), opt-in session receiver. Example action: runtime/python.exe -m streamclipper.cli deck marker. No external network service. Commands expire after 30s; busy/modal conditions prevent unwanted edits. Native Stream Deck plugin not supplied.
- #37 cuts-only CMX3600 EDL (24/25/30 NDF) and FCPXML with frame-quantized source and record times; scene ordering respected. No effects, captions, speed curves or full track interchange. VFR/source-timecode parity and actual NLE import are open.
- #41 bilingual primary controls and menu shell; specialist dialogs, error messages, full language persistence/coverage NOT complete. Feature remains open, not deferred without owner approval.
- #42 alternate GIF (<=15 seconds, no audio) and WebM (<=120 seconds, VP9/Opus) use existing RenderRequest composition and local validation; native Windows media playback/export tests pending.
- #43 watch folders: explicitly selected folder during session, 15 seconds unchanged size/mtime, user manually opens recognized files. No auto source replacement.
- Local SRT/VTT import with source time bounds and explicit replacement / undo; no fabricated words. Downloaded sidecars may be manually selected.
- Publishing preparation: QA-bound PublishAsset, fail-closed provider adapter interface; YouTube registered desktop app OAuth via system browser, loopback state/PKCE and exact upload scope, optional separate Windows Credential Manager token vault. No upload/publish/status implementation; TikTok/Instagram/Snapchat provider app approval and actual OAuth adapters remain open. Retry/idempotency provider contracts remain M19 work; no success claims. Sources: https://developers.google.com/identity/protocols/oauth2/native-app and https://developers.google.com/youtube/data/guides/authentication. yt-dlp options reference https://github.com/yt-dlp/yt-dlp/blob/master/README.md.

## Explicit remaining work / gates
- Full DE/EN localization and language preference; actual provider/auth adapter support and provider-specific retry/idempotency design; secure opt-in authenticated media import only where allowed (not implemented).
- Actual authorized YouTube/Shorts, Twitch VOD/clip and Kick VOD/clip tests, real provider metadata and redirect/cancel/resume behavior, native OBS/Stream Deck, NLE, watch-folder and channel polling. No fabricated external tests. YouTube may require a separately approved local JS runtime/EJS components; no silent installation.
- Exact-head CI, native Windows portable upgrade and dependency tests, actual 6-hour workload, independent M16/M17 quality validation, network security review. No release/merge on implementation alone.


## Second M18 pass — 26.11.2026

Prior exact M18 commit 260b4c2: all three hosted workflows PASS (CI,
Windows portable build, True portable runtime). Changes since that point:

- Download worker now runs through streamclipper.import_worker with Python
  audit restrictions on direct sockets/DNS and child executables; local
  FFmpeg/FFprobe only, curl_cffi disabled, implicit JS and remote components
  disabled. Windows audit command line parsed with CommandLineToArgvW.
  IPv6 transition ranges blocked. Local container probe restricts demuxers
  and protocols. Selected format identity must remain unchanged between
  preflight and transfer; explicit alternative audio selects video-only
  stream. Existing receipt never overwritten. This is defense in depth,
  NOT an OS sandbox. Actual provider redirects and subprocess behavior
  require external Windows/security acceptance. Modern YouTube formats
  requiring JS/EJS may fail; no automatic component install.
- DE/EN exact presentation catalog expanded across core controls, menus,
  tab/header labels and M18 prompts. Language preference under
  data/settings/language.json; no model/content translation. Original labels
  retained for reversibility, combo IDs and tab behavior independent of
  translation, caption and source labels protected. Full app/dialog/error
  coverage still INCOMPLETE. Do not label #41 fully implemented.
- TikTok desktop authorization request contract (hex SHA256 PKCE, state,
  exact registered callback, exact scope, token response parser) and
  conservative preliminary asset validation; no live token exchange and
  no embedded confidential client secret. Official token backend and
  provider approval are still required. YouTube desktop OAuth pilot remains
  as previously. Instagram and Snapchat are not connected; approved
  provider accounts/app/backend still missing. M19 upload/publish absent.
- Local operation identity and retry policy distinguish safe read-only
  checks from ambiguous writes; write operations never blindly retried.
  No claim of provider-enforced idempotency. Source references:
  https://developers.tiktok.com/docs/en/login-kit-desktop
  https://developers.tiktok.com/docs/en/oauth-get-a-user-access-token
  https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide
- scripts/validate_m18_native.py: explicit authorized test manifest runner,
  up to 12 local test entries with size caps, preflight-only option,
  redacted per-provider results. No authorized provider corpus supplied.
  Example manifest {"videos":[{"url":"<your authorized single-video URL>",
  "authorized":true,"rights":"Own recording","max_gib":1,"height":720}]}.
  Command: runtime/python.exe scripts/validate_m18_native.py cases.json
  data/imports data/bench/m18-native.json --authorized --commit EXACT_SHA.
  Actual native results remain NOT_EVALUATED.
- Tests added: actual yt-dlp CLI flags (dependency included in CI),
  direct network/child guard, TikTok state/PKCE/scope, retries, persistent
  language and offscreen Qt roundtrip. New exact-head CI still required.

Residual implementation: full DE/EN catalog coverage including dynamic
messages and specialist dialogs; approved provider auth integration and
permitted authenticated import paths; no bypass or confidential credentials
in the client. Real provider/OBS/Deck/NLE/native security and quality gates
remain. No main merge, release or M19 start.


## Third M18 pass — import recovery and remaining provider contracts

Exact prior head 116c30d: CI, Windows portable build, true portable
runtime all PASS. New implementation:
- import_publication.py journals exact validated files and hashes before
  publication. Existing media, subtitle and receipt names reserved as a
  bundle, no overwrite; conflicting bytes fail closed. Recovery after
  interruption between media and receipt publication is supported. Same
  source/format/subtitle/container request reuses the validated existing
  bundle. Staged large links removed after receipt completion. Journal
  retained for dedup; deleted or modified output requires manual conflict
  resolution rather than silent overwrite. This is recoverable multi-file
  publication, not a single atomic multi-file filesystem transaction.
- Disk monitoring continues while downloader produces no progress lines.
  Local probe now requires four actual decoded gray pixels, not just
  FFmpeg exit zero, from start and near end. Expected audio must exist;
  genuinely silent sources are permitted. GUI displays verification stage.
- Instagram Business Login and Snapchat Public Profile OAuth request,
  redirect/state/expiry and token-response contracts added. Confidential
  backend owns grants and secrets. No real registered app or live OAuth
  exchange supplied. Scope references:
  https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/
  https://developers.snap.com/marketing-api/Public-Profile-API/GetStarted
  Snapchat requires allowlisting; neither local grant nor token parsing
  proves provider access. No upload/publish implemented.
- DE/EN import preflight and dynamic progress text expanded. Full app-wide
  localization remains incomplete.
- Regression tests for interrupted receipt recovery, collision detection,
  reused imports, changed preflight, and provider grants. New exact-head
  CI still required. Real provider downloads, native integrations and
  adversarial security acceptance remain open. No M19 start.
