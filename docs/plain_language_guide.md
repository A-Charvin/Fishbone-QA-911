# Plain Language Guide - Fishbone-QA-911

## What Is This Tool For?

When maintaining a 911 address database, two of the most important datasets are **civic address points** (where a building or property is located) and **road segments** (the streets those addresses belong to). These two datasets need to agree with each other - a house at 145 Main Street should actually sit beside the stretch of Main Street that covers house numbers in the 100–200 range, **and it should be on the correct side of the street** (odd or even).

In reality, data entry errors, outdated road ranges, mismatched street names, and addresses placed on the wrong side of the street mean these two datasets often disagree. This tool finds those disagreements automatically and visualizes them so a GIS analyst can quickly identify and fix the problems.

## The Core Concept - What Are We Actually Checking?

Every road segment in a 911 database carries address range information. For example, a segment of Main Street might say:

- Left side: house numbers 100 to 200 (even addresses only)
- Right side: house numbers 101 to 199 (odd addresses only)

This tells us two important things:

1. **Range**: Any civic address on Main Street should have a number between 100 and 200
2. **Parity (odd/even)**: Even addresses (100, 102, 104...) belong on the left side, odd addresses (101, 103, 105...) belong on the right side

The tool checks both of these rules. If a point says it is 450 Main Street but no segment of Main Street covers that range, something is wrong. Similarly, if address 102 (even) is placed on the right side where only odd addresses belong, that's also wrong and needs fixing.

## Why "Fishbone"?

The visualization draws a line from each civic address point to the road segment it belongs to. When you zoom out and look at a whole street, all those little lines branching off the road look like the bones of a fish - hence the name. It is a well-established GIS quality assurance technique for visually auditing address data.

## How the Logic Works - Step by Step

### 1. Start with the Civic Point
Each civic point has two key pieces of information: a **street name** (e.g. `MAIN ST`) and a **street number** (e.g. `145`). These are the two things we need to verify.

### 2. Find Candidate Road Segments
The tool looks through all road segments and pulls out every segment whose name matches the civic point's street name. So for `145 MAIN ST`, it finds every segment of Main Street in the database. These are the **candidates**.

Street names are converted to uppercase and trimmed of extra spaces on both sides before comparing - this prevents mismatches caused purely by formatting differences like `Main St` vs `MAIN ST`.

### 3. Check the Address Ranges
For each candidate segment, the tool checks whether the civic number (145) falls within that segment's address ranges. Road segments store ranges for both the left and right side of the street, so the tool checks both.

**Example:**
```
Segment 1 of Main St:
  Left: 100-200
  Right: 101-199

Address 145:
  100 <= 145 <= 200? YES (left side contains it)
  101 <= 145 <= 199? YES (right side contains it)
```

So address 145 is numerically within BOTH ranges. Now the tool needs to decide which side is correct.

### 4. Parity-Based Matching (Updated)

This is where the enhanced version differs from the original. Instead of just picking whichever side is closest, the tool checks the **odd/even pattern**:

**Step 4a - Determine Parity:**
- Address 145 is an ODD number
- Left range 100-200: starts at 100 (even), ends at 200 (even) → EVEN parity
- Right range 101-199: starts at 101 (odd), ends at 199 (odd) → ODD parity

**Step 4b - Match by Parity:**
- Address is ODD, right range is ODD → **MATCH!**
- The tool selects the RIGHT range because the parity matches

**Step 4c - Validate:**
- Address parity: ODD
- Range parity: ODD
- ParityMatch: MATCH ✓

This ensures addresses automatically go to their correct odd/even side, which is how most addressing systems work.

### 5. Pick the Best Match (When Multiple Segments Qualify)

Sometimes more than one segment of the same street will have the correct parity range. When that happens, the tool picks whichever matching segment is **physically closest** to the civic point using straight-line distance. This is the most reliable tiebreaker.

### 6. Record the Result
The tool writes several pieces of information back to the civic point copy:

- **MatchedSegmentOID** - the database ID of the road segment it was matched to
- **RangeStatus** - whether the match was successful
- **MatchedSide** - which side it matched to (LEFT or RIGHT)
- **AddressParity** - whether the address is EVEN or ODD
- **RangeParity** - whether the matched range is EVEN, ODD, or MIXED
- **ParityMatch** - whether the parity is correct (MATCH or MISMATCH)

There are three possible outcomes for every civic point:

| Result | What It Means |
|---|---|
| `WithinRange` | The civic number falls within a matching road segment's range |
| `OutOfRange` | The street name was found but no segment's range covers this number |
| `NoData` | The civic point is missing a street name or number entirely |

