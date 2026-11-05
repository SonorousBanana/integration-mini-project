# Deploying Visit Counter to Kubernetes

The commands below assume `kubectl` is configured for the target cluster and are
run from the repository root in PowerShell.

## Before deploying

1. Build the image from the app directory and push it to a registry reachable by
   the cluster:

   ```powershell
   docker build -t <registry-host>/<username>/visit-counter:1.0.0 .\visit-counter-app
   docker push <registry-host>/<username>/visit-counter:1.0.0
   ```

2. Edit `kubernetes-enviroment\frontend\web-app-deployment.yml` and replace
   `visit-counter:1.0.0` with the full image name used above. Do this before
   using either deployment method.

3. If the image is in a private registry, create the pull secret in the same
   namespace as the app. The Deployment already refers to a Secret named
   `registry-credentials`:

   ```powershell
   kubectl create namespace visit-counter
   kubectl create secret docker-registry registry-credentials `
     --namespace=visit-counter `
     --docker-server=<registry-host> `
     --docker-username=<username> `
     --docker-password=<access-token>
   ```

   Use a registry access token with only the required pull permissions. Avoid
   committing credentials to the repository or putting real tokens in YAML.
   For a public image, remove the `imagePullSecrets` entry from the Deployment.

4. The Redis StatefulSet requests a 1Gi persistent volume. Verify that the
   cluster has a default StorageClass, or set `storageClassName` in
   `kubernetes-enviroment\redis\redis-sts.yml` to a class available in your
   cluster.

## Deploy with Kustomize

From the repository root:

```powershell
kubectl apply -k .\kubernetes-enviroment
kubectl get pods,services,pvc -n visit-counter
```

The Kustomization applies the namespace, ConfigMap, Redis Service and StatefulSet,
and web app Service and Deployment. It deliberately does not apply the registry
Secret template or the Contour HTTPProxy:

- Create the registry Secret as described above only when needed.
- The HTTPProxy requires Contour and its CRD to be installed in the cluster.
  After Contour is installed, change the example hostname in
  `routes\web-app-httpproxy.yml` to a DNS name routed to Contour/Envoy, then
  apply it:

  ```powershell
  kubectl apply -f .\kubernetes-enviroment\routes\web-app-httpproxy.yml
  ```

## Deploy without Kustomize

From the repository root, apply the manifests in dependency order:

```powershell
kubectl apply -f .\kubernetes-enviroment\namespace\namespace.yml
kubectl apply -f .\kubernetes-enviroment\configmaps\web-app-configmap.yml
kubectl apply -f .\kubernetes-enviroment\redis\redis-svc.yml
kubectl apply -f .\kubernetes-enviroment\redis\redis-sts.yml
kubectl apply -f .\kubernetes-enviroment\frontend\web-app-svc.yml
kubectl apply -f .\kubernetes-enviroment\frontend\web-app-deployment.yml
kubectl get pods,services,pvc -n visit-counter
```

Create the registry Secret first if the image is private. Apply the HTTPProxy
separately after installing Contour and setting its hostname, as described
above.

## Access the app

Without an ingress controller, use port-forwarding:

```powershell
kubectl port-forward -n visit-counter service/web-app 8000:8000
```

Then open `http://localhost:8000`. If using Contour, access the hostname configured
in the HTTPProxy instead.

## Remove the deployment

```powershell
kubectl delete -k .\kubernetes-enviroment
```

Deleting a StatefulSet does not necessarily delete its PersistentVolumeClaim.
Inspect the PVC before deleting it; deleting the claim may permanently delete
the Redis data, depending on the StorageClass reclaim policy.
