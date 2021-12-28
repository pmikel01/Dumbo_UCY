import datetime

start = None

print("label", "time", "latency", "batch")

pre_non_block_time = 0
pre_block_time = 0
first_epoch_block = True

with open('mule.log', 'r') as hosts:
    for line in hosts:
        if "run_bft INFO Node 0 starts to run at time" in line:
            params = line.split()
            start = datetime.datetime.strptime(params[1], "%H:%M:%S,%f")
            print("start", 0, None, None)
            pre_block_time = start - start
            pre_non_block_time = start - start
        if "one_slot INFO Fast block at Node 0 for Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            if first_epoch_block:
                print("fast-block", diff_time.total_seconds(), float(params[-2].replace(",", "")) + (diff_time - pre_non_block_time).total_seconds(), float(params[-1]) / (diff_time - pre_block_time).total_seconds() )
            else:
                print("fast-block", diff_time.total_seconds(), params[-2].replace(",", ""), int(params[-1]) / (diff_time - pre_block_time).total_seconds() )
            pre_block_time = diff_time
            first_epoch_block = False
        if "hsfastpath INFO Leaves fastpath at" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("view-change", diff_time.total_seconds(), None, None)
            first_epoch_block = True
        if "INFO Node 0 Delivers ACS Block in Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("acs-block", diff_time.total_seconds(), float(params[-4]) + (diff_time - pre_non_block_time).total_seconds(), float(params[-1]) / (diff_time - pre_non_block_time).total_seconds())
            pre_block_time = diff_time
            first_epoch_block = False

print()

print("label", "time", "latency", "batch")
prev_time = 0
with open('dumbo.log', 'r') as hosts:
    for line in hosts:
        if "run_bft INFO Node 0 starts to run at time" in line:
            params = line.split()
            start = datetime.datetime.strptime(params[1], "%H:%M:%S,%f")
            print("start", 0, None, None)
        if "INFO Node 0 Delivers ACS Block in Round" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("acs-block", diff_time.total_seconds(), diff_time.total_seconds() - prev_time, params[-2])
            prev_time = diff_time.total_seconds()
print()


print("label", "time", "latency", "batch")

with open('hotstuff.log', 'r') as hosts:
    for line in hosts:
        if "run_bft INFO Node 0 starts to run at time" in line:
            params = line.split()
            start = datetime.datetime.strptime(params[1], "%H:%M:%S,%f")
            print("start", 0, None, None)
        if "one_slot INFO Fast block at Node 0 for Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("fast-block", diff_time.total_seconds(), params[-2].replace(",", ""), params[-1])
        if "hsfastpath INFO Leaves fastpath at" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("view-change", diff_time.total_seconds(), None, None)
        if "INFO Node 0 Delivers ACS Block in Epoch" in line:
            params = line.split()
            diff_time = datetime.datetime.strptime(params[1], "%H:%M:%S,%f") - start
            print("acs-block", diff_time.total_seconds(), params[-4], params[-1])
print()