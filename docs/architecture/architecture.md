# Part 2 - Data Ingestion and Exploitation on AWS

This is my design for running the Part 1 pipeline on AWS, with S3 as the data lake and the Data Science team's
Tableau querying it from a separate private VPC. There are two diagrams:

| Diagram | Shows |
|---|---|
| [overview.png](overview.png) | Accounts, networks and how the data moves between them |
| [ingestion.png](ingestion.png) | The monthly batch: three pipeline stages and the output groups they write |

The circled numbers below match the numbered arrows on the diagrams.

## Assumptions

- Everything runs in the Singapore region (ap-southeast-1), across two Availability Zones.
- Three AWS accounts: **network**, **data platform** and **analytics** (Tableau). A mistake in one account does
  not affect the others.
- HDB's office network is already connected privately to AWS (Direct Connect or VPN).
- HDB uses Databricks on AWS, running on **classic compute**: the clusters run inside HDB's own network, so data is
  stored and processed inside HDB's AWS account.
- A monthly batch is enough: data.gov.sg updates this dataset about once a month.

## Main components

| Component | What it does |
|---|---|
| Databricks control plane | Databricks' managed service: the workspace, the job scheduler and Unity Catalog (table permissions). It holds no HDB data. |
| Databricks job clusters | Run the three pipeline stages from the notebook, inside HDB's Data VPC |
| Databricks SQL warehouse | Answers Tableau's queries, also inside the Data VPC |
| Amazon S3 | One bucket per output group: Raw, Cleaned, Quarantined, Transformed, Hashed |
| Firewall (network account) | The only way out to the internet |
| Transit Gateway | Connects the networks and decides which can talk to which |
| Tableau Server | Dashboards for the Data Science team, in its own VPC |

## How the data flows

**① Jobs start.** A Databricks Workflow runs once a month and starts the job clusters in the Data VPC. The
clusters talk to Databricks over a private connection (PrivateLink), not the internet.

**② API call and download.** The stage 1 task calls the data.gov.sg API and downloads the file. The job clusters
have no direct internet access. The only way out is a central firewall in the network account, which allows
data.gov.sg and nothing else. The diagram shows the full path.

**③ Write to S3.** Each stage writes its output to S3 over a private connection inside AWS:
stage 1 writes Raw, stage 2 writes Cleaned and Quarantined, stage 3 writes Transformed and Hashed.
The tables are registered in Unity Catalog, but the files always stay in HDB's S3 buckets.

**④ Analysts open Tableau.** Analysts reach Tableau from the HDB office network over the private connection to
AWS. Tableau is not exposed to the internet.

**⑤ Tableau reads the data.** Tableau queries the SQL warehouse through a private connection (PrivateLink).
The warehouse reads the Hashed tables from S3 and returns the results. Tableau has no network route to the Data
VPC; it can only ask the warehouse, and Unity Catalog decides what it is allowed to read.

## Large files (over 100 MB)

The file is never held whole in memory. It is streamed in chunks straight into S3 (multipart upload): the parts
upload in parallel, a failed part is retried on its own, and the file only appears in Raw once every part has
arrived. A failed run never leaves half a file behind. This is the same idea as the streaming download in the
notebook.

## Security

- **Nothing is on the internet.** No server or cluster has a public IP address.
- **One way out**, through a firewall that only allows data.gov.sg.
- **Networks are kept apart.** The Data VPC and the Tableau VPC cannot reach each other.
- **Private connections** to Databricks and S3, so this traffic never uses the internet.
- **S3 is locked down:** public access is blocked for the whole account, data is encrypted, and each bucket only
  accepts requests from our own networks.
- **The hashing key** is stored in AWS Secrets Manager and only the stage 3 job can read it.
- **Everything is logged** for audit (AWS CloudTrail and Databricks audit logs).

## Who can see what

People sign in with their HDB account, and permissions come from their HDB directory groups, so someone who
leaves loses access automatically. Unity Catalog decides who can read each table.

| Who | Raw | Cleaned | Quarantined | Transformed | Hashed |
|---|---|---|---|---|---|
| Pipeline stage 1 | write | - | - | - | - |
| Pipeline stage 2 | read | write | write | - | - |
| Pipeline stage 3 | - | read | - | write | write |
| Data Science (Tableau) | - | - | - | - | read |
| Data engineers | read | read | read | on approval only | read |
| Data steward | - | - | read | - | - |

Transformed holds the readable identifier, so nobody has standing access to it. A stricter option would be no
standing production access for engineers at all.

## Security, reliability, scalability, maintainability and performance

| | How the design handles it |
|---|---|
| Security | Private networks only, one filtered way out, private connections, encryption, table-level permissions, audit logs |
| Reliability | Two Availability Zones; each pipeline task retries on failure; re-running a month is safe because each run rebuilds its own outputs; alert on failure |
| Scalability | Clusters and the SQL warehouse scale out as data grows; S3 has no practical size limit |
| Maintainability | The same three stages as the notebook, each re-runnable on its own; infrastructure defined as code; one platform for scheduling, processing and SQL |
| Performance | Parallel upload of large files; tables partitioned by year; Tableau extracts for dashboards |

## Alternatives I considered

- **AWS-native services (Glue, Athena, Lake Formation, Step Functions).** Fully serverless and all inside AWS. I
  chose Databricks because Unity Catalog gives finer access control, one platform covers scheduling, processing
  and SQL, and it is the platform I know best. The network design would stay the same.
- **Databricks serverless.** Less to manage, but it runs in Databricks' own account, so data would be processed
  outside HDB's account.
- **Plain containers (ECS Fargate).** Enough for today's data volume, but it does not grow well with more data or
  more pipelines.
