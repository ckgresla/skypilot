# When using pod@namespace@context, rsync passes args as: {us} -l pod@namespace context
# We need to split the pod@namespace into pod and namespace
shift
pod_at_namespace=$1
pod=$(echo $pod_at_namespace | cut -d@ -f1)
namespace=$(echo $pod_at_namespace | cut -d@ -f2)
shift
context=$1
shift
context_lower=$(echo "$context" | tr '[:upper:]' '[:lower:]')
if [ "$context_lower" = "none" ]; then
    kubectl exec -i $pod -n $namespace -- "$@"
else
    kubectl exec -i $pod -n $namespace --context=$context -- "$@"
fi