FROM debian:buster

WORKDIR /root
COPY sources.list /etc/apt/sources.list
COPY env env
COPY activation-1.1.1.jar activation-1.1.1.jar
RUN hdp_version="3.2.0" \
    && hdp_url="http://mirrors.tuna.tsinghua.edu.cn/apache/hadoop/common/hadoop-${hdp_version}/hadoop-${hdp_version}.tar.gz" \
    && apt-get update \
    && apt-get install openssh-server net-tools vim -y --no-install-recommends \
    && apt-get install openjdk-11-jdk axel rsync gawk -y --no-install-recommends \
    && axel -n 4 ${hdp_url} -o hadoop-${hdp_version}.tar.gz \
    && tar -zxf hadoop-${hdp_version}.tar.gz \
    && rm -f hadoop-${hdp_version}.tar.gz \
    && ln -sf hadoop-${hdp_version} hadoop \
    && cp -f activation-1.1.1.jar hadoop/share/hadoop/common/lib/ \
    && cp -f activation-1.1.1.jar hadoop/share/hadoop/yarn/lib/ \
    && cp -f activation-1.1.1.jar hadoop/share/hadoop/yarn/ \
    && cat env >> hadoop/etc/hadoop/hadoop-env.sh \
    && cat env >> .bashrc \
    && rm -rf env \
    && rm -rf activation-1.1.1.jar \
    && mkdir -p /root/hadoop/logs \
    && mkdir -p /home/hadoop/tmp \
    && mkdir -p /home/hadoop/hdfs/name \
    && mkdir -p /home/hadoop/hdfs/data

CMD ["/bin/bash"]
