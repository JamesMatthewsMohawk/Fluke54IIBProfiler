# Project: Superba Tunnel Profiler (C++ rewrite reference)

## What this app does
Desktop app that connects to a **Fluke 54 II B** dual-input thermometer over
its infrared/USB adapter cable, downloads a logged temperature run, and
turns it into a time/temperature "profile" for a Superba textile tunnel
(a heat-treatment tunnel; plants pull a probe through it on a cable to
log the temperature ramp). Profiles are stored locally, chartable,
comparable, and exportable. The original was Python/PySide6/SQLite;
this document is a self-contained reference for rewriting it (e.g. in
C++) without needing the original source tree.

## Hardware / connection
- Cable: **Fluke IRUSB Rev. II**, an FTDI-based USB-to-IR adapter.
  USB VID:PID = **0403:6001**. Enumerates as a virtual COM port.
- Serial settings: **9600 baud, 8 data bits, no parity, 1 stop bit**, no
  flow control.
- The meter **only responds while its display shows "Ir SEnd"**,
  entered by pressing **SHIFT + RECALL** on the meter. It times out
  back to the normal display after a period of inactivity -- there is
  no remote command to enter this mode. In normal display mode the
  meter is completely silent on the wire.

## Wire protocol (empirically reverse-engineered; NOT vendor-documented
## beyond the bare `ID` command)
- Every command is ASCII text + a trailing `\r` (no `\n`).
- Every response is `<status>\r` followed by optional data, where
  status is the single ASCII byte `'0'` (OK) or `'1'` (error/unrecognized
  command).
- The device only inspects the **first 2 characters** of a command --
  longer command names collapse onto their 2-char prefix. Don't rely on
  full-word commands meaning what they look like.
- Response data is **not reliably terminated** for binary-payload
  commands (notably `QD`), so you must read with a "quiet period"
  cutoff (stop once no new bytes have arrived for N ms), not a fixed
  terminator or fixed length known in advance. Reference timings used:
  up to a 5-10s total window, treat the read as complete after ~1.5-2s
  of silence following at least some data.
- `ID\r` -> `0\r` + ASCII text like `FLUKE 54-II, V1.5\r` (model,
  comma, firmware version). This is the only command Fluke documents
  publicly for this meter family.
- `QD <index>\r` -> `0\r` + `QD,` + a binary payload (see below). This
  downloads a logged session. Only index values **0 and 1** have been
  characterized:
  - `QD 0` returns a **different, short, non-log response** -- treat it
    as a status/summary value, not sample data, and don't try to parse
    it as the QD binary structure below (it will fail a length check).
  - `QD 1` has, in every test so far, held the **full logged sample
    set** currently in the meter's memory (see "Multiple runs in one
    download" below -- this can include more than one logical run
    concatenated together).
  - Indices beyond that are meter-state-dependent; expect `1\r`
    (rejected) for indices with nothing stored there. Don't assume a
    fixed valid range -- probe and handle rejection gracefully.
- **Never send these commands** (all empirically or documentedly
  destructive):
  - `CD` -- undocumented; empirically observed to **clear the meter's
    logged memory** during protocol discovery. A brute-force sweep of
    2-letter commands that included this is what discovered it, the
    hard way.
  - `RI` -- documented as "Reset Instrument", a full factory reset
    (clears all logged memory and settings).
  - `DS` -- documented as a settings-reset/power-cycle equivalent.
    Empirically confirmed NOT to clear logged memory, but still treat
    as excluded from any generic/exploratory command sender as a
    precaution.
  - General rule: do not send arbitrary/undocumented commands to a
    meter that might have real customer data logged on it. Only `ID`
    and `QD <index>` are considered safe and are all this app needs.
- No working "live reading" command was found. The documented query for
  this meter family (`QM`) was tested extensively (bare, with
  arguments, after `DS`, after `ID`, with inter-character delays) and
  was rejected every time. Treat live/real-time reading as
  **unsupported** -- this app is download-only, of already-logged data.
