# GoSwift Backend AWS Deployment Guide

This guide deploys the GoSwift backend from GitHub Actions to AWS using:

- EC2 for Docker runtime
- Elastic IP for a stable public IP
- ECR for backend Docker images
- RDS PostgreSQL for the production database
- S3 for media uploads
- Docker Redis for cache, Channels, and Celery broker
- Docker Celery worker and Celery beat
- Nginx for HTTP and WebSocket reverse proxy
- Gmail SMTP for OTP and application emails

The project deploy path on EC2 is:

```bash
/opt/goswift-backend/
```

No domain or SSL is configured in this first deployment phase. The API will run on:

```text
http://YOUR_ELASTIC_IP/
```

The deployment flow is:

```text
GitHub main branch
  -> GitHub Actions builds Docker image
  -> image is pushed to Amazon ECR
  -> workflow connects to EC2 over SSH
  -> EC2 pulls the exact image tag from ECR
  -> Docker Compose recreates GoSwift services
  -> Nginx exposes the backend on port 80
```

The runtime architecture is:

```text
Client / Frontend
  -> http://YOUR_ELASTIC_IP
  -> Nginx container
  -> Daphne ASGI Django container
  -> RDS PostgreSQL
  -> Redis container
  -> S3 media bucket
```

Important production decisions in this setup:

- RDS is managed by AWS, not by Docker.
- Redis is inside Docker for this first deployment phase.
- Celery worker and Celery beat run from the same backend image as Django.
- Media files go to S3, not the EC2 disk.
- Static files are collected into a Docker volume and served by Nginx.
- WebSockets go through Nginx to Daphne, so port `8000` does not need to be public.

---

## 1. Confirm Local Files

Before starting AWS setup, make sure these files exist in the repository:

```text
Dockerfile
docker-compose.prod.yml
.env.production.example
.github/workflows/deploy-production.yml
deploy/nginx/goswift.conf
deploy/scripts/docker-entrypoint.sh
```

The production compose stack contains:

- `nginx`
- `web`
- `celery_worker`
- `celery_beat`
- `redis`

Redis uses the official `redis:7.4-alpine` image. Django, Celery worker, and Celery beat use the same GoSwift backend image from ECR.

What each deployment file is responsible for:

```text
Dockerfile
  Builds the GoSwift backend runtime image with Python, project code, and requirements.

docker-compose.prod.yml
  Defines the production containers and their relationships.

.env.production.example
  Documents the environment variables needed on EC2.

.github/workflows/deploy-production.yml
  Builds/pushes the Docker image and deploys it to EC2.

deploy/nginx/goswift.conf
  Exposes HTTP, proxies API/WebSocket traffic, and serves static files.

deploy/scripts/docker-entrypoint.sh
  Waits for PostgreSQL, optionally runs migrations, optionally runs collectstatic,
  then starts Daphne/Celery depending on the container command.
```

The real production env file must be created manually on EC2:

```text
/opt/goswift-backend/.env.production
```

That file must not be committed to GitHub because it contains secrets.

---

## 2. Choose AWS Region

Pick one AWS region and use it everywhere.

Example:

```text
us-east-1
```

Use the same region for:

- ECR
- RDS
- S3
- EC2
- GitHub secret `AWS_REGION`

Why this matters:

- EC2 can pull from ECR faster when both are in the same region.
- EC2 can connect to RDS more easily when resources are in the same VPC/region.
- S3 media latency is lower when the app and bucket are nearby.
- GitHub Actions only needs one `AWS_REGION` value.

Write the final region down before continuing:

```text
AWS_REGION=YOUR_REGION
```

Example:

```text
AWS_REGION=us-east-1
```

---

## 3. Create IAM Access Key For GitHub Actions

You said you already have an IAM user with AdministratorAccess but no access key yet.

In AWS Console:

1. Go to `IAM`.
2. Open `Users`.
3. Select your deployment IAM user.
4. Go to `Security credentials`.
5. Create an access key.
6. Choose `Command Line Interface (CLI)` if AWS asks for the use case.
7. Save both values:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

You will add these to GitHub Actions secrets later.

Important: do not commit these keys into the repository or `.env.production`.

What these keys are used for:

- GitHub Actions uses them to authenticate to AWS.
- The workflow uses them to push Docker images to ECR.
- The workflow also uses them to get an ECR login token.

What these keys are not used for:

- They should not be used by the running Django app.
- They should not be placed on EC2 in `.env.production`.
- They should not be used for S3 from Django if the EC2 instance role is configured.

