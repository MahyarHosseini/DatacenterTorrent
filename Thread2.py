import sys
import threading

class StopThread(StopIteration): pass

threading.SystemExit = SystemExit, StopThread



class Thread2(threading.Thread):

	
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, Verbose=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs, Verbose)
        self._return = None
       
 
    def stop(self):
        self.__stop = True


    def _bootstrap(self):
        if threading._trace_hook is not None:
            raise ValueError('Cannot run thread with tracing!')
        self.__stop = False
        sys.settrace(self.__trace)
        super(Thread2, self)._bootstrap()
       # super()._bootstrap()


    def __trace(self, frame, event, arg):
        if self.__stop:
            raise StopThread()
        return self.__trace
    
    def run(self):
        if self._Thread__target is not None:
            self._return = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
   
 
    def join(self):
    	super(Thread2, self).join(self)
        return self._return
    

    def join(self, *args, **kwargs):
        super(Thread2, self).join(*args, **kwargs)
        return self._return