- No "clear memory" feature is exposed by this app, deliberately (see
  dangerous commands above) -- clearing memory is left to the user,
  manually, on the meter itself.

## QD payload binary structure
Bytes immediately following the `QD,` prefix in the response data:

```
[sample_count : uint16, little-endian]
[block_0      : 8 bytes -- header/metadata block, NOT a reading]
[block_1 .. block_{sample_count-1} : 8 bytes each -- see block format]
[checksum     : 1 byte]
```

- Total payload length must equal `2 + sample_count*8 + 1` bytes exactly
  -- validate this before parsing; treat a mismatch as corrupt/incomplete
  data (most often caused by cutting the read off too early).
- Checksum = additive sum, mod 256, of every byte from block_0 onward
  (i.e. excluding the leading sample_count field and the checksum byte
  itself). Mismatch -> log a warning but the data may still be usable;
  this was never seen to actually mismatch in practice.
- **Each 8-byte block has a 2-byte type tag in its first two bytes**,
  determining how to interpret the rest:
  - Tag `FF FF` -> a real reading block:
    `FF FF <temp_raw: uint16 LE> <sequence: uint16 LE> 01 00`
    - `temp_raw` -> degrees Celsius via a **linear calibration**:
      `temperature_c = temp_raw * 0.037171 + (-274.2066)`
      (Fitted by linear regression against 6 precise manual meter
      readings taken during a rapid temperature ramp, raw values
      8154-8303 against ground truth 28.9-34.4C. Max fit error ~0.03C.
      Note the constants are close to, but deliberately not simplified
      to, `temp_raw/27 - 273.15` -- 273.15 being the C/Kelvin offset,
      suggesting temp_raw is an internal fixed-point Kelvin value, but
      the empirical fit tracked ground truth more precisely than that
      clean approximation.)
    - `sequence` increments by exactly **+1 per sample within one
      logged run**, but is NOT reliable as an absolute time base across
      runs (see below) -- don't use it to compute elapsed time; instead
      derive elapsed time from each reading's position in the sequence
      of readings you decode (`index * sample_interval_seconds`), where
      the sample interval is whatever the user configured on the meter
      (this app defaults to assuming **1.0 second** per sample and does
      not have a way to query the meter's configured interval).
  - Tag `00 00` -> a **run-boundary marker**, not a reading. Its
    remaining 6 bytes are NOT understood/decoded (empirically: the
    would-be temp_raw field is 0, which is otherwise an impossible
    temperature, and the would-be sequence field is unrelated to
    neighboring readings' sequence numbers -- consistent with this
    being a distinct record type, not reading noise). **Drop this block
    from your readings list**, but remember its position: the very
    next `FF FF` block starts a new logical run.
  - Any other tag: unrecognized -- skip it and log a warning; don't
    guess at its meaning.
- block_0 (right after the sample_count field) is always a
  header/metadata block -- **never treat it as a reading**, regardless
  of its tag.

### Multiple runs in one download
If the meter was started and stopped (logging) more than once without
a memory clear or a download in between, **all logged runs come back
concatenated in a single `QD 1` response**, separated by one `00 00`
marker block between each pair of runs. This was confirmed against a
real two-run capture (two ~60-second tunnel passes back to back): 61
readings, one marker block, 61 more readings, with the second run's
sequence numbers jumping to an unrelated base value (not a continuation
of the first run's sequence) then incrementing normally from there.

**The app must detect this and split accordingly** -- do not assume a
download is always exactly one run. Concretely: walk the decoded
blocks in order; every time you hit a `00 00` marker (with at least one
reading already collected since the last split point), that marks the
start of a new run. Build a list of split indices (starting with
`[0]`), and slice your flat readings list at those points to get one
reading-list per logical run. Each run then gets its own elapsed-time
axis (starting back at 0) and its own name/label from the user -- when
more than one run is detected, prompt the user for a name (e.g. a
tunnel identifier) for each one before saving, since they're
independent named things (e.g. "Tunnel 8" and "Tunnel 9" logged back to
back) that must not be merged into one profile.

## Application behavior to replicate

### Data model
- A **Run**: id, plant (free text), tunnel (free text), run_date
  (timestamp of when it was downloaded/created), peak_temp_c,
  min_temp_c, measurement_count, source_unit ('C' or 'F' -- records
  what the meter's *display* was set to at log time, purely for the
  user's own reference; it does NOT affect how temp_raw is decoded,
  which is always the same Celsius calibration regardless).
- A **Measurement**: belongs to a run; elapsed_time_s (float, computed
  as `index * sample_interval_s`), temperature_c (float, always stored
  in Celsius; Fahrenheit is only ever a display-time conversion,
  `f = c * 9/5 + 32`).
- Storage: originally SQLite, two tables (`runs`, `measurements`, with
  a foreign key + index on `measurements.run_id`). Reasonable to keep
  as-is for a C++ rewrite (SQLite has a solid C API).

### Core workflows
1. **Download**: user enters Plant + Tunnel (free text) and which unit
   the meter's display was showing, connects the meter in "Ir SEnd"
   mode, clicks Download. App connects (`ID` to verify, then `QD 1`),
   parses, splits into 1+ runs as above, prompts for a name per run if
   more than one, and saves each as a new Run + its Measurements.
2. **Chart**: overlay multiple runs (elapsed_time_s on X, temperature
   on Y, one color per run) to compare them. Because each run's start
   time is set by hand on the meter, overlaid runs often don't align --
   support **dragging a plotted curve left/right** to apply a
   time-offset per run (visual only, doesn't mutate stored data; goes
   into any "export what's currently plotted" feature so an export
   reflects the alignment) and double-click to reset a curve's offset
   to zero. Y axis is a fixed range per unit (not autoscaled) so
   comparing looks consistent (used 0-195C / 0-390F).
3. **Hovering the chart**: show a marker on every plotted curve at the
   moused-over time (interpolated between that curve's own two nearest
   samples, not just the nearest single point) plus each curve's live
   temperature value and the shared time value in a legend/readout --
   there's no single meaningful "the" temperature at a mouse position
   once more than one run is overlaid, so avoid a single crosshair
   value tied only to raw mouse Y position.
4. **Database/search**: list/search all stored runs by plant/tunnel
   (partial text) and date range; export a run's data to CSV; print/
   export a one-page report (stats + graph image).
5. **Settings**: toggle global display unit C/F (affects graph, lists,
   exports -- never affects what's stored, only presentation).

### Licensing (optional to carry over, described for completeness)
The original added a **soft license gate** on meter downloads only (not
on viewing/exporting existing data): an offline, machine-locked,
Ed25519-signed key, generated by a small separate offline tool (never
shipped with the main app) using a private signing key that never
leaves the issuer's machine. The main app embeds only the Ed25519
**public** key and verifies a pasted key locally (signature over the
target machine's stable OS-provided machine GUID) -- no network call,
no server. This is explicitly a soft gate (deters casual copying, not a
defense against a determined reverse-engineer) and is worth noting as a
design choice, not a security boundary.

## Known open questions / do not assume
- Whether the meter's C/F display setting at log time affects the raw
  logged values in any way is **unconfirmed** -- currently assumed not
  to (the same calibration is applied regardless), but this is why
  `source_unit` is stored per run even though it's not used in the
  decode math.
- QD indices beyond 0 and 1 are unexplored beyond "some are rejected."
- The run-boundary marker format is reverse-engineered from **one**
  real two-run capture, not from vendor documentation -- solid enough
  to build against, but if you ever see 3+ concatenated runs or a
  different firmware version, re-verify before trusting it blindly.
- No live-measurement command works on this meter (see above) --
  don't spend time trying to add a "live view" feature via the meter
  protocol itself.
