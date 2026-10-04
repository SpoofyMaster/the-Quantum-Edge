# Video transcript analysis — timestamped strategy map

**Video (primary source, "V"):** "I Made $1.4M Trading Gold, Here's What Actually Works" — channel *tomtrades*
(@itstomtrades), <https://www.youtube.com/watch?v=xSVlVpXLuV0>. Uploaded 2026-03-31, 11:40 long.
YouTube chapters: 00:00 Introduction to correlation · 00:38 Gold and dollar relationship · 01:41 Defining the
strategy · 02:29 Applying entry model inversion · 03:31 Analyzing trade examples · 06:00 Live market application ·
08:49 Validation and final tips.

## 1. What could and could not be accessed (honest provenance)

| Item | Status | How |
|---|---|---|
| Metadata, description, chapters | **Accessed** | YouTube oEmbed + `yt-dlp --skip-download --write-info-json` (client `web_embedded`) |
| Full English transcript | **Accessed** (YouTube auto-generated captions, `en` and `en-orig`, 186 caption events, 00:00–11:40) | `yt-dlp --write-auto-subs --sub-format json3 --extractor-args youtube:player_client=web_embedded` |
| Video frames | **Partially accessed**: the official YouTube storyboard, 141 frames at **320×180**, one every **≈4.96 s** | `yt-dlp -f sb0` (client `web_safari`), sheets fetched from `i.ytimg.com` |
| Video stream (360p–1080p) | **Not accessible**: YouTube answered "Sign in to confirm you're not a bot" / HTTP 403 on the media URLs from this sandbox's IP | — |

Consequences, stated once and applied everywhere below:
- Every **verbal rule** in the video was read in full (the captions cover the whole 11:40).
- The **frames are good enough to see shapes** (candle boxes, drawings, position boxes, which pane goes up or down) and
  to read the two rule slides. They are **not good enough to read prices, times on the axis, or the symbol header**.
  No price level in this project is claimed to come from the video.
- Caption text is machine-generated; wording errors are possible (e.g. "Alli candle" = "hourly candle",
  "50-minute" = "15-minute"). Quotes below are short and corrected only where the meaning is unambiguous.

Supplementary sources by the **same author** were used **only to define the author's own terms** that the video uses
without defining ("type three shift", "middle time frame range", "trending range", "overextend", AOI). They are listed
in [`supplementary_sources.md`](supplementary_sources.md) with IDs S1–S9. A rule taken from them is always labelled
with its S-ID; a rule labelled **V mm:ss** comes from the target video itself.

## 2. Timestamped map (V)

Legend for "Role": CTX = context/bias, LOC = location (where), TRG = trigger (how price must arrive), ENT = entry model,
CORR = DXY correlation filter, SL / TP / MGMT, INV = invalidation, META = claims, motivation.
"Mandatory?" = M (stated as required), P (preferred / "ideally"), I (illustrative only).

### 00:00–00:38 — Introduction to correlation (META)
- Author claims 6+ years trading gold, >$1.4M profit, first 2.5 years failing.
- Shows his journal (frame `intro_01_author_journal_dashboard.jpg`, ≈00:05): Net P&L $1,541,580.36, trade win 78.19%,
  avg win/loss 2.12, profit factor 7.59, calendar March 2026. **Status: PUBLISHED-by-author, unverifiable.**
- Claim: average win rate 64% over 400+ trades → 82% "if I just add in this one concept of correlation" (00:20).
  **Unverifiable author claim; not used as evidence of edge.**

### 00:38–01:36 — Gold and dollar relationship (CTX / CORR rationale)
| Statement (short) | Role | Mandatory? | Notes |
|---|---|---|---|
| XAU/USD (forex) or GC (futures) = price of gold *relative to the dollar* (00:38) | CTX | — | Defines the instrument: XAUUSD, GC. |
| If gold strength and dollar strength both rise they "balance out" → "low volume rangy price action" (00:57) | CTX/INV | — | Motivates avoiding periods with no strength mismatch. |
| Big moves need a **mismatch** between dollar strength and gold strength (01:15) | CTX | P | Buys: gold very bullish **and** dollar very bearish; sells: gold weak **or** dollar strong. |
| "avoid any times where they're … around the same sort of strength" (01:15) | INV | P | Not quantified in V. Visual: the "XAUUSD Balance" indicator (frames `intro_02..04`) shows a gold-strength bar, a DXY-strength bar and a state *Neutral / Leaning Bull / Bullish / Bearish*. |

