import datetime as dt
import dateutil

faultyIntervals = [
  ("2020-06-23 09:19", "2020-06-23 09:52"),
  ("2020-06-23 11:58", "2020-06-23 12:01"),
  ("2020-06-23 13:48", "2020-06-23 13:55"),
  ("2020-06-23 12:07", "2020-06-23 12:14"),

  ("2020-06-24 12:07", "2020-06-24 12:39"),
  ("2020-06-24 15:22", "2020-06-24 15:35"),
  ("2020-06-24 16:05", "2020-06-24 16:18"),

  ("2020-06-25 08:21", "2020-06-25 08:33"),
  ("2020-06-25 08:52", "2020-06-25 09:01"),
  ("2020-06-25 13:52", "2020-06-25 15:41"),
]

faultyIntervals = list(map(lambda x: (dateutil.parser.parse(x[0]).astimezone(tz=dt.timezone.utc), dateutil.parser.parse(x[1]).astimezone(tz=dt.timezone.utc)), faultyIntervals))

def cleanup(eventlog, debug=False):

  toRemove = []

  for log in eventlog:
    startts = dateutil.parser.parse(log["Start Betrieb"]).astimezone(tz=dt.timezone.utc)
    endts = dateutil.parser.parse(log["Ende Betrieb"]).astimezone(tz=dt.timezone.utc)
    if(timeStampInFaulty(startts)):
      if(debug): print("Removing on " + log["Maschinenname"] + " Bauteil " + log["Bauteilname"])
      toRemove.append(log["Bauteilname"])
  return list(filter(lambda x: not x["Bauteilname"] in toRemove, eventlog))

def timeStampInFaulty(timestamp):
  for faulty in faultyIntervals:
    if(timestamp > faulty[0] and timestamp < faulty[1]):
      return True
  return False