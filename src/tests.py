import changepoints
import datetime
import dateutil
import json
import os
import twopass

import matplotlib.pyplot as plt
import matplotlib.dates as dates
from matplotlib.patches import Rectangle
import datetime as dt
import numpy as np

from cleanup import cleanup, timeStampInFaulty

plt.rcParams["figure.figsize"] = [20, 6]  # width, height
plt.rcParams['xtick.direction'] = 'out'

margin = 60
good_machines = ["HaasMM2", "Lasebox", "HaasST10", "cleanlaser", "Kasto"]

def pattern(influx = False, _margin = 60, pen = 10, window = 35, interval = "5s", algo = "dtw", template = "dba", trimming = True):
  if influx:
    changepoints.clearDB()

  global margin
  margin = _margin

  ids = changepoints.getIds()
  eventLog = changepoints.readEventLog()
  machineSet = list(changepoints.getMachines(eventLog))

  machineSet = good_machines

  metrics = []

  for machine in machineSet:
    resultsbyday, logsbyday = checkpointsMatrixOrDTW(machine, eventLog, ids, influx, pen, window, algo, interval, template, trimming)
    if len(logsbyday) > 0:
      calculated = calculateMetrics(resultsbyday, logsbyday)

      metricsbyday = []
      avg_precision = 0
      avg_recall = 0
      for calc in calculated:
        if((calc["TP"] + calc["FP"]) != 0 and (calc["TP"] + calc["FN"] != 0)):
          metric = {
            "prec": calc["TP"] / (calc["TP"] + calc["FP"]),
            "recall": calc["TP"] / (calc["TP"] + calc["FN"])
          }
          avg_precision = avg_precision + calc["TP"] / (calc["TP"] + calc["FP"])
          avg_recall = avg_recall + calc["TP"] / (calc["TP"] + calc["FN"])
          metricsbyday.append(metric)
      if(len(metricsbyday) > 0):
        avg_precision = avg_precision / len(metricsbyday)
        avg_recall = avg_recall / len(metricsbyday)

      metrics.append({
        "name": machine,
        "metricsbyday": metricsbyday,
        "avg_precision": avg_precision,
        "avg_recall": avg_recall
      })

  prefix = "2pass"
  prefix += "M" + str(_margin)
  prefix += "P" + str(pen)
  prefix += "W" + str(window)
  prefix += "I" + str(interval)
  prefix += str(algo)
  prefix += str(template)
  prefix += "T" + str(trimming)

  outfile = open(os.path.join(os.path.dirname(__file__), "../out/" + prefix + "metrics.json"), "w")
  json.dump(metrics, outfile)
  outfile.close()
  print("All Done")

  return metrics

    

def main(influx = False, _margin = 60, n_bkps = False, pen = 10, window = 100, wirkl_only = True, algo = "Window", model="l2"):
  if influx:
    changepoints.clearDB()

  global margin 
  margin = _margin

  ids = changepoints.getIds()
  eventLog = changepoints.readEventLog()
  machineSet = list(changepoints.getMachines(eventLog))

  metrics = []

  for machine in machineSet:
    resultsbyday, logsbyday = checkPointsForMachine(machine, eventLog, ids, influx, wirkl_only, n_bkps, pen, window, algo, model)
    if len(logsbyday) > 0:
      calculated = calculateMetrics(resultsbyday, logsbyday)

      metricsbyday = []
      avg_precision = 0
      avg_recall = 0
      for calc in calculated:
        if((calc["TP"] + calc["FP"]) != 0 and (calc["TP"] + calc["FN"] != 0)):
          metric = {
            "prec": calc["TP"] / (calc["TP"] + calc["FP"]),
            "recall": calc["TP"] / (calc["TP"] + calc["FN"])
          }
          avg_precision = avg_precision + calc["TP"] / (calc["TP"] + calc["FP"])
          avg_recall = avg_recall + calc["TP"] / (calc["TP"] + calc["FN"])
          metricsbyday.append(metric)
      if(len(metricsbyday) > 0):
        avg_precision = avg_precision / len(metricsbyday)
        avg_recall = avg_recall / len(metricsbyday)

      metrics.append({
        "name": machine,
        "metricsbyday": metricsbyday,
        "avg_precision": avg_precision,
        "avg_recall": avg_recall
      })

  prefix = ""
  prefix += "M" + str(_margin)
  if(n_bkps):
    prefix += "B"
  prefix += "P" + str(pen)
  prefix += "W" + str(window)
  if(wirkl_only):
    prefix += "Wirk"
  prefix += str(algo)
  prefix += str(model)

  outfile = open(os.path.join(os.path.dirname(__file__), "../out/" + prefix + "metrics.json"), "w")
  json.dump(metrics, outfile)
  outfile.close()
  print("All Done")

  return metrics

