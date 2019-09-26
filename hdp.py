#!/usr/bin/python
#coding=utf-8

# Copyright (c) 2019 smithemail@163.com. All rights reserved.
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
        self.cluster_size = cluster_size if cluster_size > 0 else 1
        self.ip_to_host = {}
        self.master_ip = ''
        self.master_host = 'hdpmaster'
        self.hdpdocker_images = 'hdpworker'
        self.hdp_network = 'hdp_network'
        self._initilization()

    def _initilization(self):
        try:
            sub_network = ipaddress.IPv4Network(self.subnet, strict=False)
            if not sub_network.is_private:
                logging.error('provide subnet %s is not private', self.subnet)
                sys.exit(-1)
            cmd = 'docker inspect bridge'
            out = self._exec_command(cmd)
            default_subnet = json.loads(out)[0]['IPAM']['Config'][0]['Subnet']
            default_subnet = ipaddress.IPv4Network(default_subnet, strict=False)
            if sub_network.overlaps(default_subnet):
                logging.error('provide subnet %s overlaps with default subnet %s',
                              self.subnet, str(default_subnet))
                sys.exit(-1)
        except json.JSONDecodeError as je:
            logging.error('parser default subnet error, %s', str(je))
            traceback.print_exc()
            sys.exit(-1)
        subnet_iter = iter(sub_network)
        next(subnet_iter), next(subnet_iter)
        idx = 1
        for ip, _ in zip(subnet_iter, range(self.cluster_size)):
            ip = str(ip)
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
        return self._exec_command(docker_cmd)

    def _exec_command(self, command):
        try:
            command = command.strip()
            p = subprocess.Popen(command, shell=True, encoding='utf8',
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
            if out.strip():
                logging.debug(out.strip())
            if err.strip():
                logging.debug(err.strip())
        except Exception as e:
            logging.error('execute conmand fail: %s', command)
            traceback.print_exc()
            sys.exit(1)
        logging.debug('exec cmd success, %s', command)
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
        cmd = 'rm -f hdp_master_idrsa.pub'
        self._exec_command(cmd)
        for host in self.ip_to_host.values():
            cmd = 'ssh-keyscan -H %s >> ~/.ssh/known_hosts' % host
            self._master_exec(cmd)
        return True

    def create_cluster(self):
        logging.info('create docker images: %s ...', self.hdpdocker_images)
        self._create_docker_images()
        logging.info('create docker network: %s ...', self.subnet)
        docker_cmd = 'docker network create --subnet %s %s'\
                     % (self.subnet, self.hdp_network)
        self._exec_command(docker_cmd)
        logging.info('create cluster master: %s ...', self.master_host)
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
            logging.info('create cluster slave: %s ...', host)
            slave_cmd = docker_cmd % (cwd, self.hdp_network, ip, host,
                                      host, self.hdpdocker_images)
            self._exec_command(slave_cmd)
        logging.info('configure cluster ...')
        self._configure_cluster()
        logging.info('start cluster ...')
        self.start_cluster(True)

    def start_cluster(self, init_start=False):
        if init_start:
            cmd = 'source /root/.bashrc && hdfs namenode -format && start-all.sh'
            self._master_exec(cmd)
            return True
        with open('hosts', 'r') as reader:
            for line in reader:
                contain_name = line.strip().split('\t')[1].strip()
                cmd = 'docker start %s' % contain_name
                self._exec_command(cmd)
                logging.info('contain %s start ...', contain_name)
            logging.info('contains sshd service start...')
            cmd = 'service ssh start'
            self._cluster_exec(cmd, True)
            logging.info('hadoop service start...')
            cmd = 'source /root/.bashrc && start-all.sh'
            self._master_exec(cmd)

    def status_cluster(self):
        cmd = 'source /root/.bashrc && hdfs dfsadmin -report'
        out = self._master_exec(cmd)
        logging.info(out)
        return True

    def stop_cluster(self):
        with open('hosts', 'r') as reader:
            for line in reader:
                contain_name = line.strip().split('\t')[1].strip()
                logging.info('stop contain %s ...', contain_name)
                cmd = 'docker stop %s' % (contain_name)
                self._exec_command(cmd)

    def clean_cluster(self):
        with open('hosts', 'r') as reader:
            cmd = 'docker inspect %s -f "{{json .NetworkSettings.Networks }}"'\
                  % (self.master_host)
            json_string = self._exec_command(cmd)
            for line in reader:
                contain_name = line.split('\t')[1].strip()
                logging.info('removing contain %s ...', contain_name)
                cmd = 'docker rm -f %s' % (contain_name)
                self._exec_command(cmd)
            try:
                networks = json.loads(json_string).keys()
            except json.JSONDecodeError as je:
                logging.warning('parse network string error, json:%s', json_string.strip())
                return False
            except Exception as e:
                logging.warn('find network error: %s', str(e))
                return False
            for network in networks:
                logging.info('removing network %s ...', network)
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
            logging.error('not find relate operation of %s' % command)
            return False
        return process[command]()


if __name__ == '__main__':
    log_format = '[%(levelname)s %(asctime)s] %(message)s'
    logging.basicConfig(level='INFO', format=log_format)
    parser = OptionParser()
    parser.add_option('-c', '--cmd', type='string', dest='command', default='status',
            help='操作命令: create, start, status, stop, clean, 默认:%default')
    parser.add_option('--subnet', type='string', dest='subnet',
            default='172.17.0.1/16', help='用于部署的子网, 默认:%default')
    parser.add_option('--size', type='int', dest='cluster_size', default=4,
            help='集群数量, 默认:%default')
    option, args = parser.parse_args()
    hdp_docker = HdpDocker(option.subnet, option.cluster_size)
    hdp_docker.run(option.command)
