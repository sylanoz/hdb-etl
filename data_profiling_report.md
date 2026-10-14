# Data Profiling Report

This report describes the HDB resale data at each stage of the pipeline, from the raw files through to the hashed
output, with most of the detail on the quarantined records. All the numbers come from running
`hdb_resale_etl.ipynb`.

## Key findings

- The data itself is in good shape. In the 113,053 sales between 2012 and 2017 there are no empty values, no badly
  formatted numbers and no malformed storey ranges.
- Only 1,318 rows (1.2%) were quarantined: 870 have a flat model that doesn't appear in January 2012 and 451 are
  exact duplicates. Only one value looks like a genuine typing error.
- Storey ranges change over time (5-floor bands in March to May 2012, new bands for taller blocks), so I validated
  them by format rather than by exact value. Matching exact values would have quarantined around 7,000 valid sales.
- Prices per square metre peaked in 2013 and were about 13% lower by 2017.
- Only 385 sales (0.34%) were flagged as price anomalies, and most of those are newer flats rather than errors.
- The resale identifier format from the brief isn't unique on its own, so I added a counter. All final identifiers
  and hashes are unique.

## Raw data

The data comes as four files on data.gov.sg:

| File | Months covered | Rows | Columns |
|---|---|---|---|
| Approval date, 2000 to Feb 2012 | 2000-01 to 2012-02 | 369,651 | 10 |
| Registration date, Mar 2012 to Dec 2014 | 2012-03 to 2014-12 | 52,203 | 10 |
| Registration date, Jan 2015 to Dec 2016 | 2015-01 to 2016-12 | 37,153 | 11 |
| Registration date, Jan 2017 onwards | 2017-01 to 2026-10 | 242,454 | 11 |

That's 701,461 rows in total, but only 113,053 fall in the 2012-2017 range I needed.

A few things stood out:

- The period I needed is spread across all four files. January and February 2012 are in the "approval date" file,
  while everything from March 2012 is by "registration date". These aren't quite the same event, so comparisons
  across March 2012 should be read with that in mind.
- The files from 2015 onwards have an extra `remaining_lease` column, and it isn't even in the same format between
  files (plain years in one, "years and months" in the other). Since January 2012 doesn't have this column, I left
  it out and calculated remaining lease myself for every row.
- The last file is still being updated (it goes up to October 2026), so a new download will include more rows,
  although none of them affect 2012-2017.
- Floor areas range from 31 to 280 sqm, prices from $175,000 to $1,180,000, and lease start years from 1966 to
  2015. Nothing looked impossible.
- 451 rows are exact copies of another row.

### Storey ranges

There are 25 different storey ranges in 2012-2017 but only 12 in January 2012. The other 13 are all valid:

- Eight are 5-floor bands ("01 TO 05", "06 TO 10" and so on up to "36 TO 40"), used for 6,838 sales between March
  and May 2012. Every other month uses 3-floor bands like "01 TO 03".
- Five are high floors ("37 TO 39" up to "49 TO 51", 212 sales). Those blocks exist, there just wasn't a sale that
  high in January 2012.

Every value, including all of the January 2012 ones, follows the same "NN TO NN" format with the lower floor first.
This is why I check the format of the storey range instead of comparing it to a fixed list.

## Row counts through the pipeline

| Stage | Rows | Location |
|---|---|---|
| Raw (all four files) | 701,461 | data/raw |
| In scope, 2012-01 to 2017-12 | 113,053 | |
| Quarantined | 1,318 | data/silver/quarantined.csv |
| Cleaned | 111,735 | data/silver/cleaned.csv |
| Transformed | 111,735 | data/gold/transformed.csv |
| Hashed | 111,735 | data/gold/hashed.csv |

Cleaned plus quarantined adds back up to 113,053, so no rows were lost along the way.

## Quarantined records

### Why rows were quarantined

| Check | Rows failed |
|---|---|
| flat_model_not_in_jan_2012 | 870 |
| duplicate | 451 |
| town_not_in_jan_2012 | 0 |
| flat_type_not_in_jan_2012 | 0 |
| invalid_storey_range | 0 |
| empty_value | 0 |
| invalid_number | 0 |

3 rows failed two checks (a duplicate that also has a new flat model), so the quarantine holds 1,318 rows.

The checks that found nothing stay in place for future files. A misspelt town, a blank price or a storey range
like "4 TO 6" would be caught here instead of flowing through to the identifier and the hash.

### What was actually rejected

- **869 rows have flat models that weren't sold in January 2012**: DBSS (583), Type S1 (179), Type S2 (78),
  Improved-Maisonette (15), Premium Maisonette (8) and Premium Apartment Loft (6). These are real HDB flat models.
  DBSS flats only start appearing in March 2014, and Type S1/S2 at the end of 2014. They fail because the brief
  makes January 2012 the authoritative list.
