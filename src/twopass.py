from src.changepoints import ChangePointDetection
from sklearn import cluster
import math
import statistics
import pandas as pd
import stumpy
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as dates
from matplotlib.patches import Rectangle
import datetime as dt
from tslearn.barycenters import dtw_barycenter_averaging_petitjean, dtw_barycenter_averaging, softdtw_barycenter
from dtaidistance import dtw
import array

plt.rcParams["figure.figsize"] = [20, 6]  # width, height
plt.rcParams['xtick.direction'] = 'out'


def firstPass(value_points, pen=1000, window=35, debug=False, method="Window"):
    cp = ChangePointDetection()
    res = cp.rupture(value_points=value_points, pen=pen, window=window, algrthm=method)

    if(debug):
        plt.suptitle('HaasST10 Wirkleistung', fontsize='30')
        plt.xlabel('Time', fontsize ='20')
        plt.ylabel('Acceleration', fontsize='20')
        plt.plot(value_points)

        for idx in res:
            plt.axvline(x=idx, linestyle="dashed")
        plt.show()
    
    segments = []
    for bp in range(1,len(res)):
        segments.append(value_points[res[bp-1]-1:res[bp]-1])
    return segments

# Template trimming

def trimming(tmpl, trimrange=0.25, debug=False):
    trim_start = len(tmpl) - math.floor(len(tmpl) * trimrange)

    lowest_diff = (0, len(tmpl) - 1)

    for i in range(1,math.floor(len(tmpl) * trimrange)):
        avg_f = sum(tmpl[trim_start:trim_start + i])/len(tmpl[trim_start:trim_start + i])
        avg_b = sum(tmpl[trim_start+i:])/len(tmpl[trim_start+i:])

        if(avg_b - avg_f < lowest_diff[0]):
            lowest_diff = (avg_b - avg_f, trim_start+i)

    if(debug):
        plt.suptitle('diff=' + str(lowest_diff[0]), fontsize='30')
        plt.xlabel('Time', fontsize ='20')
        plt.ylabel('Acceleration', fontsize='20')
        plt.plot(tmpl)
        plt.axvline(x=lowest_diff[1], linestyle="dashed", color="red")
        plt.axvline(x=trim_start, linestyle="dashed", color="black")

        plt.show()
    return tmpl[:lowest_diff[1]+1]

def clusterSegments(segments):
    seg_avg = list(map(lambda x: sum(x)/len(x), segments))
    
    print("Average value:", str(len(seg_avg)), "; Number of segments:", str(len(segments)))
    
    # perform k-means clustering
    kmeans = cluster.KMeans(n_clusters=2, random_state=0).fit(np.array(seg_avg).reshape(-1,1))
    tmpl_pool = []

    print("Number of labels: ", len(kmeans.labels_))

    lookforlabel = np.argmax(kmeans.cluster_centers_)
    for i in range(len(kmeans.labels_)):
        if(kmeans.labels_[i] == lookforlabel):
            tmpl_pool.append(segments[i])

    # filter too far away from average length
    avglen = sum(list(map(lambda x: len(x), tmpl_pool)))/len(tmpl_pool)
    lentmpl_pool = []
    for tmpl in tmpl_pool:
        if(abs(len(tmpl) - avglen) < avglen * 0.3):
            lentmpl_pool.append(tmpl)
    
    print("Kept " + str(len(lentmpl_pool)) + " segments out of " + str(len(tmpl_pool)) + " total")

    tmpl_pool = lentmpl_pool
    return tmpl_pool


def averageTemplate(tmpl_pool, template="avg"):

    maxrange = math.floor(sum(list(map(lambda x: len(x), tmpl_pool)))/len(tmpl_pool))

    # Get a tempalte by selecting a section with median average value
    pool_avgs = list(map(lambda x: sum(x)/len(x), tmpl_pool))
    zipped_pool = zip(pool_avgs, tmpl_pool)
    zipped_pool = sorted(zipped_pool, key=lambda x: x[0])

    selected_template = zipped_pool[math.floor(len(zipped_pool) / 2)][1]
    average_template = []
    median_template = []
    for i in range(maxrange):
        avg = 0
        dec = 0
        med_pool = []
        for tmpl in tmpl_pool:
            if(len(tmpl) > i):
                avg += tmpl[i]
                med_pool.append(tmpl[i])
            else:
                dec-=1
        avg = avg / (len(tmpl_pool) + dec)
        average_template.append(avg)
        med = statistics.median_high(med_pool)
        median_template.append(med)
    
    if(template=="avg"):
        return average_template
    elif(template=="med"):
        return median_template
    elif(template=="select"):
        return selected_template
    else:
        print("Template Unknown, using avg as default")
        return average_template

def barycenterTemplate(tmpl_pool, template="dba"):
    # Templating via barycenters
    dba = []
    if(template=="dba"):
        dba = dtw_barycenter_averaging(tmpl_pool)
    elif(template=="fp_dba"):
        dba = dtw_barycenter_averaging_petitjean(tmpl_pool)
    elif(template=="softdba"):
        dba = softdtw_barycenter(tmpl_pool, gamma=1.)
    else:
        print("Unknown Barycenter Algorithm, using DBA as default")
        dba = dtw_barycenter_averaging(tmpl_pool)
    dba_reshaped = []
    for v in dba:
        dba_reshaped.append(v[0])
    return dba_reshaped

def dtw_finder(template, series, offset_amount):

    x = array.array("d", template)

    profile = []
    for i in range(0, len(series)-1):
        found = (i,1000000000000,0)
        for offset in range(math.floor(-len(template) * offset_amount), math.floor(len(template) * offset_amount)):
            y = array.array("d", series[i:i+len(template)+offset])
            dist = dtw.distance_fast(x,y, window = math.floor(len(template) * offset_amount * 2))
            if(dist < found[1]):
                found = (i, dist, min(np.int64(offset + len(template)), np.int64(len(series) - i - 1)))
        profile.append(found)
    return profile

