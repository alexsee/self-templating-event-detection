import datetime
import dateutil

import ruptures as rpt
import numpy as np
import datetime
import dateutil
import json
import os

from influxdb import InfluxDBClient

class ChangePointDetection:

  def __init__(self):
    self.client: InfluxDBClient = None

  def connect_to_influxdb(self):
    # setup InfluxDB stuff
    self.client = InfluxDBClient(host='localhost', port=8086)
    self.client.get_list_database()
    self.client.switch_database("iotdata")

  def main(self):
    beginning, end = self.setTimeframe(2020, 6, 22, 8, 30, 10, 45)

    # obtain all change points, the event log, and all machines
    ids = self.getIds()
    eventLog = self.readEventLog()
    machineSet = self.getMachines(eventLog)

    # read points from influx db
    points, value_points = self.query(beginning, end, ['dik.Objects.VarOut.CiP_Dreh_HaasST10_Energie', 'dik.Objects.VarOut.CiP_Dreh_HaasST10_Volumenstrom_DL', 'dik.Objects.VarOut.CiP_Dreh_HaasST10_Wirkl'])
    result = self.rupture(value_points)

    # clear db and insert results of rupture
    self.clearDB()
    self.insertToDB(result, points, "ruptures")

  def getIds(self):
    query_result = self.client.query('SHOW TAG VALUES ON iotdata WITH KEY = "id"')
    return list(map(lambda x: x['value'], query_result.get_points(measurement="iotdata")))

  def readEventLog(self):
    with open(os.path.join(os.path.dirname(__file__), "../../lab/converted/aggregated.json")) as f:
      data = json.load(f)
      return data

  def getMachines(self, eventLog):
    machineSet = set(map(lambda x: x["Maschinenname"], eventLog))
    return machineSet

  def setTimeframe(sefl, year, month, day, s_hour, s_minute, e_hour, e_minute):
    # set timeframe here
    day = [year, month, day]
    start = [s_hour,s_minute]
    end = [e_hour,e_minute]

    beginning = datetime.datetime(year=day[0], month=day[1], day=day[2], hour=start[0], minute=start[1])
    end = datetime.datetime(year=day[0], month=day[1], day=day[2], hour=end[0], minute=end[1])
    beginning = beginning.astimezone(tz=datetime.timezone.utc).isoformat()
    end = end.astimezone(tz=datetime.timezone.utc).isoformat()

    return beginning, end

  def query(self, beginning, end, ids, interval = "5s"):
    # build query to obtain IoT data
    idstring = " or ".join(list(map(lambda x: "id ='" + x + "'", ids)))
    queryString = "SELECT mean(*) FROM iotdata WHERE " + idstring + " AND time >= '" + beginning + "' and time <= '" + end + "' GROUP BY time(" + interval + "), \"id\" fill(linear)"

    # run Query
    query_result = self.client.query(queryString)
    points = []
    
    for machinename in ids:
      subarray = list(query_result.get_points(tags={"id": machinename}))
      points.append(subarray)

    tuples = []
    for i in range(len(points[0])):
      my_tuple = []
      for subarray in points:
        my_tuple.append(subarray[i])
      tuples.append(my_tuple)

    # fill nones with values instead of stripping
    tuples = list(filter(lambda x: not(None in list(map(lambda y: y["mean_value"], x))), tuples)) 

    value_points = list(map(lambda x: np.array(list(map(lambda y: y["mean_value"], x))), tuples))
    return tuples, value_points

  def rupture(self, value_points, n_bkps = None, pen = 10, model="l2", window = 100, algrthm = "Window"):
    # run ruptures
    algo = None
    result = None

    # sliding window approach
    if(algrthm == "Window"):
      algo = rpt.Window(model=model, jump=1, width = window).fit(np.array(value_points))
      result = algo.predict(pen=pen, n_bkps = n_bkps)

    elif(algrthm == "Dynp"):
      algo = rpt.Dynp(model=model, jump=1).fit(np.array(value_points))
      result = algo.predict(n_bkps = n_bkps)

    # binary segmentation
    elif(algrthm == "Binseg"):
      algo = rpt.Binseg(model=model, jump=1).fit(np.array(value_points))
      result = algo.predict(pen=pen, n_bkps=n_bkps)

    # bottom-up segmentation
    elif(algrthm == "Botup"):
      algo = rpt.BottomUp(model=model, jump=1).fit(np.array(value_points))
      result = algo.predict(pen=pen, n_bkps=n_bkps)

    else:
      print("Error: select one of the implemented algorithms!")
      return False

    return result

  def clearDB(self):
    # clear change points in database
    self.client.drop_measurement("changepoints")

  def insertToDB(self, result, points, machine_id):
    for point in result[:-1]:
        timestamp = dateutil.parser.parse(points[point][0]['time'])
        timestamp = int(timestamp.timestamp() * 1000)

        json_body = [
            {
                "measurement": "changepoints",
                "tags": {
                    "id": machine_id
                },
                "time": timestamp - 2000,
                "fields": {
                    "value": 1
                }
            },
            {
                "measurement": "changepoints",
                "tags": {
                    "id": machine_id
                },
                "time": timestamp,
                "fields": {
                    "value": 0
                }
            },
            {
                "measurement": "changepoints",
                "tags": {
                    "id": machine_id
                },
                "time": timestamp + 2000,
                "fields": {
                    "value": 1
                }
            }
        ]
        self.client.write_points(json_body, time_precision="ms")

    print("All Data written")

if __name__ == "__main__":
  change_point_detection = ChangePointDetection()
  change_point_detection.connect_to_influxdb()
  change_point_detection.main()