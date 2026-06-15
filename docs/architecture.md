# Architecture

```mermaid
flowchart LR
    CloudTrail["CloudTrail Event History API"] --> Ingest["FastAPI ingestion jobs"]
    IAM["IAM credential report"] --> Ingest
    Analyzer["External IAM Access Analyzer"] --> Ingest
    Ingest --> SQLite["SQLite on instance volume"]
    SQLite --> Rules["Rule-based anomaly detection"]
    Rules --> API["FastAPI API"]
    SQLite --> API
    API --> React["React dashboard served by Nginx"]
    API --> Reports["PDF and CSV reports on local disk"]
```

The deployed app runs on one short-lived EC2 instance. The React build is served by Nginx, and `/api/*` requests proxy to FastAPI on `127.0.0.1:8000`.

No project S3 bucket, CloudTrail trail, CloudTrail Lake, load balancer, NAT Gateway, Elastic IP, or CloudWatch log delivery is created.

