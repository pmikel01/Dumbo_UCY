import argparse
import boto3
import sys, os
import time
from operator import attrgetter
# if not boto.config.has_section('ec2'):
#     boto.config.add_section('ec2')
#     boto.config.setbool('ec2','use-sigv4',True)
ec2 = boto3.resource('ec2')

secgroups = {
    'eu-west-3':'sg-0638252c8d13e9315', #default 0e50b636305f6fede
    'eu-central-1':'sg-0f0a4b3d24f428d06', #default 0fcbe44a71eab0814
    'ca-central-1':'sg-0e95c6f3567970899', #default 09a3dc1babd0bf054
    'us-east-1':'sg-03e71fec894fb3db0', #default 081493fb0126963c1
    'us-west-1':'sg-072bbfe8725e8da84' #default 02857b09bc1dd8a9f
}
regions = sorted(secgroups.keys())[::-1]

amis = {
    'eu-west-3':'ami-0c6ebbd55ab05f070',
    'eu-central-1':'ami-0d527b8c289b4af7f',
    'ca-central-1':'ami-0aee2d0182c9054ac',
    'us-east-1':'ami-04505e74c0741db8d',
    'us-west-1':'ami-0892d3c7ee96c0bf7'
}

sshKeys = {
    'eu-west-3':'pmikel01-mc2ec2',
    'eu-central-1':'pmikel01-mc2ec2',
    'ca-central-1':'pmikel01-mc2ec2',
    'us-east-1':'pmikel01-mc2ec2',
    'us-west-1':'pmikel01-mc2ec2'
}

NameFilter = 'Badger'

######## Not Used #########
def getAddrFromEC2Summary(s):
    return [
            x.split('ec2.')[-1] for x in s.replace(
                '.compute.amazonaws.com', ''
                ).replace(
                    '.us-west-1', ''    # Later we need to add more such lines
                    ).replace(
                        '-', '.'
                        ).strip().split('\n')]

def get_ec2_instances_ip(region):
    ec2 = boto3.resource('ec2', region_name=region)

    if ec2:
        result = []
        instances = ec2.instances.all()
        for instance in instances:
            #needed ?
            instance.load()
            if instance.public_dns_name:
                currentIP = instance.public_dns_name.split('.')[0][4:].replace('-','.')
                result.append(currentIP)
                print(currentIP)
        return result
    else:
        print('Region failed', region)
        return None

def get_ec2_instances_id(region):
    if ec2:
        result = []
        instances = ec2.instances.all()
        for instance in instances:
            instance.load()
            print(instance.id)
            result.append(instance.id)
        return result
    else:
        print('Region failed', region)
        return None

def stop_all_instances(region):
    ec2 = boto3.resource('ec2', region_name=region)
    idList = []
    if ec2:
        # ec2.instances.all().stop()
        instances = ec2.instances.all()
        for instance in instances:
            instance.stop()
            instance.wait_until_stopped()

def terminate_all_instances(region):
    ec2 = boto3.resource('ec2', region_name=region)
    idList = []
    if ec2:
        # ec2.instances.all().terminate()
        instances = ec2.instances.all()
        for instance in instances:
            instance.terminate()
            instance.wait_until_terminated()

def launch_new_instances(region, number):
    ec2 = boto3.resource('ec2', region_name=region)
    # dev_sda1 = ec2.instBlockDeviceMappings.Ebs(delete_on_termination=True)
    # dev_sda1.size = 8 # size in Gigabytes
    # dev_sda1.size = 1 # size in Gigabytes
    # dev_sda1.delete_on_termination = True
    # bdm = ec2.BlockDeviceMappings.BlockDeviceMapping()
    # bdm['/dev/sda1'] = dev_sda1
    launchedInstances = ec2.create_instances(ImageId=amis[region], #'ami-04505e74c0741db8d',  # ami-04505e74c0741db8d
                                 MinCount=number,
                                 MaxCount=number,
                                 KeyName=sshKeys[region], 
                                 InstanceType='t2.micro',
                                 SecurityGroupIds = [secgroups[region], ])
    i=0
    for instance in launchedInstances:
        print(f'EC2 instance "{instance.id}" has been launched')
        
        instance.wait_until_running()
        print(f'EC2 instance "{instance.id}" has been started')
        i+=1
    print(i, "instances launced and running in ", region)

    #If needed change deleteOnTermination here

    return launchedInstances


def start_all_instances(region):
    ec2 = boto3.resource('ec2', region_name=region)
    idList = []
    if ec2:
        # ec2.instances.all().start()
        instances = ec2.instances.all()
        for instance in instances:
            instance.start()
            instance.wait_until_running()

