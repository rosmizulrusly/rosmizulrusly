# Gold Trading Platform - Deployment Guide

## Prerequisites

### Required Software
- Node.js 18+ and npm 9+
- MongoDB 6.0+
- Redis 7.0+
- Docker and Docker Compose (optional but recommended)
- Git
- Ethereum wallet with testnet ETH (for blockchain deployment)

### Required Services
- Cloud hosting account (AWS/GCP/Azure)
- Domain name and SSL certificate
- Email service (SMTP)
- SMS service (Twilio)
- Payment gateway accounts (Stripe, crypto providers)
- KYC/AML service accounts (Onfido, ComplyAdvantage)

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/rosmizulrusly/rosmizulrusly.git
cd rosmizulrusly
```

### 2. Install Dependencies

```bash
# Backend
cd backend
npm install

# Frontend (if applicable)
cd ../frontend
npm install

# Smart Contracts
cd ../smart-contracts
npm install
```

### 3. Environment Configuration

```bash
# Copy example environment file
cp config/.env.example config/.env

# Edit with your values
nano config/.env
```

Required environment variables:
- `MONGODB_URI` - MongoDB connection string
- `REDIS_URL` - Redis connection string
- `JWT_SECRET` - Secret for JWT tokens
- `BLOCKCHAIN_RPC_URL` - Ethereum RPC endpoint
- API keys for external services

### 4. Database Setup

```bash
# Start MongoDB
sudo systemctl start mongod

# Start Redis
sudo systemctl start redis

# Run migrations
npm run migrate

# Seed initial data (optional)
npm run seed
```

### 5. Smart Contract Deployment

```bash
cd smart-contracts

# Compile contracts
npx hardhat compile

# Deploy to testnet
npx hardhat run scripts/deploy.js --network sepolia

# Save contract address to .env
echo "GOLD_TRADING_CONTRACT_ADDRESS=<deployed-address>" >> ../config/.env
```

### 6. Start Development Server

```bash
cd backend
npm run dev

# Server should start on http://localhost:3000
```

## Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Docker Compose File

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    ports:
      - "3000:3000"
    depends_on:
      - mongodb
      - redis
    environment:
      NODE_ENV: production
      MONGODB_URI: mongodb://admin:${MONGO_PASSWORD}@mongodb:27017/gold-trading
      REDIS_URL: redis://redis:6379
    volumes:
      - ./backend:/app
      - /app/node_modules

volumes:
  mongodb_data:
  redis_data:
```

## Production Deployment

### AWS Deployment

#### 1. Infrastructure Setup

```bash
# Create VPC and subnets
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# Create security groups
aws ec2 create-security-group \
  --group-name gold-trading-api \
  --description "Security group for API servers"

# Launch EC2 instances
aws ec2 run-instances \
  --image-id ami-xxxxx \
  --instance-type t3.medium \
  --key-name your-key \
  --security-group-ids sg-xxxxx
```

#### 2. Database Setup

```bash
# Create DocumentDB cluster (MongoDB compatible)
aws docdb create-db-cluster \
  --db-cluster-identifier gold-trading-cluster \
  --engine docdb \
  --master-username admin \
  --master-user-password <password>

# Create ElastiCache Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id gold-trading-cache \
  --engine redis \
  --cache-node-type cache.t3.medium \
  --num-cache-nodes 1
```

#### 3. Load Balancer Setup

```bash
# Create Application Load Balancer
aws elbv2 create-load-balancer \
  --name gold-trading-alb \
  --subnets subnet-xxxxx subnet-yyyyy \
  --security-groups sg-xxxxx

# Create target group
aws elbv2 create-target-group \
  --name gold-trading-targets \
  --protocol HTTP \
  --port 3000 \
  --vpc-id vpc-xxxxx
```

#### 4. Application Deployment

```bash
# SSH to EC2 instance
ssh -i your-key.pem ec2-user@<instance-ip>

# Clone repository
git clone https://github.com/rosmizulrusly/rosmizulrusly.git
cd rosmizulrusly/backend

# Install dependencies
npm ci --production

# Set environment variables
export NODE_ENV=production
export MONGODB_URI=<docdb-connection-string>
export REDIS_URL=<elasticache-endpoint>

# Start with PM2
npm install -g pm2
pm2 start server.js --name gold-trading-api
pm2 startup
pm2 save
```

### Using Kubernetes

#### 1. Create Kubernetes Manifests

**deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gold-trading-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gold-trading-api
  template:
    metadata:
      labels:
        app: gold-trading-api
    spec:
      containers:
      - name: api
        image: your-registry/gold-trading-api:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: "production"
        - name: MONGODB_URI
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: mongodb-uri
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**service.yaml**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: gold-trading-api
spec:
  selector:
    app: gold-trading-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 3000
  type: LoadBalancer
```

#### 2. Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace gold-trading

# Create secrets
kubectl create secret generic app-secrets \
  --from-literal=mongodb-uri=<connection-string> \
  --from-literal=redis-url=<redis-url> \
  --from-literal=jwt-secret=<jwt-secret> \
  -n gold-trading

# Apply manifests
kubectl apply -f deployment.yaml -n gold-trading
kubectl apply -f service.yaml -n gold-trading

# Check deployment status
kubectl get pods -n gold-trading
kubectl get svc -n gold-trading

# View logs
kubectl logs -f deployment/gold-trading-api -n gold-trading
```

## CI/CD Pipeline

### GitHub Actions

**.github/workflows/deploy.yml**
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm test

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -t gold-trading-api:${{ github.sha }} .
      - name: Push to registry
        run: |
          docker tag gold-trading-api:${{ github.sha }} \
            ${{ secrets.DOCKER_REGISTRY }}/gold-trading-api:latest
          docker push ${{ secrets.DOCKER_REGISTRY }}/gold-trading-api:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/gold-trading-api \
            api=${{ secrets.DOCKER_REGISTRY }}/gold-trading-api:latest \
            -n gold-trading
```

## Monitoring Setup

### DataDog Agent

```bash
# Install DataDog agent
DD_AGENT_MAJOR_VERSION=7 \
DD_API_KEY=<your-api-key> \
DD_SITE="datadoghq.com" \
bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh)"

# Configure application monitoring
echo "
logs_enabled: true
apm_config:
  enabled: true
" >> /etc/datadog-agent/datadog.yaml

# Restart agent
sudo systemctl restart datadog-agent
```

### Health Check Endpoints

Add to your Express app:

```javascript
// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date(),
    uptime: process.uptime()
  });
});

// Readiness check
app.get('/ready', async (req, res) => {
  try {
    await mongoose.connection.db.admin().ping();
    await redisClient.ping();
    res.status(200).json({ status: 'ready' });
  } catch (error) {
    res.status(503).json({ status: 'not ready', error: error.message });
  }
});
```

## SSL/TLS Configuration

### Using Let's Encrypt with Nginx

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.goldtrading.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.goldtrading.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.goldtrading.com;

    ssl_certificate /etc/letsencrypt/live/api.goldtrading.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.goldtrading.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Backup Strategy

### Automated Database Backups

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/mongodb"

# MongoDB backup
mongodump --uri="$MONGODB_URI" --out="$BACKUP_DIR/$DATE"

# Compress backup
tar -czf "$BACKUP_DIR/$DATE.tar.gz" "$BACKUP_DIR/$DATE"
rm -rf "$BACKUP_DIR/$DATE"

# Upload to S3
aws s3 cp "$BACKUP_DIR/$DATE.tar.gz" s3://gold-trading-backups/mongodb/

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

# Cron job (daily at 2 AM)
# 0 2 * * * /path/to/backup.sh
```

## Security Checklist

- [ ] Environment variables secured (not in code)
- [ ] SSL/TLS certificates installed
- [ ] Firewall rules configured
- [ ] Database access restricted to application servers
- [ ] API rate limiting enabled
- [ ] CORS properly configured
- [ ] Security headers implemented (Helmet.js)
- [ ] Regular security updates applied
- [ ] Sensitive data encrypted at rest
- [ ] Monitoring and alerting configured
- [ ] Backup and disaster recovery tested

## Troubleshooting

### Common Issues

**1. Database Connection Failed**
```bash
# Check MongoDB status
sudo systemctl status mongod

# Check connection string
echo $MONGODB_URI

# Test connection
mongo "$MONGODB_URI"
```

**2. Redis Connection Failed**
```bash
# Check Redis status
sudo systemctl status redis

# Test connection
redis-cli ping
```

**3. High Memory Usage**
```bash
# Check Node.js memory
pm2 monit

# Restart application
pm2 restart gold-trading-api
```

## Rollback Procedure

```bash
# Kubernetes rollback
kubectl rollout undo deployment/gold-trading-api -n gold-trading

# PM2 rollback
pm2 stop gold-trading-api
git checkout <previous-commit>
npm install
pm2 start server.js --name gold-trading-api
```

## Support

For deployment support:
- Email: devops@goldtrading.com
- Slack: #gold-trading-ops
- Documentation: https://docs.goldtrading.com/deployment
