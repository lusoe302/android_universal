import os
import sys

for file in os.listdir(sys.argv[1]):
    if "init" in file and ".usb.rc" in file:
        ft=os.path.join(sys.argv[1],file)
        with open(ft,'rb') as rf:
            data=rf.readlines()
        with open(ft, 'wb') as wf:
            flag=0
            i=0
            while (i<len(data)):
                    line=data[i]
                    if b"on property:sys.usb.config=mtp" in line and not b"adb" in line:
                        while (not b"setprop sys.usb.state ${sys.usb.config}" in line):
                            line=data[i]
                            if b"functions" in line:
                                idx=line.rfind(b"functions ")
                                line=line[:idx+10]+b"mtp,adb\n"
                            elif b"setprop sys.usb.state" in line:
                                wf.write(b'    start adbd\n')
                                break
                            wf.write(line)
                            i+=1
                    if b"on property:sys.usb.config=sec_charging" in line and not b"adb" in line:
                        while (not b"setprop sys.usb.state ${sys.usb.config}" in line):
                            line=data[i]
                            if b"functions" in line:
                                idx=line.rfind(b"functions ")
                                line=line[:idx+10]+b"sec_charging,adb\n"
                            elif b"setprop sys.usb.state" in line:
                                wf.write(b'    start adbd\n')
                                break
                            wf.write(line)
                            i+=1
                    if b"on property:sys.usb.config=charging" in line and not b"adb" in line:
                        while (not b"setprop sys.usb.state ${sys.usb.config}" in line):
                            line=data[i]
                            if b"functions" in line:
                                idx=line.rfind(b"functions ")
                                line=line[:idx+10]+b"charging,adb\n"
                            elif b"setprop sys.usb.state" in line:
                                wf.write(b'    start adbd\n')
                                break
                            wf.write(line)
                            i+=1
                    wf.write(line)
                    i+=1
                