Initial permission note:

- AdministratorAccess is acceptable for getting the first deployment working.
- After deployment is stable, reduce this IAM user to a smaller deployment-only policy.
- A later improvement is GitHub OIDC, which avoids long-lived AWS access keys.

---

## 4. Create ECR Repository

In AWS Console:

1. Go to `Elastic Container Registry`.
2. Create a private repository.
3. Repository name:

```text
goswift-backend
```

After creating it, note the repository URI. It will look like:

```text
ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/goswift-backend
```

For GitHub Actions, the secret `ECR_REPOSITORY` should be only:

```text
goswift-backend
```

Do not use the full repository URI for `ECR_REPOSITORY`. The workflow already receives the ECR registry from AWS and combines it with this repository name.

Correct:

```text
ECR_REPOSITORY=goswift-backend
```

Incorrect:

```text
ECR_REPOSITORY=123456789012.dkr.ecr.us-east-1.amazonaws.com/goswift-backend
```

Optional cleanup:

- Add an ECR lifecycle policy later to keep only the latest 10 or 20 images.
- This keeps ECR storage clean after repeated deployments.

---

## 5. Create S3 Bucket For Media

In AWS Console:

1. Go to `S3`.
2. Create a bucket.
3. Use a globally unique name, for example:

```text
goswift-media-prod-yourname
```

4. Select the same AWS region.
5. Keep `Block all public access` enabled for the first deployment.

The backend is configured to use signed media URLs by default, so keeping the bucket private is fine.

Later, if you want public media or CloudFront, update the storage policy separately.

Recommended S3 env values:

```env
USE_S3_MEDIA=True
AWS_STORAGE_BUCKET_NAME=goswift-media-prod-YOUR_SUFFIX
AWS_S3_REGION_NAME=YOUR_AWS_REGION
AWS_QUERYSTRING_AUTH=True
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

Why `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` stay blank:

- EC2 will have an IAM role.
- Boto3/Django storage can use the EC2 role automatically.
- This avoids storing AWS credentials in the production env file.

What goes to S3:

- provider profile photos
- onboarding documents
- restaurant photos and logos
- menu item photos
- courier documents
- car rental vehicle photos
- room/property listing photos
- other uploaded media

Security note:

- Private media is safer for regulatory documents and provider identity files.
- Public media can be introduced later using CloudFront or a separate public media strategy.

---

## 6. Create RDS PostgreSQL Database

In AWS Console:

1. Go to `RDS`.
2. Create database.
3. Engine: `PostgreSQL`.
4. Template: choose a small production/dev size depending on budget.
5. DB instance identifier:

```text
goswift-postgres
```

6. Database name:

```text
goswift
```

7. Master username:

```text
goswift_admin
```

8. Set a strong password and save it.
9. Make sure RDS is in the same VPC as the EC2 instance you will create.
10. For public access, prefer `No` if EC2 is in the same VPC.

After creation, copy the RDS endpoint. It will look like:

```text
goswift-postgres.xxxxxxxxxxxx.REGION.rds.amazonaws.com
```

You will use this as:

```text
DB_HOST
```

Recommended RDS settings for first deployment:

```text
Engine: PostgreSQL
Database name: goswift
Master username: goswift_admin
Public access: No
Port: 5432
VPC: same VPC as EC2
Storage autoscaling: Optional but useful
Backups: Enabled
Deletion protection: Enabled for real production
```

Production env values will look like:

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=goswift
DB_USER=goswift_admin
DB_PASSWORD=YOUR_RDS_PASSWORD
DB_HOST=YOUR_RDS_ENDPOINT
DB_PORT=5432
```

Important:

- `DB_HOST` must be the RDS endpoint, not `localhost`.
- `DB_NAME` must match the initial database name created in RDS.
- If RDS public access is `No`, EC2 must be in the same VPC or connected network.
- The RDS security group must allow PostgreSQL from the EC2 security group.

Common first-time RDS problem:

```text
django.db.utils.OperationalError: connection timed out
```

Usually this means the RDS security group is not allowing traffic from EC2, or EC2/RDS are not in reachable networking.

---

## 7. Plan EC2 Security Group During Instance Creation

You do not need to create a separate EC2 security group before launching the instance. You can create and attach the EC2 security group directly during the EC2 launch flow.

When launching EC2, create a new security group named:

```text
goswift-backend-sg
```

Inbound rules:

```text
SSH   TCP 22  YOUR_PUBLIC_IP/32
HTTP  TCP 80  0.0.0.0/0
```

