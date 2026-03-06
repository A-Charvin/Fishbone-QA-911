# Plain Language Guide - Fishbone-QA-911

## What Is This Tool For?

When maintaining a 911 address database, two of the most important datasets are **civic address points** (where a building or property is located) and **road segments** (the streets those addresses belong to). These two datasets need to agree with each other - a house at 145 Main Street should actually sit beside the stretch of Main Street that covers house numbers in the 100–200 range.

In reality, data entry errors, outdated road ranges, and mismatched street names mean these two datasets often disagree. This tool finds those disagreements automatically and visualizes them so a GIS analyst can quickly identify and fix the problems.


## The Core Concept - What Are We Actually Checking?

Every road segment in a 911 database carries address range information. For example, a segment of Main Street might say:

- Left side: house numbers 100 to 198
- Right side: house numbers 101 to 199

This tells us that any civic address point claiming to be on Main Street should have a number somewhere between 100 and 199. If a point says it is 450 Main Street but no segment of Main Street covers that range, something is wrong - either the civic number is incorrect, the road ranges are outdated, or the street name is mismatched.

This tool checks every single civic point against its road segments and flags anything that does not add up.


## Why "Fishbone"?

The visualization draws a line from each civic address point to the road segment it belongs to. When you zoom out and look at a whole street, all those little lines branching off the road look like the bones of a fish - hence the name. It is a well-established GIS quality assurance technique for visually auditing address data.


## How the Logic Works - Step by Step

### 1. Start with the Civic Point
Each civic point has two key pieces of information: a **street name** (e.g. `MAIN ST`) and a **street number** (e.g. `145`). These are the two things we need to verify.

### 2. Find Candidate Road Segments
The tool looks through all road segments and pulls out every segment whose name matches the civic point's street name. So for `145 MAIN ST`, it finds every segment of Main Street in the database. These are the **candidates**.

Street names are converted to uppercase and trimmed of extra spaces on both sides before comparing - this prevents mismatches caused purely by formatting differences like `Main St` vs `MAIN ST`.

### 3. Check the Address Ranges
For each candidate segment, the tool checks whether the civic number (145) falls within that segment's address ranges. Road segments store ranges for both the left and right side of the street, so the tool checks both. If 145 falls within either side's range, that segment is considered a **match**.

The check uses min and max guards - this means even if a range is stored backwards (e.g. 200 to 100 instead of 100 to 200), the tool still catches it correctly.

### 4. Pick the Best Match
Sometimes more than one segment of the same street will cover the same range. When that happens, the tool picks whichever matching segment is **physically closest** to the civic point using straight-line distance. This is the most reliable tiebreaker because the civic point should geographically sit beside its correct segment.

### 5. Record the Result
The tool writes two things back to the civic point copy:
- **MatchedSegmentOID** - the database ID of the road segment it was matched to
- **RangeStatus** - a flag saying whether the match was successful

There are three possible outcomes for every civic point:

| Result | What It Means |
|---|---|
| `WithinRange` | The civic number falls within a matching road segment's range. All good. |
| `OutOfRange` | The street name was found but no segment's range covers this number. Problem. |
| `NoData` | The civic point is missing a street name or number entirely. Problem. |

## What Gets Created

### Civic_QA_Result
A copy of your input civic layer with two extra fields - `MatchedSegmentOID` and `RangeStatus`. Your original civic layer is never touched. This copy is your primary reference for understanding which points matched and which did not.

### Fishbone_Lines
For every civic point flagged `WithinRange`, the tool draws a line from the civic point to the nearest point on its matched road segment. Each line carries the road name, civic number, and the address range of the matched segment. This lets you visually confirm that addresses are sitting in sensible positions relative to their road, and the attributes give you full context without having to click on individual features.

### Fishbone_OutOfRange
For every civic point flagged `OutOfRange` or `NoData`, the tool copies that point into this separate feature class. These points have no valid road segment to connect to, which is why they live separately from the lines - there is nothing to draw a line to. In ArcGIS Pro you can symbolize these with a bold circle marker to make them stand out from the `Fishbone_Lines` layer when viewing both together.

## How to Read the Map

A healthy street looks like a fish skeleton - the road runs down the middle and short lines branch off it at regular intervals. The lines should be short and roughly consistent in length.

**Warning signs to look for:**

- **Long fishbone lines** - the civic point is far from its matched segment, suggesting it may be snapped to the wrong street entirely
- **Points in Fishbone_OutOfRange** - the address number does not exist in any road range, meaning either the civic number is wrong or the road ranges need updating
- **Clusters of OutOfRange points on one street** - the road ranges for that segment are likely out of date or were never entered correctly
- **Lines crossing other streets** - the civic point may be matched to the wrong segment, possibly due to a duplicate street name in the database

## What This Tool Does Not Fix

This tool is purely a **diagnostic** - it finds and visualizes problems but does not automatically correct them. Once you identify issues, the fixes need to be made manually:

- Wrong civic numbers need to be corrected in the source civic layer
- Missing or incorrect road ranges need to be updated in the source road layer
- Street name mismatches such as abbreviations or spelling differences need to be standardized before re-running

After making corrections, simply re-run the tool - it cleans up and rebuilds all outputs from scratch each time.

## Re-running the Tool

The tool is fully safe to re-run at any time. Both `Fishbone_Lines` and `Fishbone_OutOfRange` are deleted and rebuilt from scratch on every run, and `Civic_QA_Result` is re-copied from your original input. You will always be looking at results that reflect the current state of your data.

## Known Limitations

- **Name matching is exact** after normalization - abbreviation differences such as `ST` vs `STREET` will cause missed matches. Pre-normalize your street names before running for best results.
- **Address ranges stored as text** are converted to numbers at runtime. Non-numeric values such as empty strings or placeholder text are safely handled and treated as absent.
- **Civic points without geometry** are skipped silently and will not appear in either output.
- **Multiple matched segments** are resolved by proximity only - the nearest segment wins regardless of odd/even side conventions.
