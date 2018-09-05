import os
import argparse
import struct
import binascii
import platform

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
    
def main():
    print("\nMakeramdisk Android Generic v1.4 (c) B. Kerler 2018, Email: bjoern@kerler.re")
    print("------------------------------------------------------------\n")
    busybox=os.path.join("root","scripts","busybox")+" ash "
    Linux=False
    if platform.system()=="Windows":
        print("Windows detected.")
    else:
        print("Linux/Mac detected.")
        busybox=""
        Linux=True
        
    fake=None
    if os.path.exists("boot.img.lz4"):
        print("Compressed lz4 boot detected, unpacking.")
        fn=os.path.join("root","scripts","lz4","boot.img.lz4")
        os.system(fn)
    try:
        with open("boot.img","rb") as rf:
            data=rf.read()
            try:
                param=getheader("boot.img")
                kernelsize = int((param.kernel_size + param.page_size - 1) / param.page_size) * param.page_size
                ramdisksize = int((param.ramdisk_size + param.page_size - 1) / param.page_size) * param.page_size
                secondsize = int((param.second_size + param.page_size - 1) / param.page_size) * param.page_size
                qcdtsize = int((param.qcdt_size + param.page_size - 1) / param.page_size) * param.page_size
                length=param.page_size+kernelsize+ramdisksize+secondsize+qcdtsize
                fake=data[length:]
            except:
                fake=None
    except:
        print("Couldn't find boot.img, aborting.")
        exit(1)
    
    scriptpath="root/scripts/patchit.sh"
   
    idx=data.find(b"aarch64")
    if (idx!=-1):
        print("64Bit detected")
        os.system(busybox+scriptpath+" boot.img boot.patched 64Bit")
    else:
        print("32Bit detected")
        os.system(busybox+scriptpath+" boot.img boot.patched 32Bit")

    if fake!=None:
        if os.path.exists("boot.patched.signed"):
                os.rename("boot.patched.signed","boot.signed")
                param=getheader("boot.signed")
                kernelsize = int((param.kernel_size + param.page_size - 1) / param.page_size) * param.page_size
                ramdisksize = int((param.ramdisk_size + param.page_size - 1) / param.page_size) * param.page_size
                secondsize = int((param.second_size + param.page_size - 1) / param.page_size) * param.page_size
                qcdtsize = int((param.qcdt_size + param.page_size - 1) / param.page_size) * param.page_size
                length=param.page_size+kernelsize+ramdisksize+secondsize+qcdtsize
                print("Creating rot fake....")
                with open("boot.signed","rb") as rf:
                    data=rf.read()
                    data=data[:length]
                    with open("boot.rotfake","wb") as wb:
                        wb.write(data)
                        wb.write(fake)
                print("Done :D")

if __name__ == '__main__':
    main()