And for parity validation:

| Parity Result | What It Means |
|---|---|
| `MATCH` | Address parity matches range parity (even with even, odd with odd) |
| `MISMATCH` | Address parity doesn't match - address may be on wrong side or range data is incorrect |
| `UNKNOWN` | Parity couldn't be determined (missing data) |

## Understanding Odd/Even Parity

In most addressing systems:
- **Even addresses** (100, 102, 104, 106...) are on one side of the street
- **Odd addresses** (101, 103, 105, 107...) are on the other side

This is called the **parity** of an address. The tool checks this automatically:

**How parity is determined:**

For a **single address:**
- 124 ÷ 2 = 62 with no remainder → EVEN
- 125 ÷ 2 = 62 with remainder 1 → ODD

For a **range:**
- Range 100-200: both endpoints are even → EVEN parity (only even addresses)
- Range 101-199: both endpoints are odd → ODD parity (only odd addresses)
- Range 100-199: endpoints differ → MIXED parity (contains both odd and even)

**MIXED ranges** accept any address since they contain both odd and even numbers. These sometimes occur on short streets or cul-de-sacs.

## What Gets Created

### Civic_QA_Result
A copy of your input civic layer with extra QA fields. Your original civic layer is never touched. This copy is your primary reference for understanding which points matched and which did not.

**Key fields:**
- `RangeStatus` - WithinRange, OutOfRange, or NoData
- `MatchedSide` - LEFT or RIGHT
- `AddressParity` - EVEN or ODD
- `RangeParity` - EVEN, ODD, or MIXED
- `ParityMatch` - MATCH or MISMATCH

### Fishbone_Lines
For every civic point flagged `WithinRange`, the tool draws a line from the civic point to the nearest point on its matched road segment. Each line carries the road name, civic number, the address range (with parity shown), and parity match status.

**Example MatchedRange value:** `L:100-200 (EVEN) R:101-199 (ODD)`

This tells you immediately what the odd/even pattern should be on each side.

### Fishbone_OutOfRange
For every civic point flagged `OutOfRange` or `NoData`, the tool copies that point into this separate feature class. These points have no valid road segment to connect to. In ArcGIS Pro you can symbolize these with a bold circle marker to make them stand out.

### Road_QA_Issues (NEW)
The tool also validates the road segment data itself and creates this layer when problems are found:

**Common issues:**
- "Left range: From and To addresses are identical" → Range needs updating
- "Left range parity: Mixed parity range: 100 (EVEN) to 199 (ODD)" → Range should probably be 100-200 or 100-198
- "Right range: Unusually large range gap: 10000" → Possible data entry error

These issues should be fixed in your road data before re-running the civic QA.

## How to Read the Map

A healthy street looks like a fish skeleton - the road runs down the middle and short lines branch off it at regular intervals. The lines should be short and roughly consistent in length, and when parity validation is enabled, all lines should show `ParityMatch: MATCH`.

**Warning signs to look for:**

- **Red fishbone lines (ParityMatch: MISMATCH)** - the address is in a range with wrong parity, meaning either the civic point or road range has an error
- **Long fishbone lines** - the civic point is far from its matched segment, suggesting it may be snapped to the wrong street entirely or placed on the wrong side
- **Points in Fishbone_OutOfRange** - the address number does not exist in any road range, meaning either the civic number is wrong or the road ranges need updating
- **Clusters of OutOfRange points on one street** - the road ranges for that segment are likely out of date or were never entered correctly
- **Lines crossing other streets** - the civic point may be matched to the wrong segment, possibly due to a duplicate street name in the database
- **Features in Road_QA_Issues** - road segment ranges have data quality problems that need fixing

## Interpreting Parity Results

### Scenario 1: All Clear
```
Address 102 (EVEN)
Matched to: Left range 100-200 (EVEN)
ParityMatch: MATCH ✓

This is perfect - even address in even range.
```

### Scenario 2: Parity Mismatch
```
Address 102 (EVEN)
Matched to: Right range 101-199 (ODD)
ParityMatch: MISMATCH ✗

Problem! Even address is in odd-only range.
Actions to check:
  1. Is the civic point on the wrong side of the street?
  2. Is the address number wrong (should it be 101 or 103)?
  3. Are the road ranges incorrect?
```

### Scenario 3: Mixed Range (No Error)
```
Address 102 (EVEN)
Matched to: Left range 100-199 (MIXED)
ParityMatch: MATCH ✓

Mixed ranges accept any parity, so this is okay.
However, check Road_QA_Issues - the range might
still need updating to follow proper odd/even pattern.
```

## What This Tool Does Not Fix

