import random
import socket
import time
import threading
import errno
import select
import sys
import traceback
from multiprocessing.dummy import Pool as ThreadPool 
import itertools

from IO_Handler import *
from Thread2 import *

class Node:
	IPAddresses = []
	sources = []
        AckNodes = []
	dataPort = 1022
        controlPort = 1023
        delay = 2
        terminateFlag = 0
        MaxNumClientListenedTo = 200
        timeout_in_seconds = 10
        bufferSize = 2**16#Let the OS decides on packet fragmentation to get the most efficiency
        threadPoolSize = 1 
        debugEnable = False
        debugLevel2Enable = False

        def __init__ (self, ip, NodesIpAddrs, inFileAddr, segmentsTotalNum):
            self.ip = ip 
            Node.IPAddresses = NodesIpAddrs#In Non-source nodes, IPs of sources will be removed from this list and added to sources during the execution
            self.inFileAddr = inFileAddr 
            self.segmentsTotalNum = segmentsTotalNum #Total number of segments that a file is divided to.
            self.recvSegments = 0
            self.toSendTupleList = []#Each tuple contains (segmentNo, data)
	    self.fileSize = 0
	    self.recvData = 0
            self.startTime = 0
            self.dataRecvCounterLock = threading.Lock()
            self.segmentRecvCounterLock = threading.Lock()
            self.toSendLock = threading.Lock()
            self.originalChecksum = None
            self.connectingPeersNum = segmentsTotalNum#Equale with N-1 (N includes the source/leader as well)
            self.receptionFlag = False
            self.thread_send = None



        def isMainThreadActive(self):
            isAlive = any((i.name == "MainThread") and i.is_alive() for i in threading.enumerate())
            return isAlive

       
 
        def randomIPSelect(self):
            if len(Node.IPAddresses) > 0:
                ipList  = random.choice(Node.IPAddresses)
                while ipList == self.ip:
                    ipList = random.choice(Node.IPAddresses)
                return ipList
            else:
		return ["0.0.0.0"]

	
        
        def isReceptionDone(self):
            if self.recvData > 0 and  self.recvData == self.fileSize:
                self.receptionFlag = True
                return self.receptionFlag
            return self.receptionFlag



        def isDistributionDone(self):
            if self.isReceptionDone() and len(self.toSendTupleList) == 0:
                return True
            return False


        
        def addSourceIp(self, ip):
            if ip not in Node.sources:
                Node.sources.append(ip)



        def getSourcesIp(self):
            self.addSourceIp(Node.IPAddresses[0])
            return Node.sources



        def sendSignal(self, msg, ip):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, Node.controlPort))
                s.sendall(str(msg))
                s.close()
            except:
                print "Cannot Connet with: ", ip, " to send <", msg, "> signal."
                traceback.print_exception(*sys.exc_info())



        def handler(self, hasSourceFile = False):
            try:
                if hasSourceFile:
                    send_event = threading.Event()
                    nodeIsOn_event = threading.Event()
                    thread_recvControlCommands = Thread2(name = "RecvControlCommandsThread", target = self.leaderControlCommands, args = (send_event, nodeIsOn_event))
                    thread_recvControlCommands.start()
                   
                    #Leader's control command starts the "thread_send" thread after that all peeres have been connected to each other.
                    self.thread_send = threading.Thread(name = "SendThread", target = self.sendSourceFile, args = (self.inFileAddr, self.segmentsTotalNum, send_event, nodeIsOn_event))
                    self.thread_send.start()
                    exeTimeMax = thread_recvControlCommands.join()
                    self.thread_send.join()
                    return exeTimeMax
                else:
                    time.sleep(Node.delay)
                    thread_receive = Thread2(name = "ReceiveThread", target = self.receiveDataHandler)
                    thread_receive.start()
                    
                    #Waits for connect signal from the leader 
                    relayFlag = self.nodeControlCommands() 
                    if relayFlag:
                        thread_relay = threading.Thread(name = "RelayThread", target = self.relaySegment_Parallel)
                        thread_relay.start()
                    else:
                        print "\t\tError: No connect command received from the leader!!!"
                        
                    thread_receive.join()
                    thread_relay.join()
            except:
                traceback.print_exception(*sys.exc_info())




	def relayWorker(self, (socketConn, ip, data)):
            ready = select.select([], [socketConn], [], Node.timeout_in_seconds)
            if ready[1]: #ready[] is list of ready_to_write sockets.     
                try:
                    socketConn.sendall(data) 
                except socket.error, v:
                    errorcode=v[0]
                    if errorcode==errno.ECONNREFUSED:
                        print "\t(RelayWorker) Error: Connection Refused in RelayWorker function."
		    elif  socket.error == errno.ECONNRESET:
			print "(RelayWorker) Connection reset ! Node's IP: " + str(ip)
                    elif errorcode == errno.EPIPE:
                        #print "\tError: Broken Pipe in RelaySegment function."
                        print "\n(RelayWorker) Error in relayWorker. Broken pipe! Cannot relay data to ", ip
                    else:
                        print "\n(RelayWorker) Error2 in relay Worker while relying to ", ip, "!!! ErrorCode: ", errorcode
                    traceback.print_exception(*sys.exc_info())
                except:
                    print "\n(RelayWorker) Error3 in relay worker while relying to ", ip, "!!! ErrorCode: ", errorcode
                    traceback.print_exception(*sys.exc_info())
            else:
                print "\n\n\t(RelayWorker) Timeout reached! Cannot send  to ip:", ip, "Through socket: ", socket, "and ready [1]: ", ready[1] != [], "\n\n"

   
 
	def relaySegment_Parallel(self):
            connectionInfoList = []
            seenSegments = []
            readyServers = []
            oneTimeFlag = True #DELETE
            BUFFER_SIZE = Node.bufferSize
            while len(readyServers) < self.connectingPeersNum - 1 and self.isMainThreadActive():#Data won't be relayed to itself
                try:
                    tempIp = None
                    for ip in Node.IPAddresses:
                        if ip not in readyServers and ip != self.ip and ip not in self.getSourcesIp():#Same data will not be sent to resources.
                            tempIp = ip
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.connect((ip, Node.dataPort))
                            connectionInfoList.append((s, ip))
                            readyServers.append(ip)
                except socket.error, v:
                    errorcode = v[0]
                    if  errorcode == errno.ECONNRESET:
                        print "(RelayHandler) Connection reset ! Node's IP: " + str(tempIp)
                    if errorcode == errno.ECONNREFUSED:
                        print "(RelayHandler) Node " + str(tempIp) + " are not ready yet!"
                    continue
                except:
                    print "Error: Cannot connect to IP: " + str (tempIp)
                    continue
            
            leaderAddress = self.chooseLeader() 
            self.sendSignal("RelayReady", leaderAddress)
            
            try:
                pool = ThreadPool(processes = Node.threadPoolSize)
                while Node.terminateFlag == 0 and not self.isDistributionDone() and self.isMainThreadActive():
                    if len(self.toSendTupleList) > 0:
                        self.toSendLock.acquire()
                        segmentNo, segmentSize, segmentStartingOffset, data = self.toSendTupleList.pop(0)
                        self.toSendLock.release()

                        if len(data) > 0:
                            if segmentNo not in seenSegments:
                                #Type: 0 = From Sourece , 1 = From Rlayer
                                #Sender Type/Segment No./Segment Size/Segment Starting Offset/
                                tempList = []
                                for s, ip in connectionInfoList:
                                    tempData = "1/" + str(self.fileSize) + "/"  + str(segmentNo) + "/" + str(segmentSize) + "/" + str(segmentStartingOffset) + "/"
                                    tempList.append((s, ip, tempData))
                                pool.map(self.relayWorker, tempList)
                                seenSegments.append(segmentNo)	
                            
                            relayList = []
                            for s, ip in connectionInfoList:
                                relayList.append((s, ip, data))
                            pool.map(self.relayWorker, relayList)
                pool.close() 
                pool.join()
                for s, ip in connectionInfoList:
                    s.shutdown(2)# 0:Further receives are disallowed -- 1: Further  sends are disallow / sends -- 2: Further sends and receives are disallowed.
                    s.close()
            except socket.error, v:
                errorcode=v[0]
                if errorcode==errno.ECONNREFUSED:
                    print "\t(RelayHandler) Error: Connection Refused in RelaySegment function. It can not connect to: ", ip
                else:
                    print "\n(RelayHandler) Error1 in relaying segments (Parallel) to ", ip, " !!! ErrorCode: ", errorcode
                traceback.print_exception(*sys.exc_info())
            except:
                print "\n(RelayHandler) Error2 in relaying segments (Parallel) to ", ip 
                traceback.print_exception(*sys.exc_info())



        def sendSourceFile(self, fileAddress, segmentsTotalNum, send_event, nodeIsOn_event):
            print "Leader sending thread is started!" 
            counter = 0
            fileChecksum = ""
            timeStamp = 0
            if Node.terminateFlag == 0 and not self.isDistributionDone() and self.isMainThreadActive():
                BUFFER_SIZE = Node.bufferSize
                fHandler = fileHandler(fileAddress, BUFFER_SIZE)
                ################# KEEP IT FOR ENABLING FILE WRITE ###################
