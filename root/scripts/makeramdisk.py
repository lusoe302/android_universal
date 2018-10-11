#!/usr/bin/env python3
import os
import struct
import argparse
import tarfile
import platform
import subprocess, sys
import shutil
import gzip
import stat

from time import sleep
version="v3.0"

class androidboot:
    magic="ANDROID!" #BOOT_MAGIC_SIZE 8
    kernel_size=0
    kernel_addr=0
    ramdisk_size=0
    ramdisk_addr=0
    second_addr=0
    second_size=0
    tags_addr=0
    page_size=0
    qcdt_size=0
    os_version=0
    name="" #BOOT_NAME_SIZE 16
    cmdline="" #BOOT_ARGS_SIZE 512
    id=[] #uint*8
    extra_cmdline="" #BOOT_EXTRA_ARGS_SIZE 1024

def getheader(inputfile):
    param = androidboot()
    with open(inputfile, 'rb') as rf:
        header = rf.read(0x660)
        fields = struct.unpack('<8sIIIIIIIIII16s512s8I1024s', header)
        param.magic = fields[0]
        param.kernel_size = fields[1]
        param.kernel_addr = fields[2]
        param.ramdisk_size = fields[3]
        param.ramdisk_addr = fields[4]
        param.second_size = fields[5]
        param.second_addr = fields[6]
        param.tags_addr = fields[7]
        param.page_size = fields[8]
        param.qcdt_size = fields[9]
        param.os_version = fields[10]
        param.name = fields[11]
        param.cmdline = fields[12]
        param.id = [fields[13],fields[14],fields[15],fields[16],fields[17],fields[18],fields[19],fields[20]]
        param.extra_cmdline = fields[21]
    return param

def int_to_bytes(x):
    return x.to_bytes((x.bit_length() + 7) // 8, 'big')

def del_rw(action, name, exc):
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)

