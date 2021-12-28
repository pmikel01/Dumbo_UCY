import datetime

start = None

print("label", "time", "latency", "batch")

pre_time = 0
pre_vc_time = 0
with open('mule.log', 'r') as hosts:
    for line in hosts:
        if "run_bft INFO Node 0 starts to run at time" in line:
            params = line.split()
            start = datetime.datetime.strptime(params[1], "%H:%M:%S,%f")
            print("start", 0, None, None)
            pre_time = start - start
        if "_change_network" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("net-change", '\t', diff_time.total_seconds(), '\t', None, '\t', None)
        if "one_slot INFO Fast block at Node 0 for Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("fast-block", '\t', diff_time.total_seconds(), '\t', params[-2].replace(",", ""), '\t', int(params[-1]) / (diff_time - pre_time).total_seconds() )
            pre_time = diff_time
        if "_run_epoch INFO VIEW CHANGE costs time" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("view-change", '\t', diff_time.total_seconds(), '\t', None, '\t', None)
            pre_vc_time = diff_time
        if "INFO Node 0 Delivers ACS Block in Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("acs-block", '\t', diff_time.total_seconds(), '\t', (diff_time - pre_vc_time).total_seconds(), '\t', float(params[-1]) / (diff_time - pre_vc_time).total_seconds())
            pre_time = diff_time

print()

print("label", "time", "latency", "batch")
pre_time = 0
with open('dumbo.log', 'r') as hosts:
    for line in hosts:
        if "run_bft INFO Node 0 starts to run at time" in line:
            params = line.split()
            start = datetime.datetime.strptime(params[1], "%H:%M:%S,%f")
            pre_time = start - start
            print("start", 0, None, None)
        if "_change_network" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("net-change", '\t', diff_time.total_seconds(), '\t', None, '\t', None)
        if "INFO Node 0 Delivers ACS Block in Round" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("acs-block", '\t', diff_time.total_seconds(), '\t', diff_time.total_seconds() - pre_time.total_seconds(), '\t', float(params[-2]) / (diff_time - pre_time).total_seconds() )
            pre_time = diff_time
print()


print("label", "time", "latency", "batch")

with open('hotstuff.log', 'r') as hosts:
    for line in hosts:
        if "run_bft INFO Node 0 starts to run at time" in line:
            params = line.split()
            start = datetime.datetime.strptime(params[1], "%H:%M:%S,%f")
            print("start", 0, None, None)
            pre_time = start - start
        if "_change_network" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("net-change", '\t', diff_time.total_seconds(), '\t', None, '\t', None)
        if "one_slot INFO Fast block at Node 0 for Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("fast-block", '\t', diff_time.total_seconds(), '\t', params[-2].replace(",", ""), '\t', int(params[-1]) / (diff_time - pre_time).total_seconds() )
            pre_time = diff_time
        if "seconds in epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("view-change", '\t', diff_time.total_seconds(), '\t', None, '\t', None)
            pre_vc_time = diff_time
        if "INFO Node 0 Delivers ACS Block in Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("acs-block", '\t', diff_time.total_seconds(), '\t', (diff_time - pre_vc_time).total_seconds(), '\t', float(params[-1]) / (diff_time - pre_vc_time).total_seconds())
            pre_time = diff_time
print()