- **1 row looks like a genuine mistake**: a 2-room flat in Pasir Ris (October 2016) with flat model "2-room", which
  is a flat type rather than a model.
- **451 rows are duplicates.** 187 of them are in April and May 2014, far more than any other month, which points
  to a problem when those months were published. With no transaction ID or unit number in the data they can't be
  proven to be errors, so the first copy of each is kept.

### By year

| Year | Rows in scope | Quarantined | % | Main reason |
|---|---|---|---|---|
| 2012 | 23,198 | 17 | 0.07 | Duplicates |
| 2013 | 16,097 | 14 | 0.09 | Duplicates |
| 2014 | 16,096 | 301 | 1.87 | Duplicates in Apr/May, DBSS from March |
| 2015 | 17,780 | 175 | 0.98 | Type S1/S2 and DBSS |
| 2016 | 19,373 | 257 | 1.33 | DBSS, Type S1/S2 |
| 2017 | 20,509 | 554 | 2.70 | DBSS and duplicates |

The quarantine grows from 2014 because the new flat models start selling then. DBSS and Type S flats tend to be
at the top end of the market, so the cleaned data slightly under-represents expensive flats from 2014 onwards.

## Cleaned data

### Prices

| Year | Sales | Median price | Median price per sqm |
|---|---|---|---|
| 2012 | 23,181 | $445,000 | $4,701 |
| 2013 | 16,083 | $455,000 | $4,886 |
| 2014 | 15,795 | $420,000 | $4,565 |
| 2015 | 17,605 | $405,000 | $4,298 |
| 2016 | 19,116 | $408,000 | $4,286 |
| 2017 | 19,955 | $408,000 | $4,258 |

Prices went up into 2013, dropped through 2014 and 2015, and then stayed fairly flat. By 2017 the median price per
sqm was about 13% below its 2013 level. 2012 had the most sales of any year, and 2013 and 2014 the fewest.
4-room flats were the most common sale (44,625, median $425,000), followed by 3-room (31,197, median $328,000) and
5-room (25,748, median $500,000).

### Remaining lease as at 1 January 2027

| Flat type | Median remaining lease |
|---|---|
| 1 room | 47 years |
| 2 room | 49 years |
| 3 room | 53 years |
| 4 room | 65 years |
| 5 room | 70 years |
| Executive | 67 years |

Across all flats the median is 60 years, and 46% of them will have less than 60 years left in 2027. Smaller flat
types tend to be older, which is why their leases are shorter.

Because only the lease start year is available, I assumed every lease started on 1 January. As the calculation date
is also 1 January, the months part of the remaining lease always comes out as 0. With the real start month the
figures would be up to 11 months higher.

### Price anomalies

| Flag | Rows | % |
|---|---|---|
| normal | 109,204 | 97.73 |
| not_assessed | 2,146 | 1.92 |
| high | 378 | 0.34 |
| low | 7 | 0.01 |

Most of the high flags are newer flats: their median lease start year is 2008, compared with 1988 for normal
sales. A flat with 90+ years left in an older town is worth more per
square metre, and my comparison group (town, flat type and year) doesn't take lease age into account. 32 of the
high flags are HDB terrace houses, which are rare and much larger than a normal 3-room flat.

The 7 low flags are the best candidates for review. The lowest is a 4-room flat in Yishun sold in October 2012 at
$2,375 per sqm, a little over half the typical price for that group.

The not_assessed rows are mostly 2-room (985) and Executive (510) flats, in towns where there weren't enough of
those sales in a year to compare against.

## Transformed and hashed data

Using the identifier format from the brief, the 111,735 cleaned rows only produced 97,657 different identifiers, so
about 23% of rows shared one with another sale. The biggest group was 14 sales in Sengkang block 436 in April 2013.
This mostly happens because several flats in the same block sell in the same month, and because block letters are
dropped (436A and 436B both become 436). After adding the two-digit counter, all 111,735 identifiers are unique.

For the hashed output I used HMAC-SHA256 rather than plain SHA-256. Every part of the identifier can be worked out
from public data, so with a plain hash someone could just rebuild all the identifiers and hash them to find a match.
With a secret key that isn't possible. All 111,735 hashes are unique.

Hashing hides the identifier but doesn't make the dataset anonymous, because the block, street, month and price
are still there.

## Recommendations

1. Keep the flat model list up to date. Using January 2012 as the only reference rejects 869 valid DBSS and Type S
   sales; a maintained list of approved models would do the same job without losing them.
2. Ask the data owner about the April and May 2014 duplicates, and whether a transaction ID could be added.
3. Use one storey band format. The 5-floor bands in March to May 2012 pass validation but can't be compared
   directly with the 3-floor bands used everywhere else.
4. If the lease start month were published, the remaining lease could be calculated exactly.
5. The anomaly check would be more useful if it compared flats of a similar age, so new flats stop showing up as
   outliers.