def dtwChangepoints(average_template, value_points, mode="dynamic", t=1000, k=10):
    # statick, dynamic

    profile = dtw_finder(average_template, value_points, 0.1)
    # This simply returns the (sorted) positional indices of the top 16 smallest distances found in the distance_profile
    # The default maximum distance is max_distance = max(np.mean(D) - 2 * np.std(D), np.min(D)). This is the typical “two standard deviations below from the mean”.
    #k = math.floor(len(profile)/4)
    idxs = np.argsort(np.array(profile)[:,1])
    #idxs = idxs[:k]

    filtering_range = 0.8

    filtered_idxs = []
    for idx in idxs:
        kill = False
        for filtered in filtered_idxs:
            if(idx > filtered - len(average_template) * filtering_range and idx < filtered + len(average_template) * filtering_range):
                kill = True
                break
        if(not(kill)):
            filtered_idxs.append(idx)

    if(mode == "dynamic"):
        ## Clean filtered_idxs output
        filtidxtosim = [profile[x][1]  for x in filtered_idxs]
        filtidxtoavg = [sum(value_points[x:x+profile[x][2]])/len(value_points[x:x+profile[x][2]]) for x in filtered_idxs]
        kmeans = cluster.KMeans(n_clusters=2, random_state=0).fit(np.array(list(zip(filtidxtosim, filtidxtoavg))))
        #kmeans = cluster.KMeans(n_clusters=2, random_state=0).fit(np.array(filtidxtosim).reshape(-1,1))
        kmeans.cluster_centers_
        label_to_select = np.argmin([x[0] for x in kmeans.cluster_centers_])
        filtered_idxs = [x for idx, x in enumerate(filtered_idxs) if kmeans.labels_[idx] == label_to_select]
    elif(mode == "statick"):
        print("mode k: " + str(k))
        filtered_idxs = filtered_idxs[:k]
    elif(mode == "statict"):
        filtered_idxs = [x for x in filtered_idxs if profile[x][1] < t]
    else:
        print("Event Detection Mode " + mode + " unknown")

    result = list(map(lambda x: (x, x + profile[x][2], profile[x][1]), filtered_idxs))
    return result

def matrixChangepoints(average_template, value_points, mode="dynamic", t=1000, _k=10):
    distance_profile = stumpy.core.mass_absolute(average_template, value_points)
    #
    idx = np.argmin(distance_profile)

    # This simply returns the (sorted) positional indices of the top x smallest distances found in the distance_profile
    k = len(distance_profile)-1
    idxs = np.argpartition(distance_profile, k)[:k]
    idxs = idxs[np.argsort(distance_profile[idxs])]

    filtering_range = 0.8

    filtered_idxs = []
    for idx in idxs:
        kill = False
        for filtered in filtered_idxs:
            if(idx > filtered - len(average_template) * filtering_range and idx < filtered + len(average_template) * filtering_range):
                kill = True
                break
        if(not(kill)):
            filtered_idxs.append(idx)

    if(mode == "dynamic"):
        ## Clean filtered_idxs output
        filtidxtosim = [distance_profile[x]  for x in filtered_idxs]
        filtidxtoavg = [sum(value_points[x:x+len(average_template)])/len(average_template) for x in filtered_idxs]
        kmeans = cluster.KMeans(n_clusters=2, random_state=0).fit(np.array(list(zip(filtidxtosim, filtidxtoavg))))
        kmeans.cluster_centers_
        label_to_select = np.argmin([x[0] for x in kmeans.cluster_centers_])
        filtered_idxs = [x for idx, x in enumerate(filtered_idxs) if kmeans.labels_[idx] == label_to_select]
    elif(mode == "statick"):
        print("mode k: " + str(_k))
        filtered_idxs = filtered_idxs[:_k]
    elif(mode == "statict"):
        filtered_idxs = [x for x in filtered_idxs if distance_profile[x] < t]
    else:
        print("Event Detection Mode " + mode + " unknown")

    result = list(map(lambda x: (x, min(x + len(average_template), len(value_points) - 1)), filtered_idxs))
    return result

def main(value_points, pen, window, algo, template, _trimming, cpmethod, mode, t, k):
    segments = firstPass(value_points, pen=pen, window=window, method=cpmethod)

    tmpl_pool = clusterSegments(segments)

    if(_trimming):
        tmpl_pool = list(map(lambda x: trimming(x), tmpl_pool))
    
    average_template = []
    if(template=="avg"):
        average_template = averageTemplate(tmpl_pool, template)
    elif(template=="med"):
        average_template = averageTemplate(tmpl_pool, template)
    elif(template=="select"):
        average_template = averageTemplate(tmpl_pool, template)
    elif(template=="dba"):
        average_template = barycenterTemplate(tmpl_pool, template)
    elif(template=="fp_dba"):
        average_template = barycenterTemplate(tmpl_pool, template)
    elif(template=="softdba"):
        average_template = barycenterTemplate(tmpl_pool, template)
    else:
        print("Templating Algorithm unknown")
        return False
    
    changepoints = []

    if(algo == "matrix"):
        changepoints = matrixChangepoints(average_template, value_points, mode, t, k)
    elif(algo == "dtw"):
        changepoints = dtwChangepoints(average_template, value_points, mode, t, k)
    else:
        print("Pattern matching Algorithm unknown")
        return False

    return changepoints

if __name__ == "__main__":

    print("Hallo")
    
    