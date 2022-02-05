import os
import string

host = "127.0.0.1"
port = 10007

for i in range(10000,10200):
    cmdcc = "kill -9 $(lsof -ti tcp:"+str(i)+") > /dev/null 2>&1"
    os.system(cmdcc)
    # cmdcc = "lsof -ti tcp:"+str(i)+" | xargs kill > /dev/null 2>&1"
    # os.system(cmdcc)
    # cmdcc = "kill -9 $(lsof -ti:"+str(i)+") > /dev/null 2>&1"
    # os.system(cmdcc)
    # cmdcc = "lsof -ti:"+str(i)+" | xargs kill > /dev/null 2>&1"
    # os.system(cmdcc)