For now, do not open port `8000`. Nginx exposes port `80` and proxies to the internal Django container.

When you later add a domain and SSL, you will also open:

```text
HTTPS TCP 443 0.0.0.0/0
```

More detailed inbound rules:

```text
Type   Protocol  Port  Source
SSH    TCP       22    YOUR_PUBLIC_IP/32
HTTP   TCP       80    0.0.0.0/0
```

Do not add these public inbound rules:

```text
8000  Django/Daphne should stay internal
6379  Redis should stay internal
5432  PostgreSQL is on RDS and should not be public
```

Finding your public IP:

- Search `what is my IP` in your browser.
- Use that value as `YOUR_PUBLIC_IP/32`.

Example:

```text
103.55.22.11/32
```

If your internet provider changes your IP, you may need to update this rule before PuTTY can connect again.

Important:

- This security group is created/attached while creating the EC2 instance.
- After EC2 is created, copy this security group's ID.
- Then update the RDS security group to allow PostgreSQL from this EC2 security group.

---

## 8. Allow EC2 To Connect To RDS

Open the RDS security group.

Inbound rule:

```text
PostgreSQL TCP 5432 EC2_SECURITY_GROUP
```

Do not open PostgreSQL to the whole internet.

The source should be the EC2 security group ID, not your laptop IP.

Correct source:

```text
sg-xxxxxxxxxxxxxxxxx  (goswift-backend-sg)
```

Avoid:

```text
0.0.0.0/0
```

Why:

- Django runs on EC2, so EC2 needs database access.
- Your local laptop does not need direct production database access.
- Keeping RDS private greatly reduces risk.

---

## 9. Create EC2 Instance

In AWS Console:

1. Go to `EC2`.
2. Launch instance.
3. Name:

```text
goswift-backend-prod
```

4. Amazon Machine Image:

```text
Ubuntu Server 24.04 LTS (HVM), SSD Volume Type
```

5. Instance size: start with `t3.small` or larger.
6. Create or select a key pair for PuTTY.
7. In `Network settings`, create a new security group named `goswift-backend-sg`.
8. Add inbound SSH from your public IP and HTTP from anywhere.
9. Launch instance.

For PuTTY, if AWS gives you a `.pem` file, convert it to `.ppk` using PuTTYgen.

Recommended EC2 settings:

```text
Name: goswift-backend-prod
AMI: Ubuntu Server 24.04 LTS (HVM), SSD Volume Type
Instance type: t3.small or larger
Storage: at least 20 GiB
VPC: same VPC as RDS
Security group: goswift-backend-sg
```

Why `t3.small` or larger:

- This stack runs Nginx, Django/Daphne, Celery worker, Celery beat, and Redis.
- Very tiny instances can run out of memory during Docker image pulls, migrations, or traffic spikes.

After launch, wait for:

```text
Instance state: Running
Status checks: 2/2 checks passed
```

After the instance is created:

1. Open the EC2 instance details.
2. Open the attached security group.
3. Copy the security group ID.
4. Use that security group ID when updating the RDS security group in step 8.

---

## 10. Allocate And Attach Elastic IP

In AWS Console:

1. Go to `EC2`.
2. Open `Elastic IPs`.
3. Allocate Elastic IP.
4. Associate it with the GoSwift EC2 instance.

Save the Elastic IP. You will use it for:

```text
ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS
WEBSOCKET_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS
BASE_URL
GitHub secret EC2_HOST
```

Example:

```text
13.52.100.25
```

Temporary production URLs:

```text
API:       http://13.52.100.25/
Swagger:   http://13.52.100.25/api/docs/
Admin:     http://13.52.100.25/admin/
Health:    http://13.52.100.25/health/
WebSocket: ws://13.52.100.25/ws/...
```

Important:

- Elastic IP can cost money if allocated but not attached to a running instance.
- Keep it associated with the GoSwift EC2 instance.
- Later, the domain DNS record should point to this Elastic IP.

---

## 11. Attach EC2 IAM Role For S3 And ECR Pull

Create an IAM role for EC2.

Attach permissions that allow:

- reading from ECR
- accessing the GoSwift media S3 bucket

For the first deployment, you may attach these AWS managed policies:

```text
AmazonEC2ContainerRegistryReadOnly
AmazonS3FullAccess
```

Later, replace `AmazonS3FullAccess` with a tighter bucket-only policy.

Attach the role to the EC2 instance:

