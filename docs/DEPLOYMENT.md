# Deployment Guide

This document provides step-by-step instructions for deploying the Social Flood API in various environments.

## Prerequisites

Before deploying the Social Flood API, ensure you have the following:

- Docker and Docker Compose (for local and container-based deployments)
- Kubernetes cluster (for production deployments)
- Google API credentials (see [GOOGLE_SERVICES.md](GOOGLE_SERVICES.md))
- Redis instance (optional, for caching and rate limiting)
- PostgreSQL database (optional, for persistent storage)

## Local Development Deployment

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/social-flood.git
cd social-flood
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit the `.env` file with your configuration:

```
# API settings
API_KEYS=your_api_key_1,your_api_key_2
ENABLE_API_KEY_AUTH=true

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_TIMEFRAME=3600

# Caching
ENABLE_CACHE=true
CACHE_TTL=3600
REDIS_URL=redis://localhost:6379/0

# Application settings
DEBUG=true
ENVIRONMENT=development
PROJECT_NAME=Social Flood
VERSION=1.0.0
DESCRIPTION=API for social media data aggregation and analysis
```

### 3. Build and Run with Docker Compose

```bash
docker-compose up -d
```

This will start the following services:
- Social Flood API on port 8000
- Redis on port 6379 (if configured)
- PostgreSQL on port 5432 (if configured)

### 4. Verify Deployment

```bash
curl http://localhost:8000/health
```

You should see a response like:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "timestamp": 1622548800.123456
}
```

## Production Deployment with Docker

### 1. Build the Docker Image

```bash
docker build -t social-flood:1.0.0 .
```

### 2. Run the Container

```bash
docker run -d \
  --name social-flood \
  -p 8000:8000 \
  -e API_KEYS=your_api_key_1,your_api_key_2 \
  -e ENABLE_API_KEY_AUTH=true \
  -e RATE_LIMIT_ENABLED=true \
  -e RATE_LIMIT_REQUESTS=100 \
  -e RATE_LIMIT_TIMEFRAME=3600 \
  -e ENABLE_CACHE=true \
  -e CACHE_TTL=3600 \
  -e REDIS_URL=redis://redis:6379/0 \
  -e DEBUG=false \
  -e ENVIRONMENT=production \
  -e PROJECT_NAME="Social Flood" \
  -e VERSION=1.0.0 \
  -e DESCRIPTION="API for social media data aggregation and analysis" \
  social-flood:1.0.0
```

## Production Deployment with Kubernetes

### 1. Create Kubernetes Secrets

```bash
kubectl create namespace social-flood

kubectl create secret generic social-flood-secrets \
  --namespace social-flood \
  --from-literal=API_KEYS=your_api_key_1,your_api_key_2 \
  --from-literal=REDIS_URL=redis://redis:6379/0 \
  --from-literal=DATABASE_URL=postgresql://user:password@postgres:5432/social_flood
```

### 2. Create Kubernetes ConfigMap

```bash
kubectl create configmap social-flood-config \
  --namespace social-flood \
  --from-literal=ENABLE_API_KEY_AUTH=true \
  --from-literal=RATE_LIMIT_ENABLED=true \
  --from-literal=RATE_LIMIT_REQUESTS=100 \
  --from-literal=RATE_LIMIT_TIMEFRAME=3600 \
  --from-literal=ENABLE_CACHE=true \
  --from-literal=CACHE_TTL=3600 \
  --from-literal=DEBUG=false \
  --from-literal=ENVIRONMENT=production \
  --from-literal=PROJECT_NAME="Social Flood" \
  --from-literal=VERSION=1.0.0 \
  --from-literal=DESCRIPTION="API for social media data aggregation and analysis"
```

### 3. Deploy Redis (if needed)

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: social-flood
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:6.2-alpine
        ports:
        - containerPort: 6379
        resources:
          limits:
            cpu: "0.5"
            memory: "512Mi"
          requests:
            cpu: "0.2"
            memory: "256Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: social-flood
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

Apply the Redis deployment:

```bash
kubectl apply -f redis-deployment.yaml
```

### 4. Deploy the Social Flood API

```yaml
# social-flood-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: social-flood
  namespace: social-flood
spec:
  replicas: 3
  selector:
    matchLabels:
      app: social-flood
  template:
    metadata:
      labels:
        app: social-flood
    spec:
      containers:
      - name: social-flood
        image: social-flood:1.0.0
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: social-flood-config
        - secretRef:
            name: social-flood-secrets
        resources:
          limits:
            cpu: "1"
            memory: "1Gi"
          requests:
            cpu: "0.5"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: social-flood
  namespace: social-flood
spec:
  selector:
    app: social-flood
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

Apply the Social Flood API deployment:

```bash
kubectl apply -f social-flood-deployment.yaml
```

### 5. Create Ingress for External Access

```yaml
# social-flood-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: social-flood-ingress
  namespace: social-flood
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.socialflood.com
    secretName: social-flood-tls
  rules:
  - host: api.socialflood.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: social-flood
            port:
              number: 80
```

Apply the Ingress:

