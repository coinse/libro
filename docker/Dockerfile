FROM ubuntu:20.04

ENV DEBIAN_FRONTEND noninteractive

# set default java environment variable
ENV JAVA_VERSION_MAJOR=8 \
    JAVA_VERSION_MINOR=111 \
    JAVA_HOME=/usr/lib/jvm/default-jvm \
    PATH=${PATH}:/usr/lib/jvm/default-jvm/bin/

# RUN apt-get update && \ 
#     apt-get upgrade -y && \
#     apt install openjdk-17-jdk openjdk-17-jre -yq && \
#     ln -s /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/default-jvm && \
#     apt-get clean all

RUN apt-get update && \ 
    apt-get upgrade -y && \
    apt install openjdk-11-jdk -yq && \
    apt install openjdk-17-jdk -yq 

RUN apt-get update && \ 
    apt install openjdk-8-jdk -yq && \
    ln -s /usr/lib/jvm/java-8-openjdk-amd64 /usr/lib/jvm/default-jvm && \
    apt-get clean all

# Check Java version
RUN java -version && \
    javac -version

# Install linux packages
RUN apt-get update
RUN apt-get -qq -y install software-properties-common git curl build-essential subversion perl wget unzip vim bc 

RUN apt-get install maven -yq

# Setup Apache Maven
ENV MAVEN_OPTS="-Xms256m -Xmx512m"

# Check Maven version
RUN mvn -version

# Install Python
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update
RUN apt-get install -y --no-install-recommends python3.9 python3.9-dev python3-pip python3-setuptools python3-wheel gcc
RUN python3.9 -m pip install pip --upgrade

RUN echo 'alias python=python3.9' >> /root/.bashrc

WORKDIR /root

# Install Defects4j
COPY install_defects4j.sh install_defects4j.sh
RUN chmod +x install_defects4j.sh

ENV TZ="America/Los_Angeles"
ENV D4J_HOME="/root/defects4j"
ENV PATH="${PATH}:/root/defects4j/framework/bin"
RUN ./install_defects4j.sh


COPY vimrc .vimrc
ENV JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF8"
ENV TMP_DIR="/tmp"

ENV PYTHONIOENCODING=utf-8
