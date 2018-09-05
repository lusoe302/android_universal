#!/bin/sh
VERSION=V1.4
SOURCE=$1
TARGET=$2
BIT=$3
disable=0
RPATH=./root/tmp
RAMDISK=./root/tmp/ramdisk

#Detect Windows
which winver >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Windows detected"
	WINDOWS=1
	XZ=./xz
else
    echo "Linux detected"
	WINDOWS=0
	XZ=xz
fi

BOOTIMG=./root/scripts/bootimg
SEINJECT_TRACE_LEVEL=1
BB=./root/scripts/busybox

ask() {
	local response
	local response_caption
	local __retval=$2
	local __retvar=$3

	local prompt
	[ "$2" == "1" ] && prompt="[Y/n]" || prompt="[y/N]"

# Busybox "read" does not have -s and does not return before a linefeed,
# so let's use "choice" on Windows
	if [ ${WINDOWS} -eq 1 ]; then
		choice /C:YN /N /M "$1 $prompt"
		[ $? -eq 1 ] && __retval=1 ||__retval=0
	else
		read -s -n 1 -r -p "$1 $prompt " response
		if [ "$response" == "y" ] || [ "$response" == "Y" ]; then
			__retval=1
		elif [ "$response" == "n" ] || [ "$response" == "n" ]; then
			__retval=0
		fi
		[ ${__retval} -eq 1 ] && echo y || echo n
	fi
	eval ${__retvar}=${__retval}
} 

perform() {
	if [ ${WINDOWS} -eq 1 ]; then
		"$BB" "$@"
	else
		"$@"
	fi
} 

detect_platform() {
	local bin

	for file in init init.bin sbin/adbd; do
		bin=$(find_file ${RAMDISK}/${file})
		if [ ! -z "${bin}" ]; then
			"${BOOTIMG}" getarch -q -i ${bin}
			PLATFORM=$?
			if [ ${PLATFORM} -ne 0 ]; then
				ui_print "- Detected platform: $PLATFORM-bit"
				return
			fi
		fi
	done
	ui_print "- Could not determine platfrom"
}

