import string
import random
import time
  
def tx_generator(id, chars=string.ascii_uppercase + string.digits):

    sensor_id = ''.join(random.choice(chars) for _ in range(5))
    timestamp = str(time.time())
    address = ''.join(random.choice(chars) for _ in range(30))

    rnd_tmp = random.randint(5, 25)
    name = ''.join(random.choice(chars) for _ in range(rnd_tmp))

    rnd_tmp = random.randint(5, 15)
    location = ''.join(random.choice(chars) for _ in range(rnd_tmp))

    lat = ''.join(random.choice(chars) for _ in range(5))
    lon = ''.join(random.choice(chars) for _ in range(5))
    status = ''.join(random.choice(chars) for _ in range(5))
    noise = ''.join(random.choice(chars) for _ in range(5))

    rnd_tmp = random.randint(0, 50)
    temperature = str(rnd_tmp)
    rnd_tmp = random.randint(0, 50)
    humidity = str(rnd_tmp)
    rnd_tmp = random.randint(0, 50)
    pressure = str(rnd_tmp)

    return '<Id: ' + id + ', Sensor_Id: ' + sensor_id + ', Time: ' + timestamp + ', Address: ' + address + ', Name: ' + name + ', Location: ' + location + ', Lat: ' + lat + ', Lon: ' + lon + ', Status: ' + status + ', Noise: ' + noise + ', Temperature: ' + temperature + ', Humidity: ' + humidity + ', Pressure: ' + pressure + '>'