def toCSVLines(metrics, _margin = 60, n_bkps = False, pen = 10, window = 100, wirkl_only = True, algo = "Window", model="l2"):
  csvlines = ""

  for metric in metrics:
    for index, day in enumerate(metric["metricsbyday"]):
      csvlines += str(metric["name"]) + ";"
      csvlines += str(index) + ";"
      csvlines += str(day["prec"]) + ";"
      csvlines += str(day["recall"]) + ";"
      csvlines += str(_margin) + ";"
      csvlines += str(n_bkps) + ";"
      csvlines += str(pen) + ";"
      csvlines += str(window) + ";"
      csvlines += str(wirkl_only) + ";"
      csvlines += str(algo) + ";"
      csvlines += str(model) + "\n"
  
  return csvlines

def checkPointsForMachine(name, eventlog, ids, influx, wirkl_only, n_bkps, pen, window, algo, model, debug = False):
  relevantlog = list(filter(lambda x: x["Maschinenname"] == name and not("1970" in x["Start Betrieb"]) , eventlog)) #Filter some falsy dates/values with 1970
  relevantlog = cleanup(relevantlog)
  relevantids = list(filter(lambda x: name in x and (not(wirkl_only) or "Wirkl" in x) and not("Mode_Bearbeitung" in x) and not("Staubsauger" in x), ids))
  days = list(set(map(lambda x: dateutil.parser.parse(x["Start Betrieb"]).strftime("%Y %m %d"), relevantlog)))
  resultsbyday = []
  logsbyday = []

  if(len(relevantids) == 0): 
    return resultsbyday, logsbyday

  for day in days:
    daydata = list(filter(lambda x: dateutil.parser.parse(x["Start Betrieb"]).strftime("%Y %m %d") == day, relevantlog))

    sortedTimestamps = sorted(map(lambda x: dateutil.parser.parse(x["Start Betrieb"]), daydata))
    beginning, end = changepoints.setTimeframe(int(day.split(" ")[0]), int(day.split(" ")[1]), int(day.split(" ")[2]), int(sortedTimestamps[0].strftime("%H")), 0, int(sortedTimestamps[-1].strftime("%H")) + 1, 0)
    
    points, value_points = changepoints.query(beginning, end, relevantids)
    bkps = None
    if (n_bkps):
      bkps = len(daydata) * 2
    result = changepoints.rupture(value_points, pen=pen, model=model, window=window, algrthm=algo, n_bkps = bkps)
    mappedresult = []

    if debug:
      plt.suptitle('Initial segmentation')
      plt.xlabel('Time')
      plt.ylabel('Power usage')
      plt.plot(value_points)

      for idx in result:
        plt.axvline(x=idx, linestyle="dashed", c="dimgray")
      plt.show()

    for res in result[:-1]:
      mappedresult.append(points[res])

    resultsbyday.append(mappedresult)
    logsbyday.append(daydata)
    if influx:
      changepoints.insertToDB(result, points, name)
    
  print("Done with " + name)
  return resultsbyday, logsbyday

def checkpointsMatrixOrDTW(name, eventlog, ids, influx, pen, window, algo, interval, template, trimming, firstpassmethod="Window", mode="dynamic", t=1000, debug = False):
  #name = "HaasMM2"
  print("Starting for " + name)
  wirkl_only = True
  relevantlog = list(filter(lambda x: x["Maschinenname"] == name and not("1970" in x["Start Betrieb"]) , eventlog)) #Filter some falsy dates/values with 1970
  relevantlog = cleanup(relevantlog)
  relevantids = list(filter(lambda x: name in x and (not(wirkl_only) or "Wirkl" in x) and not("Mode_Bearbeitung" in x) and not("Staubsauger" in x), ids))
  days = list(set(map(lambda x: dateutil.parser.parse(x["Start Betrieb"]).strftime("%Y %m %d"), relevantlog)))

  if(name!="Kasto"):
    days = [day for day in days if day != "2020 06 23"]

  resultsbyday = []
  logsbyday = []

  if(len(relevantids) == 0): 
    return resultsbyday, logsbyday

  for day in days:
    print("Day: " + day)
    daydata = list(filter(lambda x: dateutil.parser.parse(x["Start Betrieb"]).strftime("%Y %m %d") == day, relevantlog))

    sortedTimestamps = sorted(map(lambda x: dateutil.parser.parse(x["Start Betrieb"]), daydata))
    beginning, end = changepoints.setTimeframe(int(day.split(" ")[0]), int(day.split(" ")[1]), int(day.split(" ")[2]), int(sortedTimestamps[0].strftime("%H")), 0, int(sortedTimestamps[-1].strftime("%H")) + 1, 0)
    
    points, value_points = changepoints.query(beginning, end, relevantids, interval)
    result = twopass.main(value_points, pen, window, algo, template, trimming, firstpassmethod, mode, t, len(sortedTimestamps))
    mappedresult = []

    for res in result:
      startp = points[res[0]]
      endp = points[res[1]]
      parsedTime = dateutil.parser.parse(startp[0]["time"])
      if(not timeStampInFaulty(parsedTime)):
        mappedresult.append((startp, endp))

    resultsbyday.append(mappedresult)
    logsbyday.append(daydata)

    if(debug):

      resultRupt = changepoints.rupture(value_points, pen=pen, model="l2", window=window, algrthm=firstpassmethod)

      # Transform daydata into changepoints
      parsediotdata = list(map(lambda x:dateutil.parser.parse(x[0]["time"]), points))
      daydata_chp = []

      for log in daydata:
          
          startts = dateutil.parser.parse(log["Start Betrieb"]).astimezone(tz=dt.timezone.utc)
          endts = dateutil.parser.parse(log["Ende Betrieb"]).astimezone(tz=dt.timezone.utc)
          startidx = np.argmin(list(map(lambda x: abs(startts - x).total_seconds(),parsediotdata)))
          endidx = np.argmin(list(map(lambda x: abs(endts - x).total_seconds(),parsediotdata)))
          daydata_chp.append((startidx, endidx))

      # Plot
      fig, axs = plt.subplots(3, sharex=True, gridspec_kw={'hspace': 0})
      plt.suptitle(name + " on " + str(day))

      #plt.xlim(800,1800)

      axs[0].plot(value_points)
      axs[0].set_ylabel('Ground Truth')
      axs[1].set_xlabel('Time')
      axs[1].set_ylabel('Predicted')
      axs[2].set_ylabel("Detected")
      axs[1].plot(value_points)
      axs[2].plot(value_points)

      for chp in daydata_chp:
          #plt.plot(range(idx, idx+profile[idx][2]), value_points[idx:idx+profile[idx][2]], lw=2)
          axs[0].axvline(x=chp[0], linestyle="dashed", c="green")
          axs[0].axvline(x=chp[1], linestyle="dashed", c="red")

      for res in resultRupt:
          axs[1].axvline(x=res, linestyle="dashed")

      for res in result:
          axs[2].plot(range(res[0], res[1]), value_points[res[0]:res[1]], lw=2)
          axs[2].axvline(x=res[0], linestyle="dashed")

      plt.show()

    if influx:
      changepoints.insertToDB(result, points, name)
    
  print("Done with " + name)

  return resultsbyday, logsbyday