1. Open EC2 instance.
2. `Actions`.
3. `Security`.
4. `Modify IAM role`.
5. Select the role.

Because the app supports instance-role credentials, you can leave these blank in `.env.production`:

```text
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

Recommended role name:

```text
goswift-ec2-role
```

Why the role is needed:

- EC2 must pull private images from ECR during deployment.
- Django must upload/read media files from S3.
- Using a role is safer than placing permanent AWS keys inside `.env.production`.

Later stricter S3 policy example:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    }
  ]
}
```

Use the broad managed policy first if you want speed, then tighten permissions after the first successful deployment.

---

## 12. Connect To EC2 Using PuTTY

Use:

```text
Host: YOUR_ELASTIC_IP
Port: 22
Username: ubuntu
Private key: your .ppk file
```

For Ubuntu Server 24.04 LTS on EC2, the default username is:

```text
ubuntu
```

PuTTY checklist:

```text
Session > Host Name: ubuntu@YOUR_ELASTIC_IP
Session > Port: 22
Session > Connection type: SSH
Connection > SSH > Auth > Credentials > Private key file: your .ppk file
```

Common PuTTY errors:

```text
Network error: Connection timed out
```

Usually means:

- wrong Elastic IP
- EC2 security group does not allow SSH from your current IP
- EC2 instance is stopped

```text
Permission denied / Server refused our key
```

Usually means:

- wrong key pair
- wrong username
- `.ppk` does not match the EC2 instance key pair

For Ubuntu Server 24.04 LTS, use:

```text
ubuntu
```

---

## 13. Install Docker, Compose Plugin, Git, And AWS CLI On EC2

Run these commands on EC2:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git unzip curl
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
```

Log out of PuTTY and log in again so the Docker group permission applies.

Then verify Docker:

```bash
docker --version
docker compose version
```

Install or verify AWS CLI:

```bash
aws --version
```

If `aws` is missing:

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

Verify the EC2 role can call AWS:

```bash
aws sts get-caller-identity
```

Expected output should include an assumed role ARN, similar to:

```json
{
  "UserId": "...",
  "Account": "123456789012",
  "Arn": "arn:aws:sts::123456789012:assumed-role/goswift-ec2-role/..."
}
```

If Docker says permission denied after installing:

```bash
exit
```

Then reconnect with PuTTY and try:

```bash
docker ps
```

If `docker compose version` fails:

- Confirm `docker-compose-v2` installed correctly.
- On Ubuntu 24.04, the command should be `docker compose version`, not `docker-compose version`.
- If missing, install Docker using Docker's official Ubuntu repository instructions.

After setup, these commands should all work:

```bash
docker --version
docker compose version
aws --version
aws sts get-caller-identity
```

---

## 14. Create Deploy Directory On EC2

Run:

```bash
sudo mkdir -p /opt/goswift-backend
sudo chown -R ubuntu:ubuntu /opt/goswift-backend
cd /opt/goswift-backend
```

Verify:

```bash
pwd
ls -la
```

Expected:

```text
/opt/goswift-backend
```

This directory will contain:

```text
.env.production
docker-compose.prod.yml
deploy/nginx/goswift.conf
```

The GitHub workflow uploads `docker-compose.prod.yml` and `deploy/nginx/goswift.conf`.

You create `.env.production` manually on EC2 because it contains secrets.

---

## 15. Create Production Environment File On EC2

Create the file:

```bash
nano /opt/goswift-backend/.env.production
```

Paste and update this template:

```env
SECRET_KEY=CHANGE_ME_TO_A_LONG_RANDOM_SECRET
DEBUG=False
ALLOWED_HOSTS=YOUR_ELASTIC_IP,localhost,127.0.0.1

CORS_ALLOWED_ORIGINS=http://YOUR_ELASTIC_IP
WEBSOCKET_ALLOWED_ORIGINS=http://YOUR_ELASTIC_IP,ws://YOUR_ELASTIC_IP
CSRF_TRUSTED_ORIGINS=http://YOUR_ELASTIC_IP

BASE_URL=http://YOUR_ELASTIC_IP/
FRONTEND_URL=http://YOUR_FRONTEND_OR_PLACEHOLDER

DB_ENGINE=django.db.backends.postgresql
DB_NAME=goswift
DB_USER=goswift_admin
DB_PASSWORD=YOUR_RDS_PASSWORD
DB_HOST=YOUR_RDS_ENDPOINT
DB_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379
USE_REDIS_CHANNELS=True

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=YOUR_GMAIL_ADDRESS
EMAIL_HOST_PASSWORD=YOUR_GMAIL_APP_PASSWORD
DEFAULT_FROM_EMAIL=GoSwift <YOUR_GMAIL_ADDRESS>

