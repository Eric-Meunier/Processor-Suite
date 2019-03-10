"""
Will probably all be in a function in the future, so it can iterate through multiple files
"""

import re
import matplotlib.pyplot as plt
import numpy as np #Not used yet, not sure if it's needed yet. 

with open("Z.PEM", "rt") as in_file:
    file = in_file.read()

    re_header = re.compile( #Parsing the header information
    r'~[\r\n](?:<.*[\r\n])+(?P<Client>\w.*)[\r\n](?P<Grid>.*)[\r\n](?P<LineHole>.*)[\r\n](?P<Loop>.*)[\r\n](?P<Date>.*)[\r\n](?P<TypeOfSurvey>\w+\s\w+).+\s(?P<Timebase>\d+\.\d+)\s(?P<Ramp>\d+)\s(?P<NumChannels>\d+).*[\r\n](?P<Receiver>#\d+).*[\n\r]+(?P<ChannelTimes>[\W\d]+[^$])$',re.MULTILINE)
    
    headers=['Client','Grid','LineHole','Loop','Date','TypeOfSurvey','Timebase','Ramp','NumChannels','Receiver','ChannelTimes']
    header_results={}

    for i in range(len(headers)): #Compiles the header information from the PEM file into a dictionary
        for m in re.finditer(re_header, file):
            header_results[headers[i]]=m.group(i+1)
    units = re.search(r"<UNI> (\w.+)", file, re.MULTILINE)
    
        # Header section finished. Everything below is for the EM data in the PEM files

    re_data = re.compile( #Parsing the EM data information
        r'(?P<Station>^\d+)\s(?P<Component>[a-zA-Z])R(?P<ReadingIndex>\d+).*[\r\n](?:D\d.+[\n\r])(?P<Data>[\W\d]+[\n\r])', re.MULTILINE)
    station_number=[]
    reading_index=[]
    decay=[]
    component=[]

    for match in re_data.finditer(file): #Compiles the EM data section
        station_number.append(match.group('Station'))
        reading_index.append(match.group('ReadingIndex'))
        decay.append([float(x) for x in match.group('Data').split()])        
        component.append(match.group('Component'))

        # print('\n\nStation: ',station_number,'\nReading Index :',reading_index,'\nDecay: ',decay,'\nComponent: ',component)
    
    survey=[[s,r,c,d] for s,r,c,d in zip(station_number,reading_index,component,decay)] #combines the lists into one list of lists. Not sure if it will be used.
    
    unique_stations={int(n) for n in station_number} #Creates a set out of all the stations, which automatically removes duplicates.
    print (sorted(unique_stations))

    # for station in ([x for i, x in enumerate(station_number) if station_number.index(x) == i]):
    #     print (station_number.index(station))
    
    """
     Plotting section below. Will probably be a function in the future.
    """
    # x=station_number 
    # y=[y[6] for y in decay]
    # plt.plot(x,y)
    # plt.show()
 

