#!/bin/bash

set -x

project_pwd=`pwd`

docker run -itd -v ${project_pwd}:/smith --ip 172.17.0.2 -h hdp_master --name hdp_master \
           --privileged  debian
docker run -itd -v ${project_pwd}:/smith --ip 172.17.0.3 -h hdp_slave1 --name hdp_slave1 \
           --privileged  debian
docker run -itd -v ${project_pwd}:/smith --ip 172.17.0.4 -h hdp_slave2 --name hdp_slave2 \
           --privileged  debian
docker run -itd -v ${project_pwd}:/smith --ip 172.17.0.5 -h hdp_slave3 --name hdp_slave3 \
           --privileged  debian


## 安装必备软件
command="cp /smith/sources.list /etc/apt/sources.list \
         && apt-get update \
         && apt-get install openssh-server net-tools vim -y\
         && apt-get install wget openjdk-11-jdk axel rsync gawk -y\
         && service ssh start \
         && ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa"
docker exec hdp_master bash -c "${command}"
docker exec hdp_slave1 bash -c "${command}"
docker exec hdp_slave2 bash -c "${command}"
docker exec hdp_slave3 bash -c "${command}"


command="axel -n 4 http://mirrors.tuna.tsinghua.edu.cn/apache/hadoop/common/hadoop-3.2.0/hadoop-3.2.0.tar.gz -o /root/hadoop-3.2.0.tar.gz"
docker exec hdp_master bash -c "${command}"

command="cd /root/ && tar -zxvf hadoop-3.2.0.tar.gz && ln -sf /root/hadoop-3.2.0 hadoop"
docker exec hdp_master bash -c "${command}"

command="cat /smith/env >> /root/.bashrc && cat /smith/hosts >> /etc/hosts"
docker exec hdp_master bash -c "${command}"
docker exec hdp_slave1 bash -c "${command}"
docker exec hdp_slave2 bash -c "${command}"
docker exec hdp_slave3 bash -c "${command}"

command="cp -f /smith/core-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/mapred-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/hdfs-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/yarn-site.xml /root/hadoop/etc/hadoop \
         && awk -F'\t' '{print $2}' /smith/hosts > /root/hadoop/etc/hadoop/workers \
         && cat /smith/env >> /root/hadoop/etc/hadoop/hadoop-env.sh"
docker exec hdp_master bash -c "${command}"


## 复制到各个节点
command="cp /root/.ssh/id_rsa.pub /smith/hdp_master_idrsa.pub"
docker exec hdp_master bash -c "${command}"

command="cat /smith/hdp_master_idrsa.pub >> /root/.ssh/authorized_keys"
docker exec hdp_master bash -c "${command}"
docker exec hdp_slave1 bash -c "${command}"
docker exec hdp_slave2 bash -c "${command}"
docker exec hdp_slave3 bash -c "${command}"

command="ssh-keyscan -H hdp_master >> ~/.ssh/known_hosts \
         && ssh-keyscan -H hdp_slave1 >> ~/.ssh/known_hosts \
         && ssh-keyscan -H hdp_slave2 >> ~/.ssh/known_hosts \
         && ssh-keyscan -H hdp_slave3 >> ~/.ssh/known_hosts "
docker exec hdp_master bash -c "${command}"

command="rsync -avz /root/hadoop hdp_slave1:/root/ \
         && rsync -avz /root/hadoop-3.2.0 hdp_slave1:/root/ \
         && rsync -avz /root/hadoop hdp_slave2:/root/ \
         && rsync -avz /root/hadoop-3.2.0 hdp_slave2:/root/ \
         && rsync -avz /root/hadoop hdp_slave3:/root/ \
         && rsync -avz /root/hadoop-3.2.0 hdp_slave3:/root/"
docker exec hdp_master bash -c "${command}"