USE_S3_MEDIA=True
AWS_STORAGE_BUCKET_NAME=YOUR_S3_BUCKET_NAME
AWS_S3_REGION_NAME=YOUR_AWS_REGION
AWS_QUERYSTRING_AUTH=True
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

Generate a strong Django secret key locally or on EC2. Example:

```bash
python3 - <<'PY'
from secrets import token_urlsafe
print(token_urlsafe(64))
PY
```

Save the file.

Set safer permissions:

```bash
chmod 600 /opt/goswift-backend/.env.production
```

Detailed variable notes:

```text
SECRET_KEY
  Long random string. Must be unique for production.

DEBUG
  Must be False.

ALLOWED_HOSTS
  Include Elastic IP now. Add domain later.

CORS_ALLOWED_ORIGINS
  Origins allowed to call the API from browser frontend code.

WEBSOCKET_ALLOWED_ORIGINS
  Origins allowed to open WebSocket connections.

CSRF_TRUSTED_ORIGINS
  Trusted browser origins for CSRF-sensitive endpoints/admin.

BASE_URL
  Backend base URL used when building absolute links.

FRONTEND_URL
  Frontend URL used in emails/redirects. Use placeholder until frontend is ready.

DB_HOST
  RDS endpoint. Never localhost in production.

REDIS_HOST
  Must be redis because that is the Docker Compose service name.

USE_S3_MEDIA
  True means uploaded media goes to S3.

AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  Leave blank when using EC2 IAM role.
```

Verify the env file exists without printing all secrets:

```bash
ls -la /opt/goswift-backend/.env.production
```

Avoid casually running `cat .env.production` because it prints production secrets into the terminal.

---

## 16. Configure Gmail SMTP

For Gmail SMTP, use an app password, not your normal Gmail password.

In Google Account:

1. Enable 2-Step Verification.
2. Create an App Password.
3. Use that app password as:

```text
EMAIL_HOST_PASSWORD
```

Example:

```env
EMAIL_HOST_USER=your.email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=GoSwift <your.email@gmail.com>
```

More Gmail notes:

- Your normal Gmail password will not work for SMTP when 2-step verification is enabled.
- Use a Gmail App Password.
- If Google shows the app password with spaces, you can paste it with or without spaces.
- First OTP emails may land in spam until sending reputation improves.

After deployment, test Gmail by triggering the OTP flow. If email sending is done in Celery, check:

```bash
docker logs goswift-celery-worker --tail=200
```

If sending happens directly in the web request, check:

```bash
docker logs goswift-web --tail=200
```

---

## 17. Create GitHub Actions Secrets

In GitHub:

1. Open repository.
2. Go to `Settings`.
3. Open `Secrets and variables`.
4. Open `Actions`.
5. Add these repository secrets:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
ECR_REPOSITORY
EC2_HOST
EC2_USER
EC2_SSH_PRIVATE_KEY
```

Recommended values:

```text
AWS_REGION=us-east-1
ECR_REPOSITORY=goswift-backend
EC2_HOST=YOUR_ELASTIC_IP
EC2_USER=ubuntu
```

For `EC2_SSH_PRIVATE_KEY`, use the private key content that GitHub Actions can use for SSH.

If your AWS key file is `.pem`, paste the full file content:

```text
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
```

If you only have `.ppk`, convert it back/export it from PuTTYgen as an OpenSSH private key.

What each secret means:

```text
AWS_ACCESS_KEY_ID
  IAM access key used by GitHub Actions to authenticate to AWS.

AWS_SECRET_ACCESS_KEY
  Secret half of the IAM access key.

AWS_REGION
  The AWS region used for ECR and deploy commands.

ECR_REPOSITORY
  The ECR repository name only: goswift-backend.

EC2_HOST
  The Elastic IP of the EC2 instance.

EC2_USER
  Use ubuntu for Ubuntu Server 24.04 LTS.

EC2_SSH_PRIVATE_KEY
  The private key GitHub Actions uses to SSH into EC2.
