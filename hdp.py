#!/usr/bin/python
#coding=utf-8

# Copyright (c) 2019 smtihemail@163.com. All rights reserved.
# Author：smithemail@163.com
# Time  ：2019-09-23

import os
import sys
import json
import logging
import traceback
import ipaddress
import subprocess
from optparse import OptionParser


class HdpDocker(object):
    def __init__(self, subnet, cluster_size):
        self.subnet = subnet
        self.cluster_size = cluster_size
        self.ip_to_host = {}
        self.master_ip = ''
        self.master_host = 'hdpmaster'
        self.hdpdocker_images = 'hdpworker'
        self.hdp_network = 'hdp_network'
        self._initilization()

    def _initilization(self):
        ips = [str(ip) for ip in ipaddress.IPv4Network(self.subnet, strict=False)]
        idx = 1
        for ip, _ in zip(ips[2:], range(self.cluster_size)):
            if not self.master_ip:
                self.master_ip = ip
                self.ip_to_host[self.master_ip] = self.master_host
                continue
            self.ip_to_host[ip] = 'hdpslave' + str(idx)
            idx += 1
        return True

    def _cluster_exec(self, command, include_master=False):
        for ip, host in self.ip_to_host.items():
            if not include_master and ip == self.master_ip:
                continue
            docker_cmd = 'docker exec %s bash -c "%s"' % (host, command)
            self._exec_command(docker_cmd)
        return True

    def _master_exec(self, command):
        docker_cmd = 'docker exec %s bash -c "%s"' % (self.master_host, command)
        self._exec_command(docker_cmd)
        return True

    def _exec_command(self, command):
        try:
            p = subprocess.Popen(command, shell=True, encoding='utf8',
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
            if out.strip():
                print(out.strip())
            if err.strip():
                print(err.strip())
        except Exception as e:
            logging.error('execute conmand fail: %s', command)
            traceback.print_exc()
            sys.exit(1)
        logging.info('execute conmand success: %s', command)
        return out

    def _create_docker_images(self):
        cmd = 'docker build -t %s .' % self.hdpdocker_images
        self._exec_command(cmd)
        return True

    def _gen_hosts(self):
        with open('hosts', 'w') as writer:
            for ip, host in self.ip_to_host.items():
                writer.write('%s\t%s\n' % (ip, host))
        return True

    def _configure_cluster(self):
        self._gen_hosts()
        cmd = "cat /smith/hosts >> /etc/hosts \
               && service ssh start \
               && ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa \
               && cp -f /smith/core-site.xml /root/hadoop/etc/hadoop \
               && cp -f /smith/mapred-site.xml /root/hadoop/etc/hadoop \
               && cp -f /smith/hdfs-site.xml /root/hadoop/etc/hadoop \
               && cp -f /smith/yarn-site.xml /root/hadoop/etc/hadoop \
               && cp -f /smith/yarn-env.sh /root/hadoop/etc/hadoop \
               && awk -F'\t' '{print $2}' /smith/hosts > /root/hadoop/etc/hadoop/workers \
               && cat /smith/env >> /root/hadoop/etc/hadoop/hadoop-env.sh"
        self._cluster_exec(cmd, True)
        master_cmd = "cp /root/.ssh/id_rsa.pub /smith/hdp_master_idrsa.pub"
        self._master_exec(master_cmd)
        slave_cmd = "cat /smith/hdp_master_idrsa.pub >> /root/.ssh/authorized_keys"
        self._cluster_exec(slave_cmd, True)
        for host in self.ip_to_host.values():
            cmd = 'ssh-keyscan -H %s >> ~/.ssh/known_hosts' % host
            self._master_exec(cmd)
        return True

    def create_cluster(self):
        docker_cmd = 'docker network create --subnet %s %s'\
                     % (self.subnet, self.hdp_network)
        self._exec_command(docker_cmd)
        cwd = os.getcwd()
        docker_cmd = 'docker run -itd -v %s:/smith --net %s --ip %s -h %s\
                                 --name %s --privileged %s'
        master_cmd = docker_cmd % (cwd, self.hdp_network, self.master_ip,
                                   self.master_host, self.master_host,
                                   ' -p 8088:8088 ' + self.hdpdocker_images)
        self._exec_command(master_cmd)
        for ip, host in self.ip_to_host.items():
            if ip == self.master_ip:
                continue
            slave_cmd = docker_cmd % (cwd, self.hdp_network, ip, host,
                                      host, self.hdpdocker_images)
            self._exec_command(slave_cmd)
        self._configure_cluster()
        self.start_cluster(True)
        pass

    def start_cluster(self, init_start=False):
        if init_start:
            cmd = 'source /root/.bashrc \
                   && hdfs namenode -format \
                   && start-all.sh && sleep 5 && jps'
            self._master_exec(cmd)
            return True
        with open('hosts', 'r') as reader:
            for line in reader:
                contain_name = line.split('\t')[1]
                cmd = 'docker start %s' % contain_name
                self._exec_command(cmd)
            cmd = 'service ssh start'
            self._cluster_exec(cmd, True)
            cmd = 'source /root/.bashrc && start-all.sh'
            self._master_exec(cmd)

    def status_cluster(self):
        cmd = 'source /root/.bashrc && hdfs dfsadmin -report'
        self._master_exec(cmd)
        return True

    def stop_cluster(self):
        with open('hosts', 'r') as reader:
            for line in reader:
                contain_name = line.split('\t')[1]
                cmd = 'docker stop %s' % (contain_name)
                self._exec_command(cmd)

    def clean_cluster(self):
        with open('hosts', 'r') as reader:
            cmd = 'docker inspect %s -f "{{json .NetworkSettings.Networks }}"'\
                  % (self.master_host)
            json_string = self._exec_command(cmd)
            for line in reader:
                contain_name = line.split('\t')[1]
                cmd = 'docker rm -f %s' % (contain_name)
                self._exec_command(cmd)
            for network in json.loads(json_string).keys():
                cmd = 'docker network rm %s' % network
                self._exec_command(cmd)
        return True;

    def run(self, command):
        process = {
            'create': self.create_cluster,
            'start' : self.start_cluster,
            'status': self.status_cluster,
            'stop'  : self.stop_cluster,
            'clean' : self.clean_cluster
        }
        if command not in process:
            logging.error('not find relate operationg of %s' % command)
            return False
        return process[command]()


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    parser = OptionParser()
    parser.add_option('--subnet', type='string', dest='subnet',
            default='172.17.0.1/16', help='用于部署的子网')
    parser.add_option('--size', type='int', dest='cluster_size', default=4,
            help='集群数量')
    parser.add_option('-c', '--cmd', type='string', dest='command', default='status',
            help='操作命令: create, start, status, stop, clean')
    option, args = parser.parse_args()
    hdp_docker = HdpDocker(option.subnet, option.cluster_size)
    hdp_docker.run(option.command)
