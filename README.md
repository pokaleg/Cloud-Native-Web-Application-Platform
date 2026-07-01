# Cloud-Native Web Application Platform

A production-grade cloud-native backend system built and deployed across **AWS** and **GCP**, developed as part of CSYE6225 – Network Structures and Cloud Computing at Northeastern University.

This project spans the full cloud engineering lifecycle — RESTful API design, infrastructure as code, custom machine image pipelines, managed databases, object storage, auto-scaling, load balancing, SSL termination, DNS, observability, and AI-powered features via MCP.

> All infrastructure is defined as code. No manual cloud console steps were used for deployment.

---

## System Architecture

```
┌─────────────────────────────────────────┐
│        Route 53 (DNS + Alias)           │
│  dev.domain.tld / demo.domain.tld       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│       Application Load Balancer         │
│   HTTPS :443  →  App :8080              │
│   SSL/TLS termination via ACM           │
└──────────┬──────────────────────────────┘
           │  (Load Balancer SG only)
┌──────────▼──────────────────────────────┐
│         Auto Scaling Group              │
│   Min: 3  |  Desired: 3  |  Max: 5      │
│   EC2 instances (Custom AMI)            │
│   FastAPI · Uvicorn · Python 3.12       │
└──────┬─────────────────────┬────────────┘
       │                     │
┌──────▼──────────┐  ┌───────▼──────────┐
│  RDS PostgreSQL │  │    S3 Bucket     │
│ (Private Subnet)│  │ (Syllabus Files) │
│  Not publicly   │  │ Encrypted +      │
│  accessible     │  │ Lifecycle Policy │
└─────────────────┘  └──────────────────┘
       │
┌──────▼──────────────────────────────────┐
│          AWS CloudWatch                 │
│    Logs · Custom Metrics · Alarms       │
└─────────────────────────────────────────┘
```

---

## Key Features

### RESTful API — Python · FastAPI · PostgreSQL
- `GET /healthz` — Database-backed health check; auto-bootstraps schema on startup
- `POST /v1/user` — User registration with BCrypt password hashing
- `GET /PUT /v1/user/self` — Authenticated user profile management (HTTP Basic Auth)
- `GET /v1/metadata` — Runtime cloud platform detection (AWS vs. GCP); returns instance metadata without any hardcoded config
- `GET POST PUT DELETE /v1/courses` — Full course catalog CRUD with field validation and uniqueness constraints
- `POST GET DELETE /v1/courses/{id}/syllabus` — Multipart file upload to S3; metadata persisted in RDS
- Stateless, JSON-only, no UI layer

### Infrastructure as Code — Terraform
- **AWS:** VPC, public/private subnets across 3 AZs, Internet Gateway, route tables, security groups, Launch Template, Auto Scaling Group, Application Load Balancer, RDS, S3, IAM roles/policies, Route 53, ACM
- **GCP:** Custom VPC, regional subnets, Cloud Router, firewall rules, Compute Engine instance
- Fully parameterized — supports multiple isolated deployments from the same templates
- Separate dev and demo environments across AWS accounts and GCP projects

### Auto Scaling + Load Balancing
- Auto Scaling Group with min 3 / max 5 EC2 instances, 60s cooldown
- Scale-up policy: average CPU > 5% → add 1 instance
- Scale-down policy: average CPU < 3% → remove 1 instance
- Application Load Balancer routes HTTPS traffic to healthy instances
- Direct internet access to EC2 instances is blocked — all traffic flows through the ALB
- Route 53 A record aliased to the load balancer for a stable public endpoint

### SSL/TLS Termination
- ACM certificate provisioned and attached to the load balancer
- ALB terminates HTTPS (:443) and forwards HTTP to application instances
- Application accessible at `https://(dev|demo).your-domain-name.tld`

### DNS — Amazon Route 53
- Root hosted zone for `yourdomainname.tld` in the root AWS account
- Subdomain delegation: `dev.yourdomainname.tld` → dev account, `demo.yourdomainname.tld` → demo account
- A records aliased to the load balancer, managed via Terraform

### Custom Machine Images — Packer
- Single HCL template targeting both AWS (AMI) and GCP (Compute Image) simultaneously
- Ubuntu 24.04 LTS base with application baked in — zero manual setup on launch
- Application runs as a hardened non-login system user (`csye6225:csye6225`)
- Systemd service auto-starts on instance boot
- AMIs built in dev account, automatically shared with demo account/project
- CloudWatch Unified Agent installed and enabled in the image