```

Recommended values:

```text
AWS_REGION=us-east-1
ECR_REPOSITORY=goswift-backend
EC2_HOST=YOUR_ELASTIC_IP
EC2_USER=ubuntu
```

Important distinction:

- GitHub secrets are for CI/CD.
- `.env.production` is for the running Django app.
- Do not put Django `SECRET_KEY`, DB password, or Gmail password into GitHub unless the workflow explicitly needs them. This workflow does not.

---

## 18. Create GitHub Actions Variable

In GitHub:

1. Go to `Settings`.
2. Open `Secrets and variables`.
3. Open `Actions`.
4. Go to `Variables`.
5. Add:

```text
DEPLOY_PATH=/opt/goswift-backend
```

Why this is a variable instead of a secret:

- It is not sensitive.
- It lets the workflow know where the deployment files live on EC2.
- If the path ever changes, you can update the GitHub variable without editing YAML.

---

## 19. First Deployment

Commit and push the deployment files to `main`.

Before pushing, check that no secret files are staged:

```bash
git status
```

These files must not be committed:

```text
.env
.env.production
*.pem
*.ppk
firebase-credentials.json
```

The production env file belongs only on EC2:

```text
/opt/goswift-backend/.env.production
```

GitHub Actions will:

1. Build the Docker image.
2. Push the image to ECR.
3. Copy deployment files to EC2.
4. SSH into EC2.
5. Pull the new image.
6. Start the production containers.

You can also trigger manually:

1. Open GitHub repository.
2. Go to `Actions`.
3. Select `Deploy GoSwift Backend`.
4. Click `Run workflow`.
5. Choose `main`.

The workflow deploys the exact commit image using the Git SHA tag, then also pushes `latest`.

Expected first-deploy behavior:

- Docker build can take several minutes.
- First ECR push can take a while.
- First EC2 image pull can take a while.
- The `web` container runs migrations and collectstatic on startup.
- Celery worker and beat wait for Redis and database availability through the same env settings.

---

## 20. Verify Containers On EC2

After the workflow succeeds, SSH into EC2 and run:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Expected containers:

```text
goswift-nginx
goswift-web
goswift-celery-worker
goswift-celery-beat
goswift-redis
```

Check logs:

```bash
docker logs goswift-web --tail=100
docker logs goswift-celery-worker --tail=100
docker logs goswift-celery-beat --tail=100
docker logs goswift-nginx --tail=100
```

Healthy signs:

- `goswift-web` is up and not restarting.
- Daphne starts successfully.
- migrations complete or say no migrations to apply.
- collectstatic completes.
- `goswift-celery-worker` starts and imports Django tasks.
- `goswift-celery-beat` starts the scheduler.
- `goswift-redis` says it is ready to accept connections.
- `goswift-nginx` stays running.

If a container is restarting repeatedly:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker logs CONTAINER_NAME --tail=300
```

---

## 21. Verify API Health

From your local computer browser:

```text
http://YOUR_ELASTIC_IP/health/
```

From EC2:

```bash
curl -i http://localhost/health/
```

If the health endpoint responds, Nginx and Django are connected.

If local EC2 health works but browser health does not:

- Check EC2 security group allows inbound port `80`.
- Check Elastic IP is attached to the correct EC2 instance.
- Check Nginx container is running.

If both fail:

- Check `goswift-nginx` logs.
- Check `goswift-web` logs.
- Check whether the web container is restarting.

---

## 22. Create Django Superuser

Run:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Use this account to verify:

```text
http://YOUR_ELASTIC_IP/admin/
```

If the command cannot connect to the container:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker logs goswift-web --tail=200
```

---

## 23. Verify Static Files

The `web` container runs `collectstatic` during startup.

Nginx serves static files from the shared Docker volume:

```text
static_volume:/app/staticfiles
```

If Swagger/admin static files look broken, run:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
docker compose --env-file .env.production -f docker-compose.prod.yml restart nginx
```

Then open:

```text
http://YOUR_ELASTIC_IP/admin/
http://YOUR_ELASTIC_IP/api/docs/
```

If CSS/JS still looks broken:

- refresh browser with cache disabled
- check `goswift-nginx` logs
- confirm `static_volume` is mounted for both web and nginx
- confirm `collectstatic` completed in web logs

---

## 24. Verify S3 Media Uploads

After deployment:

1. Use an endpoint that uploads an image or file.
2. Confirm the file appears in the S3 bucket.
3. Confirm API responses return media URLs.

If upload fails, check:

```bash
docker logs goswift-web --tail=200
aws sts get-caller-identity
```

Also confirm the EC2 IAM role has permission for the S3 bucket.

Good signs:

- upload endpoint returns success
- file appears inside the S3 bucket
- API response includes a media URL
- Django logs do not show `AccessDenied`

