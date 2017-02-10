import mmap
import os
import threading
import hashlib

class fileHandler:
    
    def __init__ (self, fileAddress, bufferSize):
        self.bufferSize = bufferSize
        self.segmentsWrittenByteMap = {}
        self.mapLock = threading.Lock()
        self.fileLock = threading.Lock()
        self.fileRef = None
        self.fileAddr = fileAddress

    def fLoad(self):
        with open(self.fileAddr, 'rb') as fileRef:
            # Size 0 will read the ENTIRE file into memory!
            fileRef = mmap.mmap(fileRef.fileno(), 0, prot=mmap.PROT_READ) #File is open read-only
            # Proceed with your code-- note the file is already in memory
            self.fileRef = fileRef
        return fileRef #Reference to the file is loaded in the memory.


    def fFlush(self):
        self.fileRef.flush()#Data will be copied from the program buffer to the operating system buffer. However, due to the operating system buffers, this might not mean that the data is written to disk.
        os.fsync # Ensures all operating system buffers are synchronized with the storage devices they're for, in other words, that method will copy data from the operating system buffers to the disk.

    
    def fClose(self):
	self.fFlush()
	#print "Last file Offset: ", self.fileRef.tell()
        self.fileRef.close()


    def isClosed(self):
        return self.fileRef.closed


    def fRead(self, fileOffset, maxOffset2Read):            
        content = ""
        self.fileLock.acquire()
        # so "readine" here will be as fast as could be
        self.fileRef.seek(fileOffset)
        if fileOffset + self.bufferSize < maxOffset2Read:
            content = self.fileRef.read(self.bufferSize)
        else:
            content = self.fileRef.read(maxOffset2Read - fileOffset)
        self.fileLock.release()
        return content


    def getFSize(self):# return file Size in bytes.
        return os.stat(self.fileAddr).st_size


    # Splits the file into predetermined number of segments, and return a list including start offset of each segment
    def fsplit(self, segmentTotalNum):
        fileSize = self.getFSize()
        segmentSize = fileSize / segmentTotalNum
        startOffset = 0
        segmentsStartOffeset = []
        for i in range(0, segmentTotalNum):
            segmentsStartOffeset.append(startOffset)
            startOffset += segmentSize
        return segmentsStartOffeset



    def fWrite(self, segmentNo, segmentStartingOffset, data):
        self.mapLock.acquire()
        if segmentNo in self.segmentsWrittenByteMap:
            self.segmentsWrittenByteMap[segmentNo] = self.segmentsWrittenByteMap[segmentNo] + len(data)
        else:
            self.segmentsWrittenByteMap[segmentNo] = len(data)
        self.mapLock.release()
        self.fileLock.acquire()
	self.fileRef.seek(segmentStartingOffset + self.segmentsWrittenByteMap[segmentNo] - len(data), 0)
        self.fileRef.write(data)
        self.fileLock.release()


    def fCreate(self, size):#Size is in byte
        self.fileLock.acquire()
        if not os.path.exists(self.fileAddr):
            command = "fallocate -l " + str(size) +  " " + self.fileAddr#Reserves or allocates all of the space you're seeking, but it doesn't bother to write anything   
            os.system(command)
            self.fileRef = open(self.fileAddr, 'w+b')
        self.fileRef = open(self.fileAddr, 'r+b')
        self.fileLock.release()
        return self.fileRef


    def fHash(self, hasher=hashlib.sha256(), blocksize=65536):
        fRef = open(self.fileAddr, 'rb')
        buf = fRef.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = fRef.read(blocksize)
        fRef.close()
        return hasher.digest()
    
    #"/" is a special character in our control massages 
    def encodeChecksum(self, checksum):
        checksum = str(checksum)
        for i in range (0, len(checksum)):
            if checksum[i] == "/":
                checksum = checksum + str(i)
        checksum = checksum.replace("/", "")
        return checksum