#                fileChecksum = fHandler.encodeChecksum(fHandler.fHash())
                #####################################################################
                fHandler.fLoad()
                segmentsStartOffeset = fHandler.fsplit(segmentsTotalNum)
                segmentNo = 0
                threadList = []
                toSendList = []
                socketList = []
                connected_IPs = []
                print "Leader sending thread is waiting on nodeIsOn_event . . . ."
                nodeIsOn_event.wait()
                print "Leader sending thread is starting again after receiving the nodeIsOn signal . . ."
                while len(connected_IPs) < self.connectingPeersNum:
                    try:
                        for ip_toSend in Node.IPAddresses:
                            if ip_toSend in connected_IPs or ip_toSend == self.ip:
                                continue
                            if segmentNo == segmentsTotalNum - 1:
                                maxOffset2Send = fHandler.getFSize()
                            else:
                                maxOffset2Send = segmentsStartOffeset[segmentNo + 1]
                    
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.connect((ip_toSend, Node.dataPort))
                            connected_IPs.append(ip_toSend)
                            socketList.append(s)
                            toSendList.append((ip_toSend, s, segmentNo, fHandler, segmentsStartOffeset[segmentNo], maxOffset2Send, fileChecksum))
                            segmentNo += 1
                    except socket.error, v:
                        errorcode = v[0]
                        if  errorcode == errno.ECONNRESET:
                            print "(sendSourceFile) Connection reset ! Node's IP: " + str(ip_toSend)
                        if errorcode == errno.ECONNREFUSED:
                            print "(sendSourceFile) Node " + str(ip_toSend) + " are not ready yet!"
                        continue
                    except:
                        print "Error: Cannot connect to IP: " + str (ip_toSend)
                        continue

                try:
                    timeStamp = time.time()
                    print "Time stamp starts: ", timeStamp
                    for ip_toSend, s, segmentNo, fHandler, startOffeset, maxOffset2Send, fileChecksum in toSendList:
                        thread_send = threading.Thread(target = self.sendSourceToNode, args = (ip_toSend, s, segmentNo, fHandler, startOffeset, maxOffset2Send, fileChecksum, timeStamp))
                        threadList.append(thread_send)

                    #SEND THREAD SHOULD WAIT FOR THE WAKE UP SIGNAL
                    print "Leader sending thread is waiting on send_event . . . ."
                    send_event.wait()
                    print "Leader sending thread is starting again after receiving the send_event signal . . ."
                    self.startTime = time.time()
                    for thread in threadList:
                        thread.start()
                    for thread in threadList:
                        thread.join()
                    for s in socketList:
                        s.shutdown(2)# 0:Further receives are disallowed -- 1: Further sends are disallow / sends -- 2: Further sends and receives are disallowed.
                        s.close()
                    fHandler.fClose()
                except:
                    traceback.print_exception(*sys.exc_info())
	


        def sendSourceToNode(self, nodeIp, nodeSocket, segmentNo, fileHandler, startOffset, maxOffset2Send, fileChecksum, timeStamp):
            try:
		#Type: 0 = From Sourece , 1 = From Rlayer
		#Sender Type/File Size/Segment No./Segment Size/Segment Starting Offset/Time Stamp
                nodeSocket.sendall("0/" + str(fileHandler.getFSize()) + "/" + str(segmentNo) + "/" + str(maxOffset2Send - startOffset)  + "/" + str(startOffset) + "/" + str(fileChecksum) + "/" + str(timeStamp) + "/")
                fileOffset = startOffset
                data = fileHandler.fRead(fileOffset, maxOffset2Send)
                while data:
                    nodeSocket.sendall(data)
                    fileOffset += len(data)
                    data = fileHandler.fRead(fileOffset, maxOffset2Send)
            except socket.error, v:
                errorcode=v[0]
                if errorcode==errno.ECONNREFUSED:
                    print "\tError: Connection Refused in sending from source node (",self.ip , ")to ", nodeIp, " ."
		else:
                    print "Error in sending data from source to nodes !!! ErrorCode: ", errorcode
                traceback.print_exception(*sys.exc_info())
            except:
                traceback.print_exception(*sys.exc_info())
           
 

        def receiveDataHandler(self):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #s.setblocking(False) #If flag is false, the socket is set to non-blocking, otherwise is set to blocking mode.
            try:
		# Allows us to resue the port immediately after termination of the program
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.ip, Node.dataPort))
                s.listen(Node.MaxNumClientListenedTo)
                    
                leaderAddress = self.chooseLeader() 
                self.sendSignal("NodeIsOn", leaderAddress)

                threadsList = []
                connList = []
                fHandler = fileHandler(self.inFileAddr, Node.bufferSize)
                executionTime = 0
                connectedPeersSofar = 0
                while (not self.connectingPeersNum == connectedPeersSofar)  and  self.isMainThreadActive() and Node.terminateFlag == 0 and not self.isReceptionDone():
                    conn, ipAddr = s.accept()
                    connList.append((conn, ipAddr))
                    connectedPeersSofar += 1
                for c, ip in connList:
                    thread_receiveData = Thread2(target = self.receiveData_Serial, args = (c, ip, fHandler))
                    thread_receiveData.start()
                    threadsList.append(thread_receiveData)

                leaderAddress = self.chooseLeader() 
                self.sendSignal("RecvReady", leaderAddress)
                for i in range(0, len(threadsList)):
                    threadsList[i].join()
                for conn, i in connList:
                    conn.close()
                s.close()
            except socket.error, v:
                errorcode = v[0]
                if errorcode == 22: # 22: Invalid arument
                    print "\tError: Invalid argument in connection acceptance (receive data handler)"
                elif errorcode==errno.ECONNREFUSED:
                    print "\tError: Connection Refused in receive"
		else:
		    print "Error1 in Data receive Handler !!! ErrorCode: ", errorcode
                traceback.print_exception(*sys.exc_info())
            except:
                print "\nError2 in Data receive Handler !!!"
                traceback.print_exception(*sys.exc_info())



	def receiveData_Serial(self, connection, Addr, fileHandler):
            relayFlag = False
            ipAddr = Addr[0]
            BUFFER_SIZE = Node.bufferSize  # Normally 1024, but we want fast response.
            segmentStartingOffset = 0
            newcomerFlag = 0
            leaderAddress = self.chooseLeader()
            try:
                data = connection.recv(BUFFER_SIZE)
                if data:
                    if  data == "Terminate" or data == "ACK":
                        print "Error: Wrong received data from: ", ipAddr
                    else:
			items = data.split("/")
                        self.fileSize = int(items[1].rstrip('\0'))
                        segmentNo = int(items[2].rstrip('\0'))
                        segmentSize = int(items[3].rstrip('\0'))
                        segmentStartingOffset = int(items[4].rstrip('\0'))
			#Type: 0 = From Sourece , 1 = From Rlayer
		        #From Server: Sender Type/File Size/Segment No./Segment Size/Segment Starting Offset/data/Original File's checksum/Time Stamp
		        if items[0] == "0":
			    relayFlag = True
                            self.originalChecksum = str(items[5])
                            self.startTime = str(items[6])
                            data = data[len(items[0]) + len(items[1]) + len(items[2]) + len(items[3]) + len(items[4]) + len(items[5]) + len(items[6]) + 7 : ]
			    if ipAddr in Node.IPAddresses:
                                self.addSourceIp(ipAddr)#Same data wil not be sent/relayed to the resources.
			
                        #From Relayer(with File Size): Sender Type/File Size/Segment No./Segment Size/Segment Starting Offset/data
			elif items[0] == "1":
                            data = data[len(items[0]) + len(items[1]) + len(items[2]) + len(items[3]) + len(items[4]) +  5 : ]
                        else:
                            print "\n\n\tError in recieved content. Sender type is not valid.\n\n"
                            return
			fileHandler.fCreate(self.fileSize)#fileHandler creats a file only once. In pther words, does not creat teh file if it already exists.
                        newcomerFlag = 1#Every thread listens for a single newcomer segment, not multiple segment
			segmentRecvLength = 0
                        while data or newcomerFlag == 1:
                            if newcomerFlag == 1:
                                newcomerFlag = 0
                                if len(data) == 0:
                                    data = connection.recv(BUFFER_SIZE)
                                    continue
                            if relayFlag:
                                self.toSendLock.acquire()#!!!!!!!!!!!!!!!!!!!!1111 bebin ezafi nist????? fileHandler khodesh lock vase write dare
                                self.toSendTupleList.append((segmentNo, segmentSize, segmentStartingOffset, data))
                                self.toSendLock.release()
                             #*****************    Uncomment it to enable file write   ********************