def ipAll():
    result = []
    for region in regions:
        result += get_ec2_instances_ip(region) or []
    open('hosts','w').write('\n'.join(result))
    ############ Check result ############
    print(result)
    ######################################
    callFabFromIPList(result, 'removeHosts')
    callFabFromIPList(result, 'writeHosts')
    return result


def getIP():
    return [l for l in open('hosts', 'r').read().split('\n') if l]

def idAll():
    result = []
    for region in regions:
        result += get_ec2_instances_id(region) or []
    return result

def startAll():
    for region in regions:
        start_all_instances(region)

def stopAll():
    for region in regions:
        stop_all_instances(region)

def terminateAll():
    for region in regions:
        terminate_all_instances(region)

from subprocess import check_output, Popen, call, PIPE, STDOUT
import fcntl
from threading import Thread
import platform

def callFabFromIPList(l, work):
    if platform.system() == 'Darwin':
        print(Popen(['fab', '-i', '~/.ssh/pmikel01-mc2ec2.pem',
            '-u', 'ubuntu', '-H', ','.join(l), # We rule out the client
            work]))
    else:
        call('fab -i ~/.ssh/pmikel01-mc2ec2.pem -u ubuntu -P -t 10 -n 2 -H %s %s' % (','.join(l), work), shell=True)

def non_block_read(output):
    ''' even in a thread, a normal read with block until the buffer is full '''
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.readline()
    except:
        return ''

def monitor(stdout, N, t):
    starting_time = time.time()
    counter = 0
    while True:
        output = non_block_read(stdout).strip()
        print(output)
        if 'synced transactions set' in output:
            counter += 1
            if counter >= N - t:
                break
    ending_time = time.time()
    print('Latency from client scope:', ending_time - starting_time)

######## Not Used #########
def runProtocol():  # fast-path to run, assuming we already have the files ready
    callFabFromIPList(getIP(), 'runProtocol')

######## Not Used #########
def runProtocolfromClient(client, key, hosts=None):
    if not hosts:
        callFabFromIPList(getIP(), 'runProtocolFromClient:%s,%s' % (client, key))
    else:
        callFabFromIPList(hosts, 'runProtocolFromClient:%s,%s' % (client, key))

######## Not Used #########
def runEC2(Tx, N, t, n):  # run 4 in a row
    for i in range(1, n+1):
        runProtocolfromClient('"%d %d %d"' % (Tx, N, t), "~/%d_%d_%d.key" % (N, t, i))

def stopProtocol():
    callFabFromIPList(getIP(), 'stopProtocols')

def callStartProtocolAndMonitorOutput(N, t, l, work='runProtocol'):
    if platform.system() == 'Darwin':
        popen = Popen(['fab', '-i', '~/.ssh/pmikel01-mc2ec2.pem',
            '-u', 'ubuntu', '-H', ','.join(l),
            work], stdout=PIPE, stderr=STDOUT, close_fds=True, bufsize=1, universal_newlines=True)
    else:
        popen = Popen('fab -i ~/.ssh/pmikel01-mc2ec2.pem -u ubuntu -P -H %s %s' % (','.join(l), work),
            shell=True, stdout=PIPE, stderr=STDOUT, close_fds=True, bufsize=1, universal_newlines=True)
    thread = Thread(target=monitor, args=[popen.stdout, N, t])
    thread.daemon = True
    thread.start()

    popen.wait()
    thread.join(timeout=1)

    return  # to comment the following lines
    counter = 0
    while True:
        line = popen.stdout.readline()
        if not line: break
        if 'synced transactions set' in line:
            counter += 1
        if counter >= N - t:
            break
        print(line) # yield line
        sys.stdout.flush()
    ending_time = time.time()
    print('Latency from client scope:', ending_time - starting_time)


######## Not Used #########
def callFab(s, work):  # Deprecated
    print(Popen(['fab', '-i', '~/.ssh/pmikel01-mc2ec2.pem',
            '-u', 'ubuntu', '-H', ','.join(getAddrFromEC2Summary(s)),
            work]))

#short-cuts

c = callFabFromIPList

def sk():
    c(getIP(), 'syncKeys')

def id():
    c(getIP(), 'install_dependencies')

def gp():
    c(getIP(), 'git_pull')

def rp(srp):
    c(getIP(), 'runProtocol:%s' % srp)

def pig():
    c(getIP(), 'ping')

import IPython

if  __name__ =='__main__':
  try: __IPYTHON__
  except NameError:
    
    IPython.embed()
