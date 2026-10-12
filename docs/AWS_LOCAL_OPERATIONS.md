# Local and private AWS operations

Deployment task: AGENT_EXPANSION_V1. Selected project Region: eu-north-1. AWS reported the FREE plan. The user provided a $100 credit allowance; no paid-plan upgrade or advanced-service activation was performed. AWS guidance preference: HIGH.

## What is running

The local launcher runs real PostgreSQL, Redis, API, worker, demo portal and Next frontend. Start with `backend/.venv/Scripts/python.exe scripts/local_demo.py start --agent --notifications` from the repository root. Use http://localhost:3000. Runtime files, credentials and process logs remain under ignored storage/local_runtime. The database recovered existing fictional applications after an interrupted shutdown; its stored receipts were not replaced with staged results.

The AWS CloudFormation stack is `scholarpilot-hackathon`. It runs the same six services on one t3.small EC2 host, with encrypted retained EBS, persistent database/cache volumes, a private encrypted release bucket, Secrets Manager runtime configuration, Cognito and a scoped SES sending permission. There is no inbound security-group access to web, SSH, database or cache ports. Outbound HTTPS supports actual providers and official-page research. The source bundle excludes environment files, vaults, local data, caches and generated packages.

This is a private hackathon deployment, not a public, highly available production service. PostgreSQL and Redis share one machine; host loss, backup restoration, automatic failover, a custom domain and public HTTPS delivery have not been validated. Four GB of swap helps container builds on the small host. Standard CPU credits prevent surplus-credit charges. Free Tier eligibility of the instance does not make storage, public IPv4, logs, Secrets Manager, email or all usage free.

## Access and verified sign-in

An SSM port-forward exposes remote frontend port 3000 on local port 13000. Use http://localhost:13000, then Connect identity → Sign in with verified identity. The Cognito callback is registered for exactly `http://localhost:13000/`; using a different origin loses the browser state binding. The local app callback is `http://localhost:3000/`.

The official AWS Session Manager plugin was downloaded from AWS and its executable signature validated as Amazon Web Services. Its portable binary and tunnel log are ignored runtime files. The tunnel runs only while this computer and the AWS session remain available. Reconnect using `aws ssm start-session --target INSTANCE_ID --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["3000"],"localPortNumber":["13000"]}' --profile UNI --region eu-north-1`, with the plugin directory on PATH. Obtain INSTANCE_ID from the stack output; do not put session credentials in source files.

Cognito password creation and emailed verification require the user. The real sign-in redirect was exercised. User signup/email confirmation and the fresh callback completed; the backend reports one verified OIDC profile. Evidence: evidence/verified_onboarding_20261012.json. If state expires after five minutes, reopen the app and start sign-in again. Do not bypass a login wall or a verification challenge.

## Notifications and deployment updates

SES sender verification succeeded. Direct SES and queued local email/Telegram tests returned actual provider acceptance. An AWS SES test also succeeded using the EC2 instance role. Acceptance does not verify inbox placement. The first local email job failed without AWS credentials and reached dead_letter; this failure remains in the audit. A fresh job completed after configuring the standard SDK credential process and restarting the worker.

For local SES, the ignored configuration uses profile UNI-sdk, whose credential process invokes the authorized UNI AWS CLI login. No static AWS keys are stored. The AWS containers use their instance role and do not copy the local login profile. Model, Neatlogs, Telegram and runtime secrets live in Secrets Manager; SSM commands and CloudFormation user data contain no secret values.

After reviewing/tests, `backend/.venv/Scripts/python.exe scripts/deploy_aws.py --sender VERIFIED_SENDER` builds an explicit source archive, uploads it privately, updates protected runtime configuration, and queues the Docker build/start command through SSM. It refuses a stack that is not complete. Inspect command success, then `/ready`, portal `/api/health`, frontend HTTP status and worker health; a successfully queued command is not a successful deployment.

## Costs and cleanup

Check AWS Settings → Billing for remaining credit and spend status. Confirm the Region under AWS Settings → View all projects → Overview → Additional Info → Region. Do not deploy Regional resources elsewhere. This stack does not use Lambda@Edge, StackSets, cross-Region replication or a managed database/load balancer.

Stopping EC2 reduces compute use but retained EBS, secrets, logs and other resources may still cost money. Stack deletion retains the bucket, runtime secret, Cognito pool, logs and encrypted volume so data is not silently destroyed; inventory retained resources separately before deciding on permanent cleanup. The user explicitly chose to keep the deployment running for the hackathon.

CloudFormation service validation and actual stack creation succeeded. Local cfn-lint/cfn-guard tools were unavailable and are not claimed as completed checks. Docker builds, private readiness and scoped instance-role email delivery were exercised. An operator-provisioned fictional Tobi workflow passed through the Next proxy, API and actual worker, producing owned demo receipt DEMO8273. This test does not validate human onboarding. A very short surviving essay is recorded honestly; verified source alignment is not proof of application quality. A database/cache/worker restart preserved applications, package digests, the Redis test value and authoritative receipt DEMO8273; readiness recovered. The initial restart exposed a stale Redis connection; reconnect handling was fixed and the repeated check passed. Both results are retained in evidence. Broad load, recovery from total host loss and public production security reviews remain outside this validation.
