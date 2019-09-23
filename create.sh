#!/bin/bash

set -x

project_pwd=`pwd`

docker build -t hdpworker .

docker network create --subnet=172.17.0.1/16 hdp_network

docker run -itd -v ${project_pwd}:/smith --net hdp_network --ip 172.17.0.2 -h hdpMaster \
           --name hdp_master --privileged -p 8088:8088 hdpworker
docker run -itd -v ${project_pwd}:/smith --net hdp_network --ip 172.17.0.3 -h hdpSlave1 \
           --name hdp_slave1 --privileged  hdpworker
docker run -itd -v ${project_pwd}:/smith --net hdp_network --ip 172.17.0.4 -h hdpSlave2 \
           --name hdp_slave2 --privileged  hdpworker
docker run -itd -v ${project_pwd}:/smith --net hdp_network --ip 172.17.0.5 -h hdpSlave3 \
           --name hdp_slave3 --privileged  hdpworker

command="cat /smith/hosts >> /etc/hosts \
         && service ssh start \
         && ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa"
docker exec hdp_master bash -c "${command}"
docker exec hdp_slave1 bash -c "${command}"
docker exec hdp_slave2 bash -c "${command}"
docker exec hdp_slave3 bash -c "${command}"

command="cp -f /smith/core-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/mapred-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/hdfs-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/yarn-site.xml /root/hadoop/etc/hadoop \
         && cp -f /smith/yarn-env.sh /root/hadoop/etc/hadoop \
         && awk -F'\t' '{print $2}' /smith/hosts > /root/hadoop/etc/hadoop/workers \
         && cat /smith/env >> /root/hadoop/etc/hadoop/hadoop-env.sh"
docker exec hdp_master bash -c "${command}"
docker exec hdp_slave1 bash -c "${command}"
docker exec hdp_slave2 bash -c "${command}"
docker exec hdp_slave3 bash -c "${command}"

command="cp /root/.ssh/id_rsa.pub /smith/hdp_master_idrsa.pub"
docker exec hdp_master bash -c "${command}"

command="cat /smith/hdp_master_idrsa.pub >> /root/.ssh/authorized_keys"
docker exec hdp_master bash -c "${command}"
docker exec hdp_slave1 bash -c "${command}"
docker exec hdp_slave2 bash -c "${command}"
docker exec hdp_slave3 bash -c "${command}"
rm hdp_master_idrsa.pub

command="ssh-keyscan -H hdpmaster >> ~/.ssh/known_hosts \
         && ssh-keyscan -H hdpslave1 >> ~/.ssh/known_hosts \
         && ssh-keyscan -H hdpslave2 >> ~/.ssh/known_hosts \
         && ssh-keyscan -H hdpslave3 >> ~/.ssh/known_hosts "
docker exec hdp_master bash -c "${command}"

command="source /root/.bashrc && hdfs namenode -format \
         && start-all.sh && sleep 5 && jps"
docker exec hdp_master bash -c "${command}"
