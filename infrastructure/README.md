# Infrastructure

*What this section will answer: what this doc covers and who it is for.*

## Quick reference

| I want to... | See |
|---|---|
| understand what is deployed and how it fits together | [What's deployed](#whats-deployed) |
| know how dev and prod differ | [Environments](#environments) |
| set up my machine to work on infrastructure | [Prerequisites](#prerequisites) |
| preview or deploy an infrastructure change | [I want to preview or deploy an infrastructure change](#i-want-to-preview-or-deploy-an-infrastructure-change) |
| change an environment's configuration | [I want to change an environment's configuration](#i-want-to-change-an-environments-configuration) |
| understand how CI/CD authenticates to AWS | [How GitHub Actions authenticates to AWS](#how-github-actions-authenticates-to-aws) |
| understand how a pipeline actually runs in AWS | [How pipelines run on AWS](#how-pipelines-run-on-aws) |
| put a pipeline on a schedule | [I want to schedule a pipeline](#i-want-to-schedule-a-pipeline) |
| find logs or check pipeline health | [Monitoring, logs and alerting](#monitoring-logs-and-alerting) |
| know what happens to data downstream | [Downstream consumers](#downstream-consumers) |
| know what this all costs | [Costs](#costs) |
| fix a broken deploy or auth failure | [Troubleshooting](#troubleshooting) |

## What's deployed

*What this section will answer: which AWS resources the CDK app creates, how they fit together (image registry, data storage, compute, identity, networking, logging), with an architecture diagram.*

## Environments

*What this section will answer: which environments exist, the AWS account and region they live in, their stack names, and how dev and prod behave differently.*

## Prerequisites

*What this section will answer: what you need installed and configured before working with the CDK app, and the exact commands to install the infrastructure dependencies.*

## I want to preview or deploy an infrastructure change

*What this section will answer: how to synthesise, diff and deploy a stack, in which order, and who is allowed to deploy to each environment.*

<!-- TODO: needs decision — is manual `cdk deploy` from a developer machine the endorsed deployment route, or will infrastructure changes be deployed via CI/CD? -->

## I want to change an environment's configuration

*What this section will answer: where environment configuration lives, how to change a value safely, and how to add a new environment.*

## How GitHub Actions authenticates to AWS

*What this section will answer: how OIDC authentication works, which IAM roles the workflows assume, and exactly which GitHub secrets and variables must be set.*

<!-- TODO: needs decision — existing docs and the workflows disagree on the required secrets/variables (MISSION_DATA_BUCKET, AWS_REGION and ENV_NAME are documented but unused; only AWS_ACCOUNT_ID is referenced). Confirm the required set. -->

## How pipelines run on AWS

*What this section will answer: how a container image becomes a running pipeline task — image tags, the shared task definition, and how the GitHub workflows and trigger script launch tasks.*

## I want to schedule a pipeline

*What this section will answer: how the `schedule` and `stack_name` fields in `pipelines.yaml` turn into scheduled runs, and what to do when adding a new scheduled pipeline.*

<!-- TODO: needs decision — how are schedules created and applied (no schedule resources exist in the CDK app yet), and what do `schedule` and `stack_name` in pipelines.yaml actually drive? -->

## Monitoring, logs and alerting

*What this section will answer: where pipeline logs go, how long they are retained, what alerting exists, and how pipeline health is checked.*

<!-- TODO: needs decision — does the health-check/notifier Lambda referenced in pipelines.yaml exist, where does its source live, and which stack deploys it? -->

## Downstream consumers

*What this section will answer: what happens to data after it lands in the prod bucket, and what infrastructure (if any in this repo) is involved.*

<!-- TODO: needs decision — where does the DuckLake/Superset refresh described in running-pipelines.md actually live (it is not in this repo), and are the hourly/10-minute timings accurate? -->

## Costs

*What this section will answer: what the deployed infrastructure costs per month, what drives the cost, and how to keep it down.*

<!-- TODO: needs decision — previous estimates were priced for a Lambda-based architecture; re-cost for the actual Fargate setup, or drop the section? -->

## Troubleshooting

*What this section will answer: common failures (OIDC authentication, CDK bootstrap, stack drift, failed task launches) and how to diagnose and fix them.*

---

*Last updated: 27 July 2026 by Alex*
