#!/usr/bin/python3
# encoding:utf-8

from prometheus_api_client import PrometheusConnect, MetricsList
from prometheus_client import Gauge, start_http_server, REGISTRY, GC_COLLECTOR, PLATFORM_COLLECTOR, PROCESS_COLLECTOR
from datetime import datetime
import time
import argparse

# 屏蔽非必要指标
REGISTRY.unregister(GC_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)
REGISTRY.unregister(PROCESS_COLLECTOR)


# 指标赋值
def set_metric_value(metric, label_list, value):
    metric_name = "nodata_" + metric.metric_name
    label_value_list = []
    for label in label_list:
        label_value_list.append(metric.label_config[label])
    exec("{}.labels{}.set({})".format(
        metric_name, tuple(label_value_list), value))


if __name__ == "__main__":
    # 参数处理
    parser = argparse.ArgumentParser(
        description='A exporter for prometheus nodata alert. Please run this script with python3. Access the metrics at: http://localhost:9198/metrics.')
    parser.add_argument('-u', '--url', default='http://localhost:9090/',
                        help='the prometheus query url (default: %(default)s)')
    parser.add_argument('-q', '--query', required=True,
                        help='Required, the promQL for nodata metric, for example "up{job="prometheus"}"')
    parser.add_argument('-r', '--reservedlabels', default='job,instance',
                        help='labels that nodata metric will reserved, multi-labels separated by commas (default: %(default)s)')

    args = parser.parse_args()
    prom_url = args.url
    prom_query = args.query
    reserved_label_list = args.reservedlabels.split(',')

    prom = PrometheusConnect(url=prom_url, disable_ssl=True)

    # 初始化nodata指标列表
    nodata_metric_list = MetricsList(prom.custom_query(query=prom_query))

    # 初始化指标名集合
    nodata_metric_name_set = set()
    for nodata_metric in nodata_metric_list:
        nodata_metric_name_set.add("nodata_" + nodata_metric.metric_name)

    # 声明nodata指标对象
    nodata_metric_description = "nodata_{metricX}: whether the metricX exists, 0 exist, 1 non-exist"
    for nodata_metric_name in nodata_metric_name_set:
        exec("{} = Gauge('{}', '{}', {})".format(nodata_metric_name,
             nodata_metric_name, nodata_metric_description, reserved_label_list))

    # nodata指标赋值
    print("{} init metric list:".format(datetime.now()))
    for nodata_metric in nodata_metric_list:
        print("{}{}".format(nodata_metric.metric_name, nodata_metric.label_config))
        set_metric_value(nodata_metric, reserved_label_list, 0)

    start_http_server(9198)

    # 循环更新指标值
    while True:
        nodata_metric_list_latest = MetricsList(
            prom.custom_query(query=prom_query))
        for nodata_metric in nodata_metric_list_latest:
            nodata_metric_name = "nodata_" + nodata_metric.metric_name
            # 更新指标名集合, 并声明新出现的nodata指标对象
            if nodata_metric_name not in nodata_metric_name_set:
                nodata_metric_name_set.add(nodata_metric_name)
                exec("{} = Gauge('{}', '{}', {})".format(nodata_metric_name,
                     nodata_metric_name, nodata_metric_description, reserved_label_list))
            # 更新nodata指标列表, 并对新指标赋0
            if nodata_metric not in nodata_metric_list:
                print("{} add new metric: {}{}".format(datetime.now(),
                      nodata_metric.metric_name, nodata_metric.label_config))
                nodata_metric_list.append(nodata_metric)
                set_metric_value(nodata_metric, reserved_label_list, 0)

        # 未再出现的指标赋1
        for nodata_metric in nodata_metric_list:
            if nodata_metric not in nodata_metric_list_latest:
                print("{} find nodata metric: {}{}".format(datetime.now(),
                      nodata_metric.metric_name, nodata_metric.label_config))
                set_metric_value(nodata_metric, reserved_label_list, 1)

        time.sleep(60)
