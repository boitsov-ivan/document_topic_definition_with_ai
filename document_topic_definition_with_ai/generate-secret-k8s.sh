#!/bin/bash

cat > k8s/secret.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: document-analyzer
type: Opaque
stringData:
EOF

while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    
    if [[ "$line" == *"="* ]]; then
        key=$(echo "$line" | cut -d'=' -f1 | xargs)
        value=$(echo "$line" | cut -d'=' -f2- | xargs)
        
        value="${value%\"}"
        value="${value#\"}"
        
        echo "  $key: \"$value\"" >> k8s/secret.yaml
    fi
done < .env

echo "secret.yaml создан!"