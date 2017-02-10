#!/bin/bash
#aws ec2 create-key-pair --key-name KeyPair

VM_count=30
#server_pck_portion=1
MTU=9001
# Runing (an) instance(s)
#aws ec2 run-instances --image-id ami-2d39803a --count $VM_count --instance-type t2.micro --key-name CLI_EC2-keypair  --security-group-ids sg-6589b301 --subnet-id subnet-a76ffa8c --associate-public-ip-address
aws ec2 run-instances --image-id ami-2d39803a --count $VM_count --instance-type m4.xlarge --key-name CLI_EC2-keypair  --security-group-ids sg-6589b301 --subnet-id subnet-a76ffa8c --associate-public-ip-address

sleep 1m

#Get the instance IDs (output file = istance_IDs.txt):
aws ec2 describe-instances | grep  '[^a-zA-Z]i-[0-9a-zA-Z]\{8\}' | cut -f 8 | sed '/^\s*$/d' > instance_IDs.txt
instance_IDs=$( tr '\n' ' ' < instance_IDs.txt )

#Extracting public DNS names of instances
aws ec2 describe-instances | grep '[ec2-]\{4\}[0-9]\{1,3\}-[0-9]\{1,3\}-[0-9]\{1,3\}-[0-9]\{1,3\}.compute-1.amazonaws.com' | cut -f 15 | sed '/^\s*$/d' >  public_DNS_names.txt
public_DNS_names=$( tr '\n' ' ' < public_DNS_names.txt )

instance_num=$( echo $public_DNS_names | wc -w )

#Extract internal IPs of instances in VPC (Virtual private cloud)
aws ec2 describe-instances | grep '[ip-]\{3\}[0-9]\{1,3\}-[0-9]\{1,3\}-[0-9]\{1,3\}-[0-9]\{1,3\}.ec2.internal' | cut -f 13 | sed '/^\s*$/d' > internal_VPC_IPs.txt

#Sorting IP files (First IP has the leader role)
sort internal_VPC_IPs.txt  > internal_IPs.txt
rm internal_VPC_IPs.txt
leader_public_IP=$(aws ec2 describe-instances | grep $(sed '1!d' internal_IPs.txt) | cut -f 15 | sed '/^\s*$/d')


echo "Initializing instances"
sysAndInstanceReachNum=0
#Checking the reachability of instances before runing ssh command (This number is twice of number of instances due to sohwing reachability of instances and its host)
while [ $(($sysAndInstanceReachNum/$instance_num)) -ne 2 ]
do
    sleep  30s
    sysAndInstanceReachNum=$( aws ec2 describe-instance-status --filters Name=instance-status.reachability,Values=passed | grep --fixed-strings "reachability" | wc -l )
    echo "All VMs are not reachable yet. Number of reachables: $(($sysAndInstanceReachNum/2)) Excpected: $instance_num"
done


#sleep 10s

#Setup all instances
for i in $public_DNS_names;
do
    echo $i
    #ssh-keyscan -H $i >> ~/.ssh/known_hosts
    #sudo apt-get install ntp
    #sudo vim /etc/ntp.conf
    #sudo service ntp restart
    #sudo ntpq -c lpeer
    #yes Y | ssh -o StrictHostKeyChecking=no -i CLI_EC2-keypair.pem ubuntu@$i sudo apt-get update
    #yes Y | ssh -o StrictHostKeyChecking=no -i CLI_EC2-keypair.pem ubuntu@$i sudo apt-get install git
    #yes yes | ssh -o StrictHostKeyChecking=no -i CLI_EC2-keypair.pem ubuntu@$i git clone https://github.com/MahyarHosseini/DCDataDistribution.git

    scp -o StrictHostKeyChecking=no -i CLI_EC2-keypair.pem ./internal_IPs.txt  ubuntu@$i:./internal_IPs.txt
    scp -o StrictHostKeyChecking=no -i CLI_EC2-keypair.pem ./setupScript.sh  ubuntu@$i:./setupScript.sh
done;
#yes yes | ssh -i CLI_EC2-keypair.pem ubuntu@$leader_public_IP dd if=/dev/zero of=./DCDataDistribution/tosend.dat  bs=$MTU  count=$(((VM_count-1)*server_pck_portion))

echo "Leader: $leader_public_IP"

cssh -l ubuntu  $public_DNS_names

#To terminate an Amazon EC2 instance
#aws ec2 terminate-instances --instance-ids $instance_IDs