This tool is purely a **diagnostic** - it finds and visualizes problems but does not automatically correct them. Once you identify issues, the fixes need to be made manually:

- Wrong civic numbers need to be corrected in the source civic layer
- Civic points on wrong side of street need to be moved
- Missing or incorrect road ranges need to be updated in the source road layer
- Road ranges with wrong parity patterns need to be corrected
- Street name mismatches such as abbreviations or spelling differences need to be standardized before re-running

After making corrections, simply re-run the tool - it cleans up and rebuilds all outputs from scratch each time.

## Common QA Workflows

### Workflow 1: Find Addresses on Wrong Side
1. Run tool with parity validation enabled (default)
2. Open `Fishbone_Lines` layer
3. Symbolize by `ParityMatch` field:
   - Green = MATCH (correct)
   - Red = MISMATCH (needs review)
4. Review each MISMATCH case:
   - Check aerial imagery to see actual building location
   - Move civic point to correct side if misplaced
   - Or update road ranges if they're incorrect
5. Re-run tool to verify fixes

### Workflow 2: Fix Road Range Problems
1. Open `Road_QA_Issues` layer (if created)
2. Review issues by type:
   - Identical from/to values → Update ranges
   - Mixed parity ranges → Adjust endpoints to match odd/even pattern
   - Unusually large gaps → Verify and correct
3. Update road segment data
4. Re-run tool to confirm fixes

### Workflow 3: Update Out-of-Range Addresses
1. Open `Fishbone_OutOfRange` layer
2. Sort by `StreetName` to group by street
3. For each street with multiple out-of-range points:
   - Check if road ranges need extending
   - Or if civic addresses have typos
4. Make corrections in source data
5. Re-run tool

## Re-running the Tool

The tool is fully safe to re-run at any time. All output feature classes are deleted and rebuilt from scratch on every run, and `Civic_QA_Result` is re-copied from your original input. You will always be looking at results that reflect the current state of your data.

## Settings and Options

### Parity Validation (Recommended: ON)
**When to use:** If your addressing system uses odd/even sides (most do)
**When to disable:** If addresses are numbered sequentially (1,2,3,4...) regardless of side

With parity validation ON:
- Addresses automatically match to correct odd/even side
- Parity mismatches are flagged
- Road range parity is validated

With parity validation OFF:
- Simple distance-based matching only
- No parity fields in output
- Works like original version

## Known Limitations

- **Name matching is exact** after normalization - abbreviation differences such as `ST` vs `STREET` will cause missed matches. Pre-normalize your street names before running for best results.
- **Address ranges stored as text** are converted to numbers at runtime. Non-numeric values such as empty strings or placeholder text are safely handled and treated as absent.
- **Civic points without geometry** are skipped silently and will not appear in either output.
- **Parity validation assumes standard addressing** - if your jurisdiction doesn't use odd/even sides, disable this feature.
- **Mixed parity ranges** (e.g., 100-199) will accept any address and may mask data quality issues - check `Road_QA_Issues` for these.

## Understanding the Statistics Output

When the tool runs, it displays statistics like this:

```
MATCHING STATISTICS:
  Total civic points: 10000
  Within range: 9500
  Out of range: 450
  No data: 50
  Parity mismatches (odd/even): 15
```

**What these mean:**
- **Total civic points:** Everything that was processed
- **Within range:** Found a matching road segment (good!)
- **Out of range:** No valid range found (needs fixing)
- **No data:** Missing street name or number (data error)
- **Parity mismatches:** Even/odd is wrong (review these)

**Rule of thumb:**
- 0-2% parity mismatches: Normal (corner lots, exceptions)
- 3-10%: Some issues to investigate
- >10%: Systematic data problem - check road ranges

## Troubleshooting

**Q: All addresses on one side are showing MISMATCH**
A: Make sure you're using the LATEST version with parity-preference matching. Older versions had this bug.

**Q: I see Road_QA_Issues with "mixed parity" warnings**
A: Your road ranges may need updating. A range of 100-199 contains both even (100) and odd (199). Consider changing to 100-200 (all even) or adjusting the endpoint.

**Q: ParityMatch shows MATCH but the fishbone line is very long**
A: The parity is correct, but the point may still be geometrically displaced. Check if it should be moved closer to the road or if it's a legitimate rear address.

## Version History

**v2.0 - Enhanced (Current)**
- Added parity-preference matching (matches to correct odd/even side first)
- Added address parity validation
- Added road range quality validation
- Added Road_QA_Issues output layer
- Enhanced statistics and reporting

**v1.0 - Original**
- Basic range matching
- Distance-based selection only
- No parity validation