detect_device_from_dtb() {
	local dtb_props=$(${BOOTIMG} dtbinfo -q -i $1)

	[ 0 -eq ${#dtb_props} ] && return

	eval ${dtb_props}
	VENDOR=${DTB_compatible%%,*}
	DEVICE=${DTB_compatible#*,}
	MODEL=${DEVICE%%-*}
	VARIANT=${DEVICE##*-}
}

detect_android() {
	local props=$(find_file ${RAMDISK}/default.prop)
	local val=$(perform grep ro.bootimage.build.fingerprint ${props})

	[ -z "$val" ] && return

	val=${val##*=}
	val=${val#*/}
	val=${val#*/}
	val=${val%%/*}
	VERSION=${val#*:}
	
    if [ "${VERSION}" == "9" -o "${VERSION}" == "9.0.1" ]; then
		SDK=27
    elif [ "${VERSION}" == "8" -o "${VERSION}" == "8.0.1" ]; then
		SDK=26
    elif [ "${VERSION}" == "7.1" -o "${VERSION}" == "7.1.1" ]; then
		SDK=25
    elif [ "${VERSION}" == "7" -o "${VERSION}" == "7.0.1" ]; then
		SDK=24
	elif [ "${VERSION}" == "6" -o "${VERSION}" == "6.0.1" ]; then
		SDK=23
	elif [ "${VERSION}" == "5.1" ]; then
		SDK=22
	elif [ "${VERSION}" == "5.0" ]; then
		SDK=21
	fi
	
	local info="- Detected Android version: ${VERSION}"
	[ ! -z ${SDK} ] && info="${info} (sdk ${SDK})"
	
	ui_print "${info}"
}

extract_kernel_info() {
	perform strings -n 3 $1 | perform awk -v model_known=$2 '{
		if (!version && $1 == "Linux" && $2 == "version") {
			match($0, "[34]\\.[0-9]+\\.[0-9]+\\-[^\\ ]*")
			if (RLENGTH > 0)
				version = substr($0,RSTART, RLENGTH)
			else {
				match($0, "[34]\\.[0-9]+\\.[0-9]+")
				if (RLENGTH > 0)
					version = substr($0,RSTART, RLENGTH)
			}
		} else if (!model_known) {
			if (next_is_build) {
				model = $0
				next_is_build = 0
			} else if (next_is_variant) {
				variant = $0
				next_is_variant = 0;
			} else if ($0 == "build_product") {
				next_is_build = 1
			} else if ($0 == "build_variant") {
				next_is_variant = 1
			}
		}
	} END {
		print "KERNEL_VERSION=" version
		if (!model_known && model) {
			print "VENDOR=somc"
			print "MODEL=" model
			print "VARIANT=" variant
		}
	}'
}

get_kernel_info() {
	local kernel=$1
	local header=$(perform od -N 4 -A n -t x1 $kernel)
	header=${header## }

	[ "$header" == "1f 8b 08 00" ] && {
		perform cp ${kernel} ${kernel}_tmp.gz
		perform gunzip ${kernel}_tmp.gz
		extract_kernel_info ${kernel}_tmp ${MODEL}
		perform rm ${kernel}_tmp
		return
	}
	
#	Check for LZO compression
	local off=$($BOOTIMG offsetof $kernel 89 4c 5a 4f 00 0d 0a 1a 0a)
	[ 0 -ne ${#off} ] && {
		local o
		local last_off

		for o in $off; do
			last_off=$o
		done
		perform dd if=$kernel of=${kernel}_tmp.lzo bs=$last_off skip=1 2>/dev/null
		perform unlzop -c ${kernel}_tmp.lzo >${kernel}_tmp
		perform rm ${kernel}_tmp.lzo
		extract_kernel_info ${kernel}_tmp $MODEL
		perform rm ${kernel}_tmp
		return
	}

	extract_kernel_info $kernel $MODEL
}

unpack_kernel() {
	ui_print "- Unpacking boot"
	local vars=$("$BOOTIMG" unpackelf -i "$SOURCE" -k $RPATH/kernel -r $RPATH/rd.gz -d $RPATH/dtb -q)
	if [ 0 -ne ${#vars} ]; then
		ui_print "  Found elf boot image"
		eval $vars
	else
		vars=$("$BOOTIMG" unpackimg -i "$SOURCE" -k $RPATH/kernel -r $RPATH/rd.gz -d $RPATH/dtb)
		if [ 0 -ne ${#vars} ]; then
			ui_print "  Found android boot image"
			eval $vars
		else
			ui_print "Unknown boot image format"
			ui_print "Aborting"
			exit 1
		fi
	fi

	if [ -f dtb ]; then
		detect_device_from_dtb dtb
	else
		detect_device_from_dtb kernel
	fi

	eval $(get_kernel_info $RPATH/kernel $MODEL)
	ui_print "  Kernel version: $KERNEL_VERSION"

	if [ ! -z  "$BOARD_TAGS_OFFSET" ] && [ -z "$BOARD_QCDT" ]; then
		ui_print "  Found appended DTB"
		#perform gzip kernel
		#perform mv kernel.gz kernel
		#perform cat dtb >> kernel
		#perform rm dtb
		#unset BOARD_TAGS_OFFSET
	fi

	[ -z $MODEL ] && return

	local cap_vendor="$VENDOR"
	local cap_device="$MODEL"
	if [ ! -z "$BRAND" ]; then
		cap_device="$cap_device ($BRAND)"
	fi

	ui_print "- Detected vendor: $cap_vendor, device: $cap_device, variant: $VARIANT"
}

unpack_initfs() {
	ui_print "- Unpacking initramfs"
	perform rm -rf $RAMDISK
	perform mkdir -p $RAMDISK
	perform gunzip -c $RPATH/rd.gz | "$BOOTIMG" unpackinitfs -d $RAMDISK
}

make_bootimg() {
	ui_print "- Creating new initramfs"
	"$BOOTIMG" mkinitfs $RAMDISK | perform gzip -c > $RPATH/newrd.gz
	#"$BOOTIMG" mkinitfs $RAMDISK | perform gzip -c > $TARGET.cpio.gz
	ui_print "- Creating boot image"
	mkimg_arg="--pagesize $BOARD_PAGE_SIZE --kernel $RPATH/kernel --ramdisk $RPATH/newrd.gz --base 0x00000000 --ramdisk_offset 0x$BOARD_RAMDISK_OFFSET"
	if [ ! -z $BOARD_TAGS_OFFSET ]; then
    	mkimg_arg="$mkimg_arg --dt $RPATH/dtb --tags_offset 0x$BOARD_TAGS_OFFSET"
	fi
	"$BOOTIMG" mkimg -o "$TARGET" --cmdline "$BOARD_KERNEL_CMDLINE" --board "$BOARD_KERNEL_BOARD" $mkimg_arg
}

cleanup() {
	ui_print "- Cleaning up"
	perform rm -f $RPATH/kernel $RPATH/rd.gz $RPATH/newrd.gz $RPATH/dtb
}

ui_print() {
	perform echo -n -e "$1\n"
}

patch_stuff() {
    ui_print "- Doing our stuff"
    ui_print "- Copying needed binaries"
    cp root/rootshell/init.shell.rc $RAMDISK/init.shell.rc@0750
    cp root/rootshell/rootshell.sh $RAMDISK/sbin/rootshell.sh@0755
    cp root/rootshell/enable_adb.sh $RAMDISK/sbin/enable_adb.sh@0755
    cp root/other/bruteforce $RAMDISK/sbin/bruteforce@0755
    cp root/.android/adb_keys $RAMDISK/adb_keys
    #$BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 --minimal
    $BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 --magisk
    $BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 "allow su * process { * }"
    $BOOTIMG magiskpolicy --load $RAMDISK/sepolicy@0644 --save $RAMDISK/sepolicy@0644 "allow * su process { * }"
    sed -i '/on early-init/iimport /init.shell.rc\n' $RAMDISK/init.rc@0750
    sed -i '/trigger fs/atrigger rootshell_trigger\n' $RAMDISK/init.rc@0750
     
    if [ -f $RAMDISK/prop.default@0644 ]
    then
        sed -i -e 's/persist.sys.usb.config=.*/persist.sys.usb.config=adb/g' $RAMDISK/prop.default@0644
    elif [ -f $RAMDISK/default.prop@0600 ]
    then
        sed -i -e 's/persist.sys.usb.config=.*/persist.sys.usb.config=adb/g' $RAMDISK/default.prop@0600
    elif [ -f $RAMDISK/default.prop@0644 ]
    then
        sed -i -e 's/persist.sys.usb.config=.*/persist.sys.usb.config=adb/g' $RAMDISK/default.prop@0644
    fi
    
    if [ -f $RAMDISK/sepolicy_version@0644 ]
    then
        sed -i -e '1 s/....$/\19999/' $RAMDISK/sepolicy_version@0644
    fi
    
    #sed -i -e '$a' $RAMDISK/init.rc@0750
    #sed -i -e '$aservice adbwd_service /system/bin/sh /sbin/enable_adb.sh --service' $RAMDISK/init.rc@0750
    #sed -i -e '$a\    class late_start' $RAMDISK/init.rc@0750
    #sed -i -e '$a\    user root' $RAMDISK/init.rc@0750
    #sed -i -e '$a\    seclabel u:r:su:s0' $RAMDISK/init.rc@0750
    #sed -i -e '$a\    oneshot' $RAMDISK/init.rc@0750

    python "root/scripts/fixmtp.py" $RAMDISK
    
    ask "- Make your custom stuff in ramdisk. Press Y to continue, N to abort." 1 disable
    if [ $disable -eq 0 ]; then
        return
    fi
    
    ui_print "- Done patching"
}

SCRIPT=$(basename $0 .sh)
if [ -z $1 ] && [ -z $2 ] && [ -z $3 ]; then
	ui_print "Usage: $SCRIPT <input> <output> <'64Bit' or '32Bit'>\n"
	exit 1
fi
 
ui_print "\nRoot ramdisk $VERSION (c) B.Kerler 2018\n"
# "Base system based on Tobias Waldvogel\n"

#Make sure we run on bash in Linux
if [ $WINDOWS -eq 0 ]; then
	if [ -z "$BASH_VERSION" ]; then
		BASH=$(which bash 2>/dev/null)
		if [ -z "$BASH" ]; then
			ui_print "This script requires bash"
			exit 1
		fi
        echo $BASH $0 $@
		exec $BASH $0 $@
	fi
fi


if [ ! -f $1 ]; then
  ui_print "Kernel Image not found"
  exit 1
fi

if [ ! -f $1 ]; then
  ui_print "Output name missing"
  exit 1
fi

if [ -f $3 ]; then
  ui_print "You need to say if 32Bit or 64Bit"
  exit 1
fi

if [ -f boot.rotfake ]
then
    rm boot.rotfake
fi

if [ -f boot.signed ]
then
    rm boot.signed
fi

perform mkdir -p $RPATH
unpack_kernel
unpack_initfs
patch_stuff

if [ -f boot.img.lz4 ]
then
    rm boot.img
fi
make_bootimg
ask "- Sign image. Y or N." 1 disable
if [ $disable -eq 1 ]; then
    ui_print "Signing ...."
    java -jar root/keys/BootSignature.jar /recovery $TARGET root/keys/verity.pk8 root/keys/verity.x509.pem $TARGET.signed
    java -jar root/keys/BootSignature.jar -verify $TARGET.signed
    rm $TARGET
fi
perform rm -rf $RPATH
cleanup
ui_print "Done :D"