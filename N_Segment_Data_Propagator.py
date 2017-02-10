from Node import *
import thread
import time
from Thread2 import *
import socket
import os
import time
from multiprocessing import freeze_support 

class Data_propagation:

    fixedFileSize = True
    runRepetition = 1 #Repetition of the whole process
    numOfIterations = 100 #Iterations of each configuration 
    inFileAddr = "./tosend.dat"
    resultFileAddr = './TimeResult.csv'
    iterationFileAddr = './IterationResult.csv'
    serversAddrFileAddr = './internal_IPs.txt'
    tempResultFileAddr = './tempResult.csv'
    MTU = 9001 #MTU = Maximum Transmission Unit
    pckPerServer = 100
    nodesIpAddr = []#Includes the IP of source node, First one is the source.



    def start(self):
        Data_propagation.nodesIpAddr = self.getNodesAddr(Data_propagation.serversAddrFileAddr)
	isSource = False
        nodeIP = [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
        resultFileRef = open(Data_propagation.resultFileAddr,'a')
        iterationFileRef = open(Data_propagation.iterationFileAddr,'a')
        tempResultFileRef = open(Data_propagation.tempResultFileAddr,'a')

	if fixedFileSize:
            fileBlockCount = (len(Data_propagation.nodesIpAddr)-1) * Data_propagation.pckPerServer
            command = "dd if=/dev/zero of=./tosend.dat  bs=" + str(Data_propagation.MTU) + "  count=" + str(fileBlockCount)
            os.system(command)

        for k in range(0, Data_propagation.runRepetition):
            operatingFlag = True
            reversedResults = []
            resultFileRef.write("\n" + time.strftime("%Y-%m-%d %H:%M") + ",#Iterations: " + str(Data_propagation.numOfIterations) + ",Run#: " + str(k) + "\nNumber of Nodes (including sources),Average-Max Execution Time\n")
	    for i in range(0,len(Data_propagation.nodesIpAddr)-1, 2):
                exeTimeSum = 0
                if not operatingFlag:
                    break
            
                iterationResults = []
                for j in range(0, Data_propagation.numOfIterations):
                    node = Node(nodeIP, Data_propagation.nodesIpAddr[0:len(Data_propagation.nodesIpAddr) - i], Data_propagation.inFileAddr, len(Data_propagation.nodesIpAddr) - i - 1)

                    #Leader/Source Node
                    if nodeIP == Data_propagation.nodesIpAddr[0]:
                        isSource = True
                        if not fixedFileSize:
                            fileBlockCount = (len(Data_propagation.nodesIpAddr) - i - 1) * Data_propagation.pckPerServer
                            command = "dd if=/dev/zero of=./tosend.dat  bs=" + str(Data_propagation.MTU) + "  count=" + str(fileBlockCount)
                            os.system(command)
                        print "\n\nTime: ", time.strftime("%Y-%m-%d %H:%M"),"(Detailed: ", time.time() , ") Starting: Run# ", k,  " Number of Servers: ", len(Data_propagation.nodesIpAddr) - i, " Round: ", j
                        exeTime = node.handler(hasSourceFile = True)
                        iterationResults.append(str(exeTime) + ",")
                        exeTimeSum += exeTime
                    #Receiver Node
                    else:
                        if os.path.exists(Data_propagation.inFileAddr):
                        	command = "rm " + Data_propagation.inFileAddr   
                        	os.system(command)
                        if nodeIP not in Data_propagation.nodesIpAddr[0:len(Data_propagation.nodesIpAddr) - i]:#Means that this node is out of the game, (Not engaged anymore in sending and receiving)
                            operatingFlag = False
                            break
                        print "\n\nTime: ", time.strftime("%Y-%m-%d %H:%M"),"(Detailed: ", time.time() , ") Starting: Run# ", k,  " Number of Servers: ", len(Data_propagation.nodesIpAddr) - i, " Round: ", j
                        node.handler(hasSourceFile = False)
                    print "\n\nTime: ", time.time(), " Finished: Number of Servers: ", len(Data_propagation.nodesIpAddr) - i, " Round: ", j

                if isSource:
                    avgExeTime = exeTimeSum/float(Data_propagation.numOfIterations)
                    reversedResults.append("" + str(len(Data_propagation.nodesIpAddr) - i) + "," + str(avgExeTime) + "\n")
                    tempResultFileRef.write("" + str(len(Data_propagation.nodesIpAddr) - i) + "," + str(avgExeTime) + "\n")
                    tempResultFileRef.flush()
                    print "\n\nAverage-Max execution time (for ", Data_propagation.numOfIterations, "iterations): ", avgExeTime, " Run# ", k,  " Number of Servers: ", len(Data_propagation.nodesIpAddr) - i
                    iterationFileRef.write("\nRun#: " + str(k) + ",Number Nodes: " + str(len(Data_propagation.nodesIpAddr) - i) + "\n" )
                    for res in iterationResults:
                        iterationFileRef.write(res)
                    iterationFileRef.flush()

            while isSource and len(reversedResults) > 0:
                resultFileRef.write(reversedResults.pop())
                resultFileRef.flush()
        resultFileRef.close()


    def getNodesAddr(self, fileAddr):
        f = open(fileAddr, "r")
        line = f.readline().rstrip()
        addrList = []
        while line:
            addrList.append(line)
            line = f.readline().rstrip()
        return addrList


if __name__ == '__main__':
    freeze_support()#To support multiprocessing in Windows 
    dp = Data_propagation()
    dp.start()