```bash
kubectl apply -f social-flood-ingress.yaml
```

## Continuous Integration / Continuous Deployment (CI/CD)

### GitHub Actions Workflow Example

Create a file at `.github/workflows/deploy.yml`:

```yaml
name: Deploy Social Flood API

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    - name: Test with pytest
      run: |
        pytest --cov=app tests/

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v2
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v1
    - name: Login to DockerHub
      uses: docker/login-action@v1
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
    - name: Build and push
      uses: docker/build-push-action@v2
      with:
        context: .
        push: true
        tags: yourusername/social-flood:latest,yourusername/social-flood:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v2
    - name: Set up kubectl
      uses: azure/setup-kubectl@v1
    - name: Set Kubernetes context
      uses: azure/k8s-set-context@v1
      with:
        kubeconfig: ${{ secrets.KUBE_CONFIG }}
    - name: Update deployment image
      run: |
        kubectl set image deployment/social-flood social-flood=yourusername/social-flood:${{ github.sha }} -n social-flood
        kubectl rollout status deployment/social-flood -n social-flood
```

## Monitoring and Logging

### Prometheus and Grafana Setup

1. Install Prometheus Operator:

```bash
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/bundle.yaml
```

2. Create a ServiceMonitor for Social Flood API:

```yaml
# social-flood-service-monitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: social-flood
  namespace: social-flood
spec:
  selector:
    matchLabels:
      app: social-flood
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
```

Apply the ServiceMonitor:

```bash
kubectl apply -f social-flood-service-monitor.yaml
```

### ELK Stack for Logging

1. Install Elasticsearch, Logstash, and Kibana using Helm:

```bash
helm repo add elastic https://helm.elastic.co
helm repo update

helm install elasticsearch elastic/elasticsearch -n logging --create-namespace
helm install kibana elastic/kibana -n logging
helm install logstash elastic/logstash -n logging
```

2. Configure Filebeat to collect logs:

```yaml
# filebeat-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: filebeat-config
  namespace: logging
data:
  filebeat.yml: |-
    filebeat.inputs:
    - type: container
      paths:
        - /var/log/containers/social-flood-*.log
      processors:
        - add_kubernetes_metadata:
            host: ${NODE_NAME}
            matchers:
            - logs_path:
                logs_path: "/var/log/containers/"

    output.elasticsearch:
      hosts: ["elasticsearch-master:9200"]
```

Apply the ConfigMap:

```bash
kubectl apply -f filebeat-config.yaml
```

3. Deploy Filebeat:

```yaml
# filebeat-deployment.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: filebeat
  namespace: logging
spec:
  selector:
    matchLabels:
      app: filebeat
  template:
    metadata:
      labels:
        app: filebeat
    spec:
      serviceAccountName: filebeat
      containers:
      - name: filebeat
        image: docker.elastic.co/beats/filebeat:7.15.0
        args: ["-c", "/etc/filebeat.yml", "-e"]
        volumeMounts:
        - name: config
          mountPath: /etc/filebeat.yml
          subPath: filebeat.yml
        - name: varlibdockercontainers
          mountPath: /var/lib/docker/containers
          readOnly: true
        - name: varlog
          mountPath: /var/log
          readOnly: true
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
      volumes:
      - name: config
        configMap:
          name: filebeat-config
      - name: varlibdockercontainers
        hostPath:
          path: /var/lib/docker/containers
      - name: varlog
        hostPath:
          path: /var/log
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: filebeat
  namespace: logging
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: filebeat
rules:
- apiGroups: [""]
  resources:
  - namespaces
  - pods
  verbs:
  - get
  - list
  - watch
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: filebeat
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: filebeat
subjects:
- kind: ServiceAccount
  name: filebeat
  namespace: logging
```

Apply the Filebeat deployment:

```bash
kubectl apply -f filebeat-deployment.yaml
```

## Troubleshooting Deployment Issues

### Common Issues

1. **API not starting**:
   - Check logs: `kubectl logs deployment/social-flood -n social-flood`
   - Verify environment variables: `kubectl describe pod -l app=social-flood -n social-flood`

2. **Cannot connect to Redis**:
   - Check Redis service: `kubectl get svc redis -n social-flood`
   - Verify Redis is running: `kubectl get pods -l app=redis -n social-flood`

3. **API key authentication failing**:
   - Verify API keys in secrets: `kubectl get secret social-flood-secrets -n social-flood -o yaml`
   - Check `ENABLE_API_KEY_AUTH` setting in ConfigMap

4. **Health checks failing**:
   - Check health endpoint: `kubectl port-forward svc/social-flood 8000:80 -n social-flood` then `curl http://localhost:8000/health`
   - Verify dependencies are available (Redis, database)

### Deployment Checklist

- [ ] Environment variables configured correctly
- [ ] Secrets and ConfigMaps created
- [ ] Redis deployed and running (if used)
- [ ] Database deployed and running (if used)
- [ ] API deployment successful
- [ ] Service created and accessible
- [ ] Ingress configured correctly
- [ ] TLS certificates provisioned
- [ ] Monitoring and logging set up