### CI/CD — GitHub Actions
- **On PR:** Integration tests · `packer fmt`/`validate` · `terraform fmt`/`validate`
- **On merge to main:** Full test run → artifact build → AWS AMI + GCP Image build
- Workload Identity Federation for GCP (no long-lived service account keys)
- Branch protection enforced across all repositories — no direct commits to `main`

### Observability — CloudWatch
- Unified CloudWatch Agent installed in AMI, configured at launch via EC2 user data
- Application logs streamed to CloudWatch in near real-time
- Custom StatsD metrics: API call counts, API latency, DB query latency, S3 call latency

### MCP Integration *(coming soon)*
- AI-powered features via Model Context Protocol

### Security Highlights
- Passwords hashed with BCrypt + random salt; never returned in responses
- RDS in private subnet — no public accessibility
- Database security group allows inbound only from the application security group
- EC2 instances not reachable directly from the internet — load balancer only
- IAM roles follow least-privilege; no hardcoded credentials anywhere
- S3 bucket: private, UUID name, AES-256 default encryption, lifecycle policy (STANDARD → STANDARD_IA after 30 days)
- All configuration injected via environment variables, EC2 user data, and systemd `EnvironmentFile`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI 0.109 · Uvicorn 0.27 |
| Database | PostgreSQL 16 (local dev) · AWS RDS (cloud) |
| ORM | SQLAlchemy 2.0 |
| Auth | HTTP Basic Auth · BCrypt 4.0 |
| IaC | Terraform 1.7 |
| Image Building | HashiCorp Packer |
| CI/CD | GitHub Actions |
| Object Storage | AWS S3 |
| DNS | Amazon Route 53 |
| SSL/TLS | AWS Certificate Manager (ACM) |
| Load Balancing | AWS Application Load Balancer |
| Auto Scaling | AWS Auto Scaling Group + Launch Template |
| Observability | AWS CloudWatch (Logs + Metrics) |
| Cloud Providers | AWS · GCP |
| OS | Ubuntu 24.04 LTS |

---

## Repository Structure

```
HK-Organisation/
├── webapp       # FastAPI application, Packer templates, GitHub Actions workflows
└── tf-infra     # Terraform configurations for AWS and GCP
```

```
webapp/
├── app/
│   ├── api/          # Route handlers (health, user, metadata, courses, syllabus)
│   ├── core/         # Config, DB engine, security, cloud metadata detection
│   ├── models/       # SQLAlchemy ORM models
│   └── schemas/      # Pydantic request/response schemas
├── packer/
│   ├── webapp.pkr.hcl    # Multi-cloud Packer template (AWS + GCP)
│   └── setup.sh          # Provisioner script
├── tests/                # Pytest integration tests
├── .github/workflows/    # CI (tests), Packer validate, Packer build
└── webapp.service        # Systemd unit file
```

```
tf-infra/
├── aws/    # VPC, subnets, IGW, SGs, ALB, ASG, EC2, RDS, S3, IAM, ACM, Route 53
├── gcp/    # VPC, subnets, routes, firewall rules, Compute Engine
└── .github/workflows/    # Terraform fmt + validate CI
```

---

## Deployment Flow

```
Developer pushes to feature branch
        │
        ▼
GitHub Actions: Run integration tests
        │
        ▼
GitHub Actions: packer fmt + validate / terraform fmt + validate
        │
        ▼
Pull Request review → merge to main
        │
        ▼
GitHub Actions: Build app artifact → Build AWS AMI + GCP Image
        │
        ▼
terraform apply (dev or demo environment)
        │
        ▼
Auto Scaling Group launches EC2 instances from custom AMI
App auto-starts via systemd → connects to RDS via user data config
ALB routes HTTPS traffic across healthy instances
Route 53 alias resolves to the load balancer
```

---

## API Endpoints

| Endpoint | Method(s) | Auth | Description |
|---|---|---|---|
| `/healthz` | GET | None | DB-backed health check |
| `/v1/user` | POST | None | Register new user |
| `/v1/user/self` | GET, PUT | Basic | Get / update authenticated user |
| `/v1/metadata` | GET | None | Cloud instance metadata (auto-detected) |
| `/v1/courses` | GET, POST | Basic | List / create courses |
| `/v1/courses/{id}` | GET, PUT, DELETE | Basic | Manage a course |
| `/v1/courses/{id}/syllabus` | GET, POST, DELETE | Basic | Upload / retrieve / delete syllabus |

---

## Cloud Environment

| | AWS | GCP |
|---|---|---|
| Dev | Dedicated member account | `dev-project-*` |
| Demo | Dedicated member account | `protean-unity-*` |
| Region | `us-east-1` | `us-east1` |
| Image built in | Dev account | Dev project |
| Image shared with | Demo account (AMI sharing) | Demo project (IAM binding) |

---


