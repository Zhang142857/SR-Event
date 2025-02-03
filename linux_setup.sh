#!/bin/bash

# 更新包列表
sudo apt update

# 安装Python和基本开发工具
sudo apt install -y python3 python3-pip build-essential git python3-dev

# 安装SDL相关依赖
sudo apt install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev

# 安装多媒体相关依赖
sudo apt install -y ffmpeg libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev

# 安装GStreamer相关依赖
sudo apt install -y libgstreamer1.0-dev gstreamer1.0-plugins-{bad,base,good,ugly} gstreamer1.0-{tools,x}

# 安装其他必要的开发工具
sudo apt install -y cmake pkg-config
sudo apt install -y autoconf automake libtool
sudo apt install -y libgirepository1.0-dev

# 安装Java开发工具（用于Android构建）
sudo apt install -y openjdk-11-jdk

# 安装buildozer
pip3 install --user buildozer

# 安装Android工具依赖
sudo apt install -y wget unzip
sudo apt install -y libncurses5

# 创建一个目录用于存放Android SDK
mkdir -p ~/.buildozer/android/platform/

echo "安装完成！现在你可以使用buildozer了。"
echo "请确保你的项目目录中有buildozer.spec文件。"
echo "使用 'buildozer android debug' 命令来构建APK。"
