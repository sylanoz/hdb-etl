# HDB Resale Flat Prices - ETL Assessment

This repository is my submission for the data engineering assessment.

Part 1 is a single notebook, `hdb_resale_etl.ipynb`. It downloads the HDB resale flat price data from data.gov.sg,
keeps the sales from January 2012 to December 2017, validates them against the January 2012 data, and produces the
five output groups asked for in the brief (Raw, Cleaned, Transformed, Quarantined and Hashed). My notes on the data
itself are in `data_profiling_report.md`.

Part 2, the AWS architecture, is in `docs/architecture/`: two diagrams (`overview.png` and `ingestion.png`) and my
notes explaining them (`architecture.md`).

## What's in this repository

| Path | What it is |
|---|---|
| `hdb_resale_etl.ipynb` | The pipeline (Part 1), with cell outputs |
| `config.json` | All settings used by the notebook |
| `data_profiling_report.md` | My findings on the data and the quarantined records |
| `requirements.txt` | Python libraries |
| `tests/test_api_failures.py` | Tests for how the download copes with API failures |
| `data/raw/` | Raw: the source files exactly as downloaded |
| `data/silver/` | Cleaned and Quarantined |
| `data/gold/` | Transformed and Hashed |
| `docs/architecture/overview.png` | Part 2: accounts, networks and how the data moves |
| `docs/architecture/ingestion.png` | Part 2: the monthly batch and the output groups it writes |
| `docs/architecture/architecture.md` | Part 2 notes: assumptions, flow and security |

## The assignment and where to find each part

The numbers in brackets are the requirement numbers from the brief. "Section" means the numbered section in the
notebook.

### Part 1: Developing data pipelines

| Requirement | Where it is |
|---|---|
| Get the data from data.gov.sg (collection 189) and process the files as-is, without hard-coding | Section 1, stage `src_to_raw`: `find_datasets()`, `download_dataset()`. Settings in `config.json`. Files saved unchanged in `data/raw/` |
| (1) Combine the files into one master dataset, using Jan 2012 as the authoritative set | Section 2.1: `load_raw_files()`, `combine()` |
| (2) Data profiling | Section 2.2: `column_profile()`, `numeric_profile()`, `values_not_in_reference()`. Results in section 2.6 |
| (3) Validate town, flat type, flat model and storey_range against Jan 2012, and quarantine failures | Section 2.3: `validation_checks()`, `invalid_storey_range()`, `split_valid_invalid()`. Output `data/silver/quarantined.csv` |
| (4) Remaining lease as of 1 Jan 2027, in years and months | Section 2.4: `add_remaining_lease()` |
| (5) Potentially anomalous resale prices | Section 2.4: `flag_price_anomalies()` |
| (6) Other profiling, cleaning and validation rules | Section 2.3: empty values, invalid numbers and duplicates. Section 2.4: `cast_types()`. API failure handling in section 1, tested in `tests/test_api_failures.py` |
| (7) Insights and assumptions in markdown | `data_profiling_report.md`, and "Decisions and assumptions" below |
| (8) Resale identifier, made unique without dropping records | Section 3.1: `base_identifier()`, `add_resale_identifier()`. Output `data/gold/transformed.csv` |
| (9) De-identify the identifier (irreversible, unique, safe from dictionary attacks) | Section 3.2: `get_hmac_key()`, `hash_identifier()`. Output `data/gold/hashed.csv` |
| (10, 11) The five output groups: Raw, Cleaned, Transformed, Quarantined, Hashed | `data/raw/`, `data/silver/` and `data/gold/`. Row counts in section 4 |
| (12) ETL pipeline in Python | `hdb_resale_etl.ipynb`, run as three stages; each stage is run by `run_stage()` (section 0) |
| (13) Notebook with input files, comments, markdown and cell outputs | `hdb_resale_etl.ipynb`, with the input files in `data/raw/` |
| (14) Data profiling report in markdown | `data_profiling_report.md` |
| (15) Good engineering practice and a README | This README; settings in `config.json`; logging to `logs/pipeline.log` (section 0); tests in `tests/` |

### Part 2: Architecting data ingestion and exploitation