#                            fileHandler.fWrite(segmentNo, segmentStartingOffset, data)
                             #*****************************************************************************
			    segmentRecvLength += len(data)
                            self.dataRecvCounterLock.acquire()
                            self.recvData += len(data)
                            if self.isReceptionDone():
                                self.sendSignal("RecvDone", leaderAddress)
                            self.dataRecvCounterLock.release()
                            data = connection.recv(BUFFER_SIZE)
			    if segmentRecvLength == segmentSize:
			        break
                        #*********************    Uncomment it to enable file write    **********************
#                       self.dataRecvCounterLock.acquire()
#			if not fileHandler.isClosed():
#		            fileHandler.fFlush()
#                            if self.recvData == self.fileSize:
#                                fileHandler.fClose()
#                                fileChecksum = fileHandler.encodeChecksum(fileHandler.fHash())
#                                print "\nRecieved file checksum: ", fileChecksum, " Original file checksum: ", self.originalChecksum, "\n"
#                                if (self.originalChecksum.rstrip('\0') == fileChecksum.rstrip('\0')):
#                                    print "\nChecksum verified. File has been received completely. :)\n"
#                                else:
#                                    print "\nChecksum verification failed. File is corrupted ! \n"
#                        self.dataRecvCounterLock.release()
                         #******************************************************************************************************************
            except socket.error, v:
                errorcode=v[0]
                if errorcode == 22: # 22: Invalid arument
                    print "\tError: Invalid argument in connection acceptance (receive data)"
                else:
                    print "\nError in receiveing data !!! ErrorCode: ", errorcode
                traceback.print_exception(*sys.exc_info())
	    except:
		print "\nError2 in receiveing data!"
                traceback.print_exception(*sys.exc_info())

		
                
        def sendTimeACK(self, ipAddr, executionTime):
            BUFFER_SIZE = Node.bufferSize
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect((ipAddr, Node.controlPort))
                s.sendall(str(executionTime) + "ACK")
		s.shutdown(2)# 0:Further receives are disallowed -- 1: Further  sends are disallow / sends -- 2: Further sends and receives are disallowed.
                s.close()
            except socket.error, v:
                errorcode=v[0]
                if errorcode==errno.ECONNREFUSED:
                    print "\tError: Connection Refused in sendACK"
                else:
                    print "Send Ack Error !!! ErrorCode: ", errorcode
                traceback.print_exception(*sys.exc_info())   
            except:
                print "\nError2 in sending ACK"
                traceback.print_exception(*sys.exc_info())



        def broadcastTerminationMsg(self):
            BUFFER_SIZE = Node.bufferSize
	    allAddrs = Node.IPAddresses + Node.sources 
            for ipAddr in allAddrs:
                if ipAddr != self.ip:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        s.connect((ipAddr, Node.controlPort))
                        s.sendall("Terminate")
                        s.shutdown(2)# 0:Further receives are disallowed -- 1: Further  sends are disallowsends -- 2: Further sends and receives are disallowed.
                        s.close()
                    except socket.error, v:
                        errorcode=v[0]
                        if errorcode==errno.ECONNREFUSED:
                            print "\tError: Connection Refused in broadcastTerminationMsg for Address: ", ipAddr
                            continue
                        else:
                            print "Error in broadcasting termination message !!! ErrorCode: ", errorcode
                        traceback.print_exception(*sys.exc_info())
                    except:
                        print "\nError2 in broadcasting termination message."
                        traceback.print_exception(*sys.exc_info())
     


        def isExist(self, ip, IPList):
            for temp in IPList:
                if ip == temp:
                    return True
            return False



        def chooseLeader(self):
            return Node.IPAddresses[0]



        def nodeControlCommands(self):
            startFlag = False
            BUFFER_SIZE = Node.bufferSize#Normally 1024, but we want fast response
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                #Allows us to resue the port immediately after termination of the program
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                s.bind((self.ip, Node.controlPort))
                s.listen(Node.MaxNumClientListenedTo)
                conn, addr = s.accept()
                data = conn.recv(BUFFER_SIZE)
                conn.shutdown(2)
                s.shutdown(2)
                conn.close()
                s.close()
                data = str(data)
                if len(data) > 0:
                    if data == "Connect":
                        startFlag = True
                return startFlag
            except:
                print "\nError in receiving control commands !"
                traceback.print_exception(*sys.exc_info())

         

        def leaderControlCommands(self, send_event, nodeIsOn_event):
	    exeTimeMax = 0
	    recvACK = 0
            BUFFER_SIZE = Node.bufferSize#Normally 1024, but we want fast response
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)#Take this and its correspondace out of loop!!!
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)# Allows us to resue the port immediately after termination of the program
                s.bind((self.ip, Node.controlPort))
                s.listen(Node.MaxNumClientListenedTo)
                readyNodesCount = 0
                listeningNodes = []
                recvDoneNodes = []
                while self.isMainThreadActive() and  recvACK <  len(Node.IPAddresses) - 1:#receives AKS from all nodes except itself
                    ready = select.select([s], [], [], Node.timeout_in_seconds)
                    if ready[0]:#ready[] is list of ready_to_read sockets.
                        conn, addr = s.accept()
                        data = conn.recv(BUFFER_SIZE)
                        data = str(data)
                        if len(data) > 0:
                            if data == "Terminate":
                                Node.terminateFlag = 1
                                break
                            elif "ACK" in data:#Notice: include ACK statements in the termination conditions of isDistributionDone(), Because it may receives all ACKs but if isDistributionDone()==false, broadcastTerminationMsg() will not be called anymore.
                                if not self.isExist(addr[0], Node.AckNodes):
                                    Node.AckNodes.append(addr)
                                    exeTime = float(data.split("ACK")[0].rstrip('\0'))
                                    exeTimeMax = max(exeTime, exeTimeMax)
                                    recvACK += 1
                                else:
                                    print "Error: It is the second Ack received from ", addr
                            elif data == "NodeIsOn":
                                if not self.isExist(addr[0], listeningNodes):
                                     listeningNodes.append(addr[0])
                                     if len(listeningNodes) == self.connectingPeersNum:
                                         nodeIsOn_event.set()
                                         for ip in listeningNodes:
                                             self.sendSignal("Connect", ip)
                            elif data == "RecvDone":
                                if not self.isExist(addr[0], recvDoneNodes):
                                    recvDoneNodes.append(addr[0])
                                    if len(recvDoneNodes) == self.connectingPeersNum:
                                        if self.startTime > 0:
                                            DistributionTime = time.time() - self.startTime
                                            break
                                        else:
                                            print "Error: Starting Time should be greater than zerro!"

                            elif data == "RelayReady" or data == "RecvReady":
                                readyNodesCount += 1
                                if readyNodesCount == 2 * self.connectingPeersNum:
                                    if self.thread_send != None:
                                        #WAKE UP THE SENDING THREAD
                                        send_event.set()
                                    else:
                                        print "Error: Sending thread is called before assignment!!"
                            else:
                                print "\tError: Wrong control command from: ", addr, "\n"
                        conn.close() # We should not leave a connection open by killing a thread
                s.shutdown(0)# 0:Further receives are disallowed -- 1: Further  sends are disallowsends -- 2: Further sends and receives are disallowed.
                s.close()
                print "Distribution Time: ", DistributionTime#Receives AKS from all nodes except itself 
                return DistributionTime
            except socket.error, v:
                errorcode=v[0]
                if errorcode == 22: # 22: Invalid arument
                    print "\tError: Invalid argument in connection acceptance "
                else:
                    print "Error2 in receiving control commands !!! ErrorCode: ", errorcode
                traceback.print_exception(*sys.exc_info())
            except:
                print "\nError3 in receiving control commands !"
                traceback.print_exception(*sys.exc_info())