### 01:36–02:00 — Defining the strategy (core rules) — **highest-value section**
Spoken (01:36): "my main setup is a reversal … identify a **middle time frame range**, wait for price to **overextend for
around 20 minutes into the high or low of that range**, and then look to **enter around the 30-minute mark on a market
structure shift** targeting **50% of the overextension**." Then: "We have the extension, I look for my entry, and then I
trade the correction."

On-screen slide **"My Setup — The reversal setup"** (frame `rules_01_slide_my_setup_reversal.jpg`, ≈01:49; read at
320×180, consistent with the speech):
1. Identify the middle timeframe range
2. Wait for the **hourly candle** to open and overextend into the high or low of that range
3. Around the 30-minute mark, wait for a low timeframe shift in the opposite direction
4. Enter on that shift, stop behind the most recent high or low, target 50% of the previous move

| Rule | Role | Mandatory? | TF | Sequence |
|---|---|---|---|---|
| A middle-timeframe **range** must exist | CTX | M | MTF (undefined in V → S1/S4/S6: past 4–5 h) | 1st, before the candle opens |
| The **hourly** candle opens and **overextends ~20 min** into the range **high or low** | TRG/LOC | M | H1 candle, observed on M1 | 2nd |
| Around **minute 30** of the hour, a **LTF shift opposite** to the extension | ENT | M | M1 | 3rd |
| **Enter on that shift** | ENT | M | M1 | 4th |
| **Stop behind the most recent high/low** | SL | M | M1 | at entry |
| **Target 50% of the previous move / of the overextension** | TP | M | extension leg | at entry |
| The trade is a **reversal** ("I am a reversal trader") | CTX | M | — | — |

### 02:00–02:59 — Applying entry model inversion (CORR) — **the subject of the video**
| Statement (short) | Role | Mandatory? | Notes |
|---|---|---|---|
| "look for the exact same thing on the dollar, on DXY. But … the opposite … an **inversion of my entry model**" (02:00) | CORR | M | Same checklist on DXY, mirrored. |
| "if I'm looking for a **bearish type three shift** on gold, on the dollar … a **bullish type three shift**" (02:00) | CORR/ENT | M | First use of the undefined term *type three shift* (→ S4 05:32: "a break of a low into a break of a high"). |
| "a reflection of price on the correlated pair" (02:21) | CORR | M | Visual: slide `rules_03`, sketch `rules_04` (gold zig-zag vs mirrored DXY zig-zag). |
| Question before every trade: "would I enter exactly where this [DXY] pair currently is right now? … condition? direction? entry model? **If the answer is no or it's unclear, I just don't take a trade**" (02:21–02:40) | CORR/INV | **M** | Hard gate. Slide `rules_02_slide_how_correlation_fits` (≈02:09): "Open DXY and run the exact same checklist · Looking for a bearish reversal on gold = looking for a bullish reversal on DXY · Same setup, opposite direction · One question: would I take this trade on DXY right now? · Yes = enter. No = wait." |
| Buy on gold in a "bullish trending range": gold overextends into the **range low**; DXY must overextend into its **range high** (02:40) | LOC/CORR | M | |
| Then "a market structure shift on gold. And **ideally** … the same thing on DXY" (02:59) | ENT/CORR | P | "Ideally": the DXY shift is preferred; see AMBIGUITIES A-09. |
| Target "50% of this overextension" on both (02:59) | TP | M | |

### 02:59–03:20 — Trade example 1 (illustrative, continuation-type) → `VIDEO_TRADE_DATABASE.md` T-01
"previous bullish move … The candle opened, immediately overextended into 50% of the previous move, had a little bit of a
shift here for a continuation." DXY: "overall bearish, had the candle open, immediately pushed bullish … came into 50% of
the previous move, had a bit of a shift, and then pushed bearish." Frames `setup_01_*`.
**Rule learned:** the "reversal" is a reversal of the *candle's* overextension. In a trending range it can be *with* the
MTF direction (gold pulls back into the lower half of the previous bullish move, then shifts up). LOC = 50% of the previous
move. **[TRG, LOC, ENT, CORR]**