If upload fails with `AccessDenied`:

- confirm EC2 role is attached
- confirm role has S3 permission
- confirm bucket name is correct
- confirm bucket region matches `AWS_S3_REGION_NAME`

If upload succeeds but the media URL cannot be opened:

- remember the bucket is private
- signed URLs may expire
- decide later whether some public media should use CloudFront or public bucket policy

---

## 25. Verify Redis, Celery, And WebSockets

Redis:

```bash
docker exec -it goswift-redis redis-cli ping
```

Expected:

```text
PONG
```

Celery worker:

```bash
docker logs goswift-celery-worker --tail=100
```

Celery beat:

```bash
docker logs goswift-celery-beat --tail=100
```

WebSockets are proxied through Nginx on port `80`. Use the Elastic IP in WebSocket URLs until a domain is added.

Example shape:

```text
ws://YOUR_ELASTIC_IP/ws/...
```

Use the exact WebSocket paths already defined by the service apps.

Redis should not be exposed publicly. Do not open `6379` in the EC2 security group.

Celery worker should use:

```text
celery -A core worker --loglevel=INFO
```

Celery beat should use:

```text
celery -A core beat --loglevel=INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

If Celery starts but tasks do not execute:

- confirm tasks are being queued
- check worker logs for import errors
- confirm Redis is reachable with `redis-cli ping`
- confirm migrations for `django_celery_beat` are applied

For WebSockets before SSL:

```text
Use ws://YOUR_ELASTIC_IP/...
Do not use wss:// yet.
```

Use `wss://` only after HTTPS/SSL is added.

---

## 26. Common Operations

Restart all containers:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml restart
```

Stop all containers:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml down
```

Start all containers:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

Open Django shell:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml exec web python manage.py shell
```

Run migrations manually:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml exec web python manage.py migrate
```

The current compose setup already runs migrations automatically on `web` startup.

Follow live logs:

```bash
docker logs -f goswift-web
docker logs -f goswift-celery-worker
docker logs -f goswift-nginx
```

Check disk usage:

```bash
df -h
docker system df
```

Remove unused Docker images:

```bash
docker image prune -f
```

Edit production env:

```bash
nano /opt/goswift-backend/.env.production
```

Apply env changes:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

---

## 27. Troubleshooting

If GitHub Actions fails at ECR login:

- Check `AWS_ACCESS_KEY_ID`.
- Check `AWS_SECRET_ACCESS_KEY`.
- Check `AWS_REGION`.
- Check IAM permissions.

If GitHub Actions fails at SSH:

- Check `EC2_HOST`.
- Check `EC2_USER`.
- Check `EC2_SSH_PRIVATE_KEY`.
- Check EC2 security group allows SSH from GitHub Actions runners. If needed, temporarily allow SSH from `0.0.0.0/0`, deploy, then restrict again for manual access.

If deployment fails with `.env.production` missing:

- Create `/opt/goswift-backend/.env.production` manually on EC2.
- The CI/CD workflow intentionally does not upload secrets.

If `web` cannot connect to database:

- Check `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`.
- Check RDS security group allows inbound `5432` from the EC2 security group.
- Check RDS and EC2 are in reachable VPC/subnets.

If media upload fails:

- Check `USE_S3_MEDIA=True`.
- Check `AWS_STORAGE_BUCKET_NAME`.
- Check `AWS_S3_REGION_NAME`.
- Check EC2 IAM role permissions.

If WebSocket fails:

- Check Nginx is running.
- Check client uses `ws://YOUR_ELASTIC_IP/...`.
- Check `WEBSOCKET_ALLOWED_ORIGINS` includes `http://YOUR_ELASTIC_IP` and `ws://YOUR_ELASTIC_IP`.
- Check the target route exists in `core/asgi.py` and service routing files.

If Nginx returns `502 Bad Gateway`:

- Check `goswift-web` is running.
- Check Daphne started correctly.
- Check Nginx upstream points to `web:8000`.
- Check logs:

```bash
docker logs goswift-nginx --tail=200
docker logs goswift-web --tail=200
```

If deployment says Docker cannot pull the image:

- Check EC2 IAM role has ECR read permission.
- Check workflow logged in to ECR.
- Check ECR repository exists in the same region.
- Check `APP_IMAGE` in workflow points to the pushed image URI.

If the server runs out of disk:

```bash
df -h
docker system df
docker image prune -f
```

If it still has no space, increase the EC2 EBS volume size from AWS Console and expand the filesystem.

