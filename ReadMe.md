# CI/CD Pipeline: GitHub Actions, Amazon ECR, and EC2

## Overview

This project demonstrates an end-to-end CI/CD pipeline using GitHub Actions, Amazon ECR, Docker, and Amazon EC2.

Whenever code is pushed to the `main` branch, GitHub Actions builds a Docker image, pushes it to Amazon ECR, connects to EC2 using SSH, pulls the image, and deploys the container.

## Architecture

1. Developer pushes code to GitHub.
2. GitHub Actions checks out the source code.
3. GitHub Actions authenticates to AWS using IAM access keys.
4. Docker image is built and pushed to Amazon ECR.
5. GitHub Actions connects to EC2 using an SSH private key.
6. EC2 pulls the image from ECR and runs the container.

## Prerequisites

- AWS account
- EC2 Linux instance
- GitHub repository with a `Dockerfile`
- Docker installed on the EC2 instance
- SSH key pair configured for EC2
- AWS IAM user with permissions to push images to ECR
- GitHub Actions enabled

## Step 1: Create an ECR Repository Through the AWS Console

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/).
2. Search for **Amazon ECR**.
3. Open **Private registry → Repositories**.
4. Click **Create repository**.
5. Select **Private**.
6. Enter the repository name: `my-demo-app`.
7. Keep the remaining settings at their defaults for this demo.
8. Click **Create repository**.
9. Open the repository and copy its URI.

Example URI:

`123456789012.dkr.ecr.ap-south-1.amazonaws.com/my-demo-app`

Use the actual URI from your AWS account.

## Step 2: Create an IAM User for GitHub Actions

1. Open the **IAM Console**.
2. Navigate to **Users → Create user**.
3. Enter a username, such as `github-actions-ecr-user`.
4. Create the user.
5. Grant the user only the permissions needed to authenticate and push images to your ECR repository.
6. Open the user and navigate to **Security credentials**.
7. Select **Create access key**.
8. Choose the appropriate use case for your environment and create the access key.
9. Copy the access key ID and secret access key securely.

Do not share these credentials or commit them to your repository.

For tighter security, use a custom IAM policy scoped to your specific ECR repository instead of granting broad administrator access.

## Step 3: Configure GitHub Secrets

Navigate to:

**GitHub Repository → Settings → Secrets and variables → Actions → New repository secret**

Create these secrets:

| Secret name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user's access key ID |
| `AWS_SECRET_ACCESS_KEY` | IAM user's secret access key |
| `SSH_PRIVATE_KEY` | EC2 SSH private key contents |
| `EC2_HOST` | EC2 public IP address or DNS name |
| `EC2_USER` | SSH username, such as `ubuntu` or `ec2-user` |

## Step 4: Configure EC2 to Pull Images from ECR

The EC2 instance needs permission to pull images from your private ECR repository.

1. Open the **EC2 Console**.
2. Select your instance.
3. Navigate to **Actions → Security → Modify IAM role**.
4. Attach an IAM role with the `AmazonEC2ContainerRegistryPullOnly` managed policy, or an equivalent least-privilege policy.
5. Save the changes.

Ensure the instance has network access to ECR and its S3-backed image layers. Docker must also be installed and running.

## Step 5: Configure the GitHub Actions Workflow

Create `.github/workflows/deploy.yml` in your repository:

```yaml
name: Build and Deploy to EC2

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

env:
  AWS_REGION: ap-south-1
  ECR_REPOSITORY: my-demo-app

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t "$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" .
          docker push "$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"

      - name: Prepare SSH private key
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
        run: |
          install -m 700 -d ~/.ssh
          printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keygen -y -f ~/.ssh/deploy_key > /dev/null

      - name: Configure EC2 host key
        env:
          EC2_HOST: ${{ secrets.EC2_HOST }}
        run: |
          ssh-keyscan -H "$EC2_HOST" >> ~/.ssh/known_hosts
          chmod 600 ~/.ssh/known_hosts

      - name: Deploy to EC2
        env:
          EC2_HOST: ${{ secrets.EC2_HOST }}
          EC2_USER: ${{ secrets.EC2_USER }}
          REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          ssh -i ~/.ssh/deploy_key \
            -o IdentitiesOnly=yes \
            "$EC2_USER@$EC2_HOST" \
            "aws ecr get-login-password --region '$AWS_REGION' | docker login --username AWS --password-stdin '$REGISTRY' &&
             docker pull '$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG' &&
             (docker stop my-demo-app || true) &&
             (docker rm my-demo-app || true) &&
             docker run -d --name my-demo-app --restart unless-stopped -p 80:80 '$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG'"
```

### Important configuration notes

- Change `AWS_REGION` to your ECR repository's region.
- Change `ECR_REPOSITORY` if you used a different repository name.
- The example assumes your application listens on port `80` inside the container. Adjust the port mapping if necessary.
- The EC2 instance role must have ECR pull permissions.
- The EC2 SSH user must have permission to run Docker commands.
- The example assumes the EC2 instance has the AWS CLI installed.

## Step 6: Verify the Deployment

### Verify the image in ECR

1. Open the AWS Console.
2. Navigate to **Amazon ECR → Repositories → my-demo-app**.
3. Select **Images**.
4. Confirm that an image tagged with the GitHub commit SHA has been uploaded.

### Verify the running container

Connect to EC2 and execute:

```bash
docker ps
docker logs my-demo-app
```

If your application serves HTTP on port 80, open the EC2 public IP address in your browser. Ensure the EC2 security group permits the intended HTTP traffic.

## Troubleshooting

| Error | Possible cause |
|---|---|
| `AccessDenied` during image push | IAM user lacks ECR permissions |
| `no basic auth credentials` | Docker is not logged in to ECR |
| `Permission denied (publickey)` | Incorrect SSH key or username |
| `Connection timed out` | Security group or networking issue |
| `Cannot connect to the Docker daemon` | Docker is not running |
| Container exits | Application configuration or port mismatch |

## Security Best Practices

- Store AWS access keys and SSH private keys only in GitHub Secrets.
- Never print secrets in workflow logs.
- Give the IAM user only the permissions required for ECR image pushes.
- Rotate and revoke exposed credentials promptly.
- Avoid opening SSH to the entire internet where possible.
- Verify the EC2 host key through a trusted channel; `ssh-keyscan` alone does not authenticate the server.
- Use immutable image tags, such as Git commit SHAs.
- Consider migrating to GitHub OIDC in the future to avoid long-lived AWS access keys.

## Learning Outcomes

- Creating an ECR repository through the AWS Console
- Configuring IAM access keys and GitHub Secrets
- Building and pushing Docker images through GitHub Actions
- Using SSH private-key authentication
- Pulling private ECR images on EC2
- Automating container deployment through CI/CD

## Conclusion

This project demonstrates a basic automated deployment pipeline using GitHub Actions, Amazon ECR, Docker, and EC2. It builds and publishes a container image and deploys that image to EC2 over SSH whenever code is pushed to the `main` branch.
