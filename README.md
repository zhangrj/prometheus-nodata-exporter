# prometheus-nodata-exporter
我们知道，prometheus会为所有的target生成一个`up`指标，可以使用这个指标来判断`exporter`的在线情况生成告警，一个最常见的场景是：
```yaml
- alert: exporter离线
  expr: up{job=~"process|node"} == 0
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "exporter离线"
    description: "exporter({{$labels.instance}})离线超过5分钟"
```
但是在某些特殊场景下，例如`Thanos/Cortex/Mimir`等架构中，`prometheus`承担的角色是`pull` exporter指标并`remote write`到远程端点。因此当某个`Prometheus`节点因为某些原因（如网络故障、`prometheus`节点本身故障等）离线，而无法向`Thanos/Cortex/Mimir`发送数据时（也即nodata场景），该节点所承载的监控数据（如`up{job="prometheus"`}等）将全部丢失，并且监控系统无法感知该事件。

在`prometheus`节点较少的情况下，我们可以通过枚举方法，配置`prometheus`的离线告警，例如：
```yaml
- alert: Prometheus离线
  expr: |
    absent(up{cluster="cluster1", job="prometheus"})
    or
    absent(up{cluster="cluster2", job="prometheus"})
    or
    absent(up{cluster="cluster3", job="prometheus"})
  for: 2m
  labels:
    severity: warning
  annotations:
    description: "prometheus节点{{$labels.cluster}}离线超过2分钟"
```
但该方法无法动态更新`prometheus`列表，随着`prometheus`节点数量的增加，表达式也随之变得非常非常长。

因此，我希望用一种更简单的方法解决指标nodata的告警问题，于是写了这个nodata exporter。

## 设计思路
1、以首次查询的结果初始化一个指标列表，例如：
```
up{cluster="cluster1", job="prometheus"}
up{cluster="cluster2", job="prometheus"}
up{cluster="cluster3", job="prometheus"}
```
2、生成对应的nodata指标，默认值为0，表示该指标有数据、在线：
```
nodata_up{cluster="cluster1", job="prometheus"} 0
nodata_up{cluster="cluster2", job="prometheus"} 0
nodata_up{cluster="cluster3", job="prometheus"} 0
```
3、再次获取最新查询结果，例如：
```
up{cluster="cluster2", job="prometheus"}
up{cluster="cluster3", job="prometheus"}
up{cluster="cluster4", job="prometheus"}
```
4、为第3步中所有指标的nodata指标赋值0
```
nodata_up{cluster="cluster2", job="prometheus"} 0
nodata_up{cluster="cluster3", job="prometheus"} 0
nodata_up{cluster="cluster4", job="prometheus"} 0
```
5、更新指标列表，加入将新出现的指标，得到：
```
up{cluster="cluster1", job="prometheus"}
up{cluster="cluster2", job="prometheus"}
up{cluster="cluster3", job="prometheus"}
up{cluster="cluster4", job="prometheus"}
```
6、为第4步列表中存在，但第3步列表中不存在的指标对应的nodata指标赋值1，表示该指标无数据：
```
nodata_up{cluster="cluster1", job="prometheus"} 1
nodata_up{cluster="cluster2", job="prometheus"} 0
nodata_up{cluster="cluster3", job="prometheus"} 0
nodata_up{cluster="cluster4", job="prometheus"} 0
```
7、循环执行步骤3至6，更新指标nodata情况。

## 使用方法
### python3运行：
```text
# python3 nodata_exporter.py -h
usage: nodata_exporter.py [-h] [-u URL] -q QUERY [-r RESERVEDLABELS]

A exporter for prometheus nodata alert. Please run this script with python3.
Access the metrics at: http://localhost:9198/metrics.

optional arguments:
  -h, --help            show this help message and exit
  -u URL, --url URL     the prometheus query url (default:
                        http://localhost:9090/)
  -q QUERY, --query QUERY
                        Required, the promQL for nodata metric, for example
                        "up{job="prometheus"}"
  -r RESERVEDLABELS, --reservedlabels RESERVEDLABELS
                        labels that nodata metric will reserved, multi-labels
                        separated by commas (default: job,instance)
```
例如生成prometheus的nodata指标：
```shell
python3 nodata_exporter.py -u='http://localhost:9090/' -q='up{job="prometheus"}' -r='job,instance'
```
或者生成多个指标序列的nodata指标：
```shell
python3 nodata_exporter.py -u='http://localhost:9090/' -q='up{job="prometheus"} or mysql_up' -r='job,instance'
```

### docker运行
```
docker run -d -p 9198:9198 zhangrongjie/nodata_exporter:1.0 -u='http://*:9090/' -q='up{job="prometheus"}' -r='job,instance'
```
### kubernetes运行
可参考install_nodata_exporter.yaml
```
kubectl apply -f install_nodata_exporter.yaml
```
## 告警规则
```yaml
- alert: Prometheus离线
  expr: nodata_up{job="prometheus"} == 1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "prometheus离线"
    description: "prometheus节点({{$labels.instance}})离线超过2分钟"
```
## 告警清除
程序不具备清除告警能力，如确认某些指标的nodata为正常情况，需重启exporter。