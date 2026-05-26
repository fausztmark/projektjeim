import zmq, socket, time # pip install pyzmq
# Identify your Time Controller device
IP = "172.26.34.114" # << change this to the IP address of your TC
PORT = 5555
ADDR = f'tcp://{IP}:{PORT}'
# Create zmq socket and connect to the ScpiClient
context = zmq.Context()
timecontroller = context.socket(zmq.REQ)
timecontroller.connect(ADDR)

timecontroller.send_string("INPUt1:counter:MODE ACCUM")
timecontroller.recv()
# print("Answer from input1: " + answer)
timecontroller.send_string("INPUt2:counter:MODE ACCUM")
answer = timecontroller.recv().decode('utf-8')
print("Answer from input2: " + answer)

# while 1:
# list for count rates
rates1 = []
rates2 = []

for i in range(1):
    timecontroller.send_string('INPUt1:COUNter:RESEt')
    timecontroller.recv()
    # print("Answer from input1: " + answer)
    timecontroller.send_string('INPUt2:COUNter:RESEt')
    timecontroller.recv()
    # print("Answer from input2: " + answer)
    t0 = time.perf_counter()
    time.sleep(1)
    timecontroller.send_string('INPUt1:COUNter?')
    t1 = time.perf_counter()
    n1 = int(timecontroller.recv().decode('utf-8'))
    timecontroller.send_string('INPUt2:COUNter?')
    t2 = time.perf_counter()
    n2 = int(timecontroller.recv().decode('utf-8'))
    rate1 = n1 / (t1 - t0)
    rate2 = n2 / (t2 - t0)
    rates1.append(rate1)
    rates2.append(rate2)

avg1 = 0
var1 = 0
for rate in rates1:
    avg1 += rate
avg1 /= 100
for rate in rates1:
    var1 += (rate - avg1)*(rate - avg1)
var1 /= 99

avg2 = 0
var2 = 0
for rate in rates2:
    avg2 += rate
avg2 /= 100
for rate in rates2:
    var2 += (rate - avg2)*(rate - avg2)
var2 /= 99

print(f"difference: {(avg1-avg2)}")
print(f"ratio: {(1 - avg2/avg1)}")
# print("avg1: " + avg1 + "avg2: " + avg2)
# print("var1: " + var1 + "var2: " + var2)