class ramdiskmod():
    custom=False
    precustom=False
    filename=""
    Linux=False
    TPATH=""
    NAME=""
    BOOTIMAGE= ""
    RECOVERYIMG= ""
    TARGET="boot.patched"
    disable = 0
    RPATH="tmp"
    RAMDISK = "ramdisk"
    RRAMDISK = "rramdisk"
    PARAM = "up_param"
    BOOTIMG = os.path.join("root","scripts","bootimg")
    SEINJECT_TRACE_LEVEL = 1
    BB = os.path.join("root","scripts","busybox")
    BIT=64

    def __init__(self,path,filename,bit,custom=False, precustom=False):
        self.custom=custom
        self.precustom=precustom
        self.TPATH=path
        self.BOOTIMAGE = os.path.join(self.TPATH, filename)
        self.RECOVERYIMG = os.path.join(path, "recovery.img")
        self.RPATH="tmp"
        self.RAMDISK = os.path.join(self.RPATH,"ramdisk")
        self.RRAMDISK = os.path.join(self.RPATH,"rramdisk")
        if platform.system() == "Windows":
            self.Linux=False
            self.BB +=" "
        else:
            self.Linux=True
            self.BB = ""
        self.BIT=int(bit)

    def compress(self,to_compress):
        f = open("__tmp_uncompressed__", "wb")
        f.write(to_compress)
        f.close()
        if platform.system() == "Windows":
            cmd = "root\\init-bootstrap\\quicklz.exe"
        else:
            cmd = "root/init-bootstrap/quicklz"
        if not os.path.isfile(cmd):
            raise IOError("quicklz binary not found. Please compile it first.")
        cmd = "\"" + cmd + "\"" + " comp __tmp_uncompressed__ __tmp_compressed__"
        os.system(cmd)
        f = open("__tmp_compressed__", "rb")
        data = f.read()
        f.close()
        os.remove("__tmp_uncompressed__")
        os.remove("__tmp_compressed__")
        return data


    def run(self,cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        #(output,err) = p.communicate()
        #p_status=p.wait()
        #p.stdin.write('Info\n')
        #sleep(0.1)
        output=b""
        while True:
            err = p.stderr.read(1)
            inp=b''
            if err==b'':
                inp = p.stdout.read(1)
            output+=inp
            if inp==b'' and err==b'' and p.poll() != None:
                break
            if err!=b'':
                sys.stdout.write(str(err,'utf-8'))
                sys.stdout.flush()
            if inp!=b'':
                sys.stdout.write(str(inp,'utf-8'))
                sys.stdout.flush()
        return output

    def unpack_kernel(self,path):
        print("Unpacking kernel : %s to %s" % (self.BOOTIMAGE,path))
        info=self.run(self.BOOTIMG +" unpackimg -i " + self.BOOTIMAGE + " -k " + os.path.join(path, "kernel") + " -r " + os.path.join(path, "rd.gz") + " -d " + os.path.join(path, "dtb"))
        lines=str(info,'utf-8').split("\r\n")
        details={}
        for line in lines:
            if len(line.split("="))>0:
                key=line.split("=")[0]
                value=line[len(key)+1:][1:-1]
                details[key]=value
        return details

    def unpack_recovery(self,path):
        info=self.run(self.BOOTIMG +" unpackimg -i " + self.RECOVERYIMG + " -k " + os.path.join(path, "rkernel") + " -r " + os.path.join(path, "rrd.gz") + " -d " + os.path.join(path, "rdtb"))

    def rmrf(self,path):
        if os.path.exists(path):
            if os.path.isfile(path):
                del_rw("",path,"")
            else:
                shutil.rmtree(path, onerror=del_rw)

    def guz(self,filename):
        file_content=b""
        with gzip.open(filename,'rb') as f:
            file_content = f.read()
        return file_content

    def unpack_initfs(self,filename,path):
        print ("- Unpacking initramfs to %s" % path)
        if os.path.exists(path):
            self.rmrf(path)
        os.mkdir(path)
        rdcpio=self.guz(os.path.join(self.RPATH,filename))
        p = subprocess.Popen(self.BOOTIMG+" unpackinitfs -d "+path,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        p.stdin.write(rdcpio)
        sleep(0.1)
        while True:
            out = p.stderr.read(1)
            if out==b'' and p.poll() != None:
                break
            if out !=b'':
                sys.stdout.write(out)
                sys.stdout.flush()

    def fix_mtp(self):
        for file in os.listdir(self.RAMDISK):
            if (len(file.split("."))>3) and "init" in file and ".usb.rc" in file:
                with open(self.RAMDISK + "/" + file, 'rb') as rf:
                    data = rf.readlines()
                with open(self.RAMDISK + "/" + file, 'wb') as wf:
                    flag = 0
                    i = 0
                    while (i < len(data)):
                        line = data[i]
                        if b"on property:sys.usb.config=mtp\n" in line or b"on property:sys.usb.config=mtp " in line:
                            wf.write(b'on property:sys.usb.config=mtp\n')
                            wf.write(b'    start adbd\n\n')
                            while (not b"setprop sys.usb.state ${sys.usb.config}" in line):
                                line = data[i]
                                if b"functions" in line:
                                    idx = line.rfind(b"functions ")
                                    line = line[:idx + 10] + b"mtp,adb\n"
                                elif b"setprop sys.usb.state" in line:
                                    break
                                wf.write(line)
                                i += 1
                        if b"on property:sys.usb.config=charging\n" in line or b"on property:sys.usb.config=charging " in line:
                            wf.write(b'on property:sys.usb.config=charging\n')
                            wf.write(b'    start adbd\n\n')
                            while (not b"setprop sys.usb.state ${sys.usb.config}" in line):
                                line = data[i]
                                if b"functions" in line:
                                    idx = line.rfind(b"functions ")
                                    line = line[:idx + 10] + b"charging,adb\n"
                                elif b"setprop sys.usb.state" in line:
                                    break
                                wf.write(line)
                                i += 1
                        wf.write(line)
                        i += 1

    def repack_stuff(self,details):
        self.run(self.BOOTIMG + " mkinitfs " + self.RAMDISK + " | " + self.BB + " gzip -c > "+os.path.join(self.RPATH,self.TARGET+".cpio.gz"))
        cmd=self.BOOTIMG+" mkimg --kernel "+os.path.join(self.RPATH,"kernel")+" --ramdisk "+os.path.join(self.RPATH,self.TARGET+".cpio.gz")+" "
        cmd += "--base 0x0 "
        if "BOARD_KERNEL_BOARD" in details:
            cmd+="--board \""+details["BOARD_KERNEL_BOARD"]+"\" "
        if "BOARD_PAGE_SIZE" in details:
            cmd+="--pagesize "+details["BOARD_PAGE_SIZE"]+" "
        if "BOARD_KERNEL_OFFSET" in details:
            cmd+="--kernel_offset 0x"+details["BOARD_KERNEL_OFFSET"]+" "
        if "BOARD_RAMDISK_OFFSET" in details:
            cmd+="--ramdisk_offset 0x"+details["BOARD_RAMDISK_OFFSET"]+" "
        if "BOARD_TAGS_OFFSET" in details:
            cmd+="--tags_offset 0x"+details["BOARD_TAGS_OFFSET"]+" "
        if "BOARD_KERNEL_CMDLINE" in details:
            cmd+="--cmdline \""+details["BOARD_KERNEL_CMDLINE"]+"\" "
        if os.path.exists(os.path.join(self.RPATH,"dtb")):
            cmd+="--dt "+os.path.join(self.RPATH,"dtb")+" "
        cmd+="-o "+self.TARGET
        self.run(cmd)

    def bbr(self,input):
        self.run(self.BB + input)

    def patch_stuff(self):
        if (self.precustom==True):
            input("- Make your changes before patches in the ramdisk (%s Folder). Press Enter to continue." % self.RAMDISK)
        print("- Doing our stuff")
        print("- Copying needed binaries")
        shutil.copyfile("root/rootshell/init.shell.rc",self.RAMDISK+"/init.shell.rc@0750")
        shutil.copyfile("root/rootshell/rootshell.sh", self.RAMDISK + "/sbin/rootshell.sh@0755")
        shutil.copyfile("root/rootshell/root_hack.sh", self.RAMDISK + "/sbin/root_hack.sh@0755")
        #shutil.copyfile("root/rootshell/rw", self.RAMDISK + "/sbin/rw@0755")
        shutil.copyfile("root/other/bruteforce", self.RAMDISK + "/sbin/bruteforce@0755")
        shutil.copyfile("root/.android/adb_keys",self.RAMDISK+"/adb_keys")
        print("- Patching sepolicy")
        if not os.path.exists(self.RAMDISK+"/sepolicy@0644"):
            print("- Unpacking recovery, missing sepolicy file in boot !")
            self.unpack_recovery(self.RPATH)
            self.rmrf(self.RRAMDISK)
            os.mkdir(self.RRAMDISK)
            self.unpack_initfs("rrd.gz",self.RRAMDISK)
            shutil.copyfile(self.RRAMDISK+"/sepolicy@0644",self.RAMDISK+"/sepolicy@0644")
            if not os.path.exists(self.RAMDISK + "/sepolicy_version@0644"):
                shutil.copyfile(self.RRAMDISK + "/sepolicy_version@0644", self.RAMDISK + "/sepolicy_version@0644")
            self.rmrf(self.RRAMDISK)
            os.remove(self.RPATH + "/rkernel")
            os.remove(self.RPATH + "/rrd.gz")
            os.remove(self.RPATH + "/rdtb")
        #$BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 --minimal
        self.run(self.BOOTIMG+" magiskpolicy --load "+os.path.join(self.RAMDISK,"sepolicy@0644")+" --save "+os.path.join(self.RAMDISK,"sepolicy@0644")+" --magisk")
        #$BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 "allow su vendor_toolbox_exec file { execute_no_trans }"
        #$BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 "allow su shell_data_file dir { search }"
        #$BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 "allow su { port node } tcp_socket *"
        self.run(self.BOOTIMG + " magiskpolicy --load " + os.path.join(self.RAMDISK,"sepolicy@0644")+" --save " + os.path.join(self.RAMDISK,"sepolicy@0644")+" \"allow su * process { * }\"")
        self.run(self.BOOTIMG + " magiskpolicy --load " + os.path.join(self.RAMDISK,"sepolicy@0644")+" --save " + os.path.join(self.RAMDISK,"sepolicy@0644")+" \"allow * su process { * }\"")
        self.run(self.BOOTIMG + " magiskpolicy --load " + os.path.join(self.RAMDISK,"sepolicy@0644")+" --save " + os.path.join(self.RAMDISK,"sepolicy@0644")+" \"allow su vold * { * }\"")
        self.run(self.BOOTIMG + " magiskpolicy --load " + os.path.join(self.RAMDISK,"sepolicy@0644")+" --save " + os.path.join(self.RAMDISK,"sepolicy@0644")+" \"allow vold su * { * }\"")
        #self.run(self.BOOTIMG + " magiskpolicy --load " + os.path.join(self.RAMDISK,"sepolicy@0644")+" --save " + os.#path.join(self.RAMDISK,"sepolicy@0644")+" \"allow su * process { * }\"")
        #self.run(self.BOOTIMG + " magiskpolicy --load " + os.path.join(self.RAMDISK,"sepolicy@0644")+" --save " + os.#path.join(self.RAMDISK,"sepolicy@0644")+" \"allow * su process { * }\"")
        
        print("- Injecting rootshell")
        self.bbr("sed -i \"/on early-init/iimport /init.shell.rc\\n\" "+os.path.join(self.RAMDISK,"init.rc@0750"))
        self.bbr("sed -i \"/trigger fs/atrigger rootshell_trigger\\n\" "+os.path.join(self.RAMDISK,"init.rc@0750"))

        print("- Injecting adb")
        ff=""
        if os.path.exists(self.RAMDISK+"/prop.default@0644"):
            ff=os.path.join(self.RAMDISK,"prop.default@0644")
        elif os.path.exists(self.RAMDISK + "/default.prop@0600"):
            ff = os.path.join(self.RAMDISK,"default.prop@0600")
        elif os.path.exists(self.RAMDISK + "/default.prop@0644"):
            ff = os.path.join(self.RAMDISK,"default.prop@0644")
        if ff!="":
            self.bbr("sed -i -e \"s/persist.sys.usb.config=.*/persist.sys.usb.config=adb/g\" "+ff)
        print("- Injecting sepolicy_version")
        self.bbr("sed -i -e \"1 s/....$/9999/\" "+self.RAMDISK+"/sepolicy_version@0644")
        print("- Patching init")
        self.run(self.BOOTIMG+" hexpatch "+os.path.join(self.RAMDISK,"init@0750")+" 2F76656E646F722F6574632F73656C696E75782F707265636F6D70696C65645F7365706F6C69637900 2F7365706F6C6963790000000000000000000000000000000000000000000000000000000000000000")
        self.fix_mtp()

        #if (self.MODE==1):
        #    shutil.copyfile("root/magisk/init.magisk.rc",self.RAMDISK+"/init.magisk.rc@0750")
        #    if self.BIT==32:
        #        shutil.copyfile("root/magisk/magisk32",self.RAMDISK+"/sbin/magisk@0750")
        #    elif self.BIT==64:
        #        shutil.copyfile("root/magisk/magisk64", self.RAMDISK + "/sbin/magisk@0750")
        #    self.run(self.BB+"sed -i '/on early-init/iimport /init.magisk.rc\n' "+self.RAMDISK+"/init.rc@0750")

        if (self.custom==True):
            input("- Make your changes after patches in the ramdisk (%s Folder). Press Enter to continue." % self.RAMDISK)

    def sign(self,target):
        print("Signing ....")
        if os.path.exists(target+".signed"):
           os.remove(target+".signed")
        self.run("java -jar "+os.path.join("root","keys","BootSignature.jar")+" /boot "+target+" "+os.path.join("root","keys","verity.pk8")+" "+os.path.join("root","keys","verity.x509.pem")+" "+target+".signed")
        self.run("java -jar "+os.path.join("root","keys","BootSignature.jar")+" -verify "+target+".signed")

    def rotfake(self,org,target):
        fake = None
        if ".lz4" in org:
            print("Compressed lz4 boot detected, unpacking.")
            fn = os.path.join("root", "scripts", "lz4", org)
            os.system(fn)
        try:
            with open(org, "rb") as rf:
                data = rf.read()
                try:
                    param = getheader(org)
                    kernelsize = int((param.kernel_size + param.page_size - 1) / param.page_size) * param.page_size
                    ramdisksize = int((param.ramdisk_size + param.page_size - 1) / param.page_size) * param.page_size
                    secondsize = int((param.second_size + param.page_size - 1) / param.page_size) * param.page_size
                    qcdtsize = int((param.qcdt_size + param.page_size - 1) / param.page_size) * param.page_size
                    length = param.page_size + kernelsize + ramdisksize + secondsize + qcdtsize
                    fake = data[length:]
                    fake = fake[0:(int(fake[2]) << 8) + int(fake[3])+4]
                except:
                    fake = None
        except:
            print("Couldn't find " + org + ", aborting.")
            exit(1)

        target=target[:target.rfind(".")]
        if fake != None:
            if os.path.exists(target + ".patched.signed"):
                if os.path.exists(target+".signed"):
                    os.remove(target+".signed")
                os.rename(target + ".patched.signed", target + ".signed")
                param = getheader(target + ".signed")
                kernelsize = int((param.kernel_size + param.page_size - 1) / param.page_size) * param.page_size
                ramdisksize = int((param.ramdisk_size + param.page_size - 1) / param.page_size) * param.page_size
                secondsize = int((param.second_size + param.page_size - 1) / param.page_size) * param.page_size
                qcdtsize = int((param.qcdt_size + param.page_size - 1) / param.page_size) * param.page_size
                length = param.page_size + kernelsize + ramdisksize + secondsize + qcdtsize
                print("- Creating rot fake with length 0x%08X" % length)
                with open(target + ".signed", "rb") as rf:
                    rdata = rf.read()
                    rdata = rdata[:length]
                    with open(target + ".rotfake", "wb") as wb:
                        wb.write(rdata)
                        wb.write(fake)

    def go(self):
        self.rmrf(self.RPATH)
        os.mkdir(self.RPATH)
        details=self.unpack_kernel(self.RPATH)
        self.unpack_initfs("rd.gz", self.RAMDISK)
        self.patch_stuff()
        self.repack_stuff(details)
        self.rmrf(self.RPATH)
        self.sign(self.TARGET)
        self.rotfake(self.BOOTIMAGE,self.TARGET)
        print("Done :D")
        return

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description='Makeramdisk '+version+' (c) B. Kerler 2018, Email: bjoern@kerler.re')

    parser.add_argument(
        '-filename', '-fn',
        help='boot.img or recovery.img',
        default="boot.img")

    parser.add_argument(
        '-justunpack', '-ju',
        help='Just extract kernel + ramdisk',
        action="store_true",
        default=False)
        
    parser.add_argument(
        '-custom', '-c',
        help='Stop in order to make changes',
        action="store_true",
        default=False)

    parser.add_argument(
        '-precustom', '-pc',
        help='Stop in order to make changes before patches',
        action="store_true",
        default=False)

    args = parser.parse_args()

    custom=args.custom
    precustom=args.precustom

    print("\nMakeramdisk Android "+version+" (c) B. Kerler 2018, Email: bjoern@kerler.re")
    print("------------------------------------------------------------\n")
    
    BOOTPATH,BOOTIMAGE=path,filename=os.path.split(args.filename)
    TMPPATH=os.path.join(BOOTPATH,"tmp")
    if (os.path.exists(TMPPATH)):
        shutil.rmtree(TMPPATH)
    os.mkdir(TMPPATH)

    try:
        with open(os.path.join(BOOTPATH,BOOTIMAGE),"rb") as rf:
             data=rf.read()
    except:
        print("Couldn't find boot.img, aborting.")
        #print(BOOTPATH)
        #print(BOOTIMAGE)
        #print(TMPPATH)
        exit(1)
    
    #scriptpath=os.path.join("root","scripts","patchit.sh")
    
    busybox=os.path.join("root","scripts","busybox")+" ash "
    Linux=False
    if platform.system()=="Windows":
        print("Windows detected.")
    else:
        print("Linux/Mac detected.")
        busybox=""
        Linux=True

    idx=data.find(b"aarch64")
    bit=32
    if (idx!=-1):
        print("64Bit detected")
        bit=64
    else:
        print("32Bit detected")
        bit=32

    filename=""
    if os.path.exists(args.filename):
        BOOTPATH,BOOTIMAGE=os.path.split(args.filename)
    
    rdm = ramdiskmod(BOOTPATH,BOOTIMAGE,int(bit),custom,precustom)
    if args.justunpack==True:
        rdm.RPATH=os.path.join(BOOTPATH,rdm.RPATH)
        rdm.RAMDISK=os.path.join(BOOTPATH,rdm.RAMDISK)
        rdm.unpack_kernel(rdm.RPATH)
        rdm.unpack_initfs("rd.gz", rdm.RAMDISK)
        print("Done !")
    else:
        rdm.go()

if __name__ == '__main__':
    main()