If the app works on EC2 but not from browser:

- check Elastic IP
- check security group port `80`
- check local ISP/firewall
- check Nginx logs

---

## 28. Later Domain And SSL Phase

When you buy a domain later:

1. Point domain DNS `A` record to the Elastic IP.
2. Add the domain to:

```env
ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS
WEBSOCKET_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS
BASE_URL
FRONTEND_URL
```

3. Update Nginx for the domain.
4. Add HTTPS with Certbot or an AWS load balancer.
5. Use:

```text
https://api.yourdomain.com
wss://api.yourdomain.com
```

Do not remove the Elastic IP until DNS and SSL are verified.

Recommended future API domain pattern:

```text
api.yourdomain.com
```

Example DNS:

```text
Type: A
Name: api
Value: YOUR_ELASTIC_IP
TTL: 300
```

After DNS works, update production env:

```env
ALLOWED_HOSTS=api.yourdomain.com,YOUR_ELASTIC_IP,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=https://YOUR_FRONTEND_DOMAIN
WEBSOCKET_ALLOWED_ORIGINS=https://YOUR_FRONTEND_DOMAIN,wss://YOUR_FRONTEND_DOMAIN
CSRF_TRUSTED_ORIGINS=https://api.yourdomain.com
BASE_URL=https://api.yourdomain.com/
FRONTEND_URL=https://YOUR_FRONTEND_DOMAIN
```

Then restart:

```bash
cd /opt/goswift-backend
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

SSL options later:

- Certbot directly on EC2 with Nginx adjusted for certificates.
- AWS Application Load Balancer with ACM certificate.
- CloudFront in front of the backend if the architecture grows.

After SSL, frontend WebSocket URLs must use:

```text
wss://api.yourdomain.com/ws/...
```

Before SSL, frontend WebSocket URLs should use:

```text
ws://YOUR_ELASTIC_IP/ws/...
```

---

## 29. Deployment Checklist

AWS resources:

- [ ] AWS region selected and used consistently
- [ ] IAM access key created for GitHub Actions
- [ ] ECR repository `goswift-backend` created
- [ ] S3 media bucket created
- [ ] RDS PostgreSQL database created
- [ ] EC2 instance created
- [ ] Elastic IP allocated and attached
- [ ] EC2 IAM role created and attached
- [ ] EC2 security group created during EC2 launch
- [ ] EC2 security group allows SSH from your IP and HTTP from public
- [ ] RDS security group allows PostgreSQL from EC2 security group

EC2 setup:

- [ ] PuTTY login works
- [ ] Docker installed
- [ ] Docker Compose plugin works
- [ ] AWS CLI available
- [ ] `aws sts get-caller-identity` works from EC2
- [ ] `/opt/goswift-backend/` created
- [ ] `/opt/goswift-backend/.env.production` created
- [ ] `.env.production` has permission `600`
- [ ] Gmail app password configured

GitHub setup:

- [ ] `AWS_ACCESS_KEY_ID` secret added
- [ ] `AWS_SECRET_ACCESS_KEY` secret added
- [ ] `AWS_REGION` secret added
- [ ] `ECR_REPOSITORY` secret added as `goswift-backend`
- [ ] `EC2_HOST` secret added as Elastic IP
- [ ] `EC2_USER` secret added as `ubuntu`
- [ ] `EC2_SSH_PRIVATE_KEY` secret added in OpenSSH/PEM format
- [ ] GitHub variable `DEPLOY_PATH=/opt/goswift-backend` added

Application verification:

- [ ] GitHub Actions workflow run completed successfully
- [ ] `docker compose ps` shows all containers running
- [ ] `http://YOUR_ELASTIC_IP/health/` returns success
- [ ] Django `manage.py check` passes on EC2
- [ ] Migrations applied
- [ ] Superuser created
- [ ] Admin opens and static files load
- [ ] Swagger opens and static files load
- [ ] S3 media upload tested
- [ ] Gmail SMTP/OTP tested
- [ ] Redis ping returns `PONG`
- [ ] Celery worker logs checked
- [ ] Celery beat logs checked
- [ ] WebSocket route tested with `ws://`

Security follow-ups after first successful deploy:

- [ ] Restrict SSH to your current public IP
- [ ] Replace broad S3 permission with bucket-specific policy
- [ ] Add ECR lifecycle policy
- [ ] Add domain when purchased
- [ ] Add SSL/HTTPS
- [ ] Switch WebSockets from `ws://` to `wss://`