| Requirement | Where it is |
|---|---|
| (1) Batch ingestion from data.gov.sg, including files over 100 MB | `docs/architecture/ingestion.png`; `architecture.md`, "How the data flows" steps 1 to 3 and "Large files (over 100 MB)" |
| (2) Public data.gov.sg endpoint and private VPCs, with network and component segmentation | `docs/architecture/overview.png`; `architecture.md`, step 2 and "Security" |
| (3) Tableau, in another private VPC, querying the data lake | `docs/architecture/overview.png`; `architecture.md`, steps 4 and 5 |
| (4) Keep the traffic private where possible | `architecture.md`, step 5, "Security" and "Who can see what" |
| (5) Diagrams converted to PNG | `docs/architecture/overview.png` and `docs/architecture/ingestion.png` |
| (6) Both parts in the same public Git repository | This repository |

## How to run it

You need Python 3.10 or newer. From the root of the repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook hdb_resale_etl.ipynb
```

Then use Kernel > Restart & Run All.

The notebook needs internet access, because it asks the data.gov.sg API which files make up the dataset each time
it runs. The first run also downloads those files (around 60 MB). After that they are reused from `data/raw/`, and
a run takes less than a minute. If you want to force a fresh download, delete the files in `data/raw/`.

All the settings are in `config.json`: the data.gov.sg collection, the 2012-2017 date range, the reference month,
the validation rules, the lease date, the anomaly thresholds and the output folders. To change any of these, edit
the config and re-run; the notebook code doesn't need to change.

For the hashing step I read a secret key from the environment variable `RESALE_ID_HMAC_KEY`. If it isn't set, the
notebook still runs but generates a random key, which means the hashes will be different every time. To get the
same hashes on every run, set a key first:

```bash
export RESALE_ID_HMAC_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

## How the notebook is organised

I organised the notebook as a pipeline with three stages, one for each layer of the medallion architecture. Each
stage only reads the files written by the stage before it, so if one fails I can fix it and re-run just that stage
(its "Run the stage" cell) without starting again from the download.

| Stage | What it does | Reads | Writes |
|---|---|---|---|
| `src_to_raw` | Asks data.gov.sg which files are in collection 189, keeps the ones whose dates overlap 2012-2017 (so no dataset IDs are hard-coded) and downloads them as-is | data.gov.sg API | `data/raw/` |
| `raw_to_silver` | Reads the raw files as text, combines the 2012-2017 rows using the January 2012 columns, profiles them, validates every row, cleans the ones that pass, calculates remaining lease and flags price anomalies | `data/raw/` | `data/silver/` |
| `silver_to_gold` | Builds the resale identifier, makes it unique, then hashes it | `data/silver/cleaned.csv` | `data/gold/` |

Section 0 loads `config.json` and sets up logging. Inside each stage the functions are grouped by task with a short
explanation above them, then one cell runs the stage and the cells after it show the results. Section 4 reads the
row counts back from the files on disk.

## Logging

Every step is logged with the name of its stage, both in the notebook output and in `logs/pipeline.log`:

```
2026-10-11 17:23:07 | raw_to_silver  | INFO    | Check flat_model_not_in_jan_2012      870 rows failed
2026-10-11 17:23:08 | silver_to_gold | WARNING | RESALE_ID_HMAC_KEY not set: using a random key, ...
2026-10-11 17:23:48 | silver_to_gold | ERROR   | Stage FAILED after 0.0 s
```

Each stage logs when it starts and finishes and how long it took, plus the main counts (files found and
downloaded, rows read, rows failing each check, rows written). If a stage fails, the log says which stage it was
and the full error goes into the log file, and the notebook stops there.

## Tests

`tests/test_api_failures.py` checks how the download code behaves when the data.gov.sg API fails. The real API
can't be made to fail on demand, so the tests use a fake one.

How the tests work:

- They load the download functions (`get_json`, `download_dataset`) straight from the notebook, so they test the
  code that actually runs, not a copy of it.
- They replace the API with a fake one that returns whatever each test needs, for example "rate limited twice, then
  OK". Nothing is sent to data.gov.sg.
- The waits between retries are skipped so the tests finish in about a second, but the tests still check how long
  the code would have waited.
- Downloads go to a temporary folder, never to `data/raw/`.

What they check:

| Test | The fake API... | The code should... |
|---|---|---|
| rate limit is retried with longer waits | returns HTTP 429 twice, then OK | wait 10 s, then 20 s, then succeed |
| rate limit in response body is retried | returns code 24 in the body, then OK | treat it as a rate limit and retry |
| gives up after six attempts | is rate limited every time | stop after 6 tries with a clear error |
| server error with HTML page is retried | returns 503 with an HTML error page, then OK | retry instead of crashing |
| network error is retried | drops the connection, then OK | retry |
| not found fails at once without retry | returns 404 | fail straight away, no waiting |
| download that never becomes ready fails | says "pending" 24 times | give up after 2 minutes, leave no file |
| interrupted download leaves no csv | drops the connection halfway through the file | leave only the `.part` file, no `.csv` |
| successful download | works normally | save the file exactly as received |
| existing file is not downloaded again | would fail if called | reuse the file already in `data/raw/` |

To run them, from the root of the repository:

```bash
python -m pytest tests -v
```

The results are printed in the terminal; they aren't saved to a file. Each test is listed with PASSED or FAILED,
followed by a summary line:

```
tests/test_api_failures.py::test_rate_limit_is_retried_with_longer_waits PASSED [ 10%]
...
============================== 10 passed in 1.35s ==============================
```

## Where the output goes

I stored the data in a medallion layout:

| Layer | File | Output group | Rows | Contents |
|---|---|---|---|---|
| Raw | `data/raw/*.csv` | Raw | 701,461 | The four source files, exactly as downloaded |
| Silver | `data/silver/cleaned.csv` | Cleaned | 111,735 | Rows that passed validation, with remaining lease and anomaly flags |
| Silver | `data/silver/quarantined.csv` | Quarantined | 1,318 | Rows that failed validation, with the reason |
| Gold | `data/gold/transformed.csv` | Transformed | 111,735 | Cleaned data plus `resale_identifier` |
| Gold | `data/gold/hashed.csv` | Hashed | 111,735 | Transformed data with the identifier replaced by its hash |

There are 113,053 sales in the 2012-2017 range, and every one of them ends up in either cleaned or quarantined.
The notebook asserts this so a row can't silently disappear. Each row also carries `source_file` so it can be
traced back to the raw file.

## Decisions and assumptions

**Reference data.** For town, flat type and flat model I treated the January 2012 rows as the only source of valid
values and matched them exactly, as the brief asks. These are proper reference lists, so a value that isn't in
January 2012 is quarantined.

**Storey range.** I handled this one differently. A storey range is a band of floors rather than a fixed list, and
the bands do change: March to May 2012 used 5-floor bands like "01 TO 05", and taller blocks bring in bands like
"40 TO 42". Matching exact values would have quarantined about 7,000 genuine sales just because their band didn't
come up in January 2012. Instead I take the format from January 2012, "NN TO NN" (for example "04 TO 06"), and
check that every row follows it and that the first floor isn't above the last. A row is only quarantined if its
storey range is malformed. The notebook also confirms that every January 2012 value fits the format.

**Duplicates.** If two rows are identical in every column I keep the first and quarantine the rest. There is no
transaction ID in the data, so I can't prove these are errors, but keeping both would double count the sale.

**Remaining lease.** The data only gives the year the lease started, so I assumed it started on 1 January of that
year. The remaining lease is then counted in whole months up to 1 January 2027 and rounded down. This can
understate the real figure by up to 11 months but never overstates it.

**Price anomalies.** I compared price per square metre against sales of the same flat type, in the same town and
year, and flagged anything outside 3 times the interquartile range. I used a wide threshold because I only wanted
to catch clear outliers, and I didn't judge groups with fewer than 30 sales. Flagged rows stay in the cleaned data,
since an unusual price can still be a real sale.

**Resale identifier.** I followed the format in the brief. Many sales end up with the same identifier (same block,
month and flat type), so I added a two-digit counter to every identifier. I sort the rows by their own values
before numbering them, so the result doesn't depend on the order the files were read in.

**Hashing.** The identifier is built entirely from public data, so a normal SHA-256 hash would be easy to reverse:
someone could rebuild every identifier and hash them all. I used HMAC-SHA256 with a secret key instead. Without the
key you can't produce a matching hash, and different identifiers still give different hashes. The key is never
written into the notebook.

## Libraries

pandas, numpy and requests for the pipeline, jupyter to run the notebook and pytest for the tests. Logging uses
Python's built-in `logging` module. Versions are pinned in `requirements.txt`.

## Data source

Contains information from Resale Flat Prices accessed from data.gov.sg
(https://data.gov.sg/collections/189/view), made available under the Singapore Open Data Licence version 1.0.
