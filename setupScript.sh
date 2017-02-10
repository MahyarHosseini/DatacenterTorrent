#!/bin/bash

sudo apt-get update
sudo apt-get -y install ntp
sudo service ntp restart

sudo apt-get -y install git
git clone https://github.com/MahyarHosseini/DCDataDistribution.git
mv internal_IPs.txt ./DCDataDistribution