### 03:20–04:25 — Trade example 2 (taken, win) → T-02
"reversal within this little lower time frame range … the new candle open and immediately driven bullish … extend into the
high of this range, take out the previous high, … looking for a correction into 50% of this overextension." DXY: "open here
and immediately drive bearish … below the lower half of the range." Entry (04:04): "coming into around the **halfway point
of this candle** … a little bit of a **1-minute break of a low** … **stop above this high, target 50%** … low time frame
correction." Outcome: "corrects back into 50% of this previous move." Frames `setup_02_*` (gold pane up / DXY pane down,
short position box at the spike top, risk ≈ reward).
**Rules:** candle here is a **15-minute** candle (04:25 calls the next one "this next 15-minute candle") → the model is
used on M15 candles too (AMBIGUITY A-07). Entry is **on the break** of a 1-min low (A-01). Stop **above the high** = the
extension extreme. TP = 50% of the overextension.

### 04:25–05:52 — Trade example 3 (counter-example, **loss**) and the ideal picture → T-03
"this next 15-minute candle where we are overextending again into the upper half or the high of this range … a bit of a
shift [on 1-min] … we could potentially look for a sell." DXY (05:08): "**DXY has opened and has been pushing bullish** with
gold also being in the highs … **There's no inversion of the entry model here.** … What I'd want to see is DXY to open and
immediately drive bearish, overextend into the lower half, and then look for a buy on DXY." Outcome: "**This trade goes and
hits our stop loss.**"
Restated rule (05:29–05:52): "if I'm looking for a sell on gold, I want [gold] to open, immediately drive bullish, have …
a reaction **around the halfway point of the 15-minute candle** to then take a sell back in towards 50% of the move. On
DXY, … open, immediately overextend bearish, then have a bit of a shift around the halfway point … **If it's opened and gone
in the same direction, I'm not looking to take a trade.**"
**Rules:** INV-DXY-SAME-DIRECTION (**mandatory**, HIGH confidence); DXY must overextend into the **opposite half**; DXY
shift at the halfway point of the same candle (preferred). Frames `setup_03_*`.

### 05:52–08:00 — Live trade "Monday" (taken, win) → T-04
Gold "very overall bearish … a pullback in towards 50% of the previous bearish move. Had a bit of a shift here … taken out
this previous high into then taking out this low. And I was looking for a pullback into 50% of the shift … **with some nice
15-minute candle behavior** … waited for the 15-minute candle to open and immediately drove bullish into 50% of this previous
move." DXY (06:35): "opened and … immediately driven bearish into the lower half of this previous bullish move … a little
low time frame bullish trending range that we come into on the low … that's … the inversion of the candle behavior." HTF
(06:53): "DXY is also overall quite bullish … lower half of this previous middle time frame push … starting to push
bullish again" → "I can use correlation not just for an entry model, but also on middle/high time frame confluence."
Entry (07:15–07:37): "wait for a **shift within the shift** … we'd broken this low. So can look for an **entry on the break
of this low** … **stop above the high** … I think I just **targeted or exited out around these previous lows**." Frames
`setup_04_*` (MTF box with the 50% zone; short box with reward ≈ 1.7× risk; LTF detail; live recording with
"Profit 700.00").
**Rules:** fractal use (MTF type-3 shift → pullback into 50% → LTF shift → entry on break). The target here was
*discretionary* (previous lows) rather than 50% of the extension (AMBIGUITY A-12).

### 08:00–08:42 — Counter-example (not taken; avoided a fake-out) → T-05
"this nice extension, this push higher on gold … looking for a bit of a sell … DXY … **we've actually been pushing bullish**.
So it's pretty low volume. Ideally we'd want it to be doing the opposite … a massive push bearish … we're even at the highs
of this little bullish trending range." Outcome: "It just continues pushing higher. And so using correlation allows me to
**avoid fakeouts**." Frames `setup_05_*`.
**Rule:** INV-DXY-SAME-DIRECTION again (DXY rising while gold rises → no sell).