def calculateMetrics(resultsbyday, logsbyday, start = True, end = True, debug = False, customMargin = 60):

  statsperday = []

  parsedlogs = []
  for day in logsbyday:
    parsedday = []
    for log in day:
      if(start): parsedday.append(dateutil.parser.parse(log["Start Betrieb"]).astimezone(tz=datetime.timezone.utc))
      if(end): parsedday.append(dateutil.parser.parse(log["Ende Betrieb"]).astimezone(tz=datetime.timezone.utc))
    parsedlogs.append(parsedday)

  parsedLogsPreFilter = parsedlogs
  parsedlogs = list(map(lambda x: list(filter(lambda y: not timeStampInFaulty(y), x)), parsedlogs))

  parsedresults = []
  for day in resultsbyday:
    parsedday = []
    for log in day:
      parsedTime = dateutil.parser.parse(log[0]["time"])
      if(not timeStampInFaulty(parsedTime)):
        parsedday.append(parsedTime)
      else:
        if(debug): print("Removed timestamp")

    parsedresults.append(parsedday)

  for day in range(len(parsedresults)):
    stats = {
      "TP": 0,
      "FP": 0,
      "FN": 0,
      "TotalTrue": len(parsedlogs[day]),
      "TotalPredict": len(parsedresults[day]),
      "RemTrue": len(parsedLogsPreFilter[day]) - len(parsedlogs[day]),
      "RemPredict": len(resultsbyday[day]) - len(parsedresults[day]),
      "day": parsedlogs[day][0].day,
      "deviation": []
    }

    onlyOneMode = True

    assigned = [] #[timestamp, distance]

    if(onlyOneMode):
      for log in parsedlogs[day]:
        found = list(filter(lambda x: abs(x[1]) < customMargin, list(map(lambda x: (x, (log - x).total_seconds()), parsedresults[day])) ))
        if(len(found) > 0):
          if(len(found) == 1):
            stats["TP"] = stats["TP"] + 1
            assigned.append(found[0])
          else:
            notfound = True
            for entry in sorted(found, key=lambda x: abs(x[1])):
              if not(entry[0] in [x[0] for x in assigned]):
                stats["TP"] = stats["TP"] + 1
                assigned.append(entry)
                notfound = False
                break
      stats["FP"] = stats["FP"] + len( parsedresults[day]) - len(list(set([x[0] for x in assigned])))
      stats["deviation"] = [x[1] for x in assigned]

    else:
      for log in parsedresults[day]:
        found = list(filter(lambda x: abs(x[0]) < customMargin, list(map(lambda x: ((log - x).total_seconds(), x), parsedlogs[day])) ))
        if(len(found) > 0):
          stats["TP"] = stats["TP"] + 1
          stats["deviation"].append(min([x[0] for x in found]))
        else:
          stats["FP"] = stats["FP"] + 1

    for log in parsedlogs[day]:
      found = list(filter(lambda x: x < customMargin, list(map(lambda x: abs(log - x).total_seconds(), parsedresults[day])) ))
      if(len(found) == 0):
        stats["FN"] = stats["FN"] + 1
    
    statsperday.append(stats)

  return statsperday

if __name__ == "__main__":
  pattern()