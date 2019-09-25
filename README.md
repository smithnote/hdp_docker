# hdp_docker

练习利用docker搭建hadoop环境

### 环境

1. hadoop: hadoop-3.2.0
2. java:   openjdk11
3. python: python3 

### 使用

python3 hdp.py --help

```
Usage: hdp.py [options]

Options:
  -h, --help            show this help message and exit
  -c COMMAND, --cmd=COMMAND
                        操作命令: create, start, status, stop, clean, 默认:status
  --subnet=SUBNET       用于部署的子网, 默认:172.17.0.1/16
  --size=CLUSTER_SIZE   集群数量, 默认:4
```