### 08:42–09:02 — Indicator vs. plain DXY chart (META)
"if you want access to this indicator … You also don't have to use an indicator. You can also use another chart like DXY
which tracks a dollar index." → **The DXY chart alone is sufficient**; the gold-strength gauge is optional.

### 09:02–10:46 — Live trade "Wednesday" (taken, win) → T-06
"the **hourly candle open** and then immediately drove bearish, overextended into the **lower half of this bearish
trending range**, I was looking for … a correction back in towards 50% of this extension **around the second half of the
hour**." DXY: "wanting the dollar to open and overextend push bullish. **It was a little bit low volume … not exactly what I
want to see, but it still was pushing in the opposite direction, which is nice.**" Zoomed DXY (09:42): "DXY has had a bit of
a shift bearish … taken out this high into then taking out this low … pulled back into 50% of this breaking move. So if I'm
looking for a buy on gold and I have a **bearish type three setup on DXY**, that's actually a positive indicator."
Entry (10:06): "gold take out this low into taking out this high into a bit of a pullback. So, I had an entry here on the
one-minute time frame … I'd put my **stop below this low** … just targeting a **little one-to-one trade into 50%**." Outcome:
"played out pretty nicely, went a little bit further." Frames `setup_06_*` (hourly box; DXY drive up then shift down; long
box with reward ≈ risk).
**Rules:** H1 candle (consistent with the slide); DXY extension quality may be **weaker** ("low volume") as long as the
direction is opposite (A-09); the DXY opposite type-3 shift is a **positive** indicator; entry after "a bit of a pullback"
(A-01).

### 10:46–11:40 — Validation and final tips
"whenever I'm looking to take a trade on gold, I'm always thinking, would I take the opposite trade at the same time at the
same area on DXY? … If yes, then okay … I can take the buy on gold." Purpose: "avoid being faked out or entering too early or
too late … timing the entry using some DXY correlation." Remainder is promotion (free course, indicator).

## 3. Phrase index (algorithmically important wording)

| Phrase type | Where | Content |
|---|---|---|
| "I wait for" | 01:36 | wait for ~20 min overextension into range high/low |
| "around the 30-minute mark" / "halfway point" | 01:36, 04:04, 05:29, 09:21 | shift timing = middle of the candle |
| "I just don't take a trade" | 02:21–02:40 | DXY answer "no or unclear" ⇒ no trade |
| "I'm not looking to take a trade" | 05:52 | DXY "opened and gone in the same direction" ⇒ no trade |
| "this is where my stop goes" | 04:04, 07:37, 10:27 | stop above the high (sell) / below the low (buy) |
| "my target" | 01:36, 02:59, 04:04, 10:27 | 50% of the overextension; once "previous lows" (07:37) |
| "ideally" | 01:15, 02:59, 05:08, 08:22 | strength mismatch; DXY shift; DXY opposite push — preferences, not hard rules |
| "always" | 10:46 | always ask the DXY question before a gold trade |

## 4. Contradictions and tensions found inside V (investigated in AMBIGUITIES.md)
1. **Entry on the break vs. after a pullback** — 04:04 and 07:37 enter "on the break"; 10:06 enters after "a bit of a
   pullback"; the slide says "enter on that shift". (A-01)
2. **Hourly vs. 15-minute candle** — slide and Wednesday trade use the hourly candle; examples 2–3 and the Monday trade use
   15-minute candle behavior. (A-07)
3. **Target** — 50% of the overextension (slide, examples) vs. "previous lows" (Monday) vs. "one-to-one" (Wednesday; there
   the 50% level and 1R coincided). (A-12)
4. **How strict the DXY mirror must be** — "exact same checklist" (slide) vs. accepting a "low volume … not exactly what I
   want" DXY push (Wednesday). (A-09)
5. **Range vs. trend context** — the slide demands a *range*; examples 1 and 4 are pullbacks inside *trending ranges*. The
   author's course (S2 218:28–225:14) resolves this: a *trending range* (50–75% pullbacks) is a kind of range and is
   tradable; only a *trend* (<50% pullbacks) is excluded. Not a contradiction once the term is